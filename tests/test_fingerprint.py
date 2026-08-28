from __future__ import annotations

import json
from pathlib import Path

import pytest

from thought_archaeology.fingerprint import (
    DIVERGENCE_THRESHOLD,
    MERGE_THRESHOLD,
    Fingerprint,
    climate_at,
    cluster_nodes,
    fingerprint,
    jaccard,
    normalize,
    recompute_canonical,
    token_set,
)
from thought_archaeology.inhabit import inhabit
from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import (
    SCHEMA_VERSION,
    ModelInfo,
    ThoughtGraph,
    ThoughtNode,
)
from thought_archaeology.schema import SCHEMA_DIR, ValidationError, validate_schema
from thought_archaeology.store import Store

from tests.helpers import FIXTURES
from tests.test_cli import run

SHARED = "Invent the medium first."
PARA_A = "Make thought an object you can inhabit and fork."
PARA_B = "Make thought an object you can inhabit, fork, and break."
MISS_A = "Prefer short names for the CLI."
MISS_B = "Prefer short names for the HTTP API."
HUMAN_NOT_VETO = "Skip Depth 1 entirely."


def _compile_pair(store: Path) -> tuple[str, str]:
    ids = []
    for name in ("a", "b"):
        code, out, err = run(["init", "--title", f"two-{name}"], store=store)
        assert code == 0, err
        sid = out.strip()
        code, out, err = run(
            [
                "compile",
                "--session",
                sid,
                "--mode",
                "posthoc",
                "--transcript",
                str(FIXTURES / "transcripts" / f"two-session-{name}.jsonl"),
                "--from-graph",
                str(FIXTURES / "graphs" / f"two-session-{name}.gold.json"),
            ],
            store=store,
        )
        assert code == 0, err
        ids.append(sid)
    return ids[0], ids[1]


def test_thresholds_frozen():
    assert MERGE_THRESHOLD == 0.8
    assert DIVERGENCE_THRESHOLD == 0.5


def test_normalize_and_jaccard_edges():
    assert normalize("Invent the Medium First.") == "invent the medium first"
    assert jaccard(frozenset(), frozenset()) == 1.0
    assert jaccard(frozenset({"a"}), frozenset()) == 0.0
    four = token_set("a b c d")
    five = token_set("a b c d e")
    assert jaccard(four, five) == pytest.approx(0.8)
    assert jaccard(token_set(PARA_A), token_set(PARA_B)) >= MERGE_THRESHOLD
    assert jaccard(token_set(MISS_A), token_set(MISS_B)) < MERGE_THRESHOLD


def test_canonical_tie_shortest_then_lexico():
    assert recompute_canonical(["bb", "aa", "bb"]) == "bb"
    assert recompute_canonical(["ccc", "aa", "bb"]) == "aa"
    assert recompute_canonical(["ab", "aa"]) == "aa"


def test_cluster_is_single_pass_not_global_recluster():
    now = now_iso()

    def node(text: str) -> ThoughtNode:
        return ThoughtNode(
            id=new_ulid(),
            kind="taste_call",
            text=text,
            status="accepted",
            agent="model",
            created_at=now,
            source="posthoc_compile",
        )

    g = ThoughtGraph(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        session_id=new_ulid(),
        turn_id=new_ulid(),
        created_at=now,
        prose="x",
        nodes=(),
        edges=(),
        model=ModelInfo("none", "unknown", "posthoc"),
    )
    n1 = node("red cat sat mat")
    n2 = node("red cat sat hat")
    # 3/5 = 0.6 < 0.8 → two clusters, even though a global recluster
    # with a different seed might differ. Freeze greedy ULID order.
    assert jaccard(token_set(n1.text), token_set(n2.text)) < MERGE_THRESHOLD
    clusters = cluster_nodes([(g, n1), (g, n2)])
    assert len(clusters) == 2


def test_two_session_fingerprint_cli(tmp_path: Path):
    store = tmp_path / "data"
    sid_a, sid_b = _compile_pair(store)
    out_path = tmp_path / "fp.json"
    code, out, err = run(
        [
            "fingerprint",
            "--session",
            sid_a,
            "--session",
            sid_b,
            "--out",
            str(out_path),
        ],
        store=store,
    )
    assert code == 0, err
    fid = out.strip()
    assert len(fid) == 26
    raw = json.loads(out_path.read_text(encoding="utf-8"))
    validate_schema("fingerprint.schema.json", raw)
    fp = Fingerprint.from_dict(raw)
    assert fp.min_sessions == 2
    assert fp.merge_threshold == MERGE_THRESHOLD
    assert set(fp.session_ids) == {sid_a, sid_b}

    by_canon = {c.canonical: c for c in fp.model_taste}
    shared = by_canon[SHARED]
    assert shared.count == 2
    assert shared.recurrence == "recurring"
    assert set(shared.session_ids) == {sid_a, sid_b}

    assert PARA_A in by_canon
    para = by_canon[PARA_A]
    assert para.count == 2
    assert para.recurrence == "recurring"
    assert PARA_B not in by_canon  # merged; shortest exact text wins

    assert MISS_A in by_canon
    assert MISS_B in by_canon
    assert by_canon[MISS_A].recurrence == "emerging"
    assert by_canon[MISS_B].recurrence == "emerging"
    assert by_canon[MISS_A].count == 1
    assert by_canon[MISS_B].count == 1

    veto_texts = {c.canonical for c in fp.human_vetoes}
    assert SHARED in veto_texts
    assert HUMAN_NOT_VETO not in veto_texts
    assert len(fp.human_vetoes) == 1
    assert fp.human_vetoes[0].recurrence == "emerging"

    div = [
        d
        for d in fp.divergence
        if d.taste_canonical == SHARED and d.veto_canonical == SHARED
    ]
    assert len(div) == 1
    assert div[0].jaccard == pytest.approx(1.0)

    st = Store(store)
    stored = st.load_fingerprint(fid)
    assert stored["id"] == fid
    log = (store / "store.log.jsonl").read_text(encoding="utf-8")
    assert '"op": "fingerprint"' in log


