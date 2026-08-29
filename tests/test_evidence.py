from __future__ import annotations

import json

import pytest

from thought_archaeology.evidence import EvidenceBinding
from thought_archaeology.inhabit import format_inhabit, inhabit
from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import SCHEMA_VERSION, ThoughtGraph, Turn
from thought_archaeology.schema import ValidationError, validate_schema
from thought_archaeology.store import Store, StoreError

from tests.test_schema import _minimal_graph_dict
from tests.test_cli import run


def _binding(graph: ThoughtGraph, **changes) -> EvidenceBinding:
    values = {
        "schema_version": SCHEMA_VERSION,
        "id": new_ulid(),
        "graph_id": graph.id,
        "node_id": graph.nodes[0].id,
        "kind": "behavioral_intervention",
        "result": "contradicts",
        "summary": "Dropping the premise removed the accepted conclusion.",
        "artifact_refs": ("probe:01M14QVETKXXTC7GJEXD662DDS", "diff:01M15F4EW375NQRCK2X28BMJGW"),
        "created_at": now_iso(),
        "parent_evidence_id": None,
    }
    values.update(changes)
    return EvidenceBinding(**values)


def _store_with_graph(tmp_path) -> tuple[Store, ThoughtGraph]:
    store = Store(tmp_path / "data")
    session = store.init_session("evidence")
    raw = _minimal_graph_dict(session_id=session.id)
    graph = ThoughtGraph.from_dict(raw)
    store.write_graph(graph)
    return store, graph


def test_evidence_binding_roundtrip_and_schema(tmp_path):
    store, graph = _store_with_graph(tmp_path)
    binding = _binding(graph)
    validate_schema("evidence-binding.schema.json", binding.to_dict())
    path = store.write_evidence(graph.session_id, binding.to_dict())
    loaded = EvidenceBinding.from_dict(store.load_evidence(graph.session_id, binding.id))
    assert path.name == f"{binding.id}.json"
    assert loaded == binding


def test_evidence_kinds_are_explicit_not_numeric_confidence(tmp_path):
    _, graph = _store_with_graph(tmp_path)
    raw = _binding(graph, kind="activation_correlation", result="supports").to_dict()
    validate_schema("evidence-binding.schema.json", raw)
    raw["confidence"] = 0.9
    with pytest.raises(ValidationError):
        validate_schema("evidence-binding.schema.json", raw)


def test_evidence_requires_real_node_in_session(tmp_path):
    store, graph = _store_with_graph(tmp_path)
    wrong_node = _binding(graph, node_id=new_ulid())
    with pytest.raises(StoreError, match="not in graph"):
        store.write_evidence(graph.session_id, wrong_node.to_dict())


def test_evidence_is_write_once(tmp_path):
    store, graph = _store_with_graph(tmp_path)
    binding = _binding(graph)
    store.write_evidence(graph.session_id, binding.to_dict())
    with pytest.raises(StoreError, match="write-once"):
        store.write_evidence(graph.session_id, binding.to_dict())


def test_parent_binding_supports_multi_generational_chain(tmp_path):
    store, graph = _store_with_graph(tmp_path)
    parent = _binding(graph, kind="context_provenance", result="supports")
    child = _binding(graph, parent_evidence_id=parent.id)
    store.write_evidence(graph.session_id, parent.to_dict())
    store.write_evidence(graph.session_id, child.to_dict())
    raw = json.loads(
        (store.evidence_dir(graph.session_id) / f"{child.id}.json").read_text()
    )
    assert raw["parent_evidence_id"] == parent.id
    assert [item["id"] for item in store.evidence_chain(graph.session_id, child.id)] == [
        parent.id,
        child.id,
    ]


def test_parent_binding_must_exist_in_same_session(tmp_path):
    store, graph = _store_with_graph(tmp_path)
    child = _binding(graph, parent_evidence_id=new_ulid())
    with pytest.raises(StoreError, match="parent evidence not found"):
        store.write_evidence(graph.session_id, child.to_dict())


