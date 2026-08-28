from __future__ import annotations

import json
from types import MappingProxyType

import pytest

from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import (
    SCHEMA_VERSION,
    ModelInfo,
    ThoughtEdge,
    ThoughtGraph,
    ThoughtNode,
)
from thought_archaeology.schema import (
    SCHEMA_DIR,
    ValidationError,
    load_validator,
    policy_warnings,
    validate_graph,
    validate_schema,
)


def _ulids(n: int) -> list[str]:
    return [new_ulid() for _ in range(n)]


def _minimal_graph_dict(**overrides) -> dict:
    ids = _ulids(6)
    now = now_iso()
    node_id, edge_id, graph_id, session_id, turn_id = ids[0], ids[1], ids[2], ids[3], ids[4]
    rejected_id = ids[5]
    base = {
        "schema_version": SCHEMA_VERSION,
        "id": graph_id,
        "session_id": session_id,
        "turn_id": turn_id,
        "created_at": now,
        "prose": "The product is the medium, not the microscope.",
        "nodes": [
            {
                "id": node_id,
                "kind": "claim",
                "text": "The product is the medium, not the microscope.",
                "status": "accepted",
                "agent": "model",
                "created_at": now,
                "source": "posthoc_compile",
            },
            {
                "id": rejected_id,
                "kind": "rejected_alternative",
                "text": "A dashboard of neurons.",
                "status": "rejected",
                "agent": "model",
                "created_at": now,
                "source": "posthoc_compile",
            },
        ],
        "edges": [
            {
                "id": edge_id,
                "source_id": rejected_id,
                "target_id": node_id,
                "kind": "rejects",
                "created_at": now,
            }
        ],
        "model": {
            "provider": "file",
            "name": "unknown",
            "compile_mode": "posthoc",
        },
    }
    base.update(overrides)
    return base


def test_validators_load_and_refs_resolve():
    for name in (
        "thought-node.schema.json",
        "thought-edge.schema.json",
        "thought-graph.schema.json",
        "session.schema.json",
        "turn.schema.json",
        "attribution.schema.json",
        "fingerprint.schema.json",
        "probe.schema.json",
        "graph-diff.schema.json",
        "evidence-binding.schema.json",
        "neural-intervention.schema.json",
        "recurring-circuit.schema.json",
        "training-provenance.schema.json",
        "continuation-request.schema.json",
        "continuation-completion.schema.json",
        "continuation-cancellation.schema.json",
    ):
        v = load_validator(name)
        assert v is not None
    validate_graph(_minimal_graph_dict())


def test_packaged_schema_files_exist():
    for name in (
        "thought-node.schema.json",
        "thought-edge.schema.json",
        "thought-graph.schema.json",
        "session.schema.json",
        "turn.schema.json",
        "attribution.schema.json",
        "fingerprint.schema.json",
        "probe.schema.json",
        "graph-diff.schema.json",
        "evidence-binding.schema.json",
        "neural-intervention.schema.json",
        "recurring-circuit.schema.json",
        "training-provenance.schema.json",
        "continuation-request.schema.json",
        "continuation-completion.schema.json",
        "continuation-cancellation.schema.json",
    ):
        text = SCHEMA_DIR.joinpath(name).read_text(encoding="utf-8")
        json.loads(text)


def test_parent_graph_id_oneof_null_or_ulid():
    d = _minimal_graph_dict()
    d["parent_graph_id"] = None
    validate_graph(d)
    d["parent_graph_id"] = new_ulid()
    # integrity: fork.from_graph_id must match if fork present; here no fork
    validate_graph(d)
    d["parent_graph_id"] = ["not", "a", "ulid"]
    with pytest.raises(ValidationError):
        validate_graph(d)


def test_parent_graph_id_is_not_type_array_plus_pattern():
    schema = json.loads(
        SCHEMA_DIR.joinpath("thought-graph.schema.json").read_text(encoding="utf-8")
    )
    spec = schema["properties"]["parent_graph_id"]
    assert "oneOf" in spec
    assert spec.get("type") != "array"
    kinds = {tuple(sorted(opt.items())) if False else opt.get("type") for opt in spec["oneOf"]}
    assert "null" in kinds
    assert "string" in kinds


