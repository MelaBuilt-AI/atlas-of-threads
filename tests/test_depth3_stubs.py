from __future__ import annotations

import json
from pathlib import Path

import pytest

from thought_archaeology.depth3 import (
    MAX_SUPERNODES,
    Attribution,
    DisplayRefused,
    NullSensor,
    format_attribution,
)
from thought_archaeology.depth3.sensor import NULL_SENSOR_MESSAGE, enforce_collapse
from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import SCHEMA_VERSION, Span
from thought_archaeology.schema import SCHEMA_DIR, ValidationError, validate_schema
from thought_archaeology.store import Store

from tests.helpers import FIXTURES
from tests.test_cli import run
from tests.test_schema import _minimal_graph_dict

TWELVE = FIXTURES / "attributions" / "twelve.json"


def _attribution(*, n_supernodes: int, raw_feature_count: int = 4000) -> dict:
    now = now_iso()
    supernodes = [
        {
            "id": new_ulid(),
            "label": f"concept {i}",
            "nla_sentence": f"NLA sentence {i}",
            "feature_ids": [f"feat_{i}_{j}" for j in range(3)],
            "exemplars": [f"ex {i}"],
        }
        for i in range(n_supernodes)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "id": new_ulid(),
        "graph_id": new_ulid(),
        "node_id": new_ulid(),
        "span": {"start": 0, "end": 8, "unit": "char"},
        "supernodes": supernodes,
        "raw_feature_count": raw_feature_count,
        "vendor": "custom",
        "created_at": now,
    }


def test_twelve_fixture_validates_and_displays():
    raw = json.loads(TWELVE.read_text(encoding="utf-8"))
    validate_schema("attribution.schema.json", raw)
    attr = Attribution.from_dict(raw)
    assert len(attr.supernodes) == MAX_SUPERNODES
    assert attr.raw_feature_count == 4000
    text = format_attribution(attr)
    assert "named parts" in text
    assert "collapsed view bound to a thought-node" in text
    assert "feat_1" not in text
    assert "feature_ids" not in text
    assert "raw_feature_count=4000" in text
    assert "suppressed" in text


def test_4000_supernodes_schema_ok_display_refused():
    raw = _attribution(n_supernodes=4000)
    validate_schema("attribution.schema.json", raw)
    attr = Attribution.from_dict(raw)
    assert len(attr.supernodes) == 4000
    with pytest.raises(DisplayRefused, match="refusing to display 4000"):
        format_attribution(attr)
    with pytest.raises(DisplayRefused):
        enforce_collapse(attr)
    allowed = format_attribution(attr, include_raw=True)
    assert "concept 0" in allowed
    assert "feat_0_0" not in allowed


def test_schema_has_no_maxitems_on_supernodes():
    schema = json.loads(
        SCHEMA_DIR.joinpath("attribution.schema.json").read_text(encoding="utf-8")
    )
    assert "maxItems" not in schema["properties"]["supernodes"]


def test_no_personality_node_kind():
    schema = json.loads(
        SCHEMA_DIR.joinpath("thought-node.schema.json").read_text(encoding="utf-8")
    )
    assert "personality" not in schema["properties"]["kind"]["enum"]


def test_null_sensor_raises(tmp_path: Path, simple_gold: dict):
    from thought_archaeology.compile_posthoc import compile_posthoc
    from thought_archaeology.models import ModelInfo

    store = Store(tmp_path / "data")
    session = store.init_session("t")
    graph, _ = compile_posthoc(
        "The product is the medium, not the microscope.",
        json.dumps(simple_gold),
        session_id=session.id,
        turn_id=new_ulid(),
        model=ModelInfo("file", "unknown", "posthoc"),
        now=now_iso(),
    )
    store.write_graph(graph)
    with pytest.raises(NotImplementedError, match=NULL_SENSOR_MESSAGE):
        NullSensor().attach(graph, graph.nodes[0].id)
    with pytest.raises(Exception, match="not in graph"):
        NullSensor().attach(graph, new_ulid())


def test_cli_sensor_attach_exits_4(tmp_path: Path):
    store = tmp_path / "data"
    code, out, err = run(["init", "--title", "t"], store=store)
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
    st = Store(store)
    graph = st.load_graph(out.strip())
    nid = graph.nodes[0].id
    code, out, err = run(
        ["sensor", "attach", nid, "--session", sid],
        store=store,
    )
    assert code == 4
    assert NULL_SENSOR_MESSAGE in err
    assert "include_raw" not in err
    code, _, err = run(["sensor", "attach", nid, "--include-raw"], store=store)
    assert code == 2


def test_cli_sensor_displays_twelve_refuses_dump(tmp_path: Path):
    store = tmp_path / "data"
    code, out, err = run(
        [
            "sensor",
            "attach",
            "--from-attribution",
            str(TWELVE),
        ],
        store=store,
    )
    assert code == 0, err
    assert "named parts" in out
    assert "feat_1" not in out

    dump = tmp_path / "too-many.json"
    dump.write_text(json.dumps(_attribution(n_supernodes=4000)), encoding="utf-8")
    code, out, err = run(
        [
            "sensor",
            "attach",
            "--from-attribution",
            str(dump),
        ],
        store=store,
    )
    assert code == 1
    assert "refusing to display 4000" in err
    assert out == ""


def test_cli_sensor_missing_node(tmp_path: Path):
    store = tmp_path / "data"
    code, out, err = run(["init", "--title", "t"], store=store)
    sid = out.strip()
    code, _, err = run(
        ["sensor", "attach", "01AAAAAAAAAAAAAAAAAAAAAAAA", "--session", sid],
        store=store,
    )
    assert code == 3
    assert "not found" in err


def test_attribution_roundtrip_and_span():
    raw = json.loads(TWELVE.read_text(encoding="utf-8"))
    attr = Attribution.from_dict(raw)
    again = Attribution.from_dict(attr.to_dict())
    assert again.id == attr.id
    assert again.span == Span(0, 42, "char")
    assert again.supernodes[-1].suppressed is True
    validate_schema("attribution.schema.json", attr.to_dict())


def test_attribution_schema_packaged():
    validate_schema(
        "attribution.schema.json", json.loads(TWELVE.read_text(encoding="utf-8"))
    )
    with pytest.raises(ValidationError):
        validate_schema("attribution.schema.json", {"not": "an attribution"})


def test_minimal_graph_still_validates_with_new_schema_name():
    from thought_archaeology.schema import validate_graph

    validate_graph(_minimal_graph_dict())