def test_inhabit_reads_typed_evidence_chain(tmp_path):
    store, graph = _store_with_graph(tmp_path)
    parent = _binding(graph, kind="story_report", result="supports")
    child = _binding(graph, parent_evidence_id=parent.id)
    store.write_evidence(graph.session_id, parent.to_dict())
    store.write_evidence(graph.session_id, child.to_dict())

    view = inhabit(store, graph.nodes[0].id, graph_id=graph.id)
    payload = view.to_dict()
    assert [item["kind"] for item in payload["evidence"]] == [
        "story_report",
        "behavioral_intervention",
    ]
    assert payload["read"]["evidence_line"] == (
        "evidence: an intervention tested this — contradicts this thought (2 bindings)"
    )
    assert [layer["heading_line"] for layer in payload["read"]["evidence_layers"]] == [
        "story report — supports",
        "behavioral intervention — contradicts",
    ]
    assert payload["read"]["evidence_layers"][1]["follows_line"] == (
        f"follows {parent.id}"
    )
    assert payload["read"]["evidence_action_line"] == (
        "e descends through 2 evidence strata"
    )
    text = format_inhabit(view)
    assert "evidence beneath this thought" in text
    assert f"follows {parent.id}" in text
    assert "absence is not evidence" not in text


def test_inhabit_names_missing_evidence_as_absence(tmp_path):
    store, graph = _store_with_graph(tmp_path)
    view = inhabit(store, graph.nodes[0].id, graph_id=graph.id)
    assert view.to_dict()["evidence"] == []
    assert view.to_dict()["read"]["evidence_line"] is None
    assert view.to_dict()["read"]["evidence_layers"] == []
    assert "absence is not evidence" in view.to_dict()["read"]["evidence_empty_line"]
    assert "absence is not evidence" in format_inhabit(view)


def test_inhabit_resolves_parent_chain_across_graph_nodes(tmp_path):
    store, graph = _store_with_graph(tmp_path)
    parent = _binding(graph, kind="story_report", result="supports")
    store.write_evidence(graph.session_id, parent.to_dict())

    raw = graph.to_dict()
    raw["id"] = new_ulid()
    child_graph = ThoughtGraph.from_dict(raw)
    store.write_graph(child_graph)
    leaf = _binding(
        child_graph,
        node_id=child_graph.nodes[0].id,
        parent_evidence_id=parent.id,
    )
    store.write_evidence(child_graph.session_id, leaf.to_dict())

    view = inhabit(store, leaf.node_id, graph_id=child_graph.id)
    assert [binding.id for binding in view.evidence] == [parent.id, leaf.id]
    assert "(2 bindings)" in view.to_dict()["read"]["evidence_line"]
    assert f"at graph {graph.id} node {parent.node_id}" in format_inhabit(view)


def _append_graph_turns(store: Store, graph: ThoughtGraph) -> Turn:
    user = Turn(
        SCHEMA_VERSION,
        new_ulid(),
        graph.session_id,
        0,
        "user",
        now_iso(),
        "Build a medium where a human can stand inside a thought.",
        None,
        None,
        None,
        None,
    )
    assistant = Turn(
        SCHEMA_VERSION,
        graph.turn_id,
        graph.session_id,
        1,
        "assistant",
        now_iso(),
        graph.prose,
        graph.id,
        user.id,
        None,
        "file",
    )
    store.append_turn(user)
    store.append_turn(assistant)
    return user


def test_cli_context_evidence_binds_real_preceding_turn(tmp_path):
    root = tmp_path / "data"
    store, graph = _store_with_graph(tmp_path)
    user = _append_graph_turns(store, graph)
    code, out, err = run(
        [
            "evidence", "context", "--graph", graph.id,
            "--node", graph.nodes[0].id, "--turn", user.id,
        ],
        store=root,
    )
    assert code == 0, err
    binding = store.load_evidence(graph.session_id, out.strip())
    assert binding["kind"] == "context_provenance"
    assert binding["result"] == "inconclusive"
    assert binding["artifact_refs"][0] == f"turn:{user.id}"
    assert binding["artifact_refs"][1].startswith("sha256:")
    assert "does not show causal influence" in binding["summary"]


def test_cli_context_evidence_rejects_graph_output_turn(tmp_path):
    root = tmp_path / "data"
    store, graph = _store_with_graph(tmp_path)
    _append_graph_turns(store, graph)
    code, _, err = run(
        [
            "evidence", "context", "--graph", graph.id,
            "--node", graph.nodes[0].id, "--turn", graph.turn_id,
        ],
        store=root,
    )
    assert code == 3
    assert "not preceding context" in err
