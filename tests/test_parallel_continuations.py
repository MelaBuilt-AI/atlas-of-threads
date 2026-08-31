from __future__ import annotations

import sys
from pathlib import Path

import thought_archaeology.harness as harness_module
from thought_archaeology.continuation import (
    continuation_attempt,
    parallel_batch_progress,
)
from thought_archaeology.harness import HarnessError, HarnessRegistry, process_continuation
from thought_archaeology.inhabit import inhabit
from thought_archaeology.serve import (
    InhabitHandler,
    cancel_parallel_continuations,
    create_parallel_continuations,
)
from thought_archaeology.store import Store

from tests.helpers import FIXTURES
from tests.test_cli import run

FAKE_ADAPTER = Path(__file__).with_name("fake_harness_adapter.py")


def _source(store_path: Path) -> tuple[Store, object, object]:
    code, out, err = run(["init", "--title", "parallel source"], store=store_path)
    assert code == 0, err
    code, out, err = run(
        [
            "compile",
            "--session",
            out.strip(),
            "--mode",
            "posthoc",
            "--transcript",
            str(FIXTURES / "transcripts" / "simple-freeform.jsonl"),
            "--from-graph",
            str(FIXTURES / "graphs" / "simple.gold.json"),
        ],
        store=store_path,
    )
    assert code == 0, err
    store = Store(store_path)
    graph = store.load_graph(out.strip())
    terminal = next(
        node
        for node in graph.nodes
        if inhabit(store, node.id, graph_id=graph.id).to_dict()["read"]["traversal"][
            "terminal"
        ]
    )
    return store, graph, terminal


def _registry(monkeypatch, tmp_path: Path) -> HarnessRegistry:
    path = tmp_path / "harnesses.json"
    monkeypatch.setenv("TA_HARNESS_CONFIG", str(path))
    registry = HarnessRegistry(path)
    registry.register(
        "beta",
        sys.executable,
        args=(str(FAKE_ADAPTER),),
        make_default=True,
    )
    registry.register("alpha", sys.executable, args=(str(FAKE_ADAPTER),))
    return registry


def test_parallel_batch_is_ordered_routed_and_sequential(monkeypatch, tmp_path: Path):
    store, graph, terminal = _source(tmp_path / "data")
    registry = _registry(monkeypatch, tmp_path)
    created = create_parallel_continuations(
        store,
        graph_id=graph.id,
        node_id=terminal.id,
        prompt="Preserve the disagreement and continue.",
        harnesses=["alpha", "beta"],
    )
    batch = store.load_parallel_batch(created["batch"]["id"])
    assert [job.harness for job in batch.jobs] == ["beta", "alpha"]
    requests = [store.load_continuation_request(job.request_id) for job in batch.jobs]
    assert all(request.parallel_batch_id == batch.id for request in requests)
    assert [request.requested_harness for request in requests] == ["beta", "alpha"]
    assert registry.default_name() == "beta"
    assert inhabit(store, terminal.id, graph_id=graph.id).continuation is None

    fallback = registry.get()
    first = process_continuation(store, fallback, registry=registry)
    second = process_continuation(store, fallback, registry=registry)
    assert [first["harness"], second["harness"]] == ["beta", "alpha"]
    assert [item.harness for item in store.iter_continuation_attempts()] == [
        "beta",
        "alpha",
    ]
    children = [store.load_graph(first["graph_id"]), store.load_graph(second["graph_id"])]
    assert all(child.parent_graph_id == graph.id for child in children)
    assert registry.default_name() == "beta"
    progress = parallel_batch_progress(store, batch.id)
    assert progress["terminal"] is True
    assert progress["counts"]["completed"] == 2
    assert [job["status"] for job in progress["jobs"]] == ["completed", "completed"]


