from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from thought_archaeology.compile_common import CompileError
from thought_archaeology.compile_posthoc import compile_posthoc
from thought_archaeology.compile_structured import compile_structured
from thought_archaeology.continuation import (
    continuation_cancellation,
    continuation_completion,
    continuation_request,
)
from thought_archaeology.edits import append_op_turn, commit, plan_fork, plan_veto
from thought_archaeology.evidence import context_provenance_binding
from thought_archaeology.fingerprint import DEFAULT_MIN_SESSIONS, Fingerprint, fingerprint
from thought_archaeology.fork import (
    ForkError,
    detect_regen_compile_mode,
    fork_regen_prompt,
)
from thought_archaeology.ids import is_ulid, new_ulid, now_iso
from thought_archaeology.inhabit import format_inhabit, inhabit, resolve_standing
from thought_archaeology.models import SCHEMA_VERSION, ModelInfo, Span, ThoughtGraph, Turn
from thought_archaeology.render_md import render_md
from thought_archaeology.serve import DEFAULT_BIND, DEFAULT_PORT, ServeError, serve_forever
from thought_archaeology.providers import ProviderError, build_provider
from thought_archaeology.schema import (
    ISO_Z_PATTERN,
    ValidationError,
    read_prompt,
    validate_graph,
    validate_schema,
)
from thought_archaeology.depth2 import (
    PROBE_KINDS,
    STORY_FALSIFIED,
    ProbeError,
    ProbeHarness,
    ProbeSpec,
    diff_graphs,
    evidence_from_probe,
    make_plan,
)
from thought_archaeology.depth3 import (
    DisplayRefused,
    NullSensor,
    SensorError,
    format_attribution,
)
from thought_archaeology.store import Store, StoreError, resolve_store_path

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_USAGE = 2
EXIT_IO = 3
EXIT_NOT_IMPLEMENTED = 4


class UsageError(Exception):
    """CLI usage / missing provider."""


def normalize_created_at(value: str | None, default: str) -> str:
    if not value:
        return default
    if re.match(ISO_Z_PATTERN, value):
        return value
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?Z$", value)
    if m:
        return m.group(1) + "Z"
    raw = value
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return default


