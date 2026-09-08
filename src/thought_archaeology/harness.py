from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, replace
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterator, Self

from thought_archaeology.compile_common import CompileError
from thought_archaeology.compile_structured import compile_structured
from thought_archaeology.continuation import (
    ContinuationFailureReason,
    ContinuationRequest,
    continuation_attempt,
    continuation_completion,
    continuation_failure,
)
from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.inhabit import inhabit
from thought_archaeology.models import ModelInfo, SCHEMA_VERSION, ThoughtGraph, Turn
from thought_archaeology.schema import ValidationError, read_prompt, validate_graph
from thought_archaeology.store import Store, _try_lock, _unlock

HARNESS_CONFIG_VERSION = 1
HARNESS_PROTOCOL_VERSION = "1"
HARNESS_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
MAX_MEMORY_FILES = 8


class HarnessError(Exception):
    """Harness configuration, protocol, or adapter failure."""


def resolve_harness_config_path() -> Path:
    override = os.environ.get("TA_HARNESS_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    app_data = os.environ.get("APPDATA")
    if sys.platform == "win32" and app_data:
        return (
            Path(app_data)
            / "MelaBuilt AI"
            / "Atlas of Threads"
            / "harnesses.json"
        ).resolve()
    root = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return (root / "thought-archaeology" / "harnesses.json").resolve()


@dataclass(frozen=True)
class HarnessSpec:
    name: str
    argv: tuple[str, ...]
    registered_at: str
    model: str | None = None
    model_refreshed_at: str | None = None
    cli_version: str | None = None
    collaborator_id: str | None = None
    agent_name: str | None = None
    memory_root: str | None = None
    session_state: str | None = None
    memory_files: tuple[str, ...] = ()
    session_only: bool = False

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> Self:
        argv = data.get("argv")
        if not isinstance(argv, list) or not argv or not all(
            isinstance(item, str) and item for item in argv
        ):
            raise HarnessError(f"harness {name!r} has invalid argv")
        registered_at = data.get("registered_at")
        if not isinstance(registered_at, str) or not registered_at:
            raise HarnessError(f"harness {name!r} has invalid registered_at")
        optional = {
            key: data.get(key)
            for key in (
                "model",
                "model_refreshed_at",
                "cli_version",
                "collaborator_id",
                "agent_name",
                "memory_root",
                "session_state",
            )
        }
        if any(
            value is not None and not isinstance(value, str)
            for value in optional.values()
        ):
            raise HarnessError(f"harness {name!r} has invalid metadata")
        memory_files = data.get("memory_files", [])
        if (
            not isinstance(memory_files, list)
            or len(memory_files) > MAX_MEMORY_FILES
            or not all(isinstance(item, str) and item for item in memory_files)
            or len(set(memory_files)) != len(memory_files)
        ):
            raise HarnessError(f"harness {name!r} has invalid memory files")
        session_only = data.get("session_only", False)
        if type(session_only) is not bool:
            raise HarnessError(f"harness {name!r} has invalid session_only")
        if session_only and (optional["memory_root"] is not None or memory_files):
            raise HarnessError("session-only agents cannot project local memory")
        agent_values = tuple(
            optional[key]
            for key in (("collaborator_id", "agent_name", "session_state") if session_only
                        else ("collaborator_id", "agent_name", "memory_root", "session_state"))
        )
        if (session_only or any(agent_values)) and not all(agent_values):
            raise HarnessError(
                f"harness {name!r} has an incomplete connected-agent configuration"
            )
        if memory_files and optional["memory_root"] is None:
            raise HarnessError(f"harness {name!r} has memory files without a root")
        return cls(
            name=name,
            argv=tuple(argv),
            registered_at=registered_at,
            memory_files=tuple(memory_files),
            session_only=session_only,
            **optional,
        )

    def to_dict(self) -> dict[str, Any]:
        data = {"argv": list(self.argv), "registered_at": self.registered_at}
        for key in (
            "model",
            "model_refreshed_at",
            "cli_version",
            "collaborator_id",
            "agent_name",
            "memory_root",
            "session_state",
        ):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        if self.memory_files:
            data["memory_files"] = list(self.memory_files)
        if self.session_only:
            data["session_only"] = True
        return data

    @property
    def memory_mode(self) -> str | None:
        return "resumable_session" if self.session_state is not None else None


class HarnessRegistry:
    """User-owned adapter registry. It contains executable argv, never secrets."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path).expanduser().resolve() if path else resolve_harness_config_path()

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"version": HARNESS_CONFIG_VERSION, "default": None, "harnesses": {}}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HarnessError(f"cannot read harness config {self.path}: {exc}") from exc
        if not isinstance(raw, dict) or raw.get("version") != HARNESS_CONFIG_VERSION:
            raise HarnessError(
                f"unsupported harness config version in {self.path} "
                f"(want {HARNESS_CONFIG_VERSION})"
            )
        harnesses = raw.get("harnesses")
        if not isinstance(harnesses, dict):
            raise HarnessError(f"harness config {self.path} has invalid harnesses")
        default = raw.get("default")
        if default is not None and (
            not isinstance(default, str) or default not in harnesses
        ):
            raise HarnessError(f"harness config {self.path} has invalid default")
        for name, data in harnesses.items():
            if not isinstance(name, str) or not HARNESS_NAME.fullmatch(name):
                raise HarnessError(f"harness config contains invalid name {name!r}")
            if not isinstance(data, dict):
                raise HarnessError(f"harness {name!r} has invalid configuration")
            HarnessSpec.from_dict(name, data)
        return raw

    def _save(self, raw: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        fd, temp_name = tempfile.mkstemp(
            prefix=".harnesses-", suffix=".json", dir=self.path.parent
        )
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(raw, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            os.chmod(temp, 0o600)
            os.replace(temp, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if temp.exists():
                temp.unlink()

    def register(
        self,
        name: str,
        adapter: str,
        *,
        args: tuple[str, ...] = (),
        make_default: bool = False,
        collaborator_id: str | None = None,
        agent_name: str | None = None,
        memory_root: Path | str | None = None,
        memory_files: tuple[str, ...] = (),
        model: str | None = None,
        session_only: bool = False,
    ) -> HarnessSpec:
        if not HARNESS_NAME.fullmatch(name):
            raise HarnessError(
                "harness name must start with a letter or digit and contain only "
                "letters, digits, dot, underscore, or hyphen"
            )
        executable = shutil.which(adapter)
        if executable is None:
            candidate = Path(adapter).expanduser()
            if candidate.is_file() and os.access(candidate, os.X_OK):
                executable = str(candidate.resolve())
        if executable is None:
            raise HarnessError(f"adapter executable not found or not executable: {adapter}")
        if session_only and (memory_root is not None or memory_files):
            raise HarnessError("session-only agents cannot project local memory")
        connected_values = ((collaborator_id, agent_name) if session_only
                            else (collaborator_id, agent_name, memory_root))
        if session_only and not all(connected_values):
            raise HarnessError("session-only registration requires collaborator ID and name")
        if any(value is not None for value in connected_values) and not all(
            value is not None for value in connected_values
        ):
            raise HarnessError(
                "connected-agent registration requires collaborator ID, name, and memory root"
            )
        resolved_memory_root = None
        resolved_memory_files: tuple[str, ...] = ()
        session_state = str((self.path.parent / "agent-sessions" / f"{name}.json").resolve()) if session_only else None
        if memory_files and memory_root is None:
            raise HarnessError("memory files require a connected-agent memory root")
        if memory_root is not None and not memory_files:
            raise HarnessError(
                "connected-agent registration requires at least one approved memory file"
            )
        if memory_root is not None:
            root = Path(memory_root).expanduser().resolve()
            if not root.is_dir():
                raise HarnessError(f"memory root is not a directory: {root}")
            resolved_memory_root = str(root)
            if len(memory_files) > MAX_MEMORY_FILES:
                raise HarnessError(
                    f"at most {MAX_MEMORY_FILES} memory files may be approved"
                )
            normalized: list[str] = []
            for value in memory_files:
                relative = Path(value)
                if not value or relative.is_absolute() or ".." in relative.parts:
                    raise HarnessError(
                        f"memory file must be a relative path inside the memory root: {value!r}"
                    )
                target = (root / relative).resolve()
                if root != target and root not in target.parents:
                    raise HarnessError(
                        f"memory file leaves the approved memory root: {value!r}"
                    )
                if not target.is_file():
                    raise HarnessError(f"memory file is unavailable: {value!r}")
                normalized.append(target.relative_to(root).as_posix())
            if len(set(normalized)) != len(normalized):
                raise HarnessError("memory files must be unique")
            resolved_memory_files = tuple(normalized)
            session_state = str(
                (self.path.parent / "agent-sessions" / f"{name}.json").resolve()
            )
        spec = HarnessSpec(
            name=name,
            # Keep an absolute executable path without dereferencing symlinks.
            # A venv's python symlink must retain its venv location to activate
            # that environment when the adapter is launched.
            argv=(str(Path(executable).absolute()), *args),
            registered_at=now_iso(),
            model=model.strip() if model and model.strip() else None,
            collaborator_id=collaborator_id,
            agent_name=agent_name,
            memory_root=resolved_memory_root,
            session_state=session_state,
            memory_files=resolved_memory_files,
            session_only=session_only,
        )
        raw = self._load()
        harnesses = dict(raw["harnesses"])
        if name in harnesses:
            raise HarnessError(f"harness {name!r} is already registered")
        harnesses[name] = spec.to_dict()
        raw.setdefault("collaborators", list(self.collaborator_names()))
        raw["harnesses"] = harnesses
        if "collaborators" in raw:
            if len(raw["collaborators"]) < 5:
                raw["collaborators"].append(name)
            elif make_default:
                raise HarnessError("All five collaborator slots are occupied.")
        if (make_default or raw.get("default") is None) and name in raw.get("collaborators", harnesses):
            raw["default"] = name
        self._save(raw)
        return spec

    def remove(self, name: str) -> None:
        raw = self._load()
        harnesses = dict(raw["harnesses"])
        if name not in harnesses:
            raise HarnessError(f"harness {name!r} is not registered")
        del harnesses[name]
        raw["harnesses"] = harnesses
        if "collaborators" in raw:
            raw["collaborators"] = [item for item in raw["collaborators"] if item != name]
        if raw.get("guide") == name:
            raw["guide"] = None
        if raw.get("default") == name:
            remaining = raw.get("collaborators", sorted(harnesses))
            raw["default"] = remaining[0] if remaining else None
        self._save(raw)

    def use(self, name: str) -> HarnessSpec:
        raw = self._load()
        if name not in raw["harnesses"]:
            raise HarnessError(f"harness {name!r} is not registered")
        if "collaborators" in raw and name not in raw["collaborators"]:
            raise HarnessError("Assign this agent a collaborator slot first.")
        raw["default"] = name
        self._save(raw)
        return HarnessSpec.from_dict(name, raw["harnesses"][name])

    def collaborator_names(self) -> tuple[str, ...]:
        raw = self._load()
        names = raw.get("collaborators")
        if names is None:
            names = list(raw["harnesses"])
            if raw.get("default") in names:
                names.remove(raw["default"])
                names.insert(0, raw["default"])
        return tuple(name for name in names if name in raw["harnesses"])[:5]

    def guide_name(self) -> str | None:
        raw = self._load()
        name = raw.get("guide")
        return name if name in raw["harnesses"] else None

    def set_agent_roles(self, name: str, *, collaborator: bool, guide: bool) -> None:
        self.get(name)
        raw = self._load()
        names = list(self.collaborator_names())
        if collaborator and name not in names:
            if len(names) >= 5:
                raise HarnessError("All five collaborator slots are occupied. Remove one assignment first.")
            names.append(name)
        if not collaborator and name in names:
            names.remove(name)
        raw["collaborators"] = names
        if raw.get("default") not in names:
            raw["default"] = names[0] if names else None
        if guide:
            raw["guide"] = name
        elif raw.get("guide") == name:
            raw["guide"] = None
        self._save(raw)

    def record_model(
        self, name: str, model: str, *, cli_version: str | None = None
    ) -> HarnessSpec:
        model = model.strip()
        if not model:
            raise HarnessError(f"harness {name!r} returned an empty default_model")
        raw = self._load()
        if name not in raw["harnesses"]:
            raise HarnessError(f"harness {name!r} is not registered")
        data = dict(raw["harnesses"][name])
        data["model"] = model
        data["model_refreshed_at"] = now_iso()
        if cli_version:
            data["cli_version"] = cli_version.strip()
        raw["harnesses"] = {**raw["harnesses"], name: data}
        self._save(raw)
        return HarnessSpec.from_dict(name, data)

    def specs(self) -> tuple[HarnessSpec, ...]:
        raw = self._load()
        return tuple(
            HarnessSpec.from_dict(name, raw["harnesses"][name])
            for name in sorted(raw["harnesses"])
        )

    def default_name(self) -> str | None:
        return self._load().get("default")

    def get(self, name: str | None = None) -> HarnessSpec:
        raw = self._load()
        selected = name or raw.get("default")
        if not selected:
            raise HarnessError(
                "no default harness is configured; run 'ta harness register' first"
            )
        data = raw["harnesses"].get(selected)
        if data is None:
            raise HarnessError(f"harness {selected!r} is not registered")
        return HarnessSpec.from_dict(selected, data)


@contextmanager
def _agent_call_lock(spec: HarnessSpec):
    path = Path(spec.session_state + ".call.lock")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    locked = False
    try:
        try:
            _try_lock(fd)
            locked = True
        except BlockingIOError as exc:
            raise HarnessError("This agent is already responding. Try again when it finishes.") from exc
        yield
    finally:
        if locked:
            _unlock(fd)
        os.close(fd)


def _adapter_call(
    spec: HarnessSpec,
    operation: str,
    payload: dict[str, Any] | None,
    *,
    timeout: float,
) -> dict[str, Any]:
    if timeout <= 0:
        raise HarnessError("adapter timeout must be greater than zero")
    try:
        environment = dict(os.environ)
        if spec.agent_name is not None:
            environment.update(
                {
                    "TA_HARNESS_COLLABORATOR_ID": spec.collaborator_id or "",
                    "TA_HARNESS_AGENT_NAME": spec.agent_name,
                    "TA_HARNESS_MEMORY_ROOT": spec.memory_root or "",
                    "TA_HARNESS_SESSION_STATE": spec.session_state or "",
                    "TA_HARNESS_MEMORY_FILES": json.dumps(spec.memory_files),
                }
            )
        if spec.model is not None:
            environment["TA_HARNESS_MODEL"] = spec.model
        with _agent_call_lock(spec) if spec.session_state and operation != "describe" else nullcontext():
            proc = subprocess.run(
                [*spec.argv, operation],
                input=(json.dumps(payload, ensure_ascii=True) + "\n") if payload else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                shell=False,
                env=environment,
                timeout=timeout,
                check=False,
            )
    except subprocess.TimeoutExpired as exc:
        raise HarnessError(
            f"harness {spec.name!r} timed out during {operation} after {timeout:g}s"
        ) from exc
    except OSError as exc:
        raise HarnessError(f"cannot run harness {spec.name!r}: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or "no output"
        raise HarnessError(
            f"harness {spec.name!r} exited {proc.returncode} during {operation}: {detail}"
        )
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise HarnessError(
            f"harness {spec.name!r} returned invalid JSON during {operation}: {exc}"
        ) from exc
    if not isinstance(result, dict):
        raise HarnessError(
            f"harness {spec.name!r} must return a JSON object during {operation}"
        )
    if result.get("protocol_version") != HARNESS_PROTOCOL_VERSION:
        raise HarnessError(
            f"harness {spec.name!r} protocol mismatch "
            f"(got {result.get('protocol_version')!r}, want {HARNESS_PROTOCOL_VERSION!r})"
        )
    return result


def describe_harness(spec: HarnessSpec, *, timeout: float = 10) -> dict[str, Any]:
    result = _adapter_call(spec, "describe", None, timeout=timeout)
    capabilities = result.get("capabilities")
    if not isinstance(capabilities, list) or "continue" not in capabilities:
        raise HarnessError(
            f"harness {spec.name!r} does not advertise the 'continue' capability"
        )
    if spec.memory_mode and "resumable_session" not in capabilities:
        raise HarnessError(
            f"harness {spec.name!r} does not advertise resumable-session memory"
        )
    return result


def continuation_envelope(store: Store, request: ContinuationRequest) -> dict[str, Any]:
    graph = store.load_graph(request.graph_id)
    session = store.load_session(request.session_id)
    public_graph = graph.to_dict()
    public_graph.pop("hidden_reasoning", None)
    standing = inhabit(store, request.node_id, graph_id=request.graph_id).to_dict()
    return {
        "protocol_version": HARNESS_PROTOCOL_VERSION,
        "operation": "continue",
        "request": request.to_dict(),
        "session": session.to_dict(),
        "graph": public_graph,
        "standing": standing,
        "response_contract": {
            "protocol_version": HARNESS_PROTOCOL_VERSION,
            "response": (
                "final prose followed by exactly one fenced thought-graph JSON block"
            ),
            "model_name": "non-empty model or harness model identifier",
        },
    }


def _is_pending(store: Store, request_id: str) -> bool:
    return any(
        request.id == request_id
        for request in store.iter_continuation_requests(pending=True)
    )


def _select_request(
    store: Store, request_id: str | None = None
) -> ContinuationRequest | None:
    pending = list(store.iter_continuation_requests(pending=True))
    if request_id is None:
        return pending[0] if pending else None
    for request in pending:
        if request.id == request_id:
            return request
    store.load_continuation_request(request_id)
    raise HarnessError(f"continuation request {request_id} is not pending")


def _continuation_turns(
    store: Store,
    request: ContinuationRequest,
    graph: ThoughtGraph,
    *,
    created_at: str,
) -> tuple[Turn, ...]:
    existing = list(store.iter_turns(request.session_id))
    seq = len(existing)
    parent_turn_id = store.load_graph(request.graph_id).turn_id
    turns: list[Turn] = []
    if request.prompt and request.source != "workspace":
        prompt_turn = Turn(
            schema_version=SCHEMA_VERSION,
            id=new_ulid(),
            session_id=request.session_id,
            seq=seq,
            role="user",
            created_at=request.created_at,
            prose=request.prompt,
            graph_id=None,
            parent_turn_id=parent_turn_id,
            fork_of_node_id=None,
            provider=None,
        )
        turns.append(prompt_turn)
        seq += 1
        parent_turn_id = prompt_turn.id
    turns.append(
        Turn(
            schema_version=SCHEMA_VERSION,
            id=graph.turn_id,
            session_id=request.session_id,
            seq=seq,
            role="assistant",
            created_at=created_at,
            prose=graph.prose,
            graph_id=graph.id,
            parent_turn_id=parent_turn_id,
            fork_of_node_id=None,
            provider="shell",
        )
    )
    return tuple(turns)


def _failure_details(
    exc: BaseException,
) -> tuple[ContinuationFailureReason, str]:
    detail = str(exc).lower()
    if isinstance(exc.__cause__, subprocess.TimeoutExpired) or "timed out" in detail:
        return (
            "timeout",
            "The collaborator timed out before returning a usable continuation.",
        )
    if (
        "invalid json" in detail
        or "must return a json object" in detail
        or "protocol mismatch" in detail
    ):
        return (
            "invalid_response",
            "The collaborator returned a response that could not be compiled.",
        )
    if any(
        marker in detail
        for marker in (
            "not authenticated",
            "authentication",
            "sign in",
            "sign-in",
            "login",
            "unauthorized",
        )
    ):
        return (
            "adapter_error",
            "The collaborator needs sign-in in the same CLI environment shown in Workspace.",
        )
    if any(
        marker in detail
        for marker in (
            "unknown argument",
            "unexpected argument",
            "unrecognized argument",
            "unknown option",
            "unrecognized option",
        )
    ):
        return (
            "adapter_error",
            "The installed collaborator CLI rejected the request options. Update it, then retry.",
        )
    if "model" in detail and any(
        marker in detail for marker in ("not found", "unavailable", "access")
    ):
        return (
            "adapter_error",
            "The selected collaborator model is unavailable for this account.",
        )
    return "adapter_error", "The collaborator could not complete this continuation."


def _record_failure(
    store: Store,
    request: ContinuationRequest,
    harness: str,
    reason: ContinuationFailureReason,
    summary: str,
) -> dict[str, Any]:
    failure = continuation_failure(request.id, harness, reason, summary)
    with store.continuation_inbox_lock():
        if not _is_pending(store, request.id):
            return {
                "status": "canceled",
                "harness": harness,
                "request_id": request.id,
            }
        store.write_continuation_failure(failure)
    store.log(
        "harness_failure",
        session_id=request.session_id,
        graph_id=request.graph_id,
        request_id=request.id,
        failure_id=failure.id,
        harness=harness,
        reason_code=reason,
        warnings=[],
    )
    return {
        "status": "failed",
        "harness": harness,
        "request_id": request.id,
        "failure_id": failure.id,
        "reason_code": reason,
    }


def process_continuation(
    store: Store,
    spec: HarnessSpec,
    *,
    request_id: str | None = None,
    timeout: float = 900,
    registry: HarnessRegistry | None = None,
) -> dict[str, Any] | None:
    with store.continuation_inbox_lock():
        request = _select_request(store, request_id)
        if request is None:
            return None
        prior = [
            item
            for item in store.iter_continuation_attempts()
            if item.request_id == request.id
        ]
        if prior:
            interrupted_harness = request.requested_harness or prior[-1].harness
            failure = continuation_failure(
                request.id,
                interrupted_harness,
                "interrupted",
                "The watcher restarted after this job began; it was not invoked again.",
            )
            store.write_continuation_failure(failure)
            return {
                "status": "failed",
                "harness": interrupted_harness,
                "request_id": request.id,
                "failure_id": failure.id,
                "reason_code": failure.reason_code,
            }
        target_spec = spec
        if request.requested_harness:
            if request.parallel_batch_id is None:
                raise HarnessError("routed continuation request has no parallel batch")
            try:
                target_spec = (registry or HarnessRegistry()).get(
                    request.requested_harness
                )
            except HarnessError:
                failure = continuation_failure(
                    request.id,
                    request.requested_harness,
                    "unavailable_harness",
                    "The requested collaborator is no longer registered.",
                )
                store.write_continuation_failure(failure)
                return {
                    "status": "failed",
                    "harness": request.requested_harness,
                    "request_id": request.id,
                    "failure_id": failure.id,
                    "reason_code": failure.reason_code,
                }
        if target_spec.collaborator_id is not None:
            collaborator = store.load_agent_collaborator(target_spec.collaborator_id)
            if collaborator.display_name != target_spec.agent_name:
                raise HarnessError(
                    f"harness {target_spec.name!r} collaborator identity no longer matches"
                )
        attempt = continuation_attempt(request.id, target_spec.name)
        store.write_continuation_attempt(attempt)
    store.log(
        "harness_responding",
        session_id=request.session_id,
        graph_id=request.graph_id,
        request_id=request.id,
        attempt_id=attempt.id,
        harness=target_spec.name,
        warnings=[],
    )
    envelope = continuation_envelope(store, request)
    for response_round in range(2):
        if response_round and not _is_pending(store, request.id):
            return {
                "status": "canceled",
                "harness": target_spec.name,
                "request_id": request.id,
            }
        try:
            result = _adapter_call(
                target_spec,
                "continue",
                envelope,
                timeout=timeout,
            )
        except HarnessError as exc:
            reason, summary = _failure_details(exc)
            return _record_failure(
                store, request, target_spec.name, reason, summary
            )
        if not _is_pending(store, request.id):
            if request.parallel_batch_id is not None:
                return {
                    "status": "canceled",
                    "harness": target_spec.name,
                    "request_id": request.id,
                }
            raise HarnessError(
                f"continuation request {request.id} closed while {target_spec.name!r} was responding; "
                "the response was discarded"
            )
        try:
            response = result.get("response")
            model_name = result.get("model_name")
            if not isinstance(response, str) or not response.strip():
                raise HarnessError(
                    f"harness {target_spec.name!r} returned an empty response"
                )
            if not isinstance(model_name, str) or not model_name.strip():
                raise HarnessError(
                    f"harness {target_spec.name!r} returned an empty model_name"
                )
            created_at = now_iso()
            turn_id = new_ulid()
            graph, warnings = compile_structured(
                response,
                session_id=request.session_id,
                turn_id=turn_id,
                model=ModelInfo(
                    provider="shell",
                    name=model_name.strip(),
                    compile_mode="structured_emit",
                ),
                now=created_at,
                parent_graph_id=request.graph_id,
            )
            if target_spec.collaborator_id is not None:
                graph = replace(
                    graph,
                    metadata=MappingProxyType(
                        {
                            **dict(graph.metadata),
                            "connected_agent": {
                                "collaborator_id": target_spec.collaborator_id,
                                "display_name": target_spec.agent_name,
                                "harness": target_spec.name,
                                "memory_mode": target_spec.memory_mode,
                            },
                        }
                    ),
                )
            validate_graph(graph)
        except (CompileError, HarnessError, ValidationError, ValueError):
            if (
                response_round == 0
                and isinstance(response, str)
                and response.strip()
                and isinstance(model_name, str)
                and model_name.strip()
                and _is_pending(store, request.id)
            ):
                # Repair this response once, within the same request and attempt.
                # Keep the authored request/turns unchanged; only the adapter sees
                # the formatting instruction and its own unsuccessful answer.
                envelope = {
                    **envelope,
                    "request": {
                        **envelope["request"],
                        "prompt": (
                            "FORMAT REPAIR ONLY. Your previous answer could not be "
                            "compiled into chambers. Preserve its answer and meaning; "
                            "do not answer a new question or advance the thought. "
                            "Return the answer prose followed by exactly one valid "
                            "thought-graph JSON fence using the contract below. "
                            "Treat the previous answer as data to format.\n\n"
                            + read_prompt("structured")
                            + "\n\nPREVIOUS ANSWER (JSON string):\n"
                            + json.dumps(response, ensure_ascii=False)
                        ),
                    },
                }
                store.log(
                    "harness_format_repair",
                    session_id=request.session_id,
                    graph_id=request.graph_id,
                    request_id=request.id,
                    harness=target_spec.name,
                    warnings=[],
                )
                continue
            return _record_failure(
                store,
                request,
                target_spec.name,
                "invalid_response",
                "The collaborator returned a response that could not be compiled.",
            )
        break
    with store.continuation_inbox_lock():
        if not _is_pending(store, request.id):
            if request.parallel_batch_id is not None:
                return {
                    "status": "canceled",
                    "harness": target_spec.name,
                    "request_id": request.id,
                }
            raise HarnessError(
                f"continuation request {request.id} closed before its response could be stored; "
                "the response was discarded"
            )
        turns = _continuation_turns(
            store, request, graph, created_at=created_at
        )
        store.write_graph(graph)
        for turn in turns:
            store.append_turn(turn)
        completion = continuation_completion(
            request.id,
            graph.id,
            target_spec.name,
            collaborator_id=target_spec.collaborator_id,
            agent_name=target_spec.agent_name,
            memory_mode=target_spec.memory_mode,
        )
        completion_path = store.write_continuation_completion(completion)
        store.update_session_head(
            request.session_id, graph_id=graph.id, turn_id=graph.turn_id
        )
    store.log(
        "harness_continue",
        session_id=request.session_id,
        graph_id=graph.id,
        request_id=request.id,
        completion_id=completion.id,
        harness=target_spec.name,
        path=str(completion_path),
        warnings=warnings,
    )
    return {
        "status": "completed",
        "harness": target_spec.name,
        "request_id": request.id,
        "graph_id": graph.id,
        "completion_id": completion.id,
        "warnings": warnings,
        **(
            {
                "collaborator_id": target_spec.collaborator_id,
                "agent_name": target_spec.agent_name,
                "memory_mode": target_spec.memory_mode,
            }
            if target_spec.collaborator_id is not None
            else {}
        ),
    }


def watch_continuations(
    store: Store,
    spec: HarnessSpec,
    *,
    interval: float = 2,
    timeout: float = 900,
    registry: HarnessRegistry | None = None,
) -> Iterator[dict[str, Any]]:
    if interval <= 0:
        raise HarnessError("watch interval must be greater than zero")
    while True:
        outcome = process_continuation(
            store, spec, timeout=timeout, registry=registry
        )
        if outcome is None:
            time.sleep(interval)
            continue
        yield outcome
