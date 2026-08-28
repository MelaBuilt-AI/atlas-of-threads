from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

from thought_archaeology.ids import now_iso, new_ulid
from thought_archaeology.models import SCHEMA_VERSION, Session, ThoughtGraph, ThoughtNode, Turn
from thought_archaeology.schema import ValidationError, validate_graph, validate_schema

STORE_VERSION = "1"

FILE_MODE = 0o600
DIR_MODE = 0o700


class StoreError(Exception):
    """Store I/O or immutability violation."""


def fallback_store_path() -> Path:
    """XDG data dir, not a machine-specific absolute path."""
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg).expanduser().resolve() / "thought-archaeology"
    return (Path.home() / ".local" / "share" / "thought-archaeology").resolve()


FALLBACK_STORE = fallback_store_path()  # import-time snapshot; prefer fallback_store_path()


def resolve_store_path(cli_store: str | None = None) -> Path:
    """First hit wins: --store, TA_STORE, ./data if it exists, XDG fallback."""
    if cli_store:
        return Path(cli_store).expanduser().resolve()
    env = os.environ.get("TA_STORE")
    if env:
        return Path(env).expanduser().resolve()
    cwd_data = (Path.cwd() / "data").resolve()
    if cwd_data.is_dir():
        return cwd_data
    return fallback_store_path()


def _chmod_file(path: Path) -> None:
    os.chmod(path, FILE_MODE)


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, DIR_MODE)


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _chmod_file(path)


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    _chmod_file(path)


