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
from thought_archaeology.fingerprint import DEFAULT_MIN_SESSIONS, Fingerprint, fingerprint
from thought_archaeology.fork import (
    ForkError,
    detect_regen_compile_mode,
    fork_from,
    fork_regen_prompt,
    veto_from,
)
from thought_archaeology.ids import is_ulid, new_ulid, now_iso
from thought_archaeology.inhabit import format_inhabit, inhabit, resolve_standing
from thought_archaeology.models import SCHEMA_VERSION, ModelInfo, ThoughtGraph, Turn
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
    make_plan,
)
from thought_archaeology.providers.none import NoneProvider
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
    p_run = probe_sub.add_parser(
        "run",
        parents=[sub_globals],
        help="run a probe (not implemented; exits 4)",
    )
    p_run.add_argument("--spec", required=True, metavar="PATH")
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
        help="display a stored attribution JSON (refuses uncollapsed dumps)",
    )

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
        help="read-only Inhabit Space on localhost",
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
    return (
        f"{indent}{node.kind:<20} {node.id} {node.status:<9} {text}"
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
                    print(f"node {n.id} {n.kind}")
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
            print(f"node {n.id} {n.kind}")
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


def _append_op_turn(
    store: Store,
    *,
    session_id: str,
    turn_id: str,
    now: str,
    role: str,
    prose: str,
    graph_id: str,
    fork_of_node_id: str,
    provider: str | None,
) -> None:
    existing = list(store.iter_turns(session_id))
    seq = len(existing)
    session = store.load_session(session_id)
    parent_id = session.head_turn_id
    if parent_id is None and existing:
        parent_id = existing[-1].id
    turn = Turn(
        schema_version=SCHEMA_VERSION,
        id=turn_id,
        session_id=session_id,
        seq=seq,
        role=role,  # type: ignore[arg-type]
        created_at=now,
        prose=prose,
        graph_id=graph_id,
        parent_turn_id=parent_id,
        fork_of_node_id=fork_of_node_id,
        provider=provider,  # type: ignore[arg-type]
    )
    store.append_turn(turn)
    store.update_session_head(session_id, graph_id=graph_id, turn_id=turn_id)


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
    t0 = time.perf_counter()
    now = now_iso()
    turn_id = new_ulid()
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
        user = fork_regen_prompt(graph, node, reason=args.reason, now=now)
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

    g1, warnings = fork_from(
        graph,
        node,
        session_id=args.session,
        turn_id=turn_id,
        now=now,
        model=model,
        reason=args.reason,
        regen_text=regen_text,
    )
    _emit_warnings(warnings, quiet=args.quiet)
    if args.strict and warnings:
        return EXIT_VALIDATION

    validate_graph(g1)
    path = store.write_graph(g1)
    role = "assistant" if regen_text else "human_edit"
    provider_name = model.provider if regen_text else None
    _append_op_turn(
        store,
        session_id=args.session,
        turn_id=turn_id,
        now=now,
        role=role,
        prose=g1.prose,
        graph_id=g1.id,
        fork_of_node_id=node.id,
        provider=provider_name,
    )
    store.log(
        "fork",
        session_id=args.session,
        graph_id=g1.id,
        path=str(path),
        duration_ms=round((time.perf_counter() - t0) * 1000, 3),
        warnings=warnings,
    )
    print(g1.id)
    return EXIT_OK


def cmd_veto(args: argparse.Namespace) -> int:
    store = _store(args)
    graph, node = resolve_standing(
        store,
        args.node,
        graph_id=args.graph,
        session_id=args.session,
    )
    t0 = time.perf_counter()
    now = now_iso()
    turn_id = new_ulid()
    g1, warnings = veto_from(
        graph,
        node,
        session_id=args.session,
        turn_id=turn_id,
        now=now,
        reason=args.reason,
    )
    _emit_warnings(warnings, quiet=args.quiet)
    if args.strict and warnings:
        return EXIT_VALIDATION

    validate_graph(g1)
    path = store.write_graph(g1)
    _append_op_turn(
        store,
        session_id=args.session,
        turn_id=turn_id,
        now=now,
        role="human_edit",
        prose=g1.prose,
        graph_id=g1.id,
        fork_of_node_id=node.id,
        provider=None,
    )
    store.log(
        "veto",
        session_id=args.session,
        graph_id=g1.id,
        path=str(path),
        duration_ms=round((time.perf_counter() - t0) * 1000, 3),
        warnings=warnings,
    )
    print(g1.id)
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


def _cmd_probe_plan(args: argparse.Namespace) -> int:
    store = _store(args)
    graph = store.load_graph(args.graph)
    spec = make_plan(graph, kind=args.kind, node_id=args.node)
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
    ProbeHarness().plan(graph, spec)
    try:
        ProbeHarness().run(graph, spec, NoneProvider())
    except NotImplementedError as exc:
        print(exc, file=sys.stderr)
        return EXIT_NOT_IMPLEMENTED
    raise RuntimeError("ProbeHarness.run must raise NotImplementedError")


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


def cmd_sensor(args: argparse.Namespace) -> int:
    if args.sensor_cmd != "attach":
        raise UsageError("unknown sensor command")
    # Display of a stored attribution is bookkeeping (no vendor). Attach to a
    # live node always goes through NullSensor in v1 and exits 4.
    if args.from_attribution:
        raw = json.loads(_read_path(args.from_attribution))
        from thought_archaeology.depth3 import Attribution

        attr = Attribution.from_dict(raw)
        try:
            sys.stdout.write(format_attribution(attr))
        except DisplayRefused as exc:
            print(exc, file=sys.stderr)
            return EXIT_VALIDATION
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
        "sensor": cmd_sensor,
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
