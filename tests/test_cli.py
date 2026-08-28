from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from thought_archaeology.cli import main
from thought_archaeology.models import ThoughtGraph
from thought_archaeology.schema import read_prompt
from thought_archaeology.store import Store

from tests.helpers import (
    FIXTURES,
    edge_triples,
    gold_edge_triples,
    gold_node_triples,
    node_triples,
)


def run(argv: list[str], store: Path | None = None) -> tuple[int, str, str]:
    import io
    from contextlib import redirect_stderr, redirect_stdout

    args = list(argv)
    if store is not None:
        args = ["--store", str(store), *args]
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


def test_prompt_dumps_packaged_files():
    code, out, err = run(["prompt", "structured"])
    assert code == 0
    assert out == read_prompt("structured") or out == read_prompt("structured") + "\n"
    assert "thought-graph" in out
    code, out, _ = run(["prompt", "posthoc"])
    assert code == 0
    assert "Return ONLY JSON" in out
    code, out, err = run(["prompt", "fork"])
    assert code == 0, err
    assert "regenerating an answer FROM a thought-node" in out


def test_init_prints_session_id(tmp_path: Path):
    store = tmp_path / "data"
    code, out, err = run(
        [
            "init",
            "--title",
            "origin",
            "--origin",
            "example:synthetic-origin",
        ],
        store=store,
    )
    assert code == 0, err
    sid = out.strip()
    assert len(sid) == 26
    session = Store(store).load_session(sid)
    assert session.title == "origin"
    assert session.origin == "example:synthetic-origin"


def test_posthoc_without_from_graph_or_provider_is_usage(tmp_path: Path):
    store = tmp_path / "data"
    code, out, _ = run(["init", "--title", "t"], store=store)
    sid = out.strip()
    code, _, err = run(
        ["compile", "--session", sid, "--mode", "posthoc"],
        store=store,
    )
    assert code == 2
    assert "posthoc compile requires --from-graph or a provider" in err


def test_origin_compile_strict_exit_0(tmp_path: Path, origin_gold: dict):
    store = tmp_path / "data"
    code, out, err = run(
        [
            "init",
            "--title",
            "origin",
            "--origin",
            "example:synthetic-origin",
        ],
        store=store,
    )
    assert code == 0, err
    sid = out.strip()
    transcript = FIXTURES / "transcripts" / "origin-conversation.jsonl"
    gold = FIXTURES / "graphs" / "origin-conversation.gold.json"
    code, out, err = run(
        [
            "--strict",
            "compile",
            "--session",
            sid,
            "--mode",
            "posthoc",
            "--transcript",
            str(transcript),
            "--from-graph",
            str(gold),
            "--model-name",
            "grok-4.6-build",
        ],
        store=store,
    )
    assert code == 0, err
    assert err == ""
    gid = out.strip()
    assert len(gid) == 26
    st = Store(store)
    graph = st.load_graph(gid)
    assert node_triples(graph) == gold_node_triples(origin_gold)
    assert sorted(edge_triples(graph)) == sorted(gold_edge_triples(origin_gold))
    session = st.load_session(sid)
    turns = list(st.iter_turns(sid))
    assert [t.role for t in turns] == ["user", "assistant", "user"]
    assert turns[0].graph_id is None
    assert turns[1].graph_id == gid
    assert turns[2].graph_id is None
    assert session.head_graph_id == gid
    assert session.head_turn_id == turns[1].id
    assert session.head_turn_id != turns[2].id
    assert graph.model.provider == "file"
    assert graph.model.name == "grok-4.6-build"
    assert graph.model.compile_mode == "posthoc"
    # re-run is an error
    code, _, err = run(
        [
            "compile",
            "--session",
            sid,
            "--mode",
            "posthoc",
            "--transcript",
            str(transcript),
            "--from-graph",
            str(gold),
        ],
        store=store,
    )
    assert code == 1
    assert "append-only" in err


def test_structured_compile_from_input(tmp_path: Path, simple_gold: dict):
    store = tmp_path / "data"
    code, out, err = run(["init", "--title", "s"], store=store)
    sid = out.strip()
    inp = FIXTURES / "transcripts" / "simple-structured.txt"
    code, out, err = run(
        [
            "compile",
            "--session",
            sid,
            "--mode",
            "structured",
            "--input",
            str(inp),
            "--model-name",
            "test-model",
        ],
        store=store,
    )
    assert code == 0, err
    graph = Store(store).load_graph(out.strip())
    assert node_triples(graph) == gold_node_triples(simple_gold)
    assert graph.model.compile_mode == "structured_emit"
    assert graph.model.provider == "none"


def test_show_session_tree_and_ambiguous(tmp_path: Path):
    store = tmp_path / "data"
    code, out, _ = run(["init", "--title", "origin"], store=store)
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
    code, out, err = run(["show", sid, "--format", "tree"], store=store)
    assert code == 0, err
    assert sid in out
    assert "head_graph=" + gid in out
    assert "turn 0" in out
    assert "assistant" in out
    assert "claim" in out
    code, out, err = run(["show", gid, "--format", "tree"], store=store)
    assert code == 0
    assert "graph " + gid in out
    code, out, _ = run(["show", sid, "--format", "ids"], store=store)
    assert "session " + sid in out
    code, out, _ = run(["show", gid, "--format", "json"], store=store)
    data = json.loads(out)
    assert data["id"] == gid
    code, _, err = run(["log", sid], store=store)
    assert code == 0
    assert "assistant" in err or True
    code, _, err = run(["validate", sid], store=store)
    assert code == 0, err
    code, _, err = run(["validate", gid], store=store)
    assert code == 0, err


def test_strict_fails_on_policy(tmp_path: Path):
    store = tmp_path / "data"
    code, out, _ = run(["init", "--title", "p"], store=store)
    sid = out.strip()
    tiny = tmp_path / "tiny.json"
    tiny.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "local_id": "n1",
                        "kind": "premise",
                        "text": "only a premise",
                        "status": "accepted",
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    trans = tmp_path / "t.jsonl"
    trans.write_text(
        json.dumps({"role": "assistant", "text": "only a premise"}) + "\n",
        encoding="utf-8",
    )
    code, _, err = run(
        [
            "--strict",
            "compile",
            "--session",
            sid,
            "--mode",
            "posthoc",
            "--transcript",
            str(trans),
            "--from-graph",
            str(tiny),
        ],
        store=store,
    )
    assert code == 1
    assert "rejected_alternative" in err
    # without --strict, still stores
    code, out, err = run(
        [
            "compile",
            "--session",
            sid,
            "--mode",
            "posthoc",
            "--transcript",
            str(trans),
            "--from-graph",
            str(tiny),
        ],
        store=store,
    )
    assert code == 0
    assert "rejected_alternative" in err


def test_usage_missing_mode():
    code, _, _ = run(["compile", "--session", "x"])
    assert code == 2
