from __future__ import annotations

import json
from pathlib import Path

import pytest

from thought_archaeology.compile_common import bind_span, finalize
from thought_archaeology.compile_structured import compile_structured, extract_thought_graph_json
from thought_archaeology.compile_common import CompileError
from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import ModelInfo, Span

from tests.helpers import edge_triples, gold_edge_triples, gold_node_triples, node_triples


def test_bind_span_exact_and_prefix():
    prose = "Hello world, this is a test of span binding."
    span = bind_span(prose, "this is a test of span binding.")
    assert span == Span(13, 13 + len("this is a test of span binding."))
    long = "x" * 200
    assert bind_span("nope", long) is None
    # Prefix fallback only when node_text is longer than 80 chars.
    prose80 = "A" * 120
    assert bind_span(prose80, "A" * 80 + "NOT_IN_PROSE") == Span(0, 80)
    assert bind_span("", "x") is None
    assert bind_span("abc", "") is None


def test_extract_last_thought_graph_fence():
    body = json.dumps(
        {
            "nodes": [
                {"local_id": "n1", "kind": "claim", "text": "A", "status": "accepted"}
            ],
            "edges": [],
        }
    )
    decoy = json.dumps(
        {
            "nodes": [
                {"local_id": "n1", "kind": "claim", "text": "OLD", "status": "accepted"}
            ],
            "edges": [],
        }
    )
    text = f"first\n```thought-graph\n{decoy}\n```\nmore prose\n```thought-graph\n{body}\n```\n"
    prose, payload, _ = extract_thought_graph_json(text)
    assert payload["nodes"][0]["text"] == "A"
    assert "more prose" in prose


def test_extract_pair_delimiter():
    body = '{"nodes":[{"local_id":"n1","kind":"claim","text":"P","status":"accepted"}],"edges":[]}'
    text = f"hello\n---thought-graph---\n{body}\n---end-thought-graph---\n"
    prose, payload, _ = extract_thought_graph_json(text)
    assert prose == "hello"
    assert payload["nodes"][0]["text"] == "P"


def test_extract_last_json_fence_fallback():
    body = '{"nodes":[{"local_id":"n1","kind":"claim","text":"J","status":"accepted"}],"edges":[]}'
    text = f"prose here\n```json\n{body}\n```\n"
    prose, payload, _ = extract_thought_graph_json(text)
    assert prose == "prose here"
    assert payload["nodes"][0]["text"] == "J"


def test_invalid_json_does_not_eval():
    with pytest.raises(CompileError, match="invalid thought-graph JSON"):
        extract_thought_graph_json("```thought-graph\n{not json}\n```")


def test_compile_simple_structured(fixtures_dir: Path, simple_gold: dict):
    raw = (fixtures_dir / "transcripts" / "simple-structured.txt").read_text(
        encoding="utf-8"
    )
    graph, warnings = compile_structured(
        raw,
        session_id=new_ulid(),
        turn_id=new_ulid(),
        model=ModelInfo("none", "unknown", "structured_emit"),
        now=now_iso(),
    )
    assert not any("cycle" in w for w in warnings)
    assert node_triples(graph) == gold_node_triples(simple_gold)
    assert sorted(edge_triples(graph)) == sorted(gold_edge_triples(simple_gold))
    assert graph.model.compile_mode == "structured_emit"
    assert all(n.source == "structured_emit" for n in graph.nodes)
    # ids are ULIDs, not local_id
    assert all(len(n.id) == 26 for n in graph.nodes)
    assert all(n.id != loc for n in graph.nodes for loc in ("n1", "n2", "n3"))
    # span bound for the claim which appears in prose
    claim = next(n for n in graph.nodes if n.kind == "claim")
    assert claim.span is not None
    assert graph.prose[claim.span.start : claim.span.end] in (
        claim.text,
        claim.text[:80],
    )


def test_finalize_defaults_and_orphan_error():
    now = now_iso()
    graph = finalize(
        session_id=new_ulid(),
        turn_id=new_ulid(),
        prose="x",
        raw_nodes=[
            {"local_id": "n1", "kind": "claim", "text": "C"},
            {"local_id": "n2", "kind": "rejected_alternative", "text": "R"},
            {"local_id": "n3", "kind": "uncertainty", "text": "U"},
        ],
        raw_edges=[{"from": "n2", "to": "n1", "kind": "rejects"}],
        model=ModelInfo("none", "unknown", "posthoc"),
        now=now,
    )
    by_kind = {n.kind: n for n in graph.nodes}
    assert by_kind["claim"].status == "accepted"
    assert by_kind["rejected_alternative"].status == "rejected"
    assert by_kind["uncertainty"].status == "uncertain"
    assert by_kind["claim"].agent == "model"
    assert by_kind["claim"].source == "posthoc_compile"
    with pytest.raises(CompileError, match="endpoint missing"):
        finalize(
            session_id=new_ulid(),
            turn_id=new_ulid(),
            prose="x",
            raw_nodes=[{"local_id": "n1", "kind": "claim", "text": "C"}],
            raw_edges=[{"from": "n1", "to": "missing", "kind": "supports"}],
            model=ModelInfo("none", "unknown", "posthoc"),
            now=now,
        )


def test_empty_prose_warned():
    body = json.dumps(
        {
            "nodes": [
                {"local_id": "n1", "kind": "claim", "text": "C", "status": "accepted"},
                {
                    "local_id": "n2",
                    "kind": "rejected_alternative",
                    "text": "R",
                    "status": "rejected",
                },
            ],
            "edges": [{"from": "n2", "to": "n1", "kind": "rejects"}],
        }
    )
    graph, warnings = compile_structured(
        f"```thought-graph\n{body}\n```",
        session_id=new_ulid(),
        turn_id=new_ulid(),
        model=ModelInfo("none", "unknown", "structured_emit"),
        now=now_iso(),
    )
    assert any("empty" in w for w in warnings)
    assert graph.prose == ""
