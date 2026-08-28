from __future__ import annotations

import json
from pathlib import Path

from thought_archaeology.fork import omit_set, parse_regen
from thought_archaeology.inhabit import inhabit
from thought_archaeology.models import ThoughtGraph
from thought_archaeology.store import Store

from tests.helpers import FIXTURES, edge_triples
from tests.test_cli import run

ORIGIN_GOLD = FIXTURES / "graphs" / "origin-conversation.gold.json"
ORIGIN_TRANSCRIPT = FIXTURES / "transcripts" / "origin-conversation.jsonl"
DEPENDS_GOLD = FIXTURES / "graphs" / "depends-on.gold.json"
N6_REGEN = FIXTURES / "graphs" / "origin-fork-n6-regen.gold.json"

N6_TEXT_PREFIX = "Invent the medium first."
N6_OMIT_LOCAL = ("n6", "n9", "n10")
N6_COPY_LOCAL = (
    "n1",
    "n2",
    "n3",
    "n4",
    "n5",
    "n7",
    "n8",
    "n11",
    "n12",
    "n13",
    "n14",
    "n15",
    "n16",
    "n17",
    "n18",
)
N6_SURVIVING_EDGES = (
    ("n1", "n5", "supports"),
    ("n2", "n4", "supports"),
    ("n3", "n4", "supports"),
    ("n7", "n4", "analogizes"),
    ("n8", "n5", "analogizes"),
    ("n5", "n18", "taste_of"),
    ("n17", "n5", "taste_of"),
    ("n11", "n4", "rejects"),
    ("n12", "n5", "rejects"),
    ("n13", "n4", "rejects"),
)
N6_DROPPED_EDGES = (
    ("n6", "n9", "taste_of"),
    ("n9", "n10", "supports"),
    ("n15", "n6", "rejects"),
    ("n14", "n10", "rejects"),
    ("n16", "n10", "qualifies"),
)


def _compile_gold(
    store: Path,
    gold: Path,
    *,
    transcript: Path | None = None,
    title: str = "t",
) -> tuple[str, str]:
    code, out, err = run(["init", "--title", title], store=store)
    assert code == 0, err
    sid = out.strip()
    argv = [
        "compile",
        "--session",
        sid,
        "--mode",
        "posthoc",
        "--from-graph",
        str(gold),
    ]
    if transcript is not None:
        argv.extend(["--transcript", str(transcript)])
    code, out, err = run(argv, store=store)
    assert code == 0, err
    return sid, out.strip()


def _origin(tmp_path: Path) -> tuple[Store, Path, str, ThoughtGraph, dict]:
    store_path = tmp_path / "data"
    sid, gid = _compile_gold(
        store_path,
        ORIGIN_GOLD,
        transcript=ORIGIN_TRANSCRIPT,
        title="origin",
    )
    st = Store(store_path)
    gold = json.loads(ORIGIN_GOLD.read_text(encoding="utf-8"))
    return st, store_path, sid, st.load_graph(gid), gold


def local_map(graph: ThoughtGraph, gold: dict) -> dict[str, str]:
    by = {(n.kind, n.text): n.id for n in graph.nodes}
    return {raw["local_id"]: by[(raw["kind"], raw["text"])] for raw in gold["nodes"]}


def test_omit_set_n6(tmp_path: Path):
    st, _store, _sid, g0, gold = _origin(tmp_path)
    ids = local_map(g0, gold)
    n6 = ids["n6"]
    omit = omit_set(g0, n6)
    assert omit == {ids[k] for k in N6_OMIT_LOCAL}


def test_omit_set_depends_on_table(tmp_path: Path):
    store_path = tmp_path / "data"
    sid, gid = _compile_gold(store_path, DEPENDS_GOLD)
    st = Store(store_path)
    g0 = st.load_graph(gid)
    gold = json.loads(DEPENDS_GOLD.read_text(encoding="utf-8"))
    ids = local_map(g0, gold)
    a, b, r = ids["A"], ids["B"], ids["R"]
    assert omit_set(g0, b) == {b, a}
    assert omit_set(g0, a) == {a}

    code, out, err = run(["fork", b, "--session", sid], store=store_path)
    assert code == 0, err
    g_b = st.load_graph(out.strip())
    assert {n.id for n in g_b.nodes} == {r}
    assert all(n.id != a and n.id != b for n in g_b.nodes)

    # fork A off the original graph (not the new head)
    code, out, err = run(
        ["fork", a, "--session", sid, "--graph", gid], store=store_path
    )
    assert code == 0, err
    g_a = st.load_graph(out.strip())
    assert {n.id for n in g_a.nodes} == {b, r}
    assert a not in {n.id for n in g_a.nodes}