def test_extra_keys_rejected():
    d = _minimal_graph_dict()
    d["not_a_field"] = True
    with pytest.raises(ValidationError):
        validate_graph(d)
    node = d["nodes"][0]
    node["extra"] = 1
    d2 = _minimal_graph_dict()
    d2["nodes"][0]["extra"] = 1
    with pytest.raises(ValidationError):
        validate_graph(d2)


def test_edge_endpoint_must_exist():
    d = _minimal_graph_dict()
    d["edges"][0]["target_id"] = new_ulid()
    with pytest.raises(ValidationError):
        validate_graph(d)


def test_span_end_must_exceed_start_and_fit_prose():
    d = _minimal_graph_dict()
    d["nodes"][0]["span"] = {"start": 5, "end": 5, "unit": "char"}
    with pytest.raises(ValidationError):
        validate_graph(d)
    d = _minimal_graph_dict()
    d["nodes"][0]["span"] = {"start": 0, "end": 10_000, "unit": "char"}
    with pytest.raises(ValidationError):
        validate_graph(d)
    d = _minimal_graph_dict()
    d["nodes"][0]["span"] = {"start": 0, "end": 4, "unit": "char"}
    validate_graph(d)


def test_metadata_mapping_proxy_not_mutable():
    g = ThoughtGraph.from_dict(_minimal_graph_dict())
    assert isinstance(g.metadata, MappingProxyType)
    with pytest.raises(TypeError):
        g.metadata["x"] = 1  # type: ignore[index]


def test_from_dict_to_dict_roundtrip():
    d = _minimal_graph_dict()
    d["metadata"] = {"origin": "test"}
    g = ThoughtGraph.from_dict(d)
    again = ThoughtGraph.from_dict(g.to_dict())
    assert again.id == g.id
    assert again.nodes[0].text == g.nodes[0].text
    assert dict(again.metadata) == {"origin": "test"}


def test_to_dict_snapshots_metadata():
    d = _minimal_graph_dict()
    inner = {"k": "v"}
    d["metadata"] = inner
    g = ThoughtGraph.from_dict(d)
    dumped = g.to_dict()
    inner["k"] = "mutated"
    assert dumped["metadata"]["k"] == "v"


def test_session_and_turn_schema():
    now = now_iso()
    sid, tid = new_ulid(), new_ulid()
    validate_schema(
        "session.schema.json",
        {
            "schema_version": "1.0.0",
            "id": sid,
            "title": "origin",
            "created_at": now,
            "updated_at": now,
            "origin": "example:synthetic-origin",
            "head_graph_id": None,
            "head_turn_id": None,
        },
    )
    validate_schema(
        "turn.schema.json",
        {
            "schema_version": "1.0.0",
            "id": tid,
            "session_id": sid,
            "seq": 0,
            "role": "user",
            "created_at": now,
            "prose": "hello",
            "graph_id": None,
            "parent_turn_id": None,
            "fork_of_node_id": None,
            "provider": None,
        },
    )


def test_policy_warnings_zero_rejected_and_no_claim():
    now = now_iso()
    g = ThoughtGraph(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        session_id=new_ulid(),
        turn_id=new_ulid(),
        created_at=now,
        prose="x",
        nodes=(
            ThoughtNode(
                id=new_ulid(),
                kind="premise",
                text="only a premise",
                status="accepted",
                agent="model",
                created_at=now,
                source="posthoc_compile",
            ),
        ),
        edges=(),
        model=ModelInfo("none", "unknown", "posthoc"),
    )
    w = policy_warnings(g)
    assert any("rejected_alternative" in x for x in w)
    assert any("no claim" in x for x in w)


def test_policy_cycle_on_supports_shapes():
    now = now_iso()
    a, b = new_ulid(), new_ulid()
    g = ThoughtGraph(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        session_id=new_ulid(),
        turn_id=new_ulid(),
        created_at=now,
        prose="x",
        nodes=(
            ThoughtNode(a, "claim", "A", "accepted", "model", now, "posthoc_compile"),
            ThoughtNode(b, "judgment_call", "B", "accepted", "model", now, "posthoc_compile"),
        ),
        edges=(
            ThoughtEdge(new_ulid(), a, b, "supports", now),
            ThoughtEdge(new_ulid(), b, a, "shapes", now),
        ),
        model=ModelInfo("none", "unknown", "posthoc"),
    )
    w = policy_warnings(g)
    assert any("cycle" in x for x in w)