def _parser() -> argparse.ArgumentParser:
    # Two parent parsers so global flags work both before and after the
    # subcommand without argparse overwriting a provided value with the
    # subparser default.
    main_globals = argparse.ArgumentParser(add_help=False)
    main_globals.add_argument("--store", default=None, metavar="PATH")
    main_globals.add_argument("--strict", action="store_true")
    main_globals.add_argument("--quiet", action="store_true")
    sub_globals = argparse.ArgumentParser(add_help=False)
    sub_globals.add_argument("--store", default=argparse.SUPPRESS, metavar="PATH")
    sub_globals.add_argument("--strict", action="store_true", default=argparse.SUPPRESS)
    sub_globals.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS)

    parser = argparse.ArgumentParser(
        prog="ta",
        description="Thought Archaeology — inspectable AI thought-graphs.",
        parents=[main_globals],
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", parents=[sub_globals], help="create store + session")
    p_init.add_argument("--title", default="untitled")
    p_init.add_argument("--origin", default=None)

    p_compile = sub.add_parser("compile", parents=[sub_globals], help="compile a turn into a graph")
    p_compile.add_argument("--session", required=True, metavar="ID")
    p_compile.add_argument("--mode", required=True, choices=["structured", "posthoc"])
    p_compile.add_argument("--input", default=None, metavar="PATH")
    p_compile.add_argument("--transcript", default=None, metavar="PATH")
    p_compile.add_argument("--turn-id", default=None, metavar="ID")
    p_compile.add_argument("--from-graph", default=None, metavar="PATH")
    p_compile.add_argument("--hidden", default=None, metavar="PATH")
    p_compile.add_argument(
        "--provider",
        default="none",
        choices=["none", "file", "stdin", "shell"],
    )
    p_compile.add_argument("--provider-file", default=None, metavar="PATH")
    p_compile.add_argument("--provider-cmd", default=None, metavar="CMD")
    p_compile.add_argument("--model-name", default="unknown", metavar="NAME")

    p_show = sub.add_parser("show", parents=[sub_globals], help="show a session or graph")
    p_show.add_argument("id")
    p_show.add_argument("--format", choices=["json", "tree", "ids"], default="tree")
    p_show.add_argument("--node", default=None, metavar="NODE")

    p_validate = sub.add_parser("validate", parents=[sub_globals], help="validate session or JSON")
    p_validate.add_argument("target")

    p_log = sub.add_parser("log", parents=[sub_globals], help="print session turns")
    p_log.add_argument("session")

    p_prompt = sub.add_parser("prompt", parents=[sub_globals], help="dump a packaged prompt")
    p_prompt.add_argument("name", choices=["structured", "posthoc", "fork"])

    p_inhabit = sub.add_parser(
        "inhabit", parents=[sub_globals], help="stand at a node and see discarded moves"
    )
    p_inhabit.add_argument("node")
    p_inhabit.add_argument("--graph", default=None, metavar="G")
    p_inhabit.add_argument("--session", default=None, metavar="S")

    p_fork = sub.add_parser(
        "fork", parents=[sub_globals], help="omit a node and its causal descendants"
    )
    p_fork.add_argument("node")
    p_fork.add_argument("--session", required=True, metavar="ID")
    p_fork.add_argument("--graph", default=None, metavar="G")
    p_fork.add_argument("--reason", default=None)
    p_fork.add_argument("--from-graph", default=None, metavar="PATH")
    p_fork.add_argument(
        "--provider",
        default="none",
        choices=["none", "file", "stdin", "shell"],
    )
    p_fork.add_argument("--provider-file", default=None, metavar="PATH")
    p_fork.add_argument("--provider-cmd", default=None, metavar="CMD")
    p_fork.add_argument("--model-name", default=None, metavar="NAME")

    p_veto = sub.add_parser(
        "veto", parents=[sub_globals], help="copy a graph and record a human veto"
    )
    p_veto.add_argument("node")
    p_veto.add_argument("--session", required=True, metavar="ID")
    p_veto.add_argument("--graph", default=None, metavar="G")
    p_veto.add_argument("--reason", required=True)

    p_continuation = sub.add_parser(
        "continuation",
        parents=[sub_globals],
        help="provider-neutral handoff between an inhabited chamber and an AI harness",
    )
    continuation_sub = p_continuation.add_subparsers(
        dest="continuation_cmd", required=True
    )
    p_ready = continuation_sub.add_parser(
        "ready", parents=[sub_globals], help="mark a chamber ready for continuation"
    )
    p_ready.add_argument("node")
    p_ready.add_argument("--graph", required=True, metavar="G")
    p_ready.add_argument("--prompt", default="", metavar="TEXT")
    p_pending = continuation_sub.add_parser(
        "pending", parents=[sub_globals], help="list requests awaiting a harness"
    )
    p_pending.add_argument("--format", choices=["table", "json"], default="table")
    p_cancel = continuation_sub.add_parser(
        "cancel", parents=[sub_globals], help="withdraw a pending continuation request"
    )
    p_cancel.add_argument("request")
    p_complete = continuation_sub.add_parser(
        "complete", parents=[sub_globals], help="link a request to its response graph"
    )
    p_complete.add_argument("request")
    p_complete.add_argument("--graph", required=True, metavar="G")
    p_complete.add_argument("--harness", required=True, metavar="NAME")

    p_probe = sub.add_parser(
        "probe",
        parents=[sub_globals],
        help="depth-2 probe harness (stubs)",
    )
    probe_sub = p_probe.add_subparsers(dest="probe_cmd", required=True)
    p_plan = probe_sub.add_parser(
        "plan",
        parents=[sub_globals],
        help="write a ProbeSpec JSON next to the graph (no model call)",
    )
    p_plan.add_argument("--graph", required=True, metavar="G")
    p_plan.add_argument("--kind", required=True, choices=list(PROBE_KINDS))
    p_plan.add_argument("--node", required=True, metavar="N")
    p_plan.add_argument("--out", default=None, metavar="PATH")
    p_plan.add_argument("--turn", default=None, metavar="T")
    p_plan.add_argument("--old", default=None, metavar="TEXT")
    p_plan.add_argument("--new", default=None, metavar="TEXT")
    p_run = probe_sub.add_parser(
        "run",
        parents=[sub_globals],
        help="run a drop-premise probe through the shell provider",
    )
    p_run.add_argument("--spec", required=True, metavar="PATH")
    p_run.add_argument("--provider-cmd", required=True, metavar="CMD")
    p_run.add_argument(
        "--parent-evidence",
        default=None,
        metavar="ID",
        help="continue an existing same-session evidence chain",
    )
    p_diff = probe_sub.add_parser(
        "diff",
        parents=[sub_globals],
        help="diff two graphs by id then kind+Jaccard (bookkeeping)",
    )
    p_diff.add_argument("a")
    p_diff.add_argument("b")
    p_diff.add_argument("--spec", default=None, metavar="PATH")
    p_diff.add_argument("--out", default=None, metavar="PATH")

    p_sensor = sub.add_parser(
        "sensor",
        parents=[sub_globals],
        help="depth-3 sensor interface (stubs)",
    )
    sensor_sub = p_sensor.add_subparsers(dest="sensor_cmd", required=True)
    p_attach = sensor_sub.add_parser(
        "attach",
        parents=[sub_globals],
        help="bind a collapsed attribution subgraph to a thought-node",
    )
    p_attach.add_argument("node", nargs="?")
    p_attach.add_argument("--graph", default=None, metavar="G")
    p_attach.add_argument("--session", default=None, metavar="S")
    p_attach.add_argument(
        "--from-attribution",
        default=None,
        metavar="PATH",
        help="display, or with --graph/--node store, a collapsed attribution JSON",
    )
    p_attach.add_argument(
        "--parent-evidence", default=None, metavar="ID",
        help="continue an existing same-session evidence chain",
    )
    p_import = sensor_sub.add_parser(
        "import-circuit-tracer",
        parents=[sub_globals],
        help="collapse and bind an official circuit-tracer graph",
    )
    p_import.add_argument("node")
    p_import.add_argument("--graph", required=True, metavar="G")
    p_import.add_argument("--session", default=None, metavar="S")
    p_import.add_argument("--from-graph", required=True, metavar="PATH")
    p_import.add_argument("--source-uri", required=True)
    p_import.add_argument("--producer-revision", required=True)
    p_import.add_argument("--parent-evidence", default=None, metavar="ID")
    p_activation = sensor_sub.add_parser(
        "import-activation",
        parents=[sub_globals],
        help="bind a measured Neuronpedia feature activation to a thought",
    )
    p_activation.add_argument("node")
    p_activation.add_argument("--graph", required=True, metavar="G")
    p_activation.add_argument("--session", default=None, metavar="S")
    p_activation.add_argument("--request", required=True, metavar="PATH")
    p_activation.add_argument("--from-response", required=True, metavar="PATH")
    p_activation.add_argument("--graph-position", required=True, type=int)
    p_activation.add_argument("--target", required=True)
    p_activation.add_argument("--attribution-id", default=None, metavar="ID")
    p_activation.add_argument("--parent-evidence", default=None, metavar="ID")
    p_record = sensor_sub.add_parser(
        "record-intervention",
        parents=[sub_globals],
        help="verify and bind observed baseline/intervened neural measurements",
    )
    p_record.add_argument("node")
    p_record.add_argument("--graph", required=True, metavar="G")
    p_record.add_argument("--session", default=None, metavar="S")
    p_record.add_argument("--from-result", required=True, metavar="PATH")
    p_record.add_argument("--neuronpedia-request", default=None, metavar="PATH")
    p_record.add_argument("--manifest", default=None, metavar="PATH")
    p_record.add_argument("--source-uri", required=True)
    p_record.add_argument("--parent-evidence", required=True, metavar="ID")
    p_recur = sensor_sub.add_parser(
        "synthesize-recurrence",
        parents=[sub_globals],
        help="qualify an exact feature as recurring across independent contexts",
    )
    p_recur.add_argument(
        "--neural-evidence", action="append", required=True, metavar="ID",
        help="neural_intervention evidence id; repeat for each context",
    )
    p_recur.add_argument("--minimum-contexts", type=int, default=3)

    p_evidence = sub.add_parser(
        "evidence",
        parents=[sub_globals],
        help="bind typed evidence beneath a thought-node",
    )
    evidence_sub = p_evidence.add_subparsers(dest="evidence_cmd", required=True)
    p_context = evidence_sub.add_parser(
        "context",
        parents=[sub_globals],
        help="bind an actual preceding stored turn as context provenance",
    )
    p_context.add_argument("--graph", required=True, metavar="G")
    p_context.add_argument("--node", required=True, metavar="N")

    p_provenance = sub.add_parser(
        "provenance", parents=[sub_globals],
        help="bind bounded training/checkpoint provenance without genealogy claims",
    )
    provenance_sub = p_provenance.add_subparsers(dest="provenance_cmd", required=True)
    p_checkpoint = provenance_sub.add_parser(
        "checkpoint", parents=[sub_globals],
        help="record an observed behavior trajectory across exact model checkpoints",
    )
    p_checkpoint.add_argument("--graph", required=True, metavar="G")
    p_checkpoint.add_argument("--node", required=True, metavar="N")
    p_checkpoint.add_argument("--session", default=None, metavar="S")
    p_checkpoint.add_argument("--measurements", required=True, metavar="PATH")
    p_checkpoint.add_argument("--checkpoint-map", required=True, metavar="PATH")
    p_checkpoint.add_argument("--model-card", required=True, metavar="PATH")
    p_checkpoint.add_argument("--model-card-uri", required=True)
    p_checkpoint.add_argument("--training-docs", required=True, metavar="PATH")
    p_checkpoint.add_argument("--training-docs-uri", required=True)
    p_checkpoint.add_argument("--corpus", required=True)
    p_checkpoint.add_argument("--parent-evidence", default=None, metavar="ID")
    p_context.add_argument("--turn", required=True, metavar="T")
    p_context.add_argument("--parent-evidence", default=None, metavar="ID")

    p_fp = sub.add_parser(
        "fingerprint",
        parents=[sub_globals],
        help="deterministic dual-archaeology fingerprint",
    )
    p_fp.add_argument("--session", action="append", default=None, metavar="ID")
    p_fp.add_argument(
        "--min-sessions",
        type=int,
        default=DEFAULT_MIN_SESSIONS,
        metavar="N",
    )
    p_fp.add_argument("--out", default=None, metavar="PATH")

    p_canvas = sub.add_parser(
        "canvas",
        parents=[sub_globals],
        help="render a graph as a markdown canvas",
    )
    p_canvas.add_argument("graph")
    p_canvas.add_argument("--out", default=None, metavar="PATH")
    p_canvas.add_argument("--fingerprint", default=None, metavar="PATH")

    p_wiki = sub.add_parser(
        "export-wiki",
        parents=[sub_globals],
        help="write a wiki-shaped canvas (does not touch index.md or log.md)",
    )
    p_wiki.add_argument("graph")
    p_wiki.add_argument("--out", required=True, metavar="PATH")
    p_wiki.add_argument("--fingerprint", default=None, metavar="PATH")

    p_serve = sub.add_parser(
        "serve",
        parents=[sub_globals],
        help="serve Inhabit Space on localhost",
    )
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_serve.add_argument("--bind", default=DEFAULT_BIND)

    return parser


def _store(args: argparse.Namespace) -> Store:
    return Store(resolve_store_path(getattr(args, "store", None)))


def _read_path(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).expanduser().resolve().read_text(encoding="utf-8")


def _load_transcript(path: str) -> list[dict]:
    text = Path(path).expanduser().resolve().read_text(encoding="utf-8")
    rows: list[dict] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict) or "role" not in obj or "text" not in obj:
            raise CompileError("transcript rows must be JSON objects with role and text")
        rows.append(obj)
    if not rows:
        raise CompileError("transcript is empty")
    return rows


