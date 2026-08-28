from __future__ import annotations

import os
from pathlib import Path

import pytest

from thought_archaeology.compile_posthoc import compile_posthoc
from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import SCHEMA_VERSION, ModelInfo, Turn
from thought_archaeology.store import Store, StoreError, fallback_store_path, resolve_store_path


def _compile_simple(store: Store, session_id: str, gold: dict):
    import json

    now = now_iso()
    turn_id = new_ulid()
    graph, _ = compile_posthoc(
        "The product is the medium, not the microscope.",
        json.dumps(gold),
        session_id=session_id,
        turn_id=turn_id,
        model=ModelInfo("file", "unknown", "posthoc"),
        now=now,
    )
    return graph, turn_id


def test_init_creates_tree_and_modes(tmp_path: Path):
    store = Store(tmp_path / "data")
    session = store.init_session("origin", origin="example:synthetic-origin")
    root = store.root
    assert (root / "STORE_VERSION").read_text(encoding="utf-8").strip() == "1"
    assert (root / "store.log.jsonl").is_file()
    sdir = root / "sessions" / session.id
    assert (sdir / "session.json").is_file()
    turns = sdir / "turns.jsonl"
    assert turns.is_file()
    assert turns.stat().st_size == 0
    assert (sdir / "graphs").is_dir()
    assert oct(sdir.stat().st_mode & 0o777) == oct(0o700)
    assert oct((sdir / "session.json").stat().st_mode & 0o777) == oct(0o600)
    assert oct(turns.stat().st_mode & 0o777) == oct(0o600)
    raw = session.to_dict()
    assert raw["head_graph_id"] is None
    assert raw["head_turn_id"] is None
    assert raw["title"] == "origin"


def test_write_once_raises(tmp_path: Path, simple_gold: dict):
    store = Store(tmp_path / "data")
    session = store.init_session("t")
    graph, turn_id = _compile_simple(store, session.id, simple_gold)
    store.write_graph(graph)
    with pytest.raises(StoreError, match="write-once"):
        store.write_graph(graph)


def test_session_json_is_only_mutable(tmp_path: Path, simple_gold: dict):
    store = Store(tmp_path / "data")
    session = store.init_session("t")
    graph, turn_id = _compile_simple(store, session.id, simple_gold)
    path = store.write_graph(graph)
    before = path.read_bytes()
    store.append_turn(
        Turn(
            schema_version=SCHEMA_VERSION,
            id=turn_id,
            session_id=session.id,
            seq=0,
            role="assistant",
            created_at=now_iso(),
            prose=graph.prose,
            graph_id=graph.id,
            parent_turn_id=None,
            fork_of_node_id=None,
            provider="file",
        )
    )
    session_path = store.session_dir(session.id) / "session.json"
    before_session = session_path.read_bytes()
    store.update_session_head(session.id, graph_id=graph.id, turn_id=turn_id)
    after = path.read_bytes()
    assert before == after
    assert session_path.read_bytes() != before_session
    updated = store.load_session(session.id)
    assert updated.head_graph_id == graph.id
    assert updated.head_turn_id == turn_id
    assert updated.title == "t"
    assert updated.created_at == session.created_at
    assert updated.origin == session.origin
    assert updated.tags == session.tags


def test_duplicate_seq_rejected(tmp_path: Path):
    store = Store(tmp_path / "data")
    session = store.init_session("t")
    t = Turn(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        session_id=session.id,
        seq=0,
        role="user",
        created_at=now_iso(),
        prose="hi",
        graph_id=None,
        parent_turn_id=None,
        fork_of_node_id=None,
    )
    store.append_turn(t)
    t2 = Turn(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        session_id=session.id,
        seq=0,
        role="assistant",
        created_at=now_iso(),
        prose="yo",
        graph_id=None,
        parent_turn_id=t.id,
        fork_of_node_id=None,
    )
    with pytest.raises(StoreError, match="append-only"):
        store.append_turn(t2)


def test_find_nodes(tmp_path: Path, simple_gold: dict):
    store = Store(tmp_path / "data")
    session = store.init_session("t")
    graph, _ = _compile_simple(store, session.id, simple_gold)
    store.write_graph(graph)
    nid = graph.nodes[0].id
    found = store.find_nodes(nid)
    assert len(found) == 1
    g, n = found[0]
    assert g.id == graph.id
    assert n.text == graph.nodes[0].text
    assert store.find_nodes(new_ulid()) == []


def test_resolve_store_path_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    explicit = tmp_path / "explicit"
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TA_STORE", raising=False)
    assert resolve_store_path(str(explicit)) == explicit.resolve()

    envdir = tmp_path / "env"
    envdir.mkdir()
    monkeypatch.setenv("TA_STORE", str(envdir))
    assert resolve_store_path(None) == envdir.resolve()

    monkeypatch.delenv("TA_STORE")
    data = tmp_path / "data"
    data.mkdir()
    assert resolve_store_path(None) == data.resolve()

    data.rmdir()
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg))
    assert resolve_store_path(None) == (xdg / "thought-archaeology").resolve()
    monkeypatch.delenv("XDG_DATA_HOME")
    assert resolve_store_path(None) == fallback_store_path()
    assert "/home/example/atlas-of-threads/data" not in str(
        resolve_store_path(None)
    )
