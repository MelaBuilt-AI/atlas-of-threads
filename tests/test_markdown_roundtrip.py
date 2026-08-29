from __future__ import annotations

import json
from pathlib import Path

import pytest

from thought_archaeology.fingerprint import Fingerprint
from thought_archaeology.models import ForkRef, SCHEMA_VERSION
from thought_archaeology.parse_md import DUMMY_SOURCE, DUMMY_TS, ParseError, parse_md
from thought_archaeology.render_md import render_md
from thought_archaeology.schema import validate_graph
from thought_archaeology.store import Store

from tests.helpers import (
    CANVAS_GRAPH_ID,
    CANVAS_NODES,
    FIXTURES,
    canvas_projection,
    simple_canvas_graph,
)
from tests.test_cli import run

GOLD_MD = FIXTURES / "canvases" / "simple.gold.md"


def test_render_matches_gold_fixture():
    graph = simple_canvas_graph()
    assert "do not render me" not in render_md(graph)
    assert render_md(graph) == GOLD_MD.read_text(encoding="utf-8")


def test_roundtrip_projection_and_dummy_fills():
    graph = simple_canvas_graph()
    parsed = parse_md(render_md(graph))
    assert canvas_projection(parsed) == canvas_projection(graph)
    validate_graph(parsed)
    assert parsed.created_at == DUMMY_TS
    assert parsed.turn_id == parsed.id
    assert parsed.model.provider == "none"
    assert parsed.model.name == "unknown"
    assert parsed.hidden_reasoning is None
    for node in parsed.nodes:
        assert node.created_at == DUMMY_TS
        assert node.source == DUMMY_SOURCE
        assert node.span is None
    for edge in parsed.edges:
        assert edge.created_at == DUMMY_TS
        assert len(edge.id) == 26
    assert parsed.fork is None
    assert parsed.parent_graph_id is None


def test_roundtrip_fork_fields():
    parent = "01M14CANVASAAAAAAAAAAA00P1"
    node = CANVAS_NODES["t1"]
    graph = simple_canvas_graph(
        fork=ForkRef(
            from_graph_id=parent,
            from_node_id=node,
            discarded_graph_id=parent,
            reason="secret reason",
        )
    )
    md = render_md(graph)
    assert "secret reason" not in md
    assert f"parent graph: `{parent}`" in md
    assert f"fork node: `{node}`" in md
    assert f"discarded: `{parent}`" in md
    parsed = parse_md(md)
    assert canvas_projection(parsed) == canvas_projection(graph)
    assert parsed.fork is not None
    assert parsed.fork.reason is None


def test_parse_error_parent_without_fork_node():
    graph = simple_canvas_graph(
        fork=ForkRef(
            from_graph_id="01M14CANVASAAAAAAAAAAA00P1",
            from_node_id=CANVAS_NODES["t1"],
            discarded_graph_id=None,
        )
    )
    md = render_md(graph)
    broken = md.replace(
        f"fork node: `{CANVAS_NODES['t1']}`",
        "fork node: none",
    )
    with pytest.raises(ParseError, match="fork node"):
        parse_md(broken)


def test_dual_archaeology_only_with_fingerprint():
    graph = simple_canvas_graph()
    assert "## Dual archaeology" not in render_md(graph)
    fp = Fingerprint.from_dict(
        {
            "schema_version": SCHEMA_VERSION,
            "id": "01M14CANVASAAAAAAAAAAA00F1",
            "created_at": "2026-08-27T00:00:00Z",
            "session_ids": [graph.session_id],
            "min_sessions": 2,
            "merge_threshold": 0.8,
            "model_judgments": [
                {
                    "canonical": "Invent the medium first.",
                    "normalized": "invent the medium first",
                    "count": 1,
                    "session_ids": [graph.session_id],
                    "node_ids": [CANVAS_NODES["t1"]],
                    "recurrence": "emerging",
                }
            ],
            "human_vetoes": [],
            "divergence": [],
        }
    )
    md = render_md(graph, fingerprint=fp)
    assert "## Dual archaeology" in md
    assert "Invent the medium first." in md
    parsed = parse_md(md)
    assert canvas_projection(parsed) == canvas_projection(graph)


def test_cli_canvas_and_export_wiki(tmp_path: Path):
    store = tmp_path / "data"
    code, out, err = run(["init", "--title", "c"], store=store)
    sid = out.strip()
    code, out, err = run(
        [
            "compile",
            "--session",
            sid,
            "--mode",
            "posthoc",
            "--transcript",
            str(FIXTURES / "transcripts" / "simple-freeform.jsonl"),
            "--from-graph",
            str(FIXTURES / "graphs" / "simple.gold.json"),
        ],
        store=store,
    )
    assert code == 0, err
    gid = out.strip()
    canvas_out = tmp_path / "canvas.md"
    code, out, err = run(
        ["canvas", gid, "--out", str(canvas_out)],
        store=store,
    )
    assert code == 0, err
    text = canvas_out.read_text(encoding="utf-8")
    assert "type: overview" in text
    assert "[[wiki/Concepts/thought-archaeology|Thought archaeology]]" in text
    assert "story" in text
    assert "do not render" not in text
    st = Store(store)
    stored = st.canvas_path(sid, gid)
    assert stored.is_file()
    wiki_out = tmp_path / "wiki-drop.md"
    code, out, err = run(
        ["export-wiki", gid, "--out", str(wiki_out)],
        store=store,
    )
    assert code == 0, err
    assert wiki_out.is_file()
    code, _, err = run(["export-wiki", gid], store=store)
    assert code == 2
    vault_index = tmp_path / "wiki" / "index.md"
    vault_index.parent.mkdir()
    vault_index.write_text("# index\n", encoding="utf-8")
    code, _, err = run(
        ["export-wiki", gid, "--out", str(vault_index)],
        store=store,
    )
    assert code == 2
    assert "must not write wiki/index.md" in err
    assert vault_index.read_text(encoding="utf-8") == "# index\n"


def test_cli_canvas_with_fingerprint(tmp_path: Path):
    store = tmp_path / "data"
    code, out, err = run(["init", "--title", "c"], store=store)
    sid = out.strip()
    code, out, err = run(
        [
            "compile",
            "--session",
            sid,
            "--mode",
            "posthoc",
            "--transcript",
            str(FIXTURES / "transcripts" / "simple-freeform.jsonl"),
            "--from-graph",
            str(FIXTURES / "graphs" / "simple.gold.json"),
        ],
        store=store,
    )
    gid = out.strip()
    code, out, err = run(["fingerprint", "--session", sid], store=store)
    assert code == 0, err
    fid = out.strip()
    fp_path = store / "fingerprints" / f"{fid}.json"
    out_md = tmp_path / "with-fp.md"
    code, out, err = run(
        ["canvas", gid, "--fingerprint", str(fp_path), "--out", str(out_md)],
        store=store,
    )
    assert code == 0, err
    body = out_md.read_text(encoding="utf-8")
    assert "## Dual archaeology" in body
    assert "judgment ·" in body


def test_gold_parse_is_schema_valid():
    parsed = parse_md(GOLD_MD.read_text(encoding="utf-8"))
    validate_graph(parsed)
    assert parsed.id == CANVAS_GRAPH_ID
    assert parsed.nodes[0].kind == "claim"
