from __future__ import annotations

import json
from pathlib import Path

import pytest

from thought_archaeology.continuation import (
    continuation_completion,
    continuation_request,
)
from thought_archaeology.inhabit import inhabit
from thought_archaeology.store import Store, StoreError

from tests.helpers import FIXTURES
from tests.test_cli import run


def _compiled(store_path: Path, title: str = "thought") -> tuple[str, str]:
    code, out, err = run(["init", "--title", title], store=store_path)
    assert code == 0, err
    session_id = out.strip()
    code, out, err = run(
        [
            "compile",
            "--session",
            session_id,
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
    return session_id, out.strip()


def test_continuation_request_and_completion_are_append_only(tmp_path: Path):
    store_path = tmp_path / "data"
    _session_id, graph_id = _compiled(store_path)
    store = Store(store_path)
    graph = store.load_graph(graph_id)
    node = graph.nodes[0]
    request = continuation_request(
        graph, node, prompt="What follows?", source="inhabit_space"
    )
    request_path = store.write_continuation_request(request)
    assert request_path.is_file()
    assert store.load_continuation_request(request.id) == request
    assert list(store.iter_continuation_requests(pending=True)) == [request]
    with pytest.raises(StoreError, match="new graph"):
        store.write_continuation_completion(
            continuation_completion(request.id, graph.id, "test-harness")
        )

    _next_session, next_graph = _compiled(store_path, "answer")
    completion = continuation_completion(request.id, next_graph, "test-harness")
    completion_path = store.write_continuation_completion(completion)
    assert completion_path.is_file()
    assert list(store.iter_continuation_requests(pending=True)) == []
    with pytest.raises(StoreError, match="already completed"):
        store.write_continuation_completion(
            continuation_completion(request.id, next_graph, "other-harness")
        )


def test_continuation_cli_is_a_provider_neutral_inbox(tmp_path: Path):
    store_path = tmp_path / "data"
    _session_id, graph_id = _compiled(store_path)
    graph = Store(store_path).load_graph(graph_id)
    node_id = graph.nodes[0].id
    code, out, err = run(
        [
            "continuation",
            "ready",
            node_id,
            "--graph",
            graph_id,
            "--prompt",
            "Continue from this claim.",
        ],
        store=store_path,
    )
    assert code == 0, err
    request_id = out.strip()
    code, out, err = run(
        ["continuation", "pending", "--format", "json"], store=store_path
    )
    assert code == 0, err
    pending = json.loads(out)
    assert pending == [
        {
            **Store(store_path).load_continuation_request(request_id).to_dict(),
            "source": "cli",
        }
    ]

    _next_session, next_graph = _compiled(store_path, "answer")
    code, out, err = run(
        [
            "continuation",
            "complete",
            request_id,
            "--graph",
            next_graph,
            "--harness",
            "generic-runner",
        ],
        store=store_path,
    )
    assert code == 0, err
    assert len(out.strip()) == 26
    code, out, err = run(
        ["continuation", "pending", "--format", "json"], store=store_path
    )
    assert code == 0, err
    assert json.loads(out) == []


def test_navigation_exposes_only_direct_story_steps(tmp_path: Path):
    store_path = tmp_path / "data"
    code, out, err = run(["init", "--title", "chain"], store=store_path)
    assert code == 0, err
    session_id = out.strip()
    raw = json.loads((FIXTURES / "graphs" / "simple.gold.json").read_text())
    raw["nodes"].append(
        {
            "local_id": "n7",
            "kind": "claim",
            "text": "The medium can now continue.",
            "status": "accepted",
        }
    )
    raw["edges"].append({"from": "n1", "to": "n7", "kind": "shapes"})
    graph_path = tmp_path / "chain.json"
    graph_path.write_text(json.dumps(raw), encoding="utf-8")
    code, out, err = run(
        [
            "compile",
            "--session",
            session_id,
            "--mode",
            "posthoc",
            "--transcript",
            str(FIXTURES / "transcripts" / "simple-freeform.jsonl"),
            "--from-graph",
            str(graph_path),
        ],
        store=store_path,
    )
    assert code == 0, err
    graph = Store(store_path).load_graph(out.strip())
    judgment = next(node for node in graph.nodes if node.kind == "judgment_call")
    central = next(node for node in graph.nodes if node.text.startswith("The product"))
    ending = next(node for node in graph.nodes if node.text == "The medium can now continue.")

    entry = inhabit(Store(store_path), judgment.id, graph_id=graph.id)
    assert [node.id for node in entry.forward] == [central.id]
    assert {node.id for node in entry.shaped} == {central.id, ending.id}
    assert entry.to_dict()["read"]["traversal"]["terminal"] is False

    end = inhabit(Store(store_path), ending.id, graph_id=graph.id)
    payload = end.to_dict()
    assert payload["forward"] == []
    assert payload["origin"]["id"] == judgment.id
    assert payload["read"]["traversal"]["terminal"] is True