def test_fork_n6_integrity_invariants(tmp_path: Path):
    st, store_path, sid, g0, gold = _origin(tmp_path)
    g0_path = st.session_dir(sid) / "graphs" / f"{g0.id}.json"
    g0_bytes = g0_path.read_bytes()
    turns_path = st.session_dir(sid) / "turns.jsonl"
    turns_before = turns_path.read_bytes()
    session_before = st.load_session(sid)

    ids = local_map(g0, gold)
    n6 = ids["n6"]
    n6_node = next(n for n in g0.nodes if n.id == n6)
    assert n6_node.text.startswith(N6_TEXT_PREFIX)

    code, out, err = run(
        ["fork", n6, "--session", sid, "--reason", "accept chain except this cut"],
        store=store_path,
    )
    assert code == 0, err
    g1_id = out.strip()
    g1 = st.load_graph(g1_id)

    assert g1.parent_graph_id == g0.id
    assert g1.fork is not None
    assert g1.fork.from_graph_id == g1.parent_graph_id == g0.id
    assert g1.fork.from_node_id == n6
    assert g1.fork.discarded_graph_id == g0.id
    assert g0_path.read_bytes() == g0_bytes
    assert n6 not in {n.id for n in g1.nodes}
    assert {n.id for n in g1.nodes} == {ids[k] for k in N6_COPY_LOCAL}

    g0_by_id = {n.id: n for n in g0.nodes}
    for node in g1.nodes:
        parent = g0_by_id[node.id]
        assert (node.id, node.kind, node.text) == (parent.id, parent.kind, parent.text)
        assert node.status == parent.status
        assert node.agent == parent.agent
        assert node.created_at == parent.created_at
        assert node.source == parent.source
        assert node.source != "fork"

    g1_node_ids = {n.id for n in g1.nodes}
    for edge in g1.edges:
        assert edge.source_id in g1_node_ids
        assert edge.target_id in g1_node_ids
    g0_edge_ids = {e.id for e in g0.edges}
    g1_edge_ids = {e.id for e in g1.edges}
    assert g0_edge_ids.isdisjoint(g1_edge_ids)

    def triple_from_local(local_from: str, local_to: str, kind: str) -> tuple[str, str, str]:
        src = g0_by_id[ids[local_from]]
        tgt = g0_by_id[ids[local_to]]
        return (f"{src.kind}\0{src.text}", kind, f"{tgt.kind}\0{tgt.text}")

    got_edges = set(edge_triples(g1))
    assert got_edges == {triple_from_local(*t) for t in N6_SURVIVING_EDGES}
    dropped = {triple_from_local(*t) for t in N6_DROPPED_EDGES}
    assert dropped.isdisjoint(got_edges)

    copied_texts = {n.text for n in g1.nodes}
    for local in ("n14", "n15", "n16"):
        assert g0_by_id[ids[local]].text in copied_texts

    assert g1.prose == "(fork pending regeneration)"

    turns_after = turns_path.read_bytes()
    assert turns_after.startswith(turns_before)
    assert len(turns_after) > len(turns_before)
    turns = list(st.iter_turns(sid))
    new_turn = turns[-1]
    assert new_turn.graph_id == g1.id
    assert new_turn.fork_of_node_id == n6
    assert new_turn.role == "human_edit"
    assert new_turn.id == g1.turn_id

    session = st.load_session(sid)
    assert session.head_graph_id == g1.id
    assert session.head_turn_id == new_turn.id
    assert session.updated_at >= session_before.updated_at
    assert session.head_graph_id != session_before.head_graph_id
    assert session.id == session_before.id
    assert session.title == session_before.title
    assert session.origin == session_before.origin
    assert session.created_at == session_before.created_at
    assert session.tags == session_before.tags
    assert session.schema_version == session_before.schema_version

    code, _, err = run(["validate", sid], store=store_path)
    assert code == 0, err


def test_fork_regen_new_ulids_and_source(tmp_path: Path):
    st, store_path, sid, g0, gold = _origin(tmp_path)
    ids = local_map(g0, gold)
    n6 = ids["n6"]
    g0_ids = {n.id for n in g0.nodes}
    code, out, err = run(
        ["fork", n6, "--session", sid, "--from-graph", str(N6_REGEN)],
        store=store_path,
    )
    assert code == 0, err
    g1 = st.load_graph(out.strip())
    regen_gold = json.loads(N6_REGEN.read_text(encoding="utf-8"))
    new_nodes = [n for n in g1.nodes if n.id not in g0_ids]
    assert {n.text for n in new_nodes} == {raw["text"] for raw in regen_gold["nodes"]}
    for node in new_nodes:
        assert node.id not in g0_ids
        assert node.source == "posthoc_compile"
        assert node.source != "fork"
        assert node.created_at == g1.created_at
    assert n6 not in {n.id for n in g1.nodes}
    turns = list(st.iter_turns(sid))
    assert turns[-1].role == "assistant"
    assert turns[-1].provider == "file"