def _emit_warnings(warnings: list[str], *, quiet: bool) -> None:
    if quiet:
        return
    for w in warnings:
        print(w, file=sys.stderr)


def cmd_init(args: argparse.Namespace) -> int:
    store = _store(args)
    session = store.init_session(title=args.title, origin=args.origin)
    print(session.id)
    return EXIT_OK


def _select_transcript_index(rows: list[dict], turn_id: str | None) -> int:
    if turn_id:
        for i, row in enumerate(rows):
            if row.get("id") == turn_id:
                return i
        raise UsageError(f"--turn-id {turn_id} not found in transcript")
    for i in range(len(rows) - 1, -1, -1):
        if rows[i].get("role") == "assistant":
            return i
    raise UsageError("transcript has no role=assistant row")


def _make_turn(
    *,
    session_id: str,
    seq: int,
    role: str,
    prose: str,
    created_at: str,
    graph_id: str | None,
    parent_turn_id: str | None,
    provider: str | None,
    turn_id: str | None = None,
) -> Turn:
    return Turn(
        schema_version=SCHEMA_VERSION,
        id=turn_id or new_ulid(),
        session_id=session_id,
        seq=seq,
        role=role,  # type: ignore[arg-type]
        created_at=created_at,
        prose=prose,
        graph_id=graph_id,
        parent_turn_id=parent_turn_id,
        fork_of_node_id=None,
        provider=provider,  # type: ignore[arg-type]
    )


def cmd_compile(args: argparse.Namespace) -> int:
    store = _store(args)
    try:
        store.load_session(args.session)
    except StoreError as exc:
        raise StoreError(str(exc)) from exc

    compile_mode = "structured_emit" if args.mode == "structured" else "posthoc"
    model_name = args.model_name or "unknown"
    now = now_iso()

    hidden = None
    if args.hidden:
        hidden = _read_path(args.hidden)

    transcript_rows: list[dict] | None = None
    compiled_index: int | None = None
    if args.transcript:
        transcript_rows = _load_transcript(args.transcript)
        compiled_index = _select_transcript_index(transcript_rows, args.turn_id)

    from_graph = args.from_graph
    raw_input: str | None = None

    if from_graph:
        model = ModelInfo(provider="file", name=model_name, compile_mode=compile_mode)
        raw_graph_text = _read_path(from_graph)
    elif args.mode == "posthoc":
        if args.provider == "none":
            raise UsageError("posthoc compile requires --from-graph or a provider")
        model = ModelInfo(
            provider=args.provider, name=model_name, compile_mode=compile_mode
        )
        provider = build_provider(
            args.provider,
            provider_file=args.provider_file,
            provider_cmd=args.provider_cmd,
        )
        prompt_body = ""
        if transcript_rows is not None and compiled_index is not None:
            prompt_body = transcript_rows[compiled_index].get("text") or ""
        elif args.input:
            prompt_body = _read_path(args.input)
        system = read_prompt("posthoc")
        raw_graph_text = provider.complete(prompt_body, system=system)
    else:
        # structured
        if args.input:
            raw_input = _read_path(args.input)
            model = ModelInfo(
                provider="none", name=model_name, compile_mode=compile_mode
            )
        elif args.provider != "none":
            model = ModelInfo(
                provider=args.provider, name=model_name, compile_mode=compile_mode
            )
            provider = build_provider(
                args.provider,
                provider_file=args.provider_file,
                provider_cmd=args.provider_cmd,
            )
            user_text = ""
            if transcript_rows is not None and compiled_index is not None:
                user_text = transcript_rows[compiled_index].get("text") or ""
            raw_input = provider.complete(user_text, system=read_prompt("structured"))
        else:
            raise UsageError(
                "structured compile requires --input, --from-graph, or a provider"
            )
        raw_graph_text = raw_input

    assistant_turn_id = new_ulid()
    if (
        transcript_rows is not None
        and compiled_index is not None
        and is_ulid(str(transcript_rows[compiled_index].get("id") or ""))
    ):
        assistant_turn_id = str(transcript_rows[compiled_index]["id"])

    if compile_mode == "structured_emit" and from_graph:
        prose = ""
        if transcript_rows is not None and compiled_index is not None:
            prose = str(transcript_rows[compiled_index].get("text") or "")
        graph, warnings = compile_posthoc(
            prose,
            raw_graph_text,
            session_id=args.session,
            turn_id=assistant_turn_id,
            model=model,
            now=now,
            hidden_reasoning=hidden,
        )
    elif compile_mode == "structured_emit":
        graph, warnings = compile_structured(
            raw_graph_text,
            session_id=args.session,
            turn_id=assistant_turn_id,
            model=model,
            now=now,
            hidden_reasoning=hidden,
        )
    else:
        prose = ""
        if transcript_rows is not None and compiled_index is not None:
            prose = str(transcript_rows[compiled_index].get("text") or "")
        elif args.input and not from_graph:
            prose = _read_path(args.input)
        graph, warnings = compile_posthoc(
            prose,
            raw_graph_text,
            session_id=args.session,
            turn_id=assistant_turn_id,
            model=model,
            now=now,
            hidden_reasoning=hidden,
        )

    _emit_warnings(warnings, quiet=args.quiet)
    if args.strict and warnings:
        return EXIT_VALIDATION

    try:
        validate_graph(graph)
    except ValidationError:
        raise

    path = store.write_graph(graph)
    store.log(
        "compile",
        session_id=args.session,
        graph_id=graph.id,
        path=str(path),
        warnings=warnings,
    )

    if transcript_rows is not None and compiled_index is not None:
        parent_id: str | None = None
        for i, row in enumerate(transcript_rows):
            role = row["role"]
            created = normalize_created_at(row.get("created_at"), now)
            rid = row.get("id")
            tid = rid if isinstance(rid, str) and is_ulid(rid) else None
            if i == compiled_index:
                tid = assistant_turn_id
                turn = _make_turn(
                    session_id=args.session,
                    seq=i,
                    role="assistant",
                    prose=graph.prose,
                    created_at=created,
                    graph_id=graph.id,
                    parent_turn_id=parent_id,
                    provider=model.provider,
                    turn_id=tid,
                )
            else:
                if role not in ("user", "assistant", "human_edit", "system"):
                    raise CompileError(f"unknown transcript role {role!r}")
                turn = _make_turn(
                    session_id=args.session,
                    seq=i,
                    role=role,
                    prose=str(row.get("text") or ""),
                    created_at=created,
                    graph_id=None,
                    parent_turn_id=parent_id,
                    provider=None,
                    turn_id=tid,
                )
            store.append_turn(turn)
            parent_id = turn.id
        store.update_session_head(
            args.session, graph_id=graph.id, turn_id=assistant_turn_id
        )
    else:
        existing = list(store.iter_turns(args.session))
        seq = len(existing)
        parent_id = existing[-1].id if existing else None
        turn = _make_turn(
            session_id=args.session,
            seq=seq,
            role="assistant",
            prose=graph.prose,
            created_at=now,
            graph_id=graph.id,
            parent_turn_id=parent_id,
            provider=model.provider,
            turn_id=assistant_turn_id,
        )
        store.append_turn(turn)
        store.update_session_head(
            args.session, graph_id=graph.id, turn_id=assistant_turn_id
        )

    print(graph.id)
    return EXIT_OK


