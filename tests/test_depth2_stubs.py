from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from thought_archaeology.depth2 import (
    NULL_PROBE_MESSAGE,
    STABLE_THRESHOLD,
    STORY_FALSIFIED,
    GraphDiff,
    ProbeError,
    ProbeHarness,
    ProbeSpec,
    diff_graphs,
    make_plan,
)
from thought_archaeology.fingerprint import MERGE_THRESHOLD, jaccard, token_set
from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import (
    SCHEMA_VERSION,
    ModelInfo,
    ThoughtEdge,
    ThoughtGraph,
    ThoughtNode,
)
from thought_archaeology.providers.none import NoneProvider
from thought_archaeology.schema import SCHEMA_DIR, ValidationError, validate_schema
from thought_archaeology.store import Store

from tests.helpers import FIXTURES
from tests.test_cli import run

PARA_A = "Make thought an object you can inhabit and fork."
PARA_B = "Make thought an object you can inhabit, fork, and break."
MISS_A = "Prefer short names for the CLI."
MISS_B = "Prefer short names for the HTTP API."


def _compile_simple(store: Path) -> tuple[str, str, ThoughtGraph]:
    code, out, err = run(["init", "--title", "t"], store=store)
    assert code == 0, err
    sid = out.strip()
    gold = FIXTURES / "graphs" / "simple.gold.json"
    trans = FIXTURES / "transcripts" / "simple-freeform.jsonl"
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
            str(gold),
        ],
        store=store,
    )
    assert code == 0, err
    gid = out.strip()
    graph = Store(store).load_graph(gid)
    return sid, gid, graph


def _node(
    kind: str, text: str, *, status: str = "accepted", nid: str | None = None
) -> ThoughtNode:
    return ThoughtNode(
        id=nid or new_ulid(),
        kind=kind,  # type: ignore[arg-type]
        text=text,
        status=status,  # type: ignore[arg-type]
        agent="model",
        created_at=now_iso(),
        source="posthoc_compile",
    )


def _graph(nodes: tuple[ThoughtNode, ...], edges: tuple[ThoughtEdge, ...] = ()) -> ThoughtGraph:
    return ThoughtGraph(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        session_id=new_ulid(),
        turn_id=new_ulid(),
        created_at=now_iso(),
        prose="x",
        nodes=nodes,
        edges=edges,
        model=ModelInfo("file", "unknown", "posthoc"),
    )


def _drop(graph: ThoughtGraph, node_id: str) -> ThoughtGraph:
    nodes = tuple(n for n in graph.nodes if n.id != node_id)
    edges = tuple(
        e for e in graph.edges if e.source_id != node_id and e.target_id != node_id
    )
    return replace(graph, id=new_ulid(), nodes=nodes, edges=edges)


def _by_kind(graph: ThoughtGraph, kind: str) -> ThoughtNode:
    for node in graph.nodes:
        if node.kind == kind:
            return node
    raise AssertionError(f"no {kind} node")


def test_thresholds_frozen():
    assert STABLE_THRESHOLD == 0.8
    assert STABLE_THRESHOLD == MERGE_THRESHOLD
    assert jaccard(token_set(PARA_A), token_set(PARA_B)) >= STABLE_THRESHOLD
    assert jaccard(token_set(MISS_A), token_set(MISS_B)) < STABLE_THRESHOLD


def test_probe_and_diff_schemas_validate():
    now = now_iso()
    spec = {
        "schema_version": SCHEMA_VERSION,
        "id": new_ulid(),
        "kind": "drop_premise",
        "target_node_id": new_ulid(),
        "target_graph_id": new_ulid(),
        "params": {},
        "created_at": now,
    }
    validate_schema("probe.schema.json", spec)
    ProbeSpec.from_dict(spec)
    diff = {
        "schema_version": SCHEMA_VERSION,
        "id": new_ulid(),
        "a_graph_id": new_ulid(),
        "b_graph_id": new_ulid(),
        "stable_node_ids": [],
        "changed_node_ids": [],
        "vanished_node_ids": [],
        "appeared_node_ids": [],
    }
    validate_schema("graph-diff.schema.json", diff)
    GraphDiff.from_dict(diff)
    with pytest.raises(ValidationError):
        validate_schema("probe.schema.json", {"not": "a probe"})
    with pytest.raises(ValidationError):
        validate_schema("probe.schema.json", {**spec, "kind": "drop_weight"})


def test_probe_schema_packaged():
    json.loads(SCHEMA_DIR.joinpath("probe.schema.json").read_text(encoding="utf-8"))
    json.loads(SCHEMA_DIR.joinpath("graph-diff.schema.json").read_text(encoding="utf-8"))


