from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import MappingProxyType
from urllib.parse import parse_qs, urlparse

from thought_archaeology.adapters.provider_command import (
    command_argv,
    command_location,
    discover_provider_commands,
)
from thought_archaeology.continuation import (
    continuation_cancellation,
    continuation_request,
    parallel_batch_progress,
    parallel_comparison,
    parallel_continuation_batch,
    parallel_group_summaries,
    parallel_progress_for_source,
)
from thought_archaeology.edits import commit, plan_fork, plan_veto
from thought_archaeology.fork import ForkError
from thought_archaeology.field_notes import (
    create_field_note,
    edit_field_note,
    field_note_eligibility,
    field_note_read,
    field_note_summaries,
    field_notes_for_graphs,
)
from thought_archaeology.harness import (
    HarnessError,
    HarnessRegistry,
    describe_harness,
)
from thought_archaeology.harness_service import (
    application_worker_status,
    ensure_application_worker,
    harness_service_options,
    resume_application_worker,
    resolve_harness_service_path,
    stop_application_worker,
)
from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.inhabit import entry_node, inhabit
from thought_archaeology.knowledge_capsules import (
    active_stored_launcher,
    construct_knowledge_capsule,
    knowledge_capsule_eligibility,
    knowledge_capsule_read,
    knowledge_capsule_summaries,
    launch_knowledge_capsule,
    store_knowledge_capsule_launcher,
    stored_launcher_read,
)
from thought_archaeology.models import (
    ModelInfo,
    SCHEMA_VERSION,
    ThoughtGraph,
    ThoughtNode,
    Turn,
)
from thought_archaeology.schema import ValidationError
from thought_archaeology.store import Store, StoreError

DEFAULT_PORT = 7462
DEFAULT_BIND = "127.0.0.1"

KNOWN_HARNESS_ADAPTERS = (
    {
        "name": "codex",
        "display_name": "Codex",
        "executable": "ta-harness-codex",
        "provider_executable": "codex",
        "provider_override": "TA_CODEX_BIN",
        "setup_hint": (
            "Install and sign in through the official native Codex CLI on Windows. "
            "WSL is used only when TA_WSL_DISTRO explicitly selects it."
        ),
    },
    {
        "name": "claude",
        "display_name": "Claude",
        "executable": "ta-harness-claude",
        "provider_executable": "claude",
        "provider_override": "TA_CLAUDE_BIN",
        "setup_hint": (
            "Install and sign in through the official native Claude Code CLI on Windows. "
            "Claude Desktop alone is not a programmatic Atlas bridge; WSL is used only "
            "when TA_WSL_DISTRO explicitly selects it."
        ),
    },
    {
        "name": "grok",
        "display_name": "Grok",
        "executable": "ta-harness-grok",
        "provider_executable": "grok",
        "provider_override": "TA_GROK_BIN",
        "setup_hint": (
            "Install and sign in through the official native Grok CLI on Windows. "
            "WSL is used only when TA_WSL_DISTRO explicitly selects it."
        ),
    },
    {
        "name": "opencode",
        "display_name": "OpenCode",
        "executable": "ta-harness-opencode",
        "provider_executable": "opencode",
        "provider_override": "TA_OPENCODE_BIN",
        "setup_hint": "Install and configure OpenCode, then connect here.",
    },
    {
        "name": "prime-agent",
        "display_name": "Prime Agent",
        "executable": "ta-harness-prime-agent",
        "provider_executable": "prime-agent",
        "provider_override": "TA_PRIME_AGENT_BIN",
        "setup_hint": "Install and sign in through Prime Agent, then connect here.",
    },
)

WINDOWS_PROVIDER_SETUP = MappingProxyType(
    {
        "codex": {
            "install": "irm https://chatgpt.com/codex/install.ps1 | iex",
            "sign_in": ("login",),
            "status": ("login", "status"),
        },
        "claude": {
            "install": "irm https://claude.ai/install.ps1 | iex",
            "sign_in": ("auth", "login"),
            "status": ("auth", "status"),
        },
        "grok": {
            "install": "irm https://x.ai/cli/install.ps1 | iex",
            "sign_in": ("login",),
            "status": ("models",),
        },
    }
)


def _packaged_harness_command(name: str) -> tuple[str, tuple[str, ...]] | None:
    """Find a bundled adapter even when its virtualenv is not on PATH."""
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).absolute()), (
            "adapter",
            name.removeprefix("ta-harness-"),
        )
    found = shutil.which(name)
    if found:
        return found, ()
    siblings = [Path(sys.executable).parent / name]
    if os.name == "nt":
        siblings.insert(0, Path(sys.executable).parent / f"{name}.exe")
    for sibling in siblings:
        if sibling.is_file() and os.access(sibling, os.X_OK):
            return str(sibling.absolute()), ()
    return None