def _node_line(node, indent: str = "    ") -> str:
    text = " ".join(node.text.split())
    kind = "judgment_call" if node.kind == "taste_call" else node.kind
    return (
        f"{indent}{kind:<20} {node.id} {node.status:<9} {text}"
    )


def _graph_nodes_tree(graph: ThoughtGraph, node_id: str | None) -> list[str]:
    lines = []
    for node in graph.nodes:
        if node_id and node.id != node_id:
            continue
        lines.append(_node_line(node))
    return lines


def cmd_show(args: argparse.Namespace) -> int:
    store = _store(args)
    ident = args.id
    is_session = store.session_exists(ident)
    is_graph = store.graph_exists(ident)
    if is_session and is_graph:
        print("ID matches both a session and a graph", file=sys.stderr)
        return EXIT_USAGE
    if not is_session and not is_graph:
        print(f"not found: {ident}", file=sys.stderr)
        return EXIT_IO

    if is_session:
        session = store.load_session(ident)
        turns = list(store.iter_turns(ident))
        graphs = {g.id: g for g in store.iter_graphs(ident)}
        head_graph_id = session.head_graph_id
        if head_graph_id is None:
            for t in reversed(turns):
                if t.graph_id:
                    head_graph_id = t.graph_id
                    break
        if args.format == "json":
            payload = {
                "session": session.to_dict(),
                "turns": [t.to_dict() for t in turns],
            }
            if head_graph_id and head_graph_id in graphs:
                payload["head_graph"] = graphs[head_graph_id].to_dict()
            json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
            return EXIT_OK
        if args.format == "ids":
            print(f"session {session.id}")
            if session.head_graph_id:
                print(f"head_graph {session.head_graph_id}")
            if session.head_turn_id:
                print(f"head_turn {session.head_turn_id}")
            for t in turns:
                print(f"turn {t.id} seq={t.seq} role={t.role} graph_id={t.graph_id or ''}")
            if head_graph_id and head_graph_id in graphs:
                for n in graphs[head_graph_id].nodes:
                    if args.node and n.id != args.node:
                        continue
                    kind = "judgment_call" if n.kind == "taste_call" else n.kind
                    print(f"node {n.id} {kind}")
            return EXIT_OK
        label = session.origin or session.title
        print(
            f"session {session.id}  {label}  head_graph={head_graph_id or 'none'}"
        )
        for t in turns:
            gpart = f"graph {t.graph_id}" if t.graph_id else "no graph"
            print(f"  turn {t.seq}  {t.role:<12} {gpart}")
            if t.graph_id and t.graph_id in graphs:
                for line in _graph_nodes_tree(graphs[t.graph_id], args.node):
                    print(line)
        return EXIT_OK

    graph = store.load_graph(ident)
    if args.format == "json":
        json.dump(graph.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return EXIT_OK
    if args.format == "ids":
        print(f"graph {graph.id}")
        print(f"session {graph.session_id}")
        print(f"turn {graph.turn_id}")
        for n in graph.nodes:
            if args.node and n.id != args.node:
                continue
            kind = "judgment_call" if n.kind == "taste_call" else n.kind
            print(f"node {n.id} {kind}")
        return EXIT_OK
    print(f"graph {graph.id}  session={graph.session_id}  (story graph, not a circuit trace)")
    for line in _graph_nodes_tree(graph, args.node):
        print(line)
    return EXIT_OK


def cmd_validate(args: argparse.Namespace) -> int:
    target = args.target
    path = Path(target).expanduser()
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(exc, file=sys.stderr)
            return EXIT_IO if isinstance(exc, OSError) else EXIT_VALIDATION
        try:
            if isinstance(raw, dict) and "seq" in raw and "role" in raw and "prose" in raw:
                validate_schema("turn.schema.json", raw)
            elif isinstance(raw, dict) and "title" in raw and "updated_at" in raw:
                validate_schema("session.schema.json", raw)
            else:
                validate_graph(raw)
        except ValidationError as exc:
            for msg in exc.messages:
                print(msg, file=sys.stderr)
            return EXIT_VALIDATION
        return EXIT_OK

    store = _store(args)
    if store.session_exists(target):
        errors = store.validate_session(target)
        if errors:
            for msg in errors:
                print(msg, file=sys.stderr)
            return EXIT_VALIDATION
        return EXIT_OK
    if store.graph_exists(target):
        try:
            graph = store.load_graph(target)
            validate_graph(graph)
        except (StoreError, ValidationError) as exc:
            print(exc, file=sys.stderr)
            return EXIT_VALIDATION if isinstance(exc, ValidationError) else EXIT_IO
        return EXIT_OK
    print(f"not found: {target}", file=sys.stderr)
    return EXIT_IO


def cmd_log(args: argparse.Namespace) -> int:
    store = _store(args)
    turns = list(store.iter_turns(args.session))
    print(f"{'seq':<5} {'role':<12} {'graph_id':<26} {'fork_of'}")
    for t in turns:
        print(
            f"{t.seq:<5} {t.role:<12} {t.graph_id or '-':<26} {t.fork_of_node_id or '-'}"
        )
    return EXIT_OK


def cmd_prompt(args: argparse.Namespace) -> int:
    sys.stdout.write(read_prompt(args.name))
    if not read_prompt(args.name).endswith("\n"):
        sys.stdout.write("\n")
    return EXIT_OK


def cmd_inhabit(args: argparse.Namespace) -> int:
    store = _store(args)
    view = inhabit(
        store,
        args.node,
        graph_id=args.graph,
        session_id=args.session,
    )
    sys.stdout.write(format_inhabit(view))
    return EXIT_OK


def cmd_fork(args: argparse.Namespace) -> int:
    store = _store(args)
    graph, node = resolve_standing(
        store,
        args.node,
        graph_id=args.graph,
        session_id=args.session,
    )
    model_name = args.model_name or graph.model.name or "unknown"
    regen_text: str | None = None

    if args.from_graph:
        regen_text = _read_path(args.from_graph)
        model = ModelInfo(
            provider="file",
            name=model_name,
            compile_mode=detect_regen_compile_mode(regen_text),
        )
    elif args.provider != "none":
        provider = build_provider(
            args.provider,
            provider_file=args.provider_file,
            provider_cmd=args.provider_cmd,
        )
        user = fork_regen_prompt(graph, node, reason=args.reason, now=now_iso())
        regen_text = provider.complete(user, system=read_prompt("fork"))
        model = ModelInfo(
            provider=args.provider,
            name=model_name,
            compile_mode="structured_emit",
        )
    else:
        model = ModelInfo(
            provider="none",
            name=model_name,
            compile_mode=graph.model.compile_mode,
        )

    plan = plan_fork(
        store,
        args.node,
        session_id=args.session,
        graph_id=args.graph,
        reason=args.reason,
        model=model,
        regen_text=regen_text,
    )
    _emit_warnings(plan.warnings, quiet=args.quiet)
    if args.strict and plan.warnings:
        return EXIT_VALIDATION
    commit(store, plan)
    print(plan.g1.id)
    return EXIT_OK


def cmd_veto(args: argparse.Namespace) -> int:
    store = _store(args)
    plan = plan_veto(
        store,
        args.node,
        session_id=args.session,
        graph_id=args.graph,
        reason=args.reason,
    )
    _emit_warnings(plan.warnings, quiet=args.quiet)
    if args.strict and plan.warnings:
        return EXIT_VALIDATION
    commit(store, plan)
    print(plan.g1.id)
    return EXIT_OK


def _emit_json_out(payload: dict, out: str | None) -> None:
    if not out:
        return
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if out == "-":
        sys.stdout.write(text)
        return
    dest = Path(out).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


def _load_probe_spec(path: str) -> ProbeSpec:
    raw = json.loads(_read_path(path))
    if not isinstance(raw, dict):
        raise ValidationError(["probe spec JSON must be an object"])
    validate_schema("probe.schema.json", raw)
    return ProbeSpec.from_dict(raw)


def cmd_probe(args: argparse.Namespace) -> int:
    if args.probe_cmd == "plan":
        return _cmd_probe_plan(args)
    if args.probe_cmd == "run":
        return _cmd_probe_run(args)
    if args.probe_cmd == "diff":
        return _cmd_probe_diff(args)
    raise UsageError("unknown probe command")


def cmd_evidence(args: argparse.Namespace) -> int:
    if args.evidence_cmd != "context":
        raise UsageError("unknown evidence command")
    store = _store(args)
    graph = store.load_graph(args.graph)
    node = next((n for n in graph.nodes if n.id == args.node), None)
    if node is None:
        raise StoreError(f"node {args.node} not in graph {graph.id}")
    context_turn = store.load_turn(graph.session_id, args.turn)
    lineage = store.turn_lineage(graph.session_id, graph.turn_id)
    context_ids = {turn.id for turn in lineage[:-1]}
    if context_turn.id not in context_ids:
        raise StoreError(
            f"turn {context_turn.id} is not preceding context in graph {graph.id} lineage"
        )
    if args.parent_evidence:
        store.load_evidence(graph.session_id, args.parent_evidence)
    binding = context_provenance_binding(
        graph,
        node,
        context_turn,
        parent_evidence_id=args.parent_evidence,
    )
    path = store.write_evidence(graph.session_id, binding.to_dict())
    store.log(
        "evidence_context",
        session_id=graph.session_id,
        graph_id=graph.id,
        path=str(path),
        warnings=["context provenance is chronological, not causal"],
    )
    print(binding.id)
    return EXIT_OK


def _cmd_probe_plan(args: argparse.Namespace) -> int:
    store = _store(args)
    graph = store.load_graph(args.graph)
    params: dict[str, str] = {}
    if args.kind == "edit_context":
        if not args.turn or args.old is None or args.new is None:
            raise UsageError("edit_context requires --turn, --old, and --new")
        lineage = store.turn_lineage(graph.session_id, graph.turn_id)
        context = next((turn for turn in lineage[:-1] if turn.id == args.turn), None)
        if context is None:
            raise StoreError(
                f"turn {args.turn} is not preceding context in graph {graph.id} lineage"
            )
        if not args.old or context.prose.count(args.old) != 1:
            raise UsageError("--old must occur exactly once in the context turn")
        params = {"turn_id": args.turn, "old": args.old, "new": args.new}
    spec = make_plan(graph, kind=args.kind, node_id=args.node, params=params)
    validate_schema("probe.schema.json", spec.to_dict())
    path = store.write_probe(graph.session_id, spec.to_dict())
    store.log(
        "probe_plan",
        session_id=graph.session_id,
        graph_id=graph.id,
        path=str(path),
        warnings=[],
    )
    _emit_json_out(spec.to_dict(), args.out)
    if args.out != "-":
        print(spec.id)
    return EXIT_OK


def _cmd_probe_run(args: argparse.Namespace) -> int:
    spec = _load_probe_spec(args.spec)
    store = _store(args)
    graph = store.load_graph(spec.target_graph_id)
    if args.parent_evidence:
        store.load_evidence(graph.session_id, args.parent_evidence)
    harness = ProbeHarness()
    harness.plan(graph, spec)
    provider = build_provider("shell", provider_cmd=args.provider_cmd)
    try:
        if spec.kind == "edit_context":
            lineage = store.turn_lineage(graph.session_id, graph.turn_id)
            child = harness.run_context(graph, spec, provider, lineage[:-1])
        else:
            child = harness.run(graph, spec, provider)
    except NotImplementedError as exc:
        print(exc, file=sys.stderr)
        return EXIT_NOT_IMPLEMENTED
    validate_graph(child)
    graph_path = store.write_graph(child)
    append_op_turn(
        store,
        session_id=child.session_id,
        turn_id=child.turn_id,
        now=child.created_at,
        role="assistant",
        prose=child.prose,
        graph_id=child.id,
        fork_of_node_id=spec.target_node_id,
        provider="shell",
        parent_turn_id=graph.turn_id if spec.kind == "edit_context" else None,
    )
    diff = diff_graphs(graph, child, spec=spec)
    diff_path = store.write_graph_diff(graph.session_id, diff.to_dict())
    evidence = evidence_from_probe(
        graph,
        child,
        spec,
        diff,
        parent_evidence_id=args.parent_evidence,
        created_at=child.created_at,
    )
    for binding in evidence:
        store.write_evidence(graph.session_id, binding.to_dict())
    store.log(
        "probe_run",
        session_id=graph.session_id,
        graph_id=child.id,
        path=str(graph_path),
        warnings=[diff.notes] if diff.notes else [],
    )
    if diff.notes:
        print(diff.notes, file=sys.stderr)
    print(f"graph {child.id}")
    print(f"diff {diff.id}")
    for binding in evidence:
        print(f"evidence {binding.id}")
    return EXIT_OK


def _cmd_probe_diff(args: argparse.Namespace) -> int:
    store = _store(args)
    a = store.load_graph(args.a)
    b = store.load_graph(args.b)
    spec = _load_probe_spec(args.spec) if args.spec else None
    diff = diff_graphs(a, b, spec=spec)
    validate_schema("graph-diff.schema.json", diff.to_dict())
    path = store.write_graph_diff(a.session_id, diff.to_dict())
    store.log(
        "probe_diff",
        session_id=a.session_id,
        graph_id=a.id,
        path=str(path),
        warnings=[],
    )
    if diff.notes == STORY_FALSIFIED:
        print(STORY_FALSIFIED, file=sys.stderr)
    _emit_json_out(diff.to_dict(), args.out)
    if args.out != "-":
        print(diff.id)
    return EXIT_OK


def _persist_attribution(args: argparse.Namespace, attr) -> None:
    if attr.provenance is None:
        raise UsageError("storing an attribution requires provenance")
    store = _store(args)
    graph = store.load_graph(args.graph)
    if graph.session_id != (args.session or graph.session_id):
        raise UsageError(f"graph {graph.id} is not in session {args.session}")
    if args.parent_evidence is not None:
        store.load_evidence(graph.session_id, args.parent_evidence)
    path = store.write_attribution(graph.session_id, attr.to_dict())
    from thought_archaeology.evidence import EvidenceBinding

    binding = EvidenceBinding(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        graph_id=attr.graph_id,
        node_id=attr.node_id,
        kind="activation_correlation",
        result="inconclusive",
        summary=(
            "Measured attribution features were associated with this output span; "
            "correlation does not establish that the thought-object caused, or was "
            "caused by, those features."
        ),
        artifact_refs=(
            f"attribution:{attr.id}",
            attr.provenance.source_uri,
            f"sha256:{attr.provenance.source_sha256}",
        ),
        created_at=now_iso(),
        parent_evidence_id=args.parent_evidence,
    )
    store.write_evidence(graph.session_id, binding.to_dict())
    store.log(
        "sensor_attach",
        session_id=graph.session_id,
        graph_id=graph.id,
        node_id=attr.node_id,
        attribution_id=attr.id,
        evidence_id=binding.id,
        path=str(path),
        warnings=["activation correlation is not neural causation"],
    )
    print(f"stored attribution {attr.id}  evidence {binding.id}")


def cmd_sensor(args: argparse.Namespace) -> int:
    if args.sensor_cmd == "synthesize-recurrence":
        from thought_archaeology.evidence import EvidenceBinding

        if args.minimum_contexts < 3:
            raise UsageError("recurring circuits require --minimum-contexts >= 3")
        store = _store(args)
        records = []
        identities = set()
        prompts = set()
        for evidence_id in args.neural_evidence:
            session_id, evidence = store.find_evidence(evidence_id)
            if evidence["kind"] != "neural_intervention":
                raise UsageError(f"evidence {evidence_id} is not neural_intervention")
            intervention_ref = next(
                (ref for ref in evidence["artifact_refs"] if ref.startswith("neural-intervention:")),
                None,
            )
            if intervention_ref is None:
                raise UsageError(f"evidence {evidence_id} lacks neural-intervention artifact")
            intervention_id = intervention_ref.split(":", 1)[1]
            intervention = store.load_neural_intervention(session_id, intervention_id)
            attribution = store.load_attribution(session_id, intervention["attribution_id"])
            parent_id = evidence.get("parent_evidence_id")
            if parent_id is None:
                raise UsageError(f"evidence {evidence_id} has no activation parent")
            parent = store.load_evidence(session_id, parent_id)
            if parent["kind"] != "activation_correlation":
                raise UsageError(f"evidence {evidence_id} parent is not activation_correlation")
            identity = (
                intervention["execution"]["model"],
                intervention["edit"]["layer"],
                intervention["edit"]["feature_index"],
            )
            feature_prefix = f"{identity[1]}_{identity[2]}_"
            feature_ids = {
                feature_id
                for supernode in attribution["supernodes"]
                for feature_id in supernode.get("feature_ids", [])
            }
            if not any(feature_id.startswith(feature_prefix) for feature_id in feature_ids):
                raise UsageError(f"context {evidence_id} attribution lacks exact feature")
            identities.add(identity)
            prompts.add(intervention["prompt"])
            records.append({
                "session_id": session_id,
                "graph_id": evidence["graph_id"],
                "node_id": evidence["node_id"],
                "prompt": intervention["prompt"],
                "target": intervention["target"],
                "attribution_id": intervention["attribution_id"],
                "activation_evidence_id": parent_id,
                "intervention_id": intervention_id,
                "neural_evidence_id": evidence_id,
                "result": evidence["result"],
            })
        if len(identities) != 1:
            raise UsageError("recurrence requires one exact model/layer/feature identity")
        if len(prompts) < args.minimum_contexts:
            raise UsageError(
                f"recurrence requires {args.minimum_contexts} distinct prompts; got {len(prompts)}"
            )
        if len(records) != len({record["neural_evidence_id"] for record in records}):
            raise UsageError("duplicate neural evidence does not establish recurrence")
        counts = {
            result: sum(record["result"] == result for record in records)
            for result in ("supports", "contradicts", "inconclusive")
        }
        if counts["supports"] == len(records):
            result = "supports"
        elif counts["contradicts"] == len(records):
            result = "contradicts"
        else:
            result = "inconclusive"
        model, layer, feature_index = next(iter(identities))
        circuit = {
            "schema_version": SCHEMA_VERSION,
            "id": new_ulid(),
            "model": model,
            "identity_rule": "exact_model_layer_feature",
            "feature": {"layer": layer, "feature_index": feature_index},
            "minimum_contexts": args.minimum_contexts,
            "contexts": records,
            "supporting_count": counts["supports"],
            "contradicting_count": counts["contradicts"],
            "inconclusive_count": counts["inconclusive"],
            "result": result,
            "created_at": now_iso(),
        }
        path = store.write_recurring_circuit(circuit)
        binding_ids = []
        for record in records:
            binding = EvidenceBinding(
                schema_version=SCHEMA_VERSION, id=new_ulid(),
                graph_id=record["graph_id"], node_id=record["node_id"],
                kind="recurring_circuit", result=result,
                summary=(
                    f"Exact feature {layer}:{feature_index} was naturally observed and "
                    f"causally tested across {len(records)} distinct prompts; "
                    f"{counts['supports']} supported, {counts['contradicts']} contradicted, "
                    f"and {counts['inconclusive']} were inconclusive."
                ),
                artifact_refs=(
                    f"recurring-circuit:{circuit['id']}",
                    *(f"neural-evidence:{item['neural_evidence_id']}" for item in records),
                ),
                created_at=now_iso(),
                parent_evidence_id=record["neural_evidence_id"],
            )
            store.write_evidence(record["session_id"], binding.to_dict())
            binding_ids.append(binding.id)
        store.log(
            "sensor_recurring_circuit", circuit_id=circuit["id"], path=str(path),
            evidence_ids=binding_ids,
            warnings=["recurrence is exact-feature local evidence, not semantic identity"],
        )
        print(
            f"stored recurring circuit {circuit['id']}  result {result}  evidence "
            + " ".join(binding_ids)
        )
        return EXIT_OK
    if args.sensor_cmd == "import-activation":
        from thought_archaeology.depth3 import import_neuronpedia_activation

        store = _store(args)
        graph = store.load_graph(args.graph)
        node = next((node for node in graph.nodes if node.id == args.node), None)
        if node is None:
            raise StoreError(f"node {args.node} not in graph {graph.id}")
        if node.text != args.target:
            raise UsageError("activation target must equal the bound thought text")
        attr = import_neuronpedia_activation(
            Path(args.request), Path(args.from_response),
            graph_id=graph.id, node_id=node.id, graph_position=args.graph_position,
            target=args.target, attribution_id=args.attribution_id,
        )
        store.write_sensor_source(
            graph.session_id, attr.provenance.source_sha256,
            Path(args.from_response).read_bytes(),
        )
        store.write_sensor_source(
            graph.session_id, attr.provenance.request_sha256,
            Path(args.request).read_bytes(),
        )
        sys.stdout.write(format_attribution(attr))
        _persist_attribution(args, attr)
        return EXIT_OK
    if args.sensor_cmd == "record-intervention":
        from thought_archaeology.depth3 import (
            import_intervention_result,
            import_neuronpedia_result,
        )
        from thought_archaeology.evidence import EvidenceBinding

        store = _store(args)
        graph = store.load_graph(args.graph)
        if args.session is not None and graph.session_id != args.session:
            raise UsageError(f"graph {graph.id} is not in session {args.session}")
        node = next((node for node in graph.nodes if node.id == args.node), None)
        if node is None:
            raise StoreError(f"node {args.node} not in graph {graph.id}")
        parent = store.load_evidence(graph.session_id, args.parent_evidence)
        if parent["kind"] != "activation_correlation":
            raise UsageError("neural intervention parent must be activation_correlation evidence")
        if (parent["graph_id"], parent["node_id"]) != (graph.id, node.id):
            raise UsageError("neural intervention parent is bound to another thought")
        if (args.neuronpedia_request is None) != (args.manifest is None):
            raise UsageError("Neuronpedia recording requires both --neuronpedia-request and --manifest")
        if args.neuronpedia_request is not None:
            artifact = import_neuronpedia_result(
                Path(args.neuronpedia_request), Path(args.from_result), Path(args.manifest),
                graph_id=graph.id, node_id=node.id, source_uri=args.source_uri,
            )
        else:
            artifact = import_intervention_result(
                Path(args.from_result), graph_id=graph.id, node_id=node.id,
                source_uri=args.source_uri,
            )
        if f"attribution:{artifact.attribution_id}" not in parent["artifact_refs"]:
            raise UsageError("intervention attribution is not the parent's attribution")
        attribution = store.load_attribution(graph.session_id, artifact.attribution_id)
        provenance = attribution["provenance"]
        if artifact.execution["model"] != provenance["model"]:
            raise UsageError("intervention model does not match attribution model")
        attribution_prompt = str(provenance.get("prompt") or "")
        normalized_attribution_prompt = (
            attribution_prompt.removeprefix("<bos>")
        )
        if artifact.prompt != normalized_attribution_prompt:
            raise UsageError("intervention prompt does not match attribution prompt")
        provenance_target = str(provenance.get("target") or "")
        if artifact.target.strip() not in provenance_target:
            raise UsageError("intervention target does not match attribution target")
        edit_node_id = (
            f"{artifact.edit['layer']}_{artifact.edit['feature_index']}_"
            f"{artifact.edit['position']}"
        )
        attributed_features = {
            feature_id
            for supernode in attribution["supernodes"]
            for feature_id in supernode.get("feature_ids", [])
        }
        if edit_node_id not in attributed_features:
            raise UsageError(
                f"intervened feature {edit_node_id} is absent from the attribution"
            )
        raw_source = Path(args.from_result).read_bytes()
        store.write_sensor_source(
            graph.session_id, artifact.execution["source_sha256"], raw_source
        )
        for arg_name, digest_name in (
            ("neuronpedia_request", "request_sha256"),
            ("manifest", "manifest_sha256"),
        ):
            source_path = getattr(args, arg_name)
            digest = artifact.execution.get(digest_name)
            if source_path is not None and digest is not None:
                store.write_sensor_source(
                    graph.session_id, digest, Path(source_path).read_bytes()
                )
        path = store.write_neural_intervention(graph.session_id, artifact.to_dict())
        binding = EvidenceBinding(
            schema_version=SCHEMA_VERSION,
            id=new_ulid(),
            graph_id=graph.id,
            node_id=node.id,
            kind="neural_intervention",
            result=artifact.result,
            summary=(
                f"Feature {artifact.edit['feature_index']} at layer "
                f"{artifact.edit['layer']}, position {artifact.edit['position']} received "
                f"a measured {artifact.edit['operation']} intervention; "
                f"{artifact.hypothesis['metric']} changed by {artifact.observed_delta:+.6g}."
            ),
            artifact_refs=(
                f"neural-intervention:{artifact.id}",
                f"attribution:{artifact.attribution_id}",
                artifact.execution["source_uri"],
                f"sha256:{artifact.execution['source_sha256']}",
                *(
                    [f"request-sha256:{artifact.execution['request_sha256']}"]
                    if artifact.execution.get("request_sha256") else []
                ),
                *(
                    [f"manifest-sha256:{artifact.execution['manifest_sha256']}"]
                    if artifact.execution.get("manifest_sha256") else []
                ),
            ),
            created_at=now_iso(),
            parent_evidence_id=args.parent_evidence,
        )
        store.write_evidence(graph.session_id, binding.to_dict())
        store.log(
            "sensor_neural_intervention",
            session_id=graph.session_id,
            graph_id=graph.id,
            node_id=node.id,
            intervention_id=artifact.id,
            evidence_id=binding.id,
            path=str(path),
            warnings=["local causal effect under recorded intervention conditions"],
        )
        print(
            f"stored neural intervention {artifact.id}  evidence {binding.id}  "
            f"result {binding.result}"
        )
        return EXIT_OK
    if args.sensor_cmd == "import-circuit-tracer":
        from thought_archaeology.depth3 import import_circuit_tracer_graph

        store = _store(args)
        graph = store.load_graph(args.graph)
        node = next((node for node in graph.nodes if node.id == args.node), None)
        if node is None:
            raise StoreError(f"node {args.node} not in graph {graph.id}")
        attr = import_circuit_tracer_graph(
            Path(args.from_graph),
            graph_id=graph.id,
            node_id=node.id,
            span=Span(0, len(node.text), "char"),
            source_uri=args.source_uri,
            producer_revision=args.producer_revision,
        )
        store.write_sensor_source(
            graph.session_id,
            attr.provenance.source_sha256,
            Path(args.from_graph).read_bytes(),
        )
        sys.stdout.write(format_attribution(attr))
        _persist_attribution(args, attr)
        return EXIT_OK
    if args.sensor_cmd != "attach":
        raise UsageError("unknown sensor command")
    # A supplied attribution can be viewed without a store. With an explicit
    # graph and node it becomes a write-once activation-correlation binding.
    if args.from_attribution:
        raw = json.loads(_read_path(args.from_attribution))
        from thought_archaeology.depth3 import Attribution

        attr = Attribution.from_dict(raw)
        try:
            sys.stdout.write(format_attribution(attr))
        except DisplayRefused as exc:
            print(exc, file=sys.stderr)
            return EXIT_VALIDATION
        if args.graph is not None or args.node is not None:
            if args.graph is None or args.node is None:
                raise UsageError("storing an attribution requires NODE and --graph")
            if attr.graph_id != args.graph or attr.node_id != args.node:
                raise UsageError("attribution graph_id/node_id do not match NODE and --graph")
            _persist_attribution(args, attr)
        return EXIT_OK

    if not args.node:
        raise UsageError("sensor attach requires NODE")
    store = _store(args)
    graph, node = resolve_standing(
        store,
        args.node,
        graph_id=args.graph,
        session_id=args.session,
    )
    try:
        NullSensor().attach(graph, node.id)
    except NotImplementedError as exc:
        print(exc, file=sys.stderr)
        return EXIT_NOT_IMPLEMENTED
    raise RuntimeError("NullSensor.attach must raise NotImplementedError")


def cmd_fingerprint(args: argparse.Namespace) -> int:
    if args.min_sessions < 1:
        raise UsageError("--min-sessions must be >= 1")
    store = _store(args)
    t0 = time.perf_counter()
    if args.session:
        session_ids = list(dict.fromkeys(args.session))
        for sid in session_ids:
            store.load_session(sid)
        graphs = []
        for sid in session_ids:
            graphs.extend(store.iter_graphs(sid))
    else:
        session_ids = list(store.iter_session_ids())
        graphs = list(store.iter_graphs())

    fp = fingerprint(
        graphs,
        session_ids=session_ids,
        min_sessions=args.min_sessions,
    )
    validate_schema("fingerprint.schema.json", fp.to_dict())
    path = store.write_fingerprint(fp.to_dict())
    if args.out:
        out_path = Path(args.out).expanduser()
        if str(args.out) == "-":
            json.dump(fp.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
        else:
            out_path.write_text(
                json.dumps(fp.to_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
    store.log(
        "fingerprint",
        session_id=session_ids[0] if session_ids else None,
        graph_id=None,
        path=str(path),
        duration_ms=round((time.perf_counter() - t0) * 1000, 3),
        warnings=[],
    )
    if str(args.out) != "-":
        print(fp.id)
    return EXIT_OK


def cmd_provenance(args: argparse.Namespace) -> int:
    if args.provenance_cmd != "checkpoint":
        raise UsageError("unknown provenance command")
    from thought_archaeology.evidence import EvidenceBinding
    from thought_archaeology.training import build_checkpoint_emergence

    store = _store(args)
    graph = store.load_graph(args.graph)
    if args.session is not None and graph.session_id != args.session:
        raise UsageError(f"graph {graph.id} is not in session {args.session}")
    node = next((node for node in graph.nodes if node.id == args.node), None)
    if node is None:
        raise StoreError(f"node {args.node} not in graph {graph.id}")
    if args.parent_evidence is not None:
        store.load_evidence(graph.session_id, args.parent_evidence)
    paths = {
        "measurements": Path(args.measurements),
        "checkpoint_map": Path(args.checkpoint_map),
        "model_card": Path(args.model_card),
        "training_docs": Path(args.training_docs),
    }
    artifact = build_checkpoint_emergence(
        paths["measurements"], paths["checkpoint_map"], paths["model_card"],
        paths["training_docs"], graph_id=graph.id, node_id=node.id,
        corpus_name=args.corpus, model_card_uri=args.model_card_uri,
        training_docs_uri=args.training_docs_uri,
    )
    if node.text != (
        f"Across {artifact['model']} training, target {artifact['target']!r} improved "
        f"from rank {artifact['observed']['initial_rank']:,} to "
        f"{artifact['observed']['final_rank']:,}, but final generation did not emit it."
    ):
        raise UsageError("thought text must exactly state the bounded checkpoint observation")
    source_paths = {
        "model_card": paths["model_card"],
        "training_documentation": paths["training_docs"],
        "checkpoint_measurements": paths["measurements"],
        "checkpoint_map": paths["checkpoint_map"],
    }
    for source in artifact["sources"]:
        path = source_paths[source["role"]]
        store.write_sensor_source(graph.session_id, source["sha256"], path.read_bytes())
    path = store.write_training_provenance(graph.session_id, artifact)
    binding = EvidenceBinding(
        schema_version=SCHEMA_VERSION, id=new_ulid(), graph_id=graph.id,
        node_id=node.id, kind="checkpoint_emergence", result=artifact["result"],
        summary=(
            f"Across {len(artifact['measurements'])} exact checkpoints, target "
            f"{artifact['target']!r} moved from rank "
            f"{artifact['observed']['initial_rank']:,} to "
            f"{artifact['observed']['final_rank']:,}. Final generation still did not "
            "emit the target; record membership, example influence, and weight "
            "attribution were not measured."
        ),
        artifact_refs=(
            f"training-provenance:{artifact['id']}",
            *(f"{source['role']}-sha256:{source['sha256']}" for source in artifact["sources"]),
        ),
        created_at=now_iso(), parent_evidence_id=args.parent_evidence,
    )
    store.write_evidence(graph.session_id, binding.to_dict())
    store.log(
        "provenance_checkpoint", session_id=graph.session_id, graph_id=graph.id,
        node_id=node.id, provenance_id=artifact["id"], evidence_id=binding.id,
        path=str(path),
        warnings=["checkpoint emergence is not training-example or weight attribution"],
    )
    print(f"stored checkpoint provenance {artifact['id']}  evidence {binding.id}")
    return EXIT_OK


def _refuse_wiki_catalog(path: Path) -> None:
    resolved = path.expanduser().resolve()
    if resolved.name in ("index.md", "log.md") and resolved.parent.name == "wiki":
        raise UsageError("ta must not write wiki/index.md or wiki/log.md")


def _load_fingerprint_file(path: str) -> Fingerprint:
    raw = json.loads(_read_path(path))
    if not isinstance(raw, dict):
        raise ValidationError(["fingerprint JSON must be an object"])
    return Fingerprint.from_dict(raw)


def _write_canvas_out(args: argparse.Namespace, *, require_out: bool) -> int:
    store = _store(args)
    t0 = time.perf_counter()
    graph = store.load_graph(args.graph)
    fp = _load_fingerprint_file(args.fingerprint) if args.fingerprint else None
    markdown = render_md(graph, fingerprint=fp)
    store_path = store.write_canvas(graph.session_id, graph.id, markdown)
    dest: Path | None = None
    if args.out:
        if args.out == "-":
            sys.stdout.write(markdown if markdown.endswith("\n") else markdown + "\n")
        else:
            dest = Path(args.out).expanduser()
            _refuse_wiki_catalog(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(
                markdown if markdown.endswith("\n") else markdown + "\n",
                encoding="utf-8",
            )
    elif require_out:
        raise UsageError("export-wiki requires --out PATH")
    store.log(
        "canvas",
        session_id=graph.session_id,
        graph_id=graph.id,
        path=str(dest or store_path),
        duration_ms=round((time.perf_counter() - t0) * 1000, 3),
        warnings=[],
    )
    if args.out == "-":
        return EXIT_OK
    print(str(dest.resolve()) if dest is not None else str(store_path))
    return EXIT_OK


def cmd_canvas(args: argparse.Namespace) -> int:
    return _write_canvas_out(args, require_out=False)


def cmd_export_wiki(args: argparse.Namespace) -> int:
    return _write_canvas_out(args, require_out=True)


def cmd_serve(args: argparse.Namespace) -> int:
    if args.bind not in ("127.0.0.1", "localhost", "::1"):
        raise UsageError("ta serve binds localhost only")
    store = _store(args)
    serve_forever(store, bind=args.bind, port=args.port)
    return EXIT_OK


def cmd_continuation(args: argparse.Namespace) -> int:
    store = _store(args)
    if args.continuation_cmd == "ready":
        graph, node = resolve_standing(store, args.node, graph_id=args.graph)
        request = continuation_request(
            graph, node, prompt=args.prompt, source="cli"
        )
        path = store.write_continuation_request(request)
        store.log(
            "continuation_ready",
            session_id=graph.session_id,
            graph_id=graph.id,
            node_id=node.id,
            request_id=request.id,
            path=str(path),
            warnings=[],
        )
        print(request.id)
        return EXIT_OK
    if args.continuation_cmd == "pending":
        requests = list(store.iter_continuation_requests(pending=True))
        if args.format == "json":
            print(json.dumps([item.to_dict() for item in requests], ensure_ascii=False))
        else:
            print(f"{'request':<26}  {'graph':<26}  {'node':<26}  prompt")
            for item in requests:
                prompt = " ".join(item.prompt.split()) or "(continue from here)"
                print(f"{item.id:<26}  {item.graph_id:<26}  {item.node_id:<26}  {prompt}")
        return EXIT_OK
    if args.continuation_cmd == "cancel":
        cancellation = continuation_cancellation(args.request, source="cli")
        path = store.write_continuation_cancellation(cancellation)
        store.log(
            "continuation_cancel",
            request_id=args.request,
            cancellation_id=cancellation.id,
            path=str(path),
            warnings=[],
        )
        print(cancellation.id)
        return EXIT_OK
    if args.continuation_cmd == "complete":
        completion = continuation_completion(
            args.request, args.graph, args.harness
        )
        path = store.write_continuation_completion(completion)
        store.log(
            "continuation_complete",
            graph_id=args.graph,
            request_id=args.request,
            completion_id=completion.id,
            path=str(path),
            warnings=[],
        )
        print(completion.id)
        return EXIT_OK
    raise UsageError("unknown continuation command")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return EXIT_OK
        return int(code) if isinstance(code, int) else EXIT_USAGE

    handlers = {
        "init": cmd_init,
        "compile": cmd_compile,
        "show": cmd_show,
        "validate": cmd_validate,
        "log": cmd_log,
        "prompt": cmd_prompt,
        "inhabit": cmd_inhabit,
        "fork": cmd_fork,
        "veto": cmd_veto,
        "continuation": cmd_continuation,
        "sensor": cmd_sensor,
        "evidence": cmd_evidence,
        "provenance": cmd_provenance,
        "probe": cmd_probe,
        "fingerprint": cmd_fingerprint,
        "canvas": cmd_canvas,
        "export-wiki": cmd_export_wiki,
        "serve": cmd_serve,
    }
    try:
        return handlers[args.cmd](args)
    except UsageError as exc:
        print(exc, file=sys.stderr)
        return EXIT_USAGE
    except ForkError as exc:
        print(exc, file=sys.stderr)
        return EXIT_IO
    except SensorError as exc:
        print(exc, file=sys.stderr)
        return EXIT_IO
    except ProbeError as exc:
        print(exc, file=sys.stderr)
        return EXIT_IO
    except ServeError as exc:
        print(exc, file=sys.stderr)
        return EXIT_USAGE
    except CompileError as exc:
        print(exc, file=sys.stderr)
        return EXIT_VALIDATION
    except ValidationError as exc:
        for msg in exc.messages:
            print(msg, file=sys.stderr)
        return EXIT_VALIDATION
    except ProviderError as exc:
        print(exc, file=sys.stderr)
        text = str(exc).lower()
        if "required" in text or "none" in text:
            return EXIT_USAGE
        return EXIT_IO
    except StoreError as exc:
        print(exc, file=sys.stderr)
        if "append-only" in str(exc) or "write-once" in str(exc):
            return EXIT_VALIDATION
        return EXIT_IO
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return EXIT_IO
    except OSError as exc:
        print(exc, file=sys.stderr)
        return EXIT_IO
    except json.JSONDecodeError as exc:
        print(exc, file=sys.stderr)
        return EXIT_VALIDATION


if __name__ == "__main__":
    sys.exit(main())