class Store:
    def __init__(self, root: Path | str):
        self.root = Path(root).expanduser().resolve()

    @property
    def sessions_dir(self) -> Path:
        return self.root / "sessions"

    @property
    def version_path(self) -> Path:
        return self.root / "STORE_VERSION"

    @property
    def log_path(self) -> Path:
        return self.root / "store.log.jsonl"

    def session_dir(self, session_id: str) -> Path:
        return self.sessions_dir / session_id

    def exists(self) -> bool:
        return self.root.is_dir() and self.version_path.is_file()

    def _require(self) -> None:
        if not self.exists():
            raise StoreError(f"store does not exist: {self.root}")
        version = self.version_path.read_text(encoding="utf-8").strip()
        if version != STORE_VERSION:
            raise StoreError(f"unsupported STORE_VERSION {version!r} (want {STORE_VERSION})")

    def _create_root(self) -> None:
        _mkdir(self.root)
        _mkdir(self.sessions_dir)
        _write_text(self.version_path, STORE_VERSION + "\n")
        if not self.log_path.exists():
            _write_text(self.log_path, "")

    def log(self, op: str, **fields: object) -> None:
        line = {
            "ts": now_iso(),
            "op": op,
            **{k: v for k, v in fields.items() if v is not None},
        }
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        _chmod_file(self.log_path)

    def init_session(self, title: str, origin: str | None = None) -> Session:
        t0 = time.perf_counter()
        if not self.exists():
            self._create_root()
        else:
            self._require()
        now = now_iso()
        session = Session(
            schema_version=SCHEMA_VERSION,
            id=new_ulid(),
            title=title,
            created_at=now,
            updated_at=now,
            tags=(),
            origin=origin,
            head_graph_id=None,
            head_turn_id=None,
        )
        sdir = self.session_dir(session.id)
        _mkdir(sdir)
        _mkdir(sdir / "graphs")
        _write_json(sdir / "session.json", session.to_dict())
        turns = sdir / "turns.jsonl"
        _write_text(turns, "")
        self.log(
            "init",
            session_id=session.id,
            path=str(sdir),
            duration_ms=round((time.perf_counter() - t0) * 1000, 3),
            warnings=[],
        )
        return session

    def append_turn(self, turn: Turn) -> None:
        self._require()
        path = self.session_dir(turn.session_id) / "turns.jsonl"
        if not path.is_file():
            raise StoreError(f"session not found: {turn.session_id}")
        existing_seqs = {t.seq for t in self.iter_turns(turn.session_id)}
        if turn.seq in existing_seqs:
            raise StoreError(
                f"turn seq {turn.seq} already exists in session {turn.session_id} "
                "(append-only; do not duplicate)"
            )
        validate_schema("turn.schema.json", turn.to_dict())
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(turn.to_dict(), ensure_ascii=False) + "\n")
        _chmod_file(path)

    def write_graph(self, graph: ThoughtGraph) -> Path:
        self._require()
        validate_graph(graph)
        sdir = self.session_dir(graph.session_id)
        gdir = sdir / "graphs"
        if not sdir.is_dir():
            raise StoreError(f"session not found: {graph.session_id}")
        _mkdir(gdir)
        path = gdir / f"{graph.id}.json"
        if path.exists():
            raise StoreError(f"graph {graph.id} already exists (write-once)")
        _write_json(path, graph.to_dict())
        return path

    def load_graph(self, graph_id: str) -> ThoughtGraph:
        self._require()
        path = self._find_graph_path(graph_id)
        if path is None:
            raise StoreError(f"graph not found: {graph_id}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        validate_graph(raw)
        return ThoughtGraph.from_dict(raw)

    def _find_graph_path(self, graph_id: str) -> Path | None:
        if not self.sessions_dir.is_dir():
            return None
        for sdir in self.sessions_dir.iterdir():
            candidate = sdir / "graphs" / f"{graph_id}.json"
            if candidate.is_file():
                return candidate
        return None

    def session_exists(self, session_id: str) -> bool:
        return (self.session_dir(session_id) / "session.json").is_file()

    def graph_exists(self, graph_id: str) -> bool:
        return self._find_graph_path(graph_id) is not None

    def load_session(self, session_id: str) -> Session:
        self._require()
        path = self.session_dir(session_id) / "session.json"
        if not path.is_file():
            raise StoreError(f"session not found: {session_id}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        validate_schema("session.schema.json", raw)
        return Session.from_dict(raw)

    def iter_turns(self, session_id: str) -> Iterator[Turn]:
        self._require()
        path = self.session_dir(session_id) / "turns.jsonl"
        if not path.is_file():
            raise StoreError(f"session not found: {session_id}")
        text = path.read_text(encoding="utf-8")
        if not text:
            return
            yield  # pragma: no cover  # make this a generator even if empty
        for line in text.splitlines():
            if not line.strip():
                continue
            yield Turn.from_dict(json.loads(line))

    def iter_graphs(self, session_id: str | None = None) -> Iterator[ThoughtGraph]:
        self._require()
        if session_id is not None:
            dirs = [self.session_dir(session_id) / "graphs"]
        else:
            dirs = [
                p / "graphs"
                for p in sorted(self.sessions_dir.iterdir())
                if p.is_dir()
            ]
        for gdir in dirs:
            if not gdir.is_dir():
                continue
            for path in sorted(gdir.glob("*.json")):
                raw = json.loads(path.read_text(encoding="utf-8"))
                yield ThoughtGraph.from_dict(raw)

    @property
    def fingerprints_dir(self) -> Path:
        return self.root / "fingerprints"

    def iter_session_ids(self) -> Iterator[str]:
        self._require()
        if not self.sessions_dir.is_dir():
            return
            yield  # pragma: no cover
        for p in sorted(self.sessions_dir.iterdir()):
            if (p / "session.json").is_file():
                yield p.name

    def canvas_path(self, session_id: str, graph_id: str) -> Path:
        return self.session_dir(session_id) / "canvases" / f"{graph_id}.md"

    def write_canvas(self, session_id: str, graph_id: str, markdown: str) -> Path:
        self._require()
        if not self.session_exists(session_id):
            raise StoreError(f"session not found: {session_id}")
        cdir = self.session_dir(session_id) / "canvases"
        _mkdir(cdir)
        path = self.canvas_path(session_id, graph_id)
        text = markdown if markdown.endswith("\n") else markdown + "\n"
        _write_text(path, text)
        return path

    def write_fingerprint(self, data: dict) -> Path:
        self._require()
        validate_schema("fingerprint.schema.json", data)
        _mkdir(self.fingerprints_dir)
        fid = data["id"]
        path = self.fingerprints_dir / f"{fid}.json"
        if path.exists():
            raise StoreError(f"fingerprint {fid} already exists (write-once)")
        _write_json(path, data)
        return path

    def probes_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "probes"

    def diffs_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "diffs"

    def write_probe(self, session_id: str, data: dict) -> Path:
        """Write-once ProbeSpec JSON next to the session's graphs/."""
        self._require()
        if not self.session_exists(session_id):
            raise StoreError(f"session not found: {session_id}")
        validate_schema("probe.schema.json", data)
        _mkdir(self.probes_dir(session_id))
        pid = data["id"]
        path = self.probes_dir(session_id) / f"{pid}.json"
        if path.exists():
            raise StoreError(f"probe {pid} already exists (write-once)")
        _write_json(path, data)
        return path

    def write_graph_diff(self, session_id: str, data: dict) -> Path:
        self._require()
        if not self.session_exists(session_id):
            raise StoreError(f"session not found: {session_id}")
        validate_schema("graph-diff.schema.json", data)
        _mkdir(self.diffs_dir(session_id))
        did = data["id"]
        path = self.diffs_dir(session_id) / f"{did}.json"
        if path.exists():
            raise StoreError(f"graph-diff {did} already exists (write-once)")
        _write_json(path, data)
        return path

    def iter_fingerprint_ids(self) -> Iterator[str]:
        self._require()
        if not self.fingerprints_dir.is_dir():
            return
            yield  # pragma: no cover
        for path in sorted(self.fingerprints_dir.glob("*.json")):
            yield path.stem

    def latest_fingerprint(self) -> dict | None:
        ids = list(self.iter_fingerprint_ids())
        if not ids:
            return None
        return self.load_fingerprint(ids[-1])

    def load_fingerprint(self, fingerprint_id: str) -> dict:
        self._require()
        path = self.fingerprints_dir / f"{fingerprint_id}.json"
        if not path.is_file():
            raise StoreError(f"fingerprint not found: {fingerprint_id}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        validate_schema("fingerprint.schema.json", raw)
        return raw

    def find_nodes(self, node_id: str) -> list[tuple[ThoughtGraph, ThoughtNode]]:
        found: list[tuple[ThoughtGraph, ThoughtNode]] = []
        for graph in self.iter_graphs():
            for node in graph.nodes:
                if node.id == node_id:
                    found.append((graph, node))
        return found

    def update_session_head(
        self,
        session_id: str,
        *,
        graph_id: str | None,
        turn_id: str,
    ) -> None:
        self._require()
        session = self.load_session(session_id)
        updated = replace(
            session,
            updated_at=now_iso(),
            head_graph_id=graph_id,
            head_turn_id=turn_id,
        )
        path = self.session_dir(session_id) / "session.json"
        _write_json(path, updated.to_dict())

    def validate_session(self, session_id: str) -> list[str]:
        """Referential integrity across session, turns, graphs. Empty = ok."""
        errors: list[str] = []
        try:
            session = self.load_session(session_id)
        except (StoreError, ValidationError, json.JSONDecodeError, OSError) as exc:
            return [str(exc)]

        turns = list(self.iter_turns(session_id))
        graphs = {g.id: g for g in self.iter_graphs(session_id)}
        turn_ids = {t.id: t for t in turns}

        if session.head_graph_id is not None and session.head_graph_id not in graphs:
            errors.append(f"head_graph_id {session.head_graph_id} does not exist")
        if session.head_turn_id is not None and session.head_turn_id not in turn_ids:
            errors.append(f"head_turn_id {session.head_turn_id} does not exist")

        for turn in turns:
            try:
                validate_schema("turn.schema.json", turn.to_dict())
            except ValidationError as exc:
                errors.extend(exc.messages)
            if turn.graph_id is not None and turn.graph_id not in graphs:
                errors.append(f"turn {turn.id} graph_id {turn.graph_id} does not exist")

        # Same node id in two graphs ⇒ identical kind+text.
        by_node: dict[str, tuple[str, str, str]] = {}
        for graph in graphs.values():
            try:
                validate_graph(graph)
            except ValidationError as exc:
                errors.extend(exc.messages)
            if graph.fork is not None:
                if graph.fork.from_graph_id != graph.parent_graph_id:
                    errors.append(
                        f"graph {graph.id} fork.from_graph_id != parent_graph_id"
                    )
                parent_id = graph.parent_graph_id
                if parent_id and parent_id not in graphs:
                    # parent may live in another session; try store-wide
                    try:
                        parent = self.load_graph(parent_id)
                    except StoreError:
                        errors.append(f"graph {graph.id} parent_graph_id {parent_id} missing")
                        parent = None
                else:
                    parent = graphs.get(parent_id) if parent_id else None
                if parent is not None:
                    parent_nids = {n.id for n in parent.nodes}
                    if graph.fork.from_node_id not in parent_nids:
                        errors.append(
                            f"graph {graph.id} fork.from_node_id not in parent graph"
                        )
                if graph.fork.discarded_graph_id is not None:
                    if self._find_graph_path(graph.fork.discarded_graph_id) is None:
                        errors.append(
                            f"graph {graph.id} discarded_graph_id "
                            f"{graph.fork.discarded_graph_id} missing"
                        )
            for node in graph.nodes:
                prev = by_node.get(node.id)
                if prev is None:
                    by_node[node.id] = (graph.id, node.kind, node.text)
                else:
                    _, kind, text = prev
                    if kind != node.kind or text != node.text:
                        errors.append(
                            f"node {node.id} kind+text mismatch across graphs"
                        )
        return errors