def _provider_setup_state(name: str, command) -> str:
    """Read only the provider CLI's public authentication status."""
    if command is None:
        return "missing"
    setup = WINDOWS_PROVIDER_SETUP.get(name)
    if sys.platform != "win32" or setup is None:
        return "ready"
    try:
        proc = subprocess.run(
            command_argv(command, *setup["status"]),
            capture_output=True,
            text=True,
            shell=False,
            timeout=8,
            check=False,
            env={**os.environ, "NO_COLOR": "1"},
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return "failed"
    if proc.returncode == 0:
        return "ready"
    if name in {"codex", "claude"} and proc.returncode == 1:
        return "sign_in_required"
    detail = f"{proc.stderr}\n{proc.stdout}".lower()
    if any(word in detail for word in ("login", "log in", "sign in", "auth", "api key")):
        return "sign_in_required"
    return "failed"


def _launch_provider_setup(name: str, action: str, command=None) -> None:
    """Open an allowlisted provider-owned install or sign-in flow visibly."""
    setup = WINDOWS_PROVIDER_SETUP.get(name)
    if setup is None or action not in {"install", "sign_in"}:
        raise ServeError("choose an available provider setup action")
    if action == "install":
        if sys.platform != "win32":
            raise ServeError("native provider installation is available from Windows")
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if powershell is None:
            raise ServeError("Windows PowerShell is required for provider installation")
        argv = [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            setup["install"],
        ]
    else:
        if command is None:
            raise ServeError("install the provider CLI, then check again")
        argv = command_argv(command, *setup["sign_in"])
    try:
        subprocess.Popen(
            argv,
            shell=False,
            cwd=Path.home(),
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
    except OSError as exc:
        raise ServeError(f"could not open the provider-owned {action.replace('_', ' ')} flow") from exc


class ServeError(Exception):
    """HTTP adapter failure."""


def viz_dist_path() -> Path:
    env = os.environ.get("TA_VIZ")
    if env:
        return Path(env).expanduser().resolve()
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root) / "viz" / "dist"
    here = Path(__file__).resolve()
    repo = here.parents[2] / "viz" / "dist"
    return repo


def _node_brief(node) -> dict:
    return {
        "id": node.id,
        "kind": node.kind,
        "text": node.text,
        "status": node.status,
    }


def _harness_by_graph(store: Store) -> dict[str, str]:
    return {
        completion.graph_id: completion.harness
        for completion in store.iter_continuation_completions()
    }


def _attempt_by_request(store: Store) -> dict[str, dict]:
    return {
        attempt.request_id: attempt.to_dict()
        for attempt in store.iter_continuation_attempts()
    }


def _failure_for_source(
    store: Store, graph_id: str, node_id: str
) -> dict | None:
    requests = [
        request
        for request in store.iter_continuation_requests()
        if request.parallel_batch_id is None
        and request.graph_id == graph_id
        and request.node_id == node_id
    ]
    if not requests:
        return None
    latest = max(requests, key=lambda item: (item.created_at, item.id))
    failure = next(
        (
            item
            for item in store.iter_continuation_failures()
            if item.request_id == latest.id
        ),
        None,
    )
    return failure.to_dict() if failure else None


def _continuation_source(store: Store, graph_id: str) -> dict | None:
    for completion in store.iter_continuation_completions():
        if completion.graph_id != graph_id:
            continue
        request = store.load_continuation_request(completion.request_id)
        graph = store.load_graph(request.graph_id)
        node = next(item for item in graph.nodes if item.id == request.node_id)
        session = store.load_session(request.session_id)
        return {
            "graph_id": request.graph_id,
            "node_id": request.node_id,
            "session_id": request.session_id,
            "title": session.title,
            "node": _node_brief(node),
            "model": graph.model.to_dict(),
            "prompt": request.prompt,
            "harness": completion.harness,
        }
    return None


def bootstrap_payload(store: Store) -> dict:
    if not store.exists():
        return {"sessions": []}
    harness_by_graph = _harness_by_graph(store)
    sessions = []
    for sid in store.iter_session_ids():
        session = store.load_session(sid)
        spawn = None
        if session.head_graph_id:
            try:
                graph = store.load_graph(session.head_graph_id)
            except StoreError:
                graph = None
            if graph is not None and graph.nodes:
                spawn_node = entry_node(graph)
                if spawn_node is None:
                    continue
                spawn = {
                    "graph_id": graph.id,
                    "node_id": spawn_node.id,
                    "node": _node_brief(spawn_node),
                    "model": graph.model.to_dict(),
                    "continuation_harness": harness_by_graph.get(graph.id),
                }
        sessions.append(
            {
                "id": session.id,
                "title": session.title,
                "head_graph_id": session.head_graph_id,
                "head_turn_id": session.head_turn_id,
                "spawn": spawn,
            }
        )
    return {"sessions": sessions}


def workspace_payload(store: Store) -> dict:
    """Registered collaborators and non-mutating cross-session re-entry data."""
    registry = HarnessRegistry()
    default = registry.default_name()
    service_path = resolve_harness_service_path()
    try:
        service = application_worker_status(service_path)
    except HarnessError as exc:
        service = {
            "installed": service_path.is_file(),
            "enabled": "unknown",
            "active": "unknown",
            "error": str(exc),
        }
    harnesses = [
        {
            "name": spec.name,
            "selected": spec.name == default,
            "model": spec.model,
            "model_refreshed_at": spec.model_refreshed_at,
        }
        for spec in registry.specs()
    ]
    registered = {item["name"]: item for item in harnesses}
    provider_commands = discover_provider_commands(
        (
            (
                item["provider_executable"],
                os.environ.get(item["provider_override"]),
            )
            for item in KNOWN_HARNESS_ADAPTERS
        ),
        wsl_names={"codex", "claude", "grok"},
    )
    if sys.platform == "win32":
        with ThreadPoolExecutor(max_workers=3) as executor:
            provider_states = dict(
                zip(
                    (item["name"] for item in KNOWN_HARNESS_ADAPTERS),
                    executor.map(
                        lambda item: _provider_setup_state(
                            item["name"],
                            provider_commands[item["provider_executable"]],
                        ),
                        KNOWN_HARNESS_ADAPTERS,
                    ),
                    strict=True,
                )
            )
    else:
        provider_states = {
            item["name"]: _provider_setup_state(
                item["name"], provider_commands[item["provider_executable"]]
            )
            for item in KNOWN_HARNESS_ADAPTERS
        }
    available_harnesses = []
    for item in KNOWN_HARNESS_ADAPTERS:
        provider_command = provider_commands[item["provider_executable"]]
        provider_state = provider_states[item["name"]]
        windows_setup = WINDOWS_PROVIDER_SETUP.get(item["name"])
        available_harnesses.append(
            {
                "name": item["name"],
                "display_name": item["display_name"],
                "adapter_available": _packaged_harness_command(item["executable"])
                is not None,
                "provider_available": provider_command is not None,
                "provider_location": command_location(provider_command),
                "provider_state": provider_state,
                "can_install": bool(
                    sys.platform == "win32" and windows_setup and provider_command is None
                ),
                "can_sign_in": bool(windows_setup and provider_command is not None),
                "registered": item["name"] in registered,
                "selected": bool(registered.get(item["name"], {}).get("selected")),
                "model": registered.get(item["name"], {}).get("model"),
                "setup_hint": item["setup_hint"],
            }
        )
    completions = (
        {
            completion.graph_id: completion.harness
            for completion in store.iter_continuation_completions()
        }
        if store.exists()
        else {}
    )
    history = []
    session_ids = store.iter_session_ids() if store.exists() else ()
    for session_id in session_ids:
        session = store.load_session(session_id)
        graphs = list(store.iter_graphs(session_id))
        spawn = None
        model = None
        harness = None
        author_label = "no completed graph"
        if session.head_graph_id:
            graph = next(
                (item for item in graphs if item.id == session.head_graph_id), None
            )
            if graph is not None:
                node = entry_node(graph)
                model = graph.model.to_dict()
                harness = completions.get(graph.id)
                turn = next(
                    (
                        item
                        for item in store.iter_turns(session.id)
                        if item.id == graph.turn_id
                    ),
                    None,
                )
                if harness:
                    author_label = f"{harness.capitalize()} · {graph.model.name}"
                elif turn and turn.role == "human_edit":
                    author_label = "Human edit"
                elif graph.metadata.get("workspace_origin"):
                    author_label = "Human inquiry"
                else:
                    author_label = graph.model.name
                if node is not None:
                    spawn = {"graph_id": graph.id, "node_id": node.id}
        history.append(
            {
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "head_graph_id": session.head_graph_id,
                "graph_count": len(graphs),
                "model": model,
                "harness": harness,
                "author_label": author_label,
                "spawn": spawn,
            }
        )
    history.sort(key=lambda item: (item["updated_at"], item["id"]), reverse=True)
    pending = (
        list(store.iter_continuation_requests(pending=True))
        if store.exists()
        else []
    )
    attempts = _attempt_by_request(store) if store.exists() else {}
    return {
        "platform": "windows" if sys.platform == "win32" else sys.platform,
        "active_harness": default,
        "harnesses": harnesses,
        "available_harnesses": available_harnesses,
        "service": {
            key: service.get(key)
            for key in ("installed", "enabled", "active", "error")
            if key in service
        },
        "pending": [
            {
                "request_id": request.id,
                "session_id": request.session_id,
                "harness": (attempts.get(request.id) or {}).get("harness"),
            }
            for request in pending
        ],
        "history": history,
    }


def create_workspace_inquiry(store: Store, prompt: str) -> dict:
    """Create an independent human-origin graph and queue its first AI response."""
    prompt = prompt.strip()
    if not prompt:
        raise ServeError("new graph requires an opening inquiry")
    if len(prompt) > 400:
        raise ServeError("opening inquiry must be 400 characters or fewer")
    if store.exists() and list(store.iter_continuation_requests(pending=True)):
        raise ServeError(
            "finish or cancel the current AI response before starting a new graph"
        )
    registry = HarnessRegistry()
    spec = registry.get()
    if not store.exists():
        store.initialize()
    unit_path = resolve_harness_service_path()
    options = harness_service_options(unit_path)
    ensure_application_worker(
        store,
        spec,
        interval=options["interval"],
        timeout=options["timeout"],
        path=unit_path,
    )

    title = prompt.splitlines()[0].strip()
    if len(title) > 80:
        title = title[:77].rstrip() + "…"
    session = store.init_session(title, origin="inhabit-space:new-inquiry")
    created_at = now_iso()
    turn_id = new_ulid()
    graph_id = new_ulid()
    node = ThoughtNode(
        id=new_ulid(),
        kind="uncertainty",
        text=prompt,
        status="uncertain",
        agent="human",
        created_at=created_at,
        source="human",
        notes="opening inquiry",
    )
    graph = ThoughtGraph(
        schema_version=SCHEMA_VERSION,
        id=graph_id,
        session_id=session.id,
        turn_id=turn_id,
        created_at=created_at,
        prose=prompt,
        nodes=(node,),
        edges=(),
        model=ModelInfo("none", "human inquiry", "posthoc"),
        metadata=MappingProxyType({"workspace_origin": True}),
    )
    turn = Turn(
        schema_version=SCHEMA_VERSION,
        id=turn_id,
        session_id=session.id,
        seq=0,
        role="user",
        created_at=created_at,
        prose=prompt,
        graph_id=graph.id,
        parent_turn_id=None,
        fork_of_node_id=None,
        provider="none",
    )
    store.write_graph(graph)
    store.append_turn(turn)
    store.update_session_head(session.id, graph_id=graph.id, turn_id=turn.id)
    request = continuation_request(
        graph, node, prompt=prompt, source="workspace"
    )
    path = store.write_continuation_request(request)
    store.log(
        "workspace_new_graph",
        session_id=session.id,
        graph_id=graph.id,
        node_id=node.id,
        request_id=request.id,
        path=str(path),
        warnings=[],
    )
    return {
        "ok": True,
        "session_id": session.id,
        "graph_id": graph.id,
        "stand": {"graph_id": graph.id, "node_id": node.id},
        "request": request.to_dict(),
    }


def create_parallel_continuations(
    store: Store,
    *,
    graph_id: str,
    node_id: str,
    prompt: str,
    harnesses: list[str],
) -> dict:
    """Validate and atomically publish one terminal-chamber routed batch."""
    prompt = prompt.strip()
    if not prompt:
        raise ServeError("parallel continuation requires one shared prompt")
    if len(prompt) > 400:
        raise ServeError("parallel continuation prompt must be 400 characters or fewer")
    if len(harnesses) < 2 or len(set(harnesses)) != len(harnesses):
        raise ServeError("select at least two unique collaborators")
    registry = HarnessRegistry()
    specs = registry.specs()
    registered = {spec.name for spec in specs}
    if any(name not in registered for name in harnesses):
        raise ServeError("every selected collaborator must be registered")
    default = registry.default_name()
    if not default or default not in harnesses:
        raise ServeError("the active collaborator must remain selected")
    ordered = (default,) + tuple(
        spec.name for spec in specs if spec.name in harnesses and spec.name != default
    )
    view = inhabit(store, node_id, graph_id=graph_id)
    traversal = view.to_dict().get("read", {}).get("traversal", {})
    if not traversal.get("terminal"):
        raise ServeError("parallel continuation is available only at a terminal chamber")
    batch, requests = parallel_continuation_batch(
        view.graph,
        view.node,
        prompt=prompt,
        harnesses=ordered,
    )
    path = store.write_parallel_batch(batch, requests)
    store.log(
        "parallel_continuation_ready",
        session_id=batch.session_id,
        graph_id=batch.graph_id,
        node_id=batch.node_id,
        batch_id=batch.id,
        request_ids=[request.id for request in requests],
        harnesses=list(ordered),
        path=str(path),
        warnings=[],
    )
    return {
        "ok": True,
        "batch": batch.to_dict(),
        "requests": [request.to_dict() for request in requests],
        "progress": parallel_batch_progress(store, batch.id),
    }


def cancel_parallel_continuations(store: Store, batch_id: str) -> dict:
    """Close every still-open job; completed and failed receipts remain."""
    batch = store.load_parallel_batch(batch_id)
    canceled = []
    with store.continuation_inbox_lock():
        pending = {
            request.id for request in store.iter_continuation_requests(pending=True)
        }
        for job in sorted(batch.jobs, key=lambda item: item.position):
            if job.request_id not in pending:
                continue
            receipt = continuation_cancellation(job.request_id, source="workspace")
            store.write_continuation_cancellation(receipt)
            canceled.append(receipt)
    store.log(
        "parallel_continuation_cancel",
        session_id=batch.session_id,
        graph_id=batch.graph_id,
        node_id=batch.node_id,
        batch_id=batch.id,
        request_ids=[item.request_id for item in canceled],
        warnings=[],
    )
    return {
        "ok": True,
        "cancellations": [item.to_dict() for item in canceled],
        "progress": parallel_batch_progress(store, batch.id),
    }


def thread_payload(
    store: Store,
    session_id: str,
    *,
    graph_id: str | None = None,
    node_id: str | None = None,
) -> dict:
    """Server-authored graph-generation compass for one durable session."""
    session = store.load_session(session_id)
    graphs = {graph.id: graph for graph in store.iter_graphs(session_id)}
    turns = {turn.id: turn for turn in store.iter_turns(session_id)}
    continuations = {}
    for completion in store.iter_continuation_completions():
        if completion.graph_id not in graphs:
            continue
        request = store.load_continuation_request(completion.request_id)
        if request.session_id == session_id:
            continuations[completion.graph_id] = (completion, request)

    children: dict[str | None, list] = {}
    for graph in graphs.values():
        parent = graph.parent_graph_id if graph.parent_graph_id in graphs else None
        children.setdefault(parent, []).append(graph)
    for group in children.values():
        group.sort(key=lambda graph: (graph.created_at, graph.id))

    entries = []
    visited: set[str] = set()
    evidence_by_stand: dict[tuple[str, str], list[dict[str, str]]] = {}
    for raw in store.iter_evidence(session_id):
        evidence_by_stand.setdefault(
            (raw["graph_id"], raw["node_id"]), []
        ).append({"kind": raw["kind"]})

    def visit(graph, depth: int) -> None:
        if graph.id in visited:
            return
        visited.add(graph.id)
        spawn = entry_node(graph)
        turn = turns.get(graph.turn_id)
        continuation = continuations.get(graph.id)
        if continuation:
            completion, request = continuation
            kind = "continuation"
            label = " · ".join(
                part
                for part in (
                    completion.harness.capitalize(),
                    graph.model.name if graph.model.name != "unknown" else "",
                )
                if part
            )
        elif turn and turn.role == "human_edit":
            vetoed = any(
                node.source == "human" and node.status == "vetoed"
                for node in graph.nodes
            )
            kind = "veto" if vetoed else "cut"
            label = "human no" if vetoed else "human cut"
            request = None
        elif graph.parent_graph_id:
            kind = "fork" if graph.fork else "revision"
            label = "regenerated fork" if graph.fork else "graph revision"
            request = None
        elif graph.metadata.get("workspace_origin"):
            kind = "origin"
            label = "opening inquiry"
            request = None
        else:
            kind = "origin"
            label = "conversation origin"
            request = None
        entries.append(
            {
                "graph_id": graph.id,
                "parent_graph_id": graph.parent_graph_id,
                "node_id": spawn.id if spawn else None,
                "node": _node_brief(spawn) if spawn else None,
                "evidence": evidence_by_stand.get((graph.id, spawn.id), [])
                if spawn
                else [],
                "created_at": graph.created_at,
                "depth": depth,
                "kind": kind,
                "label": label,
                "summary": spawn.text if spawn else "empty graph",
                "model": graph.model.to_dict(),
                "turn_role": turn.role if turn else None,
                "reason": graph.fork.reason if graph.fork else "",
                "prompt": request.prompt if request else "",
                "source_graph_id": request.graph_id if request else None,
                "source_node_id": request.node_id if request else None,
            }
        )
        for child in children.get(graph.id, []):
            visit(child, depth + 1)

    for root in children.get(None, []):
        visit(root, 0)
    for graph in sorted(graphs.values(), key=lambda item: (item.created_at, item.id)):
        if graph.id not in visited:
            visit(graph, 0)

    ai_entries = [entry for entry in entries if entry["kind"] == "continuation"]
    latest_ai = (
        max(ai_entries, key=lambda entry: (entry["created_at"], entry["graph_id"]))[
            "graph_id"
        ]
        if ai_entries
        else None
    )
    parallel_groups = parallel_group_summaries(store, session_id=session_id)
    entries_by_graph = {entry["graph_id"]: entry for entry in entries}
    for group in parallel_groups:
        member_entries = [
            entries_by_graph[graph_id]
            for graph_id in group["graph_ids"]
            if graph_id in entries_by_graph
        ]
        group["entries"] = member_entries
        group["depth"] = min(
            (entry["depth"] for entry in member_entries), default=0
        )
        group["field_notes"] = field_notes_for_graphs(
            store, set(group["graph_ids"])
        )
        group["knowledge_capsules"] = knowledge_capsule_summaries(
            store,
            comparison_request_id=group["representative_request_id"],
        )
    return {
        "session_id": session.id,
        "title": session.title,
        "head_graph_id": session.head_graph_id,
        "latest_ai_graph_id": latest_ai,
        "entries": entries,
        "parallel_groups": parallel_groups,
        "standing_field_notes": (
            field_note_summaries(
                store,
                session_id=session_id,
                graph_id=graph_id,
                node_id=node_id,
            )
            if graph_id and node_id
            else []
        ),
        "stored_knowledge_capsule_launcher": (
            stored_launcher_read(store, launcher, session_id=session_id)
            if (launcher := active_stored_launcher(store))
            else None
        ),
    }


class InhabitHandler(BaseHTTPRequestHandler):
    store: Store
    dist: Path

    def log_message(self, fmt: str, *args: object) -> None:
        if os.environ.get("TA_SERVE_LOG"):
            super().log_message(fmt, *args)

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: object) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            if path == "/api/health":
                self._json(200, {"ok": True, "write": True, "bind": "localhost"})
                return
            if path == "/api/sessions":
                self._json(200, bootstrap_payload(self.store))
                return
            if path == "/api/workspace":
                self._json(200, workspace_payload(self.store))
                return
            if path == "/api/field-notes":
                graph_id = (qs.get("graph") or [None])[0]
                node_id = (qs.get("node") or [None])[0]
                if node_id and not graph_id:
                    raise StoreError("Field Note node filter requires graph")
                self._json(
                    200,
                    field_note_summaries(
                        self.store, graph_id=graph_id, node_id=node_id
                    ),
                )
                return
            if path == "/api/knowledge-capsules":
                self._json(
                    200,
                    knowledge_capsule_summaries(
                        self.store,
                        session_id=(qs.get("session") or [None])[0],
                    ),
                )
                return
            if path.startswith("/api/knowledge-capsules/"):
                capsule_id = path[len("/api/knowledge-capsules/") :].strip("/")
                if not capsule_id:
                    raise StoreError("Knowledge Capsule is required")
                self._json(
                    200,
                    knowledge_capsule_read(
                        self.store,
                        self.store.load_knowledge_capsule(capsule_id),
                    ),
                )
                return
            if path.startswith("/api/field-notes/"):
                note_id = path[len("/api/field-notes/") :].strip("/")
                if not note_id:
                    raise StoreError("Field Note is required")
                note = self.store.load_field_note(note_id)
                revision_id = (qs.get("revision") or [None])[0]
                self._json(
                    200,
                    field_note_read(
                        self.store, note, revision_id=revision_id
                    ),
                )
                return
            if path.startswith("/api/thread/"):
                session_id = path[len("/api/thread/") :].strip("/")
                if not session_id:
                    raise StoreError("session is required")
                self._json(
                    200,
                    thread_payload(
                        self.store,
                        session_id,
                        graph_id=(qs.get("graph") or [None])[0],
                        node_id=(qs.get("node") or [None])[0],
                    ),
                )
                return
            if path.startswith("/api/parallel/"):
                request_id = path[len("/api/parallel/") :].strip("/")
                if not request_id:
                    raise StoreError("continuation request is required")
                batch_path = self.store.parallel_batches_dir / f"{request_id}.json"
                payload = (
                    parallel_batch_progress(self.store, request_id)
                    if batch_path.is_file()
                    else parallel_comparison(self.store, request_id)
                )
                self._json(200, payload)
                return
            if path == "/api/continuations":
                self._json(
                    200,
                    {
                        "requests": [
                            item.to_dict()
                            for item in self.store.iter_continuation_requests(
                                pending=True
                            )
                        ],
                        "parallel_batches": [
                            parallel_batch_progress(self.store, batch.id)
                            for batch in self.store.iter_parallel_batches()
                        ],
                    },
                )
                return
            if path.startswith("/api/graphs/"):
                gid = path[len("/api/graphs/") :].strip("/")
                graph = self.store.load_graph(gid)
                payload = graph.to_dict()
                payload.pop("hidden_reasoning", None)
                self._json(200, payload)
                return
            if path.startswith("/api/inhabit/"):
                nid = path[len("/api/inhabit/") :].strip("/")
                session = (qs.get("session") or [None])[0]
                graph_id = (qs.get("graph") or [None])[0]
                view = inhabit(
                    self.store, nid, graph_id=graph_id, session_id=session
                )
                payload = view.to_dict()
                payload["continuation_harness"] = _harness_by_graph(
                    self.store
                ).get(view.graph.id)
                payload["continuation_source"] = _continuation_source(
                    self.store, view.graph.id
                )
                if view.continuation:
                    payload["continuation_attempt"] = _attempt_by_request(
                        self.store
                    ).get(view.continuation["id"])
                else:
                    payload["continuation_attempt"] = None
                payload["continuation_failure"] = _failure_for_source(
                    self.store, view.graph.id, view.node.id
                )
                payload["parallel_continuation"] = parallel_progress_for_source(
                    self.store, view.graph.id, view.node.id
                )
                payload["parallel_available"] = bool(
                    payload.get("read", {}).get("traversal", {}).get("terminal")
                    and not list(
                        self.store.iter_continuation_requests(pending=True)
                    )
                )
                payload["field_notes"] = field_note_summaries(
                    self.store, graph_id=view.graph.id, node_id=view.node.id
                )
                payload["field_note_eligibility"] = (
                    field_note_eligibility(
                        self.store,
                        graph_id=view.graph.id,
                        node_id=view.node.id,
                    )
                    if payload.get("read", {}).get("traversal", {}).get("terminal")
                    else None
                )
                payload["knowledge_capsules"] = knowledge_capsule_summaries(
                    self.store,
                    source_graph_id=view.graph.id,
                    source_node_id=view.node.id,
                )
                payload["knowledge_capsule_eligibility"] = (
                    knowledge_capsule_eligibility(
                        self.store,
                        graph_id=view.graph.id,
                        node_id=view.node.id,
                    )
                )
                launcher = active_stored_launcher(self.store)
                payload["stored_knowledge_capsule_launcher"] = (
                    stored_launcher_read(
                        self.store, launcher, session_id=view.graph.session_id
                    )
                    if launcher
                    else None
                )
                payload["read"]["field_note_line"] = (
                    f"{len(payload['field_notes'])} human Field "
                    f"{'Note' if len(payload['field_notes']) == 1 else 'Notes'} "
                    "\u00b7 inspect in Thread Compass"
                    if payload["field_notes"]
                    else None
                )
                self._json(200, payload)
                return
            self._static(path)
        except ForkError as exc:
            self._json(404, {"error": str(exc)})
        except StoreError as exc:
            self._json(404, {"error": str(exc)})
        except HarnessError as exc:
            self._json(400, {"error": str(exc)})
        except FileNotFoundError as exc:
            self._json(404, {"error": str(exc)})
        except OSError as exc:
            self._json(500, {"error": str(exc)})

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 100_000:
            raise ServeError("payload too large")
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ServeError("JSON object required")
        return data

    def _require_local_json_request(self) -> None:
        content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0]
        if content_type.strip().lower() != "application/json":
            raise ServeError("provider setup requires a local JSON request")
        origin = (self.headers.get("Origin") or "").rstrip("/")
        host = self.headers.get("Host") or ""
        hostname = urlparse(f"//{host}").hostname
        if hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ServeError("provider setup is available only from this Atlas window")
        if origin and origin != f"http://{host}":
            raise ServeError("provider setup is available only from this Atlas window")
        fetch_site = (self.headers.get("Sec-Fetch-Site") or "").lower()
        if fetch_site and fetch_site not in {"same-origin", "none"}:
            raise ServeError("provider setup is available only from this Atlas window")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/fork":
                self._edit_fork()
                return
            if path == "/api/veto":
                self._edit_veto()
                return
            if path == "/api/continuation":
                self._continuation_ready()
                return
            if path == "/api/continuation/cancel":
                self._continuation_cancel()
                return
            if path == "/api/parallel":
                self._parallel_ready()
                return
            if path == "/api/field-notes":
                self._field_note_create()
                return
            if path == "/api/knowledge-capsules":
                self._knowledge_capsule_construct()
                return
            if path == "/api/knowledge-capsule-launcher/store":
                self._knowledge_capsule_launcher_store()
                return
            if path.startswith("/api/knowledge-capsules/") and path.endswith("/launch"):
                capsule_id = path[
                    len("/api/knowledge-capsules/") : -len("/launch")
                ].strip("/")
                if not capsule_id:
                    raise ServeError("Knowledge Capsule is required")
                self._knowledge_capsule_launch(capsule_id)
                return
            if path.startswith("/api/field-notes/") and path.endswith("/revisions"):
                note_id = path[
                    len("/api/field-notes/") : -len("/revisions")
                ].strip("/")
                if not note_id:
                    raise ServeError("Field Note is required")
                self._field_note_edit(note_id)
                return
            if path.startswith("/api/parallel/") and path.endswith("/cancel"):
                batch_id = path[len("/api/parallel/") : -len("/cancel")].strip("/")
                if not batch_id:
                    raise ServeError("parallel batch is required")
                self._json(200, cancel_parallel_continuations(self.store, batch_id))
                return
            if path == "/api/workspace/harness":
                self._workspace_harness()
                return
            if path == "/api/onboarding/harness":
                self._onboarding_harness()
                return
            if path == "/api/onboarding/provider":
                self._onboarding_provider()
                return
            if path == "/api/workspace/harness/model":
                self._workspace_harness_model()
                return
            if path == "/api/workspace/inquiry":
                self._workspace_inquiry()
                return
            self._json(405, {"error": "unknown write"})
        except ServeError as exc:
            self._json(400, {"error": str(exc)})
        except ForkError as exc:
            self._json(404, {"error": str(exc)})
        except StoreError as exc:
            self._json(404, {"error": str(exc)})
        except HarnessError as exc:
            self._json(400, {"error": str(exc)})
        except ValidationError as exc:
            self._json(400, {"error": "; ".join(exc.messages)})
        except json.JSONDecodeError as exc:
            self._json(400, {"error": str(exc)})

    def _standing_args(self, body: dict) -> tuple[str, str | None, str]:
        node_id = body.get("node") or body.get("node_id")
        if not node_id:
            raise ServeError("node is required")
        graph_id = body.get("graph") or body.get("graph_id")
        session_id = body.get("session") or body.get("session_id")
        if not session_id and graph_id:
            session_id = self.store.load_graph(str(graph_id)).session_id
        if not session_id:
            raise ServeError("session is required")
        return str(node_id), (str(graph_id) if graph_id else None), str(session_id)

    def _field_note_write_body(
        self,
    ) -> tuple[
        str,
        str,
        str | None,
        str | None,
        str | None,
        tuple[tuple[str, str, str], ...],
    ]:
        body = self._read_json()
        kind = str(body.get("kind") or "")
        text = str(body.get("text") or "")
        comparison_request_id = body.get("comparison_request_id") or None
        source_graph_id = body.get("source_graph_id") or None
        source_node_id = body.get("source_node_id") or None
        raw_references = body.get("references")
        if not comparison_request_id and (not source_graph_id or not source_node_id):
            raise ServeError("Field Note requires a comparison or source chamber")
        if not isinstance(raw_references, list):
            raise ServeError("Field Note references must be a list")
        references = []
        for item in raw_references:
            if not isinstance(item, dict):
                raise ServeError("Field Note reference must be an object")
            try:
                references.append(
                    (
                        str(item["session_id"]),
                        str(item["graph_id"]),
                        str(item["node_id"]),
                    )
                )
            except KeyError as exc:
                raise ServeError(f"Field Note reference missing {exc.args[0]}") from exc
        return (
            kind,
            text,
            str(comparison_request_id) if comparison_request_id else None,
            str(source_graph_id) if source_graph_id else None,
            str(source_node_id) if source_node_id else None,
            tuple(references),
        )

    def _field_note_create(self) -> None:
        kind, text, comparison_request_id, source_graph_id, source_node_id, references = (
            self._field_note_write_body()
        )
        note = create_field_note(
            self.store,
            kind=kind,  # type: ignore[arg-type]
            text=text,
            references=references,
            comparison_request_id=comparison_request_id,
            source_graph_id=source_graph_id,
            source_node_id=source_node_id,
        )
        path = self.store.field_notes_dir / f"{note.id}.json"
        self.store.log(
            "field_note_create",
            note_id=note.id,
            kind=note.kind,
            references=[
                {
                    "session_id": item.session_id,
                    "graph_id": item.graph_id,
                    "node_id": item.node_id,
                }
                for item in note.references
            ],
            path=str(path),
            warnings=[],
        )
        self._json(
            200,
            {
                "ok": True,
                "note": field_note_read(self.store, note),
                "knowledge_capsule_eligibility": (
                    knowledge_capsule_eligibility(
                        self.store,
                        graph_id=source_graph_id,
                        node_id=source_node_id,
                    )
                    if source_graph_id and source_node_id
                    else None
                ),
            },
        )

    def _field_note_edit(self, note_id: str) -> None:
        kind, text, comparison_request_id, _source_graph_id, _source_node_id, references = (
            self._field_note_write_body()
        )
        revision = edit_field_note(
            self.store,
            note_id=note_id,
            kind=kind,  # type: ignore[arg-type]
            text=text,
            references=references,
            comparison_request_id=comparison_request_id,
        )
        path = self.store.field_note_revisions_dir(note_id) / f"{revision.id}.json"
        self.store.log(
            "field_note_revision_create",
            note_id=note_id,
            revision_id=revision.id,
            previous_revision_id=revision.previous_revision_id,
            kind=revision.kind,
            references=[
                {
                    "session_id": item.session_id,
                    "graph_id": item.graph_id,
                    "node_id": item.node_id,
                }
                for item in revision.references
            ],
            path=str(path),
            warnings=[],
        )
        note = self.store.load_field_note(note_id)
        self._json(200, {"ok": True, "note": field_note_read(self.store, note)})

    def _knowledge_capsule_construct(self) -> None:
        body = self._read_json()
        comparison_request_id = body.get("comparison_request_id") or None
        graph_id = body.get("graph_id") or body.get("graph") or None
        node_id = body.get("node_id") or body.get("node") or None
        field_note_id = body.get("field_note_id") or None
        stored_launcher_id = body.get("stored_launcher_id") or None
        if not stored_launcher_id and not comparison_request_id and not (graph_id and node_id):
            raise ServeError("Knowledge Capsule requires an earned or stored launcher")
        manifest = construct_knowledge_capsule(
            self.store,
            comparison_request_id=(
                str(comparison_request_id) if comparison_request_id else None
            ),
            graph_id=str(graph_id) if graph_id else None,
            node_id=str(node_id) if node_id else None,
            field_note_id=str(field_note_id) if field_note_id else None,
            stored_launcher_id=(
                str(stored_launcher_id) if stored_launcher_id else None
            ),
        )
        path = self.store.knowledge_capsules_dir / f"{manifest.id}.json"
        self.store.log(
            "knowledge_capsule_construct",
            capsule_id=manifest.id,
            session_id=manifest.session_id,
            comparison_request_id=manifest.comparison_request_id,
            field_note_id=manifest.field_note_id,
            field_note_revision_id=manifest.field_note_revision_id,
            head_graph_id=manifest.head_graph_id,
            head_turn_id=manifest.head_turn_id,
            path=str(path),
            warnings=[],
        )
        self._json(
            200,
            {
                "ok": True,
                "construction_started": True,
                "capsule": knowledge_capsule_read(self.store, manifest),
            },
        )

    def _knowledge_capsule_launcher_store(self) -> None:
        body = self._read_json()
        graph_id = str(body.get("graph_id") or body.get("graph") or "")
        node_id = str(body.get("node_id") or body.get("node") or "")
        field_note_id = str(body.get("field_note_id") or "")
        if not graph_id or not node_id or not field_note_id:
            raise ServeError("storing a launcher requires graph, node, and Field Note")
        launcher = store_knowledge_capsule_launcher(
            self.store,
            graph_id=graph_id,
            node_id=node_id,
            field_note_id=field_note_id,
        )
        path = self.store.knowledge_capsule_launchers_dir / f"{launcher.id}.json"
        self.store.log(
            "knowledge_capsule_launcher_store",
            launcher_id=launcher.id,
            session_id=launcher.session_id,
            earning_graph_id=launcher.earning_graph_id,
            earning_node_id=launcher.earning_node_id,
            field_note_id=launcher.field_note_id,
            path=str(path),
            warnings=[],
        )
        self._json(
            200,
            {
                "ok": True,
                "launcher": stored_launcher_read(
                    self.store, launcher, session_id=launcher.session_id
                ),
            },
        )
    def _knowledge_capsule_launch(self, capsule_id: str) -> None:
        launch = launch_knowledge_capsule(self.store, capsule_id)
        self.store.log(
            "knowledge_capsule_launch",
            capsule_id=launch.capsule_id,
            launch_id=launch.id,
            markdown_sha256=launch.markdown_sha256,
            path=str(self.store.root / launch.markdown_path),
            warnings=[],
        )
        self._json(
            200,
            {
                "ok": True,
                "launch": launch.to_dict(),
                "capsule": knowledge_capsule_read(
                    self.store,
                    self.store.load_knowledge_capsule(capsule_id),
                ),
            },
        )

    def _edit_fork(self) -> None:
        body = self._read_json()
        node_id, graph_id, session_id = self._standing_args(body)
        reason = body.get("reason")
        reason_s = str(reason).strip() if reason else None
        plan = plan_fork(
            self.store,
            node_id,
            session_id=session_id,
            graph_id=graph_id,
            reason=reason_s or None,
        )
        commit(self.store, plan)
        # Stay in G0 at the cut. The continuation is a ring, not a teleport.
        self._json(
            200,
            {
                "ok": True,
                "op": "fork",
                "graph_id": plan.g1.id,
                "from_graph_id": plan.g0.id,
                "from_node_id": plan.node.id,
                "warnings": plan.warnings,
                "stand": {"graph_id": plan.g0.id, "node_id": plan.node.id},
            },
        )

    def _edit_veto(self) -> None:
        body = self._read_json()
        node_id, graph_id, session_id = self._standing_args(body)
        reason = body.get("reason")
        reason_s = str(reason).strip() if reason else ""
        if not reason_s:
            self._json(400, {"error": "veto requires a reason"})
            return
        plan = plan_veto(
            self.store,
            node_id,
            session_id=session_id,
            graph_id=graph_id,
            reason=reason_s,
        )
        commit(self.store, plan)
        # Follow into G1: the chamber remains, now with a human no.
        self._json(
            200,
            {
                "ok": True,
                "op": "veto",
                "graph_id": plan.g1.id,
                "from_graph_id": plan.g0.id,
                "from_node_id": plan.node.id,
                "warnings": plan.warnings,
                "stand": {"graph_id": plan.g1.id, "node_id": plan.node.id},
            },
        )

    def _continuation_ready(self) -> None:
        body = self._read_json()
        node_id, graph_id, _session_id = self._standing_args(body)
        if graph_id is None:
            raise ServeError("graph is required")
        view = inhabit(self.store, node_id, graph_id=graph_id)
        graph, node = view.graph, view.node
        prompt = str(body.get("prompt") or "").strip()
        request = continuation_request(
            graph, node, prompt=prompt, source="inhabit_space"
        )
        path = self.store.write_continuation_request(request)
        self.store.log(
            "continuation_ready",
            session_id=graph.session_id,
            graph_id=graph.id,
            node_id=node.id,
            request_id=request.id,
            path=str(path),
            warnings=[],
        )
        self._json(200, {"ok": True, "request": request.to_dict()})

    def _continuation_cancel(self) -> None:
        body = self._read_json()
        request_id = str(body.get("request") or body.get("request_id") or "").strip()
        if not request_id:
            raise ServeError("request is required")
        request = self.store.load_continuation_request(request_id)
        cancellation = continuation_cancellation(
            request.id, source="inhabit_space"
        )
        path = self.store.write_continuation_cancellation(cancellation)
        self.store.log(
            "continuation_cancel",
            session_id=request.session_id,
            graph_id=request.graph_id,
            node_id=request.node_id,
            request_id=request.id,
            cancellation_id=cancellation.id,
            path=str(path),
            warnings=[],
        )
        self._json(200, {"ok": True, "cancellation": cancellation.to_dict()})

    def _parallel_ready(self) -> None:
        body = self._read_json()
        graph_id = str(body.get("graph_id") or body.get("graph") or "").strip()
        node_id = str(body.get("node_id") or body.get("node") or "").strip()
        raw_harnesses = body.get("harnesses")
        if not graph_id or not node_id:
            raise ServeError("graph_id and node_id are required")
        if not isinstance(raw_harnesses, list) or not all(
            isinstance(item, str) and item.strip() for item in raw_harnesses
        ):
            raise ServeError("harnesses must be a list of collaborator names")
        result = create_parallel_continuations(
            self.store,
            graph_id=graph_id,
            node_id=node_id,
            prompt=str(body.get("prompt") or ""),
            harnesses=[item.strip() for item in raw_harnesses],
        )
        self._json(200, result)

    def _workspace_harness(self) -> None:
        body = self._read_json()
        name = str(body.get("harness") or "").strip()
        if not name:
            raise ServeError("harness is required")
        pending = (
            list(self.store.iter_continuation_requests(pending=True))
            if self.store.exists()
            else []
        )
        if pending:
            self._json(
                409,
                {
                    "error": (
                        "finish or cancel the current AI response before changing "
                        "collaborators"
                    )
                },
            )
            return
        registry = HarnessRegistry()
        spec = registry.get(name)
        previous = registry.default_name()
        registry.use(name)
        unit_path = resolve_harness_service_path()
        options = harness_service_options(unit_path)
        if self.store.exists():
            try:
                ensure_application_worker(
                    self.store,
                    spec,
                    interval=options["interval"],
                    timeout=options["timeout"],
                    path=unit_path,
                )
            except HarnessError:
                if previous and previous != name:
                    registry.use(previous)
                raise
            self.store.log(
                "workspace_harness",
                harness=name,
                path=str(unit_path),
                warnings=[],
            )
        self._json(200, {"ok": True, "workspace": workspace_payload(self.store)})

    def _onboarding_harness(self) -> None:
        body = self._read_json()
        name = str(body.get("harness") or "").strip()
        known = next(
            (item for item in KNOWN_HARNESS_ADAPTERS if item["name"] == name),
            None,
        )
        if known is None:
            raise ServeError("choose one of the packaged collaborators")
        registry = HarnessRegistry()
        if name in {spec.name for spec in registry.specs()}:
            raise ServeError(f"collaborator {name!r} is already connected")
        command = _packaged_harness_command(known["executable"])
        if command is None:
            raise ServeError(
                f"packaged adapter {known['executable']!r} is unavailable; "
                "reinstall Atlas of Threads, then try again"
            )
        executable, args = command
        spec = registry.register(name, executable, args=args)
        try:
            description = describe_harness(spec, timeout=10)
        except HarnessError:
            registry.remove(name)
            raise
        model = description.get("default_model")
        cli_version = description.get("cli_version")
        if isinstance(model, str) and model.strip():
            registry.record_model(
                name,
                model,
                cli_version=cli_version if isinstance(cli_version, str) else None,
            )
        self._json(200, {"ok": True, "workspace": workspace_payload(self.store)})

    def _onboarding_provider(self) -> None:
        self._require_local_json_request()
        body = self._read_json()
        name = str(body.get("harness") or "").strip()
        action = str(body.get("action") or "").strip()
        known = next(
            (item for item in KNOWN_HARNESS_ADAPTERS if item["name"] == name),
            None,
        )
        if known is None or name not in WINDOWS_PROVIDER_SETUP:
            raise ServeError("choose Codex, Claude, or Grok provider setup")
        command = discover_provider_commands(
            [(known["provider_executable"], os.environ.get(known["provider_override"]))],
            wsl_names={"codex", "claude", "grok"},
        )[known["provider_executable"]]
        _launch_provider_setup(name, action, command)
        self._json(200, {"ok": True, "action": action, "harness": name})

    def _workspace_harness_model(self) -> None:
        body = self._read_json()
        name = str(body.get("harness") or "").strip()
        if not name:
            raise ServeError("harness is required")
        registry = HarnessRegistry()
        description = describe_harness(registry.get(name), timeout=10)
        model = description.get("default_model")
        if not isinstance(model, str) or not model.strip():
            raise HarnessError(f"harness {name!r} returned an empty default_model")
        cli_version = description.get("cli_version")
        registry.record_model(
            name,
            model,
            cli_version=cli_version if isinstance(cli_version, str) else None,
        )
        self.store.log(
            "workspace_model_refresh",
            harness=name,
            model=model.strip(),
            warnings=[],
        )
        self._json(200, {"ok": True, "workspace": workspace_payload(self.store)})

    def _workspace_inquiry(self) -> None:
        body = self._read_json()
        result = create_workspace_inquiry(
            self.store, str(body.get("prompt") or "")
        )
        self._json(200, result)

    def do_PUT(self) -> None:  # noqa: N802
        self._json(405, {"error": "PUT is not a gesture"})

    def do_DELETE(self) -> None:  # noqa: N802
        self._json(405, {"error": "DELETE is not a gesture"})

    def _static(self, path: str) -> None:
        dist = self.dist.resolve()
        rel = path.lstrip("/") or "index.html"
        if rel.startswith("api/"):
            self._json(404, {"error": "not found"})
            return
        target = (dist / rel).resolve()
        if dist != target and dist not in target.parents:
            self._json(403, {"error": "forbidden"})
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            index = dist / "index.html"
            if index.is_file() and "." not in Path(rel).name:
                target = index
            else:
                self._send(404, b"not found\n", "text/plain; charset=utf-8")
                return
        data = target.read_bytes()
        types = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".map": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".glb": "model/gltf-binary",
            ".ogg": "audio/ogg",
            ".woff2": "font/woff2",
        }
        ctype = types.get(target.suffix, "application/octet-stream")
        self._send(200, data, ctype)


def make_server(
    store: Store,
    *,
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
    dist: Path | None = None,
) -> ThreadingHTTPServer:
    if bind not in ("127.0.0.1", "localhost", "::1"):
        raise ServeError("ta serve binds localhost only")

    class Bound(InhabitHandler):
        pass

    Bound.store = store
    Bound.dist = dist or viz_dist_path()
    try:
        return ThreadingHTTPServer((bind, port), Bound)
    except OSError as exc:
        err = str(exc).lower()
        if "address already in use" in err or getattr(exc, "errno", None) == 98:
            raise ServeError(
                f"port {port} already in use — stop the other ta serve "
                f"(ss -ltnp | grep {port})"
            ) from exc
        raise ServeError(str(exc)) from exc


def serve_forever(
    store: Store,
    *,
    bind: str = DEFAULT_BIND,
    port: int = DEFAULT_PORT,
    dist: Path | None = None,
    open_browser: bool = False,
) -> None:
    httpd = make_server(store, bind=bind, port=port, dist=dist)
    url = f"http://{bind}:{port}/"
    print(
        f"Inhabit Space  {url}  "
        "(localhost · fork/veto/continuation from the chamber)"
    )
    resume_application_worker(store)
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
        stop_application_worker()
