from __future__ import annotations

import json
import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from thought_archaeology.continuation import (
    continuation_attempt,
    continuation_cancellation,
    continuation_completion,
    continuation_request,
    parallel_comparison,
    parallel_group_summaries,
)
from thought_archaeology.ids import new_ulid
from thought_archaeology.inhabit import inhabit
from thought_archaeology.models import ModelInfo, ThoughtEdge
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


def _parallel_study(store_path: Path) -> tuple[Store, object, list[str]]:
    _session_id, graph_id = _compiled(store_path)
    store = Store(store_path)
    source = store.load_graph(graph_id)
    source_node = source.nodes[0]
    request_ids = []
    harnesses = ["grok", "codex", "claude", "opencode", "prime-agent"]
    for index, harness in enumerate(harnesses):
        prompt = "Who bears the burden when serious harm evidence is incomplete?"
        request = continuation_request(
            source, source_node, prompt=prompt, source="inhabit_space"
        )
        store.write_continuation_request(request)
        request_ids.append(request.id)
        nodes = list(source.nodes)
        judgment_index = next(
            i for i, node in enumerate(nodes) if node.kind == "judgment_call"
        )
        nodes[judgment_index] = replace(
            nodes[judgment_index], text=f"Judgment path {index + 1}"
        )
        if index == 3:
            nodes = [node for node in nodes if node.kind != "uncertainty"]
        edges = list(source.edges)
        kept_node_ids = {node.id for node in nodes}
        edges = [
            edge
            for edge in edges
            if edge.source_id in kept_node_ids and edge.target_id in kept_node_ids
        ]
        if index == 2:
            claim = next(node for node in nodes if node.kind == "claim")
            judgment = next(node for node in nodes if node.kind == "judgment_call")
            edges.append(
                ThoughtEdge(
                    new_ulid(), claim.id, judgment.id, "depends_on", source.created_at
                )
            )
        child = replace(
            source,
            id=new_ulid(),
            turn_id=new_ulid(),
            nodes=tuple(nodes),
            edges=tuple(edges),
            model=ModelInfo("shell", f"model-{index + 1}", "structured_emit"),
            parent_graph_id=source.id,
            hidden_reasoning=None,
        )
        store.write_graph(child)
        completion = continuation_completion(request.id, child.id, harness)
        store.write_continuation_completion(completion)
        warnings = (
            ["policy: supports/depends_on/shapes cycle detected"]
            if index == 2
            else []
        )
        store.log(
            "harness_continue",
            session_id=source.session_id,
            graph_id=child.id,
            request_id=request.id,
            completion_id=completion.id,
            harness=harness,
            warnings=warnings,
        )

    rephrased = continuation_request(
        source,
        source_node,
        prompt="With incomplete evidence, who has the burden?",
        source="inhabit_space",
    )
    store.write_continuation_request(rephrased)
    rephrased_graph = replace(
        source,
        id=new_ulid(),
        turn_id=new_ulid(),
        model=ModelInfo("shell", "rephrased-model", "structured_emit"),
        parent_graph_id=source.id,
        hidden_reasoning=None,
    )
    store.write_graph(rephrased_graph)
    store.write_continuation_completion(
        continuation_completion(rephrased.id, rephrased_graph.id, "codex")
    )
    other_node = source.nodes[1]
    other_source = continuation_request(
        source,
        other_node,
        prompt="Who bears the burden when serious harm evidence is incomplete?",
        source="inhabit_space",
    )
    store.write_continuation_request(other_source)
    other_graph = replace(
        source,
        id=new_ulid(),
        turn_id=new_ulid(),
        model=ModelInfo("shell", "other-node-model", "structured_emit"),
        parent_graph_id=source.id,
        hidden_reasoning=None,
    )
    store.write_graph(other_graph)
    store.write_continuation_completion(
        continuation_completion(other_source.id, other_graph.id, "grok")
    )
    return store, source_node, request_ids


