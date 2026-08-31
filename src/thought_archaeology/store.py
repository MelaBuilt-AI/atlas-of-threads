from __future__ import annotations

import json
import hashlib
import os
import time
import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from thought_archaeology.continuation import (
    ContinuationAttempt,
    ContinuationCancellation,
    ContinuationCompletion,
    ContinuationFailure,
    ContinuationRequest,
    ParallelContinuationBatch,
)
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

    def iter_log_entries(self) -> Iterator[dict]:
        self._require()
        if not self.log_path.is_file():
            return
            yield  # pragma: no cover
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield json.loads(line)

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

    def load_turn(self, session_id: str, turn_id: str) -> Turn:
        for turn in self.iter_turns(session_id):
            if turn.id == turn_id:
                return turn
        raise StoreError(f"turn not found: {turn_id}")

    def turn_lineage(self, session_id: str, turn_id: str) -> tuple[Turn, ...]:
        """Return parent-linked turns from the root through `turn_id`."""
        turns = {turn.id: turn for turn in self.iter_turns(session_id)}
        newest_first: list[Turn] = []
        seen: set[str] = set()
        current_id: str | None = turn_id
        while current_id is not None:
            if current_id in seen:
                raise StoreError(f"turn parent cycle at {current_id}")
            seen.add(current_id)
            current = turns.get(current_id)
            if current is None:
                raise StoreError(f"turn not found: {current_id}")
            newest_first.append(current)
            current_id = current.parent_turn_id
        return tuple(reversed(newest_first))

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

    @property
    def recurring_circuits_dir(self) -> Path:
        return self.root / "recurring-circuits"

    @property
    def continuation_requests_dir(self) -> Path:
        return self.root / "continuations" / "requests"

    @property
    def continuation_completions_dir(self) -> Path:
        return self.root / "continuations" / "completions"

    @property
    def continuation_attempts_dir(self) -> Path:
        return self.root / "continuations" / "attempts"

    @property
    def continuation_cancellations_dir(self) -> Path:
        return self.root / "continuations" / "cancellations"

    @property
    def continuation_failures_dir(self) -> Path:
        return self.root / "continuations" / "failures"

    @property
    def parallel_batches_dir(self) -> Path:
        return self.root / "continuations" / "parallel-batches"

    @property
    def continuation_lock_path(self) -> Path:
        return self.root / "continuations" / "inbox.lock"

    @contextmanager
    def continuation_inbox_lock(self, *, timeout: float = 5):
        """Bounded inter-process lock shared by batch creation and dequeue."""
        self._require()
        _mkdir(self.root / "continuations")
        fd = os.open(self.continuation_lock_path, os.O_CREAT | os.O_RDWR, FILE_MODE)
        started = time.monotonic()
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() - started >= timeout:
                        raise StoreError("continuation inbox is busy")
                    time.sleep(0.05)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def write_continuation_request(self, request: ContinuationRequest) -> Path:
        self._require()
        graph = self.load_graph(request.graph_id)
        if graph.session_id != request.session_id:
            raise StoreError(f"graph {graph.id} is not in session {request.session_id}")
        if request.node_id not in {node.id for node in graph.nodes}:
            raise StoreError(f"node {request.node_id} not in graph {graph.id}")
        validate_schema("continuation-request.schema.json", request.to_dict())
        _mkdir(self.continuation_requests_dir)
        path = self.continuation_requests_dir / f"{request.id}.json"
        if path.exists():
            raise StoreError(f"continuation request {request.id} already exists (write-once)")
        _write_json(path, request.to_dict())
        return path

    def write_parallel_batch(
        self,
        batch: ParallelContinuationBatch,
        requests: tuple[ContinuationRequest, ...],
    ) -> Path:
        """Publish a complete batch while the worker is excluded from dequeue."""
        self._require()
        graph = self.load_graph(batch.graph_id)
        node_ids = {node.id for node in graph.nodes}
        if graph.session_id != batch.session_id or batch.node_id not in node_ids:
            raise StoreError("parallel batch source does not match its graph")
        validate_schema("parallel-continuation-batch.schema.json", batch.to_dict())
        jobs = sorted(batch.jobs, key=lambda item: item.position)
        if [job.position for job in jobs] != list(range(len(jobs))):
            raise StoreError("parallel batch job positions must be contiguous")
        if len({job.harness for job in jobs}) != len(jobs):
            raise StoreError("parallel batch harnesses must be unique")
        by_id = {request.id: request for request in requests}
        if set(by_id) != {job.request_id for job in jobs}:
            raise StoreError("parallel batch jobs and requests do not match")
        for job in jobs:
            request = by_id[job.request_id]
            if (
                request.session_id != batch.session_id
                or request.graph_id != batch.graph_id
                or request.node_id != batch.node_id
                or request.prompt != batch.prompt
                or request.source != batch.source
                or request.parallel_batch_id != batch.id
                or request.requested_harness != job.harness
            ):
                raise StoreError("parallel request does not match its batch manifest")
            validate_schema("continuation-request.schema.json", request.to_dict())
        with self.continuation_inbox_lock():
            if list(self.iter_continuation_requests(pending=True)):
                raise StoreError(
                    "finish or cancel the current AI response before starting a parallel batch"
                )
            _mkdir(self.parallel_batches_dir)
            _mkdir(self.continuation_requests_dir)
            path = self.parallel_batches_dir / f"{batch.id}.json"
            request_paths = [
                self.continuation_requests_dir / f"{request.id}.json"
                for request in requests
            ]
            if path.exists() or any(item.exists() for item in request_paths):
                raise StoreError(f"parallel batch {batch.id} already exists (write-once)")
            for request, request_path in zip(requests, request_paths, strict=True):
                _write_json(request_path, request.to_dict())
            # The manifest is the publication marker. A routed request without
            # it is ignored by dequeue, so a crash cannot expose half a batch.
            _write_json(path, batch.to_dict())
        return path

    def load_parallel_batch(self, batch_id: str) -> ParallelContinuationBatch:
        self._require()
        path = self.parallel_batches_dir / f"{batch_id}.json"
        if not path.is_file():
            raise StoreError(f"parallel continuation batch not found: {batch_id}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        validate_schema("parallel-continuation-batch.schema.json", raw)
        return ParallelContinuationBatch.from_dict(raw)

    def iter_parallel_batches(self) -> Iterator[ParallelContinuationBatch]:
        self._require()
        if not self.parallel_batches_dir.is_dir():
            return
            yield  # pragma: no cover
        for path in sorted(self.parallel_batches_dir.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            validate_schema("parallel-continuation-batch.schema.json", raw)
            yield ParallelContinuationBatch.from_dict(raw)

    def load_continuation_request(self, request_id: str) -> ContinuationRequest:
        self._require()
        path = self.continuation_requests_dir / f"{request_id}.json"
        if not path.is_file():
            raise StoreError(f"continuation request not found: {request_id}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        validate_schema("continuation-request.schema.json", raw)
        return ContinuationRequest.from_dict(raw)

    def write_continuation_attempt(self, attempt: ContinuationAttempt) -> Path:
        self._require()
        request = self.load_continuation_request(attempt.request_id)
        if request.requested_harness and request.requested_harness != attempt.harness:
            raise StoreError("attempt harness does not match requested harness")
        validate_schema("continuation-attempt.schema.json", attempt.to_dict())
        _mkdir(self.continuation_attempts_dir)
        path = self.continuation_attempts_dir / f"{attempt.id}.json"
        if path.exists():
            raise StoreError(
                f"continuation attempt {attempt.id} already exists (write-once)"
            )
        _write_json(path, attempt.to_dict())
        return path

    def iter_continuation_attempts(self) -> Iterator[ContinuationAttempt]:
        self._require()
        if not self.continuation_attempts_dir.is_dir():
            return
            yield  # pragma: no cover
        for path in sorted(self.continuation_attempts_dir.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            validate_schema("continuation-attempt.schema.json", raw)
            yield ContinuationAttempt.from_dict(raw)

    def iter_continuation_requests(
        self, *, pending: bool = False
    ) -> Iterator[ContinuationRequest]:
        self._require()
        if not self.continuation_requests_dir.is_dir():
            return
            yield  # pragma: no cover
        closed = set()
        if pending:
            closed.update(
                item.request_id for item in self.iter_continuation_completions()
            )
            closed.update(
                item.request_id for item in self.iter_continuation_cancellations()
            )
            closed.update(item.request_id for item in self.iter_continuation_failures())
        for path in sorted(self.continuation_requests_dir.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            validate_schema("continuation-request.schema.json", raw)
            request = ContinuationRequest.from_dict(raw)
            if request.parallel_batch_id and not (
                self.parallel_batches_dir / f"{request.parallel_batch_id}.json"
            ).is_file():
                continue
            if request.id not in closed:
                yield request

    def write_continuation_cancellation(
        self, cancellation: ContinuationCancellation
    ) -> Path:
        self._require()
        self.load_continuation_request(cancellation.request_id)
        if any(
            item.request_id == cancellation.request_id
            for item in self.iter_continuation_completions()
        ):
            raise StoreError(
                f"continuation request {cancellation.request_id} already completed"
            )
        if any(
            item.request_id == cancellation.request_id
            for item in self.iter_continuation_cancellations()
        ):
            raise StoreError(
                f"continuation request {cancellation.request_id} already canceled (write-once)"
            )
        if any(
            item.request_id == cancellation.request_id
            for item in self.iter_continuation_failures()
        ):
            raise StoreError(
                f"continuation request {cancellation.request_id} already failed"
            )
        validate_schema(
            "continuation-cancellation.schema.json", cancellation.to_dict()
        )
        _mkdir(self.continuation_cancellations_dir)
        path = self.continuation_cancellations_dir / f"{cancellation.id}.json"
        _write_json(path, cancellation.to_dict())
        return path

    def iter_continuation_cancellations(
        self,
    ) -> Iterator[ContinuationCancellation]:
        self._require()
        if not self.continuation_cancellations_dir.is_dir():
            return
            yield  # pragma: no cover
        for path in sorted(self.continuation_cancellations_dir.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            validate_schema("continuation-cancellation.schema.json", raw)
            yield ContinuationCancellation.from_dict(raw)

    def write_continuation_failure(self, failure: ContinuationFailure) -> Path:
        self._require()
        request = self.load_continuation_request(failure.request_id)
        if request.parallel_batch_id is None:
            raise StoreError("failure receipts are only for parallel requests")
        if request.requested_harness != failure.harness:
            raise StoreError("failure harness does not match requested harness")
        terminal = {
            item.request_id for item in self.iter_continuation_completions()
        } | {
            item.request_id for item in self.iter_continuation_cancellations()
        } | {
            item.request_id for item in self.iter_continuation_failures()
        }
        if failure.request_id in terminal:
            raise StoreError(f"continuation request {failure.request_id} is already closed")
        validate_schema("continuation-failure.schema.json", failure.to_dict())
        _mkdir(self.continuation_failures_dir)
        path = self.continuation_failures_dir / f"{failure.id}.json"
        _write_json(path, failure.to_dict())
        return path

    def iter_continuation_failures(self) -> Iterator[ContinuationFailure]:
        self._require()
        if not self.continuation_failures_dir.is_dir():
            return
            yield  # pragma: no cover
        for path in sorted(self.continuation_failures_dir.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            validate_schema("continuation-failure.schema.json", raw)
            yield ContinuationFailure.from_dict(raw)

    def write_continuation_completion(self, completion: ContinuationCompletion) -> Path:
        self._require()
        request = self.load_continuation_request(completion.request_id)
        if (
            request.requested_harness
            and request.requested_harness != completion.harness
        ):
            raise StoreError("completion harness does not match requested harness")
        if any(
            item.request_id == completion.request_id
            for item in self.iter_continuation_cancellations()
        ):
            raise StoreError(
                f"continuation request {completion.request_id} was canceled"
            )
        if any(
            item.request_id == completion.request_id
            for item in self.iter_continuation_failures()
        ):
            raise StoreError(f"continuation request {completion.request_id} failed")
        if completion.graph_id == request.graph_id:
            raise StoreError("continuation completion must point to a new graph")
        self.load_graph(completion.graph_id)
        validate_schema("continuation-completion.schema.json", completion.to_dict())
        _mkdir(self.continuation_completions_dir)
        if any(
            item.request_id == completion.request_id
            for item in self.iter_continuation_completions()
        ):
            raise StoreError(
                f"continuation request {completion.request_id} already completed (write-once)"
            )
        path = self.continuation_completions_dir / f"{completion.id}.json"
        _write_json(path, completion.to_dict())
        return path

    def iter_continuation_completions(self) -> Iterator[ContinuationCompletion]:
        self._require()
        if not self.continuation_completions_dir.is_dir():
            return
            yield  # pragma: no cover
        for path in sorted(self.continuation_completions_dir.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            validate_schema("continuation-completion.schema.json", raw)
            yield ContinuationCompletion.from_dict(raw)

    def write_recurring_circuit(self, data: dict) -> Path:
        self._require()
        validate_schema("recurring-circuit.schema.json", data)
        _mkdir(self.recurring_circuits_dir)
        path = self.recurring_circuits_dir / f"{data['id']}.json"
        if path.exists():
            raise StoreError(f"recurring circuit {data['id']} already exists (write-once)")
        _write_json(path, data)
        return path

    def load_recurring_circuit(self, circuit_id: str) -> dict:
        self._require()
        path = self.recurring_circuits_dir / f"{circuit_id}.json"
        if not path.is_file():
            raise StoreError(f"recurring circuit not found: {circuit_id}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        validate_schema("recurring-circuit.schema.json", raw)
        return raw

    def find_evidence(self, evidence_id: str) -> tuple[str, dict]:
        self._require()
        for session_id in self.iter_session_ids():
            path = self.evidence_dir(session_id) / f"{evidence_id}.json"
            if path.is_file():
                return session_id, self.load_evidence(session_id, evidence_id)
        raise StoreError(f"evidence not found: {evidence_id}")

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

    def evidence_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "evidence"

    def attributions_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "attributions"

    def neural_interventions_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "neural-interventions"

    def training_provenance_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "training-provenance"

    def sensor_sources_dir(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "sensor-sources"

    def write_sensor_source(self, session_id: str, digest: str, source: bytes) -> Path:
        """Preserve exact sensor-source bytes once, addressed by SHA-256."""
        self._require()
        if not self.session_exists(session_id):
            raise StoreError(f"session not found: {session_id}")
        actual = hashlib.sha256(source).hexdigest()
        if actual != digest:
            raise StoreError(f"sensor source SHA-256 mismatch: {actual} != {digest}")
        _mkdir(self.sensor_sources_dir(session_id))
        path = self.sensor_sources_dir(session_id) / f"{digest}.bin"
        if path.exists():
            if path.read_bytes() != source:
                raise StoreError(f"sensor source {digest} already exists with other bytes")
            return path
        path.write_bytes(source)
        _chmod_file(path)
        return path

    def write_attribution(self, session_id: str, data: dict) -> Path:
        """Write-once measured attribution bound to a node in this session."""
        self._require()
        if not self.session_exists(session_id):
            raise StoreError(f"session not found: {session_id}")
        graph = self.load_graph(data.get("graph_id", ""))
        if graph.session_id != session_id:
            raise StoreError(f"graph {graph.id} is not in session {session_id}")
        nodes = {node.id: node for node in graph.nodes}
        node = nodes.get(data.get("node_id"))
        if node is None:
            raise StoreError(f"node {data.get('node_id')} not in graph {graph.id}")
        validate_schema("attribution.schema.json", data)
        provenance = data.get("provenance")
        if provenance is None or provenance.get("artifact_kind") != "measured_attribution":
            raise StoreError("stored attribution requires measured_attribution provenance")
        span = data["span"]
        if span["end"] > len(node.text) or span["start"] > span["end"]:
            raise StoreError(f"attribution span is outside node {node.id}")
        _mkdir(self.attributions_dir(session_id))
        path = self.attributions_dir(session_id) / f"{data['id']}.json"
        if path.exists():
            raise StoreError(f"attribution {data['id']} already exists (write-once)")
        _write_json(path, data)
        return path

    def load_attribution(self, session_id: str, attribution_id: str) -> dict:
        self._require()
        path = self.attributions_dir(session_id) / f"{attribution_id}.json"
        if not path.is_file():
            raise StoreError(f"attribution not found: {attribution_id}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        validate_schema("attribution.schema.json", raw)
        return raw

    def write_neural_intervention(self, session_id: str, data: dict) -> Path:
        """Write-once checked result of an actual activation edit."""
        self._require()
        if not self.session_exists(session_id):
            raise StoreError(f"session not found: {session_id}")
        graph = self.load_graph(data.get("graph_id", ""))
        if graph.session_id != session_id:
            raise StoreError(f"graph {graph.id} is not in session {session_id}")
        if data.get("node_id") not in {node.id for node in graph.nodes}:
            raise StoreError(f"node {data.get('node_id')} not in graph {graph.id}")
        attribution = self.load_attribution(session_id, data.get("attribution_id", ""))
        if (attribution["graph_id"], attribution["node_id"]) != (
            data.get("graph_id"), data.get("node_id")
        ):
            raise StoreError("intervention attribution is bound to another thought")
        validate_schema("neural-intervention.schema.json", data)
        _mkdir(self.neural_interventions_dir(session_id))
        path = self.neural_interventions_dir(session_id) / f"{data['id']}.json"
        if path.exists():
            raise StoreError(f"neural intervention {data['id']} already exists (write-once)")
        _write_json(path, data)
        return path

    def load_neural_intervention(self, session_id: str, intervention_id: str) -> dict:
        self._require()
        path = self.neural_interventions_dir(session_id) / f"{intervention_id}.json"
        if not path.is_file():
            raise StoreError(f"neural intervention not found: {intervention_id}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        validate_schema("neural-intervention.schema.json", raw)
        return raw

    def write_training_provenance(self, session_id: str, data: dict) -> Path:
        self._require()
        graph = self.load_graph(data.get("graph_id", ""))
        if graph.session_id != session_id:
            raise StoreError(f"graph {graph.id} is not in session {session_id}")
        if data.get("node_id") not in {node.id for node in graph.nodes}:
            raise StoreError(f"node {data.get('node_id')} not in graph {graph.id}")
        validate_schema("training-provenance.schema.json", data)
        _mkdir(self.training_provenance_dir(session_id))
        path = self.training_provenance_dir(session_id) / f"{data['id']}.json"
        if path.exists():
            raise StoreError(f"training provenance {data['id']} already exists (write-once)")
        _write_json(path, data)
        return path

    def load_training_provenance(self, session_id: str, provenance_id: str) -> dict:
        self._require()
        path = self.training_provenance_dir(session_id) / f"{provenance_id}.json"
        if not path.is_file():
            raise StoreError(f"training provenance not found: {provenance_id}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        validate_schema("training-provenance.schema.json", raw)
        return raw

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

    def write_evidence(self, session_id: str, data: dict) -> Path:
        """Write-once evidence binding attached to a node in this session."""
        self._require()
        if not self.session_exists(session_id):
            raise StoreError(f"session not found: {session_id}")
        graph = self.load_graph(data.get("graph_id", ""))
        if graph.session_id != session_id:
            raise StoreError(f"graph {graph.id} is not in session {session_id}")
        if data.get("node_id") not in {node.id for node in graph.nodes}:
            raise StoreError(f"node {data.get('node_id')} not in graph {graph.id}")
        validate_schema("evidence-binding.schema.json", data)
        parent_id = data.get("parent_evidence_id")
        if parent_id is not None:
            parent = self.evidence_dir(session_id) / f"{parent_id}.json"
            if not parent.is_file():
                raise StoreError(f"parent evidence not found: {parent_id}")
        _mkdir(self.evidence_dir(session_id))
        evidence_id = data["id"]
        path = self.evidence_dir(session_id) / f"{evidence_id}.json"
        if path.exists():
            raise StoreError(f"evidence {evidence_id} already exists (write-once)")
        _write_json(path, data)
        return path

    def load_evidence(self, session_id: str, evidence_id: str) -> dict:
        self._require()
        path = self.evidence_dir(session_id) / f"{evidence_id}.json"
        if not path.is_file():
            raise StoreError(f"evidence not found: {evidence_id}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        validate_schema("evidence-binding.schema.json", raw)
        return raw

    def iter_evidence(
        self,
        session_id: str,
        *,
        graph_id: str | None = None,
        node_id: str | None = None,
    ) -> Iterator[dict]:
        """Read evidence bindings in append order, optionally scoped to a stand."""
        self._require()
        directory = self.evidence_dir(session_id)
        if not directory.is_dir():
            return
            yield  # pragma: no cover
        for path in sorted(directory.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            validate_schema("evidence-binding.schema.json", raw)
            if graph_id is not None and raw["graph_id"] != graph_id:
                continue
            if node_id is not None and raw["node_id"] != node_id:
                continue
            yield raw

    def evidence_chain(self, session_id: str, evidence_id: str) -> tuple[dict, ...]:
        """Return one parent chain from oldest binding to the requested leaf."""
        newest_first: list[dict] = []
        seen: set[str] = set()
        current_id: str | None = evidence_id
        while current_id is not None:
            if current_id in seen:
                raise StoreError(f"evidence parent cycle at {current_id}")
            seen.add(current_id)
            current = self.load_evidence(session_id, current_id)
            newest_first.append(current)
            current_id = current.get("parent_evidence_id")
        return tuple(reversed(newest_first))

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