def test_plan_validates_target(tmp_path: Path):
    sid, gid, graph = _compile_simple(tmp_path / "data")
    premise = _by_kind(graph, "premise")
    spec = make_plan(graph, kind="drop_premise", node_id=premise.id)
    assert spec.target_graph_id == graph.id
    assert spec.target_node_id == premise.id
    assert spec.kind == "drop_premise"
    validate_schema("probe.schema.json", spec.to_dict())
    with pytest.raises(ProbeError, match="not in graph"):
        make_plan(graph, kind="drop_premise", node_id=new_ulid())


def test_non_drop_probe_remains_not_implemented(tmp_path: Path):
    _, _, graph = _compile_simple(tmp_path / "data")
    spec = make_plan(graph, kind="resample", node_id=_by_kind(graph, "premise").id)
    with pytest.raises(NotImplementedError, match=NULL_PROBE_MESSAGE):
        ProbeHarness().run(graph, spec, NoneProvider())


def test_diff_same_graph_all_stable(tmp_path: Path):
    _, _, graph = _compile_simple(tmp_path / "data")
    diff = diff_graphs(graph, graph)
    assert set(diff.stable_node_ids) == {n.id for n in graph.nodes}
    assert diff.changed_node_ids == ()
    assert diff.vanished_node_ids == ()
    assert diff.appeared_node_ids == ()
    assert diff.notes is None


def test_diff_match_by_id_then_kind_jaccard():
    shared = _node("claim", PARA_A)
    miss = _node("premise", MISS_A)
    extra = _node("rejected_alternative", "A dashboard of neurons.", status="rejected")
    a = _graph((shared, miss, extra))
    para = _node("claim", PARA_B)  # new id, same kind, Jaccard ≥ 0.8
    near = _node("premise", MISS_B)  # new id, same kind, Jaccard < 0.8
    appeared = _node("uncertainty", "Depth 3 needs a vendor API.", status="uncertain")
    b = _graph((para, near, extra, appeared))
    diff = diff_graphs(a, b)
    assert extra.id in diff.stable_node_ids
    assert shared.id in diff.stable_node_ids
    assert miss.id in diff.vanished_node_ids
    assert near.id in diff.appeared_node_ids
    assert appeared.id in diff.appeared_node_ids
    assert para.id not in diff.appeared_node_ids
    assert miss.id not in diff.stable_node_ids


def test_diff_changed_same_id_different_text():
    claim = _node("claim", "The product is the medium, not the microscope.")
    rejected = _node(
        "rejected_alternative", "A dashboard of neurons.", status="rejected"
    )
    a = _graph((claim, rejected))
    b = _graph((replace(claim, text="Something else entirely."), rejected))
    diff = diff_graphs(a, b)
    assert claim.id in diff.changed_node_ids
    assert rejected.id in diff.stable_node_ids
    assert diff.vanished_node_ids == ()
    assert diff.appeared_node_ids == ()


def test_drop_premise_falsifies_stable_conclusion(tmp_path: Path):
    _, _, graph = _compile_simple(tmp_path / "data")
    premise = _by_kind(graph, "premise")
    claim = _by_kind(graph, "claim")
    spec = make_plan(graph, kind="drop_premise", node_id=premise.id)
    b = _drop(graph, premise.id)
    diff = diff_graphs(graph, b, spec=spec)
    assert premise.id in diff.vanished_node_ids
    assert claim.id in diff.stable_node_ids
    assert diff.notes == STORY_FALSIFIED


def test_drop_premise_not_falsified_if_conclusion_moves(tmp_path: Path):
    _, _, graph = _compile_simple(tmp_path / "data")
    premise = _by_kind(graph, "premise")
    claim = _by_kind(graph, "claim")
    spec = make_plan(graph, kind="drop_premise", node_id=premise.id)
    b = _drop(graph, premise.id)
    new_claim = replace(claim, text="A completely unrelated conclusion about cats.")
    b = replace(
        b,
        nodes=tuple(new_claim if n.id == claim.id else n for n in b.nodes),
    )
    diff = diff_graphs(graph, b, spec=spec)
    assert premise.id in diff.vanished_node_ids
    assert claim.id in diff.changed_node_ids
    assert diff.notes is None


def test_identical_graphs_with_spec_are_not_falsified(tmp_path: Path):
    _, _, graph = _compile_simple(tmp_path / "data")
    spec = make_plan(graph, kind="drop_premise", node_id=_by_kind(graph, "premise").id)
    diff = diff_graphs(graph, graph, spec=spec)
    assert diff.notes is None
    assert spec.target_node_id in diff.stable_node_ids