def _store_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


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
    attempt = continuation_attempt(request.id, "test-harness")
    attempt_path = store.write_continuation_attempt(attempt)
    assert attempt_path.is_file()
    assert list(store.iter_continuation_attempts()) == [attempt]
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
    with pytest.raises(StoreError, match="already completed"):
        store.write_continuation_cancellation(
            continuation_cancellation(request.id)
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


def test_continuation_cancellation_is_append_only(tmp_path: Path):
    store_path = tmp_path / "data"
    _session_id, graph_id = _compiled(store_path)
    store = Store(store_path)
    graph = store.load_graph(graph_id)
    request = continuation_request(graph, graph.nodes[0])
    store.write_continuation_request(request)

    cancellation = continuation_cancellation(
        request.id, source="inhabit_space"
    )
    path = store.write_continuation_cancellation(cancellation)
    assert path.is_file()
    assert list(store.iter_continuation_cancellations()) == [cancellation]
    assert list(store.iter_continuation_requests(pending=True)) == []
    with pytest.raises(StoreError, match="already canceled"):
        store.write_continuation_cancellation(
            continuation_cancellation(request.id)
        )

    _next_session, next_graph = _compiled(store_path, "answer")
    with pytest.raises(StoreError, match="was canceled"):
        store.write_continuation_completion(
            continuation_completion(request.id, next_graph, "test-harness")
        )


def test_continuation_cancel_cli_withdraws_from_inbox(tmp_path: Path):
    store_path = tmp_path / "data"
    _session_id, graph_id = _compiled(store_path)
    graph = Store(store_path).load_graph(graph_id)
    code, out, err = run(
        ["continuation", "ready", graph.nodes[0].id, "--graph", graph.id],
        store=store_path,
    )
    assert code == 0, err
    request_id = out.strip()
    code, out, err = run(
        ["continuation", "cancel", request_id], store=store_path
    )
    assert code == 0, err
    assert len(out.strip()) == 26
    code, out, err = run(
        ["continuation", "pending", "--format", "json"], store=store_path
    )
    assert code == 0, err
    assert json.loads(out) == []


def test_parallel_comparison_groups_only_exact_completed_paths(tmp_path: Path):
    store_path = tmp_path / "data"
    store, source_node, request_ids = _parallel_study(store_path)
    source_graph_id = store.load_continuation_request(request_ids[0]).graph_id
    before = _store_hashes(store_path)

    groups = parallel_group_summaries(
        store, graph_id=source_graph_id, node_id=source_node.id
    )
    assert len(groups) == 1
    assert groups[0]["completed_count"] == 5
    assert groups[0]["prompt"] == (
        "Who bears the burden when serious harm evidence is incomplete?"
    )
    assert [item["display_name"] for item in groups[0]["harnesses"]] == [
        "Grok",
        "Codex",
        "Claude",
        "OpenCode",
        "Prime Agent",
    ]

    comparison = parallel_comparison(
        store,
        request_ids[0],
        graph_id=source_graph_id,
        node_id=source_node.id,
    )
    assert len(comparison["paths"]) == 5
    assert [path["harness"] for path in comparison["paths"]] == [
        "grok",
        "codex",
        "claude",
        "opencode",
        "prime-agent",
    ]
    claude = next(path for path in comparison["paths"] if path["harness"] == "claude")
    assert claude["recorded_warnings"] == [
        "policy: supports/depends_on/shapes cycle detected"
    ]
    assert claude["current_policy_warnings"] == [
        "policy: supports/depends_on/shapes cycle detected"
    ]
    opencode = next(
        path for path in comparison["paths"] if path["harness"] == "opencode"
    )
    assert opencode["uncertainties"] == []
    assert _store_hashes(store_path) == before


def test_parallel_compare_cli_lists_and_reads_group(tmp_path: Path):
    store_path = tmp_path / "data"
    store, source_node, request_ids = _parallel_study(store_path)
    source_graph_id = store.load_continuation_request(request_ids[0]).graph_id
    code, out, err = run(
        [
            "continuation",
            "compare",
            source_node.id,
            "--graph",
            source_graph_id,
            "--format",
            "json",
        ],
        store=store_path,
    )
    assert code == 0, err
    assert json.loads(out)[0]["completed_count"] == 5

    code, out, err = run(
        [
            "continuation",
            "compare",
            source_node.id,
            "--graph",
            source_graph_id,
            "--request",
            request_ids[0],
            "--format",
            "json",
        ],
        store=store_path,
    )
    assert code == 0, err
    comparison = json.loads(out)
    assert comparison["source_thought"]["id"] == source_node.id
    assert comparison["paths"][0]["model"] == "model-1"


def test_parallel_compare_rejects_singleton_and_wrong_source(tmp_path: Path):
    store_path = tmp_path / "data"
    store, source_node, request_ids = _parallel_study(store_path)
    source_graph_id = store.load_continuation_request(request_ids[0]).graph_id
    singleton = next(
        request
        for request in store.iter_continuation_requests()
        if request.prompt == "With incomplete evidence, who has the burden?"
    )
    with pytest.raises(StoreError, match="no parallel paths"):
        parallel_comparison(store, singleton.id)
    with pytest.raises(StoreError, match="not from node"):
        parallel_comparison(store, request_ids[0], node_id=new_ulid())
    assert parallel_group_summaries(
        store, graph_id=source_graph_id, node_id=new_ulid()
    ) == []


def test_parallel_compare_keeps_empty_prompt_as_its_own_group(tmp_path: Path):
    store_path = tmp_path / "data"
    store, source_node, request_ids = _parallel_study(store_path)
    source = store.load_graph(
        store.load_continuation_request(request_ids[0]).graph_id
    )
    empty_request_ids = []
    for harness in ("grok", "codex"):
        request = continuation_request(source, source_node, prompt="")
        store.write_continuation_request(request)
        empty_request_ids.append(request.id)
        child = replace(
            source,
            id=new_ulid(),
            turn_id=new_ulid(),
            model=ModelInfo("shell", f"{harness}-empty", "structured_emit"),
            parent_graph_id=source.id,
            hidden_reasoning=None,
        )
        store.write_graph(child)
        store.write_continuation_completion(
            continuation_completion(request.id, child.id, harness)
        )
    groups = parallel_group_summaries(
        store, graph_id=source.id, node_id=source_node.id
    )
    assert [group["prompt"] for group in groups] == [
        "",
        "Who bears the burden when serious harm evidence is incomplete?",
    ]
    comparison = parallel_comparison(store, empty_request_ids[0])
    assert comparison["prompt"] == ""
    assert comparison["completed_count"] == 2


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
