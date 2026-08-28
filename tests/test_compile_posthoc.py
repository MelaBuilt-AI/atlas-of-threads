from __future__ import annotations

import json
from pathlib import Path

import pytest

from thought_archaeology.compile_common import CompileError
from thought_archaeology.compile_posthoc import compile_posthoc
from thought_archaeology.compile_structured import parse_graph_payload
from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import ModelInfo
from thought_archaeology.schema import policy_warnings

from tests.helpers import edge_triples, gold_edge_triples, gold_node_triples, node_triples


def test_parse_json_loads_first():
    payload = {
        "nodes": [{"local_id": "n1", "kind": "claim", "text": "C", "status": "accepted"}],
        "edges": [],
    }
    raw = json.dumps(payload)
    got, offset = parse_graph_payload(raw)
    assert got["nodes"][0]["text"] == "C"
    assert offset == 0


def test_parse_falls_back_to_fence():
    payload = {
        "nodes": [{"local_id": "n1", "kind": "claim", "text": "F", "status": "accepted"}],
        "edges": [],
    }
    raw = "not json\n```thought-graph\n" + json.dumps(payload) + "\n```\n"
    got, _ = parse_graph_payload(raw)
    assert got["nodes"][0]["text"] == "F"


def test_parse_failure_includes_original_error():
    with pytest.raises(CompileError, match="invalid thought-graph JSON"):
        parse_graph_payload("definitely not json and no fence")


def test_origin_gold_compile(fixtures_dir: Path, origin_gold: dict):
    transcript = (
        fixtures_dir / "transcripts" / "origin-conversation.jsonl"
    ).read_text(encoding="utf-8")
    rows = [json.loads(line) for line in transcript.splitlines() if line.strip()]
    assistant = next(r for r in rows if r["role"] == "assistant")
    gold_text = (fixtures_dir / "graphs" / "origin-conversation.gold.json").read_text(
        encoding="utf-8"
    )
    graph, warnings = compile_posthoc(
        assistant["text"],
        gold_text,
        session_id=new_ulid(),
        turn_id=new_ulid(),
        model=ModelInfo("file", "grok-4.6-build", "posthoc"),
        now=now_iso(),
    )
    assert node_triples(graph) == gold_node_triples(origin_gold)
    assert sorted(edge_triples(graph)) == sorted(gold_edge_triples(origin_gold))
    assert len(graph.nodes) == 18
    assert len(graph.edges) == 15
    assert policy_warnings(graph) == []
    assert warnings == []
    # never assert compiled ULIDs equal local_ids
    assert {n.id for n in graph.nodes}.isdisjoint(
        {n["local_id"] for n in origin_gold["nodes"]}
    )
    # DAG: no n18 supports n5
    by_text = {n.text: n for n in graph.nodes}
    n18 = by_text[origin_gold["nodes"][17]["text"]]
    n5 = next(n for n in graph.nodes if n.kind == "taste_call" and "neurons" in n.text)
    for e in graph.edges:
        if e.source_id == n18.id and e.target_id == n5.id:
            raise AssertionError("n18 supports n5 must not exist")
    assert graph.model.compile_mode == "posthoc"
    assert all(n.source == "posthoc_compile" for n in graph.nodes)


def test_simple_freeform_from_graph(fixtures_dir: Path, simple_gold: dict):
    prose = json.loads(
        (fixtures_dir / "transcripts" / "simple-freeform.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()[0]
    )["text"]
    graph, _ = compile_posthoc(
        prose,
        (fixtures_dir / "graphs" / "simple.gold.json").read_text(encoding="utf-8"),
        session_id=new_ulid(),
        turn_id=new_ulid(),
        model=ModelInfo("file", "unknown", "posthoc"),
        now=now_iso(),
    )
    assert node_triples(graph) == gold_node_triples(simple_gold)
    assert sorted(edge_triples(graph)) == sorted(gold_edge_triples(simple_gold))