def test_cli_probe_plan_writes_json(tmp_path: Path):
    store = tmp_path / "data"
    sid, gid, graph = _compile_simple(store)
    premise = _by_kind(graph, "premise")
    out = tmp_path / "spec.json"
    code, stdout, err = run(
        [
            "probe",
            "plan",
            "--graph",
            gid,
            "--kind",
            "drop_premise",
            "--node",
            premise.id,
            "--out",
            str(out),
        ],
        store=store,
    )
    assert code == 0, err
    pid = stdout.strip()
    assert len(pid) == 26
    raw = json.loads(out.read_text(encoding="utf-8"))
    validate_schema("probe.schema.json", raw)
    assert raw["id"] == pid
    assert raw["target_node_id"] == premise.id
    stored = Store(store).probes_dir(sid) / f"{pid}.json"
    assert stored.is_file()
    # sidecar lives next to graphs/, not inside it
    assert not (Store(store).session_dir(sid) / "graphs" / f"{pid}.json").exists()
    graphs = list(Store(store).iter_graphs(sid))
    assert [g.id for g in graphs] == [gid]


def test_cli_probe_plan_missing_node(tmp_path: Path):
    store = tmp_path / "data"
    _, gid, _ = _compile_simple(store)
    code, _, err = run(
        [
            "probe",
            "plan",
            "--graph",
            gid,
            "--kind",
            "drop_premise",
            "--node",
            "01AAAAAAAAAAAAAAAAAAAAAAAA",
        ],
        store=store,
    )
    assert code == 3
    assert "not in graph" in err


def test_cli_probe_run_stores_child_and_diff(tmp_path: Path):
    store = tmp_path / "data"
    _, gid, graph = _compile_simple(store)
    spec_path = tmp_path / "spec.json"
    code, out, err = run(
        [
            "probe",
            "plan",
            "--graph",
            gid,
            "--kind",
            "drop_premise",
            "--node",
            _by_kind(graph, "premise").id,
            "--out",
            str(spec_path),
        ],
        store=store,
    )
    assert code == 0, err
    provider = Path(__file__).with_name("fake_probe_provider.py")
    code, out, err = run(
        [
            "probe",
            "run",
            "--spec",
            str(spec_path),
            "--provider-cmd",
            f"{sys.executable} {provider}",
        ],
        store=store,
    )
    assert code == 0, err
    lines = out.splitlines()
    child_id = lines[0].removeprefix("graph ")
    diff_id = lines[1].removeprefix("diff ")
    st = Store(store)
    child = st.load_graph(child_id)
    assert child.parent_graph_id == gid
    assert _by_kind(graph, "premise").id not in {n.id for n in child.nodes}
    assert (st.diffs_dir(child.session_id) / f"{diff_id}.json").is_file()


def test_cli_probe_run_missing_spec_is_io(tmp_path: Path):
    store = tmp_path / "data"
    run(["init", "--title", "t"], store=store)
    code, _, err = run(
        [
            "probe",
            "run",
            "--spec",
            str(tmp_path / "nope.json"),
            "--provider-cmd",
            "unused",
        ],
        store=store,
    )
    assert code == 3
    assert err != ""


def test_cli_probe_diff_falsification_message(tmp_path: Path):
    store = tmp_path / "data"
    sid, gid, graph = _compile_simple(store)
    premise = _by_kind(graph, "premise")
    spec_path = tmp_path / "spec.json"
    code, _, err = run(
        [
            "probe",
            "plan",
            "--graph",
            gid,
            "--kind",
            "drop_premise",
            "--node",
            premise.id,
            "--out",
            str(spec_path),
        ],
        store=store,
    )
    assert code == 0, err
    b = _drop(graph, premise.id)
    Store(store).write_graph(b)
    diff_out = tmp_path / "diff.json"
    code, out, err = run(
        [
            "probe",
            "diff",
            gid,
            b.id,
            "--spec",
            str(spec_path),
            "--out",
            str(diff_out),
        ],
        store=store,
    )
    assert code == 0, err
    assert STORY_FALSIFIED in err
    raw = json.loads(diff_out.read_text(encoding="utf-8"))
    validate_schema("graph-diff.schema.json", raw)
    assert raw["notes"] == STORY_FALSIFIED
    assert premise.id in raw["vanished_node_ids"]
    assert (Store(store).diffs_dir(sid) / f"{out.strip()}.json").is_file()


def test_cli_probe_diff_without_spec_is_silent(tmp_path: Path):
    store = tmp_path / "data"
    _, gid, graph = _compile_simple(store)
    b = _drop(graph, _by_kind(graph, "premise").id)
    Store(store).write_graph(b)
    code, out, err = run(["probe", "diff", gid, b.id], store=store)
    assert code == 0, err
    assert STORY_FALSIFIED not in err
    assert len(out.strip()) == 26