def test_single_session_all_emerging(tmp_path: Path):
    store = tmp_path / "data"
    sid_a, _sid_b = _compile_pair(store)
    code, out, err = run(
        ["fingerprint", "--session", sid_a],
        store=store,
    )
    assert code == 0, err
    st = Store(store)
    fp = Fingerprint.from_dict(st.load_fingerprint(out.strip()))
    assert all(c.recurrence == "emerging" for c in fp.model_taste)
    assert fp.human_vetoes == ()


def test_min_sessions_1_marks_recurring(tmp_path: Path):
    store = tmp_path / "data"
    sid_a, _sid_b = _compile_pair(store)
    code, out, err = run(
        ["fingerprint", "--session", sid_a, "--min-sessions", "1"],
        store=store,
    )
    assert code == 0, err
    st = Store(store)
    fp = Fingerprint.from_dict(st.load_fingerprint(out.strip()))
    assert fp.min_sessions == 1
    assert all(c.recurrence == "recurring" for c in fp.model_taste)


def test_fingerprint_all_sessions_in_store(tmp_path: Path):
    store = tmp_path / "data"
    sid_a, sid_b = _compile_pair(store)
    code, out, err = run(["fingerprint"], store=store)
    assert code == 0, err
    st = Store(store)
    fp = Fingerprint.from_dict(st.load_fingerprint(out.strip()))
    assert set(fp.session_ids) == {sid_a, sid_b}


def test_missing_session_is_io(tmp_path: Path):
    store = tmp_path / "data"
    run(["init", "--title", "t"], store=store)
    code, _, err = run(
        ["fingerprint", "--session", "01AAAAAAAAAAAAAAAAAAAAAAAA"],
        store=store,
    )
    assert code == 3
    assert "not found" in err


def test_min_sessions_zero_is_usage(tmp_path: Path):
    store = tmp_path / "data"
    run(["init", "--title", "t"], store=store)
    code, _, err = run(["fingerprint", "--min-sessions", "0"], store=store)
    assert code == 2


def test_schema_packaged_and_rejects_junk():
    schema = json.loads(
        SCHEMA_DIR.joinpath("fingerprint.schema.json").read_text(encoding="utf-8")
    )
    assert schema["title"] == "Fingerprint"
    with pytest.raises(ValidationError):
        validate_schema("fingerprint.schema.json", {"not": "a fingerprint"})


def test_write_once_fingerprint(tmp_path: Path):
    store = tmp_path / "data"
    sid_a, sid_b = _compile_pair(store)
    st = Store(store)
    graphs = list(st.iter_graphs())
    fp = fingerprint(graphs, session_ids=[sid_a, sid_b])
    st.write_fingerprint(fp.to_dict())
    from thought_archaeology.store import StoreError

    with pytest.raises(StoreError, match="write-once"):
        st.write_fingerprint(fp.to_dict())


def test_climate_is_atmosphere_not_a_cluster_list(tmp_path: Path):
    store = tmp_path / "data"
    sid_a, sid_b = _compile_pair(store)
    code, out, err = run(
        ["fingerprint", "--session", sid_a, "--session", sid_b],
        store=store,
    )
    assert code == 0, err
    st = Store(store)
    fp = Fingerprint.from_dict(st.latest_fingerprint())
    graph = next(st.iter_graphs(sid_a))
    by_text = {n.text: n for n in graph.nodes}

    fought = climate_at(by_text[SHARED], fp)
    assert fought["kind"] == "divergence"
    assert fought["label"] == "you fight this cut"
    assert fought["canonical"] == SHARED
    assert "clusters" not in fought
    assert "model_taste" not in fought

    habit = climate_at(by_text[PARA_A], fp)
    assert habit["kind"] == "recurring"
    assert habit["label"] == "the model's recurring taste"

    thin = climate_at(by_text[MISS_A], fp)
    assert thin["kind"] == "emerging"

    claim = next(n for n in graph.nodes if n.kind == "claim")
    still = climate_at(claim, fp)
    assert still["kind"] == "calm"
    assert still["canonical"] is None

    assert climate_at(claim, None) is None

    view = inhabit(st, by_text[SHARED].id, session_id=sid_a)
    assert view.climate["kind"] == "divergence"
    text = view.to_dict()
    assert text["climate"]["kind"] == "divergence"
    assert "model_taste" not in text