def test_veto_copies_all_null_discarded(tmp_path: Path):
    st, store_path, sid, g0, gold = _origin(tmp_path)
    g0_path = st.session_dir(sid) / "graphs" / f"{g0.id}.json"
    g0_bytes = g0_path.read_bytes()
    ids = local_map(g0, gold)
    n6 = ids["n6"]
    reason = "this taste-call is the wrong cut"
    code, out, err = run(
        ["veto", n6, "--session", sid, "--reason", reason],
        store=store_path,
    )
    assert code == 0, err
    g1 = st.load_graph(out.strip())
    assert g0_path.read_bytes() == g0_bytes
    assert g1.parent_graph_id == g0.id
    assert g1.fork is not None
    assert g1.fork.from_graph_id == g0.id
    assert g1.fork.from_node_id == n6
    assert g1.fork.discarded_graph_id is None
    assert g1.fork.reason == reason
    assert g1.prose == g0.prose
    copied = [n for n in g1.nodes if n.id in {x.id for x in g0.nodes}]
    assert {n.id for n in copied} == {n.id for n in g0.nodes}
    for node in copied:
        parent = next(n for n in g0.nodes if n.id == node.id)
        assert (node.kind, node.text, node.status) == (
            parent.kind,
            parent.text,
            parent.status,
        )
    veto_nodes = [n for n in g1.nodes if n.id not in {x.id for x in g0.nodes}]
    assert len(veto_nodes) == 1
    vn = veto_nodes[0]
    assert vn.kind == "rejected_alternative"
    assert vn.agent == "human"
    assert vn.status == "vetoed"
    assert vn.source == "human"
    assert vn.text == reason
    veto_edges = [e for e in g1.edges if e.kind == "vetoes"]
    assert len(veto_edges) == 1
    assert veto_edges[0].source_id == vn.id
    assert veto_edges[0].target_id == n6
    g0_edge_ids = {e.id for e in g0.edges}
    copied_edge_ids = {e.id for e in g1.edges if e.kind != "vetoes"}
    assert g0_edge_ids.isdisjoint(copied_edge_ids)
    turns = list(st.iter_turns(sid))
    assert turns[-1].role == "human_edit"
    assert turns[-1].fork_of_node_id == n6
    assert turns[-1].graph_id == g1.id
    code, _, err = run(["validate", sid], store=store_path)
    assert code == 0, err


def test_inhabit_fork_children_and_rejected_siblings(tmp_path: Path):
    st, store_path, sid, g0, gold = _origin(tmp_path)
    ids = local_map(g0, gold)
    n6 = ids["n6"]
    n15 = ids["n15"]
    code, out, err = run(["fork", n6, "--session", sid], store=store_path)
    assert code == 0, err
    g1_id = out.strip()

    view = inhabit(st, n6, session_id=sid)
    assert view.graph.id == g0.id  # n6 omitted from head G1
    assert view.node.id == n6
    shaped_ids = {n.id for n in view.shaped}
    assert shaped_ids == {ids["n9"], ids["n10"]}
    sibling_ids = {n.id for n in view.rejected_siblings}
    assert n15 in sibling_ids
    child_ids = {g.id for g in view.fork_children}
    assert g1_id in child_ids

    code, out, err = run(["inhabit", n6, "--session", sid], store=store_path)
    assert code == 0, err
    assert n6 in out
    assert "forks from here" in out
    assert g1_id in out
    assert "shaped" in out

    copied = ids["n1"]
    view_head = inhabit(st, copied, session_id=sid)
    assert view_head.graph.id == g1_id  # head contains n1


def test_inhabit_missing_node(tmp_path: Path):
    store_path = tmp_path / "data"
    code, out, err = run(["init", "--title", "t"], store=store_path)
    sid = out.strip()
    code, _, err = run(
        ["inhabit", "01AAAAAAAAAAAAAAAAAAAAAAAA", "--session", sid],
        store=store_path,
    )
    assert code == 3
    assert "not found" in err


def test_validate_fails_on_dangling_parent(tmp_path: Path):
    st, store_path, sid, g0, gold = _origin(tmp_path)
    ids = local_map(g0, gold)
    n6 = ids["n6"]
    code, out, err = run(["fork", n6, "--session", sid], store=store_path)
    assert code == 0, err
    g1 = st.load_graph(out.strip())
    raw_path = st.session_dir(sid) / "graphs" / f"{g1.id}.json"
    # Graphs are write-once; corrupt a copy via chmod then rewrite is not
    # allowed. Break the pointer by editing through the path after chmod.
    import os

    os.chmod(raw_path, 0o600)
    data = json.loads(raw_path.read_text(encoding="utf-8"))
    data["parent_graph_id"] = "01AAAAAAAAAAAAAAAAAAAAAAAA"
    data["fork"]["from_graph_id"] = "01AAAAAAAAAAAAAAAAAAAAAAAA"
    raw_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    errors = st.validate_session(sid)
    assert any("parent_graph_id" in e or "missing" in e for e in errors)


def test_parse_regen_structured_fence():
    body = {
        "nodes": [
            {
                "local_id": "r1",
                "kind": "rejected_alternative",
                "text": "discarded path",
                "status": "rejected",
            }
        ],
        "edges": [],
    }
    text = "New prose continues without that cut.\n\n```thought-graph\n" + json.dumps(body) + "\n```\n"
    prose, nodes, edges = parse_regen(text)
    assert prose.startswith("New prose continues")
    assert nodes[0]["local_id"] == "r1"
    assert edges == []


def test_prompt_fork_packaged():
    from thought_archaeology.schema import read_prompt

    text = read_prompt("fork")
    assert "Do not defend the discarded node." in text