def test_parallel_failure_is_sanitized_and_next_job_continues(
    monkeypatch, tmp_path: Path
):
    store, graph, terminal = _source(tmp_path / "data")
    registry = _registry(monkeypatch, tmp_path)
    created = create_parallel_continuations(
        store,
        graph_id=graph.id,
        node_id=terminal.id,
        prompt="Continue independently.",
        harnesses=["beta", "alpha"],
    )
    response = (FIXTURES / "transcripts" / "simple-structured.txt").read_text(
        encoding="utf-8"
    )

    def fail_beta(spec, operation, payload, *, timeout):
        if spec.name == "beta":
            raise HarnessError("secret adapter output must never be stored")
        return {
            "protocol_version": "1",
            "response": response,
            "model_name": "fake-alpha",
        }

    monkeypatch.setattr(harness_module, "_adapter_call", fail_beta)
    first = process_continuation(store, registry.get(), registry=registry)
    second = process_continuation(store, registry.get(), registry=registry)
    assert first["status"] == "failed"
    assert first["reason_code"] == "adapter_error"
    assert second["status"] == "completed"
    failure = next(store.iter_continuation_failures())
    assert "secret" not in failure.public_summary
    progress = parallel_batch_progress(store, created["batch"]["id"])
    assert progress["counts"] == {
        "queued": 0,
        "responding": 0,
        "completed": 1,
        "failed": 1,
        "canceled": 0,
    }


def test_parallel_restart_marks_attempt_interrupted_without_reinvoking(
    monkeypatch, tmp_path: Path
):
    store, graph, terminal = _source(tmp_path / "data")
    registry = _registry(monkeypatch, tmp_path)
    created = create_parallel_continuations(
        store,
        graph_id=graph.id,
        node_id=terminal.id,
        prompt="Continue once only.",
        harnesses=["beta", "alpha"],
    )
    request_id = created["batch"]["jobs"][0]["request_id"]
    store.write_continuation_attempt(continuation_attempt(request_id, "beta"))

    def must_not_run(*args, **kwargs):
        raise AssertionError("interrupted batch job was reinvoked")

    monkeypatch.setattr(harness_module, "_adapter_call", must_not_run)
    outcome = process_continuation(store, registry.get(), registry=registry)
    assert outcome["status"] == "failed"
    assert outcome["reason_code"] == "interrupted"
    assert len(list(store.iter_continuation_attempts())) == 1


def test_cancel_remaining_closes_active_and_unattempted_jobs(monkeypatch, tmp_path: Path):
    store, graph, terminal = _source(tmp_path / "data")
    registry = _registry(monkeypatch, tmp_path)
    created = create_parallel_continuations(
        store,
        graph_id=graph.id,
        node_id=terminal.id,
        prompt="Continue unless canceled.",
        harnesses=["beta", "alpha"],
    )
    before_graphs = {item.id for item in store.iter_graphs()}
    response = (FIXTURES / "transcripts" / "simple-structured.txt").read_text(
        encoding="utf-8"
    )

    def cancel_then_answer(spec, operation, payload, *, timeout):
        cancel_parallel_continuations(store, created["batch"]["id"])
        return {
            "protocol_version": "1",
            "response": response,
            "model_name": "too-late",
        }

    monkeypatch.setattr(harness_module, "_adapter_call", cancel_then_answer)
    outcome = process_continuation(store, registry.get(), registry=registry)
    assert outcome["status"] == "canceled"
    assert {item.id for item in store.iter_graphs()} == before_graphs
    progress = parallel_batch_progress(store, created["batch"]["id"])
    assert progress["counts"]["canceled"] == 2
    assert list(store.iter_continuation_requests(pending=True)) == []


def test_parallel_handler_and_inhabit_payload_are_server_authored(
    monkeypatch, tmp_path: Path
):
    store, graph, terminal = _source(tmp_path / "data")
    _registry(monkeypatch, tmp_path)
    replies = []
    handler = object.__new__(InhabitHandler)
    handler.store = store
    handler._json = lambda code, body: replies.append((code, body))
    handler._read_json = lambda: {
        "graph_id": graph.id,
        "node_id": terminal.id,
        "prompt": "Read this source in parallel.",
        "harnesses": ["alpha", "beta"],
    }
    handler._parallel_ready()
    assert replies[-1][0] == 200
    created = replies[-1][1]
    batch_id = created["batch"]["id"]

    handler.path = f"/api/parallel/{batch_id}"
    handler.do_GET()
    assert replies[-1][1]["id"] == batch_id
    assert replies[-1][1]["counts"]["queued"] == 2

    handler.path = f"/api/inhabit/{terminal.id}?graph={graph.id}"
    handler.do_GET()
    payload = replies[-1][1]
    assert payload["continuation"] is None
    assert payload["parallel_continuation"]["id"] == batch_id
    assert [job["status"] for job in payload["parallel_continuation"]["jobs"]] == [
        "queued",
        "queued",
    ]
