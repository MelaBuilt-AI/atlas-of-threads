from __future__ import annotations

import json
import gzip
from pathlib import Path

import pytest

from thought_archaeology.depth3 import (
    MAX_SUPERNODES,
    Attribution,
    DisplayRefused,
    NullSensor,
    format_attribution,
    import_circuit_tracer_graph,
    import_intervention_result,
    import_neuronpedia_result,
    import_neuronpedia_activation,
)
from thought_archaeology.depth3.sensor import NULL_SENSOR_MESSAGE, enforce_collapse
from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.evidence import EvidenceBinding
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


def test_cli_sensor_stores_measured_attribution_and_inconclusive_evidence(tmp_path: Path):
    store_path = tmp_path / "data"
    code, out, err = run(["init", "--title", "measured"], store=store_path)
    assert code == 0, err
    sid = out.strip()
    gold = FIXTURES / "graphs" / "simple.gold.json"
    trans = FIXTURES / "transcripts" / "simple-freeform.jsonl"
    code, out, err = run(
        [
            "compile", "--session", sid, "--mode", "posthoc",
            "--transcript", str(trans), "--from-graph", str(gold),
        ],
        store=store_path,
    )
    assert code == 0, err
    store = Store(store_path)
    graph = store.load_graph(out.strip())
    node = graph.nodes[0]
    raw = _attribution(n_supernodes=2, raw_feature_count=855)
    raw.update(
        graph_id=graph.id,
        node_id=node.id,
        span={"start": 0, "end": min(8, len(node.text)), "unit": "char"},
        provenance={
            "artifact_kind": "measured_attribution",
            "model": "google/gemma-2-2b",
            "method": "circuit-tracer cross-layer transcoder attribution graph",
            "source_uri": "https://example.test/measured.json",
            "source_sha256": "a" * 64,
            "producer_revision": "deadbeef",
            "prompt": "Fact: The capital of the state containing Dallas is",
            "target": " Austin",
        },
    )
    dump = tmp_path / "measured.json"
    dump.write_text(json.dumps(raw), encoding="utf-8")
    code, out, err = run(
        [
            "sensor", "attach", node.id, "--graph", graph.id,
            "--session", sid, "--from-attribution", str(dump),
        ],
        store=store_path,
    )
    assert code == 0, err
    assert f"stored attribution {raw['id']}" in out
    stored = store.load_attribution(sid, raw["id"])
    assert stored["provenance"]["artifact_kind"] == "measured_attribution"
    evidence = list(store.iter_evidence(sid, graph_id=graph.id, node_id=node.id))
    assert len(evidence) == 1
    assert evidence[0]["kind"] == "activation_correlation"
    assert evidence[0]["result"] == "inconclusive"
    assert f"attribution:{raw['id']}" in evidence[0]["artifact_refs"]


def test_store_refuses_fixture_as_measured_attribution(tmp_path: Path):
    store = Store(tmp_path / "data")
    session = store.init_session("t")
    from thought_archaeology.compile_posthoc import compile_posthoc
    from thought_archaeology.models import ModelInfo

    gold = json.loads((FIXTURES / "graphs" / "simple.gold.json").read_text())
    graph, _ = compile_posthoc(
        "The product is the medium, not the microscope.",
        json.dumps(gold),
        session_id=session.id,
        turn_id=new_ulid(),
        model=ModelInfo("file", "unknown", "posthoc"),
        now=now_iso(),
    )
    store.write_graph(graph)
    raw = _attribution(n_supernodes=1)
    raw.update(
        graph_id=graph.id,
        node_id=graph.nodes[0].id,
        span={"start": 0, "end": 1, "unit": "char"},
        provenance={
            "artifact_kind": "deterministic_fixture",
            "model": "fixture",
            "method": "fixture",
            "source_uri": "fixture:test",
            "source_sha256": "b" * 64,
        },
    )
    with pytest.raises(Exception, match="requires measured_attribution"):
        store.write_attribution(session.id, raw)


def test_import_circuit_tracer_gzip_collapses_structurally(tmp_path: Path):
    source = {
        "metadata": {
            "scan": "gemma-2-2b",
            "prompt": "Fact: The capital is",
        },
        "nodes": [
            {
                "node_id": "1_2_3", "feature_type": "cross layer transcoder",
                "clerp": "", "is_target_logit": False,
            },
            {
                "node_id": "27_4_3", "feature_type": "logit",
                "clerp": "Output \" Austin\" (p=0.450)", "is_target_logit": True,
            },
        ],
        "links": [{"source": "1_2_3", "target": "27_4_3", "weight": 1.0}],
    }
    path = tmp_path / "official.json"
    source_bytes = gzip.compress(json.dumps(source).encode())
    path.write_bytes(source_bytes)
    attr = import_circuit_tracer_graph(
        path,
        graph_id=new_ulid(),
        node_id=new_ulid(),
        span=Span(0, 6, "char"),
        source_uri="https://example.test/official.json",
        producer_revision="deadbeef",
    )
    assert attr.raw_feature_count == 2
    assert len(attr.supernodes) == 2
    assert attr.provenance is not None
    assert attr.provenance.artifact_kind == "measured_attribution"
    assert attr.provenance.target == 'Output " Austin" (p=0.450)'
    assert attr.provenance.source_sha256
    assert all("semantic feature interpretation" in s.nla_sentence for s in attr.supernodes)


def test_sensor_source_store_preserves_exact_bytes(tmp_path: Path):
    import hashlib

    store = Store(tmp_path / "data")
    session = store.init_session("source")
    source = b"\x1f\x8bexact compressed artifact bytes"
    digest = hashlib.sha256(source).hexdigest()
    path = store.write_sensor_source(session.id, digest, source)
    assert path.read_bytes() == source
    assert store.write_sensor_source(session.id, digest, source) == path
    with pytest.raises(Exception, match="SHA-256 mismatch"):
        store.write_sensor_source(session.id, "0" * 64, source)


@pytest.mark.parametrize(
    ("direction", "intervened", "expected"),
    [
        ("decrease", 0.20, "supports"),
        ("decrease", 0.60, "contradicts"),
        ("change", 0.44, "inconclusive"),
    ],
)
def test_intervention_result_is_computed_not_accepted(
    tmp_path: Path, direction: str, intervened: float, expected: str
):
    result = {
        "attribution_id": new_ulid(),
        "model": "gemma-2-2b",
        "prompt": "Fact: The capital of the state containing Dallas is",
        "target": " Austin",
        "method": "circuit-tracer feature_intervention",
        "runner_revision": "8f1e2438",
        "device": "cuda:0",
        "edit": {
            "operation": "set_value",
            "layer": 20, "position": 10, "feature_index": 15589,
            "baseline_activation": 8.2, "set_to": 0.0, "delta": None,
        },
        "hypothesis": {
            "metric": "target_probability",
            "expected_direction": direction,
            "minimum_absolute_change": 0.05,
        },
        "baseline": {"target_value": 0.45, "top_token": " Austin"},
        "intervened": {"target_value": intervened, "top_token": " Austin"},
        "result": "supports",  # ignored: classification is recomputed
    }
    path = tmp_path / "result.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    artifact = import_intervention_result(
        path,
        graph_id=new_ulid(),
        node_id=new_ulid(),
        source_uri="result://gpu-run",
    )
    assert artifact.result == expected
    assert artifact.observed_delta == pytest.approx(intervened - 0.45)
    validate_schema("neural-intervention.schema.json", artifact.to_dict())


def test_cli_records_neural_intervention_only_beneath_matching_attribution(tmp_path: Path):
    from thought_archaeology.compile_posthoc import compile_posthoc
    from thought_archaeology.models import ModelInfo

    store_path = tmp_path / "data"
    store = Store(store_path)
    session = store.init_session("causal")
    gold = json.loads((FIXTURES / "graphs" / "simple.gold.json").read_text())
    graph, _ = compile_posthoc(
        "The product is the medium, not the microscope.", json.dumps(gold),
        session_id=session.id, turn_id=new_ulid(),
        model=ModelInfo("file", "gemma-2-2b", "posthoc"), now=now_iso(),
    )
    store.write_graph(graph)
    node = graph.nodes[0]
    attr = _attribution(n_supernodes=1, raw_feature_count=10)
    attr.update(
        graph_id=graph.id, node_id=node.id,
        span={"start": 0, "end": 6, "unit": "char"},
        provenance={
            "artifact_kind": "measured_attribution", "model": "gemma-2-2b",
            "method": "circuit-tracer", "source_uri": "source://graph",
            "source_sha256": "c" * 64,
            "prompt": "Fact: The capital of the state containing Dallas is",
            "target": " Austin",
        },
    )
    attr["supernodes"][0]["feature_ids"] = ["20_15589_10"]
    store.write_attribution(session.id, attr)
    parent = EvidenceBinding(
        schema_version=SCHEMA_VERSION, id=new_ulid(), graph_id=graph.id,
        node_id=node.id, kind="activation_correlation", result="inconclusive",
        summary="Measured association only.",
        artifact_refs=(f"attribution:{attr['id']}",), created_at=now_iso(),
    )
    store.write_evidence(session.id, parent.to_dict())
    raw_result = {
        "attribution_id": attr["id"], "model": "gemma-2-2b",
        "prompt": "Fact: The capital of the state containing Dallas is",
        "target": " Austin", "method": "circuit-tracer feature_intervention",
        "runner_revision": "8f1e2438", "device": "cuda:0",
        "edit": {"operation": "set_value", "layer": 20, "position": 10,
                 "feature_index": 15589, "baseline_activation": 8.2,
                 "set_to": 0.0, "delta": None},
        "hypothesis": {"metric": "target_probability",
                       "expected_direction": "decrease",
                       "minimum_absolute_change": 0.05},
        "baseline": {"target_value": 0.45, "top_token": " Austin"},
        "intervened": {"target_value": 0.20, "top_token": " Texas"},
    }
    result_path = tmp_path / "gpu-result.json"
    result_path.write_text(json.dumps(raw_result), encoding="utf-8")
    code, out, err = run(
        ["sensor", "record-intervention", node.id, "--graph", graph.id,
         "--session", session.id, "--from-result", str(result_path),
         "--source-uri", "result://gpu-run", "--parent-evidence", parent.id],
        store=store_path,
    )
    assert code == 0, err
    assert "result supports" in out
    evidence = list(store.iter_evidence(session.id, graph_id=graph.id, node_id=node.id))
    assert [item["kind"] for item in evidence] == [
        "activation_correlation", "neural_intervention"
    ]
    assert evidence[-1]["parent_evidence_id"] == parent.id
    intervention_id = evidence[-1]["artifact_refs"][0].split(":", 1)[1]
    artifact = store.load_neural_intervention(session.id, intervention_id)
    assert artifact["observed_delta"] == pytest.approx(-0.25)
    source_path = store.sensor_sources_dir(session.id) / (
        artifact["execution"]["source_sha256"] + ".bin"
    )
    assert source_path.read_bytes() == result_path.read_bytes()
    code, _, err = run(
        ["sensor", "synthesize-recurrence",
         "--neural-evidence", evidence[-1]["id"],
         "--neural-evidence", evidence[-1]["id"],
         "--neural-evidence", evidence[-1]["id"]],
        store=store_path,
    )
    assert code == 2
    assert "3 distinct prompts" in err


def test_neuronpedia_import_verifies_preregistered_request_and_observed_generation(tmp_path: Path):
    import hashlib

    request = {
        "modelId": "gemma-2-2b",
        "prompt": "Fact: The capital of the state containing Dallas is",
        "features": [{"layer": 14, "index": 2268, "token_active_position": 9,
                      "steer_position": 9, "steer_generated_tokens": False,
                      "delta": -200, "ablate": False}],
    }
    response = {
        "DEFAULT_GENERATION": "<bos>Fact: The capital of the state containing Dallas is Austin.",
        "STEERED_GENERATION": "<bos>Fact: The capital of the state containing Dallas is Albany.",
        "DEFAULT_LOGITS_BY_TOKEN": [{"token": " is", "top_logits": [
            {"token": " Austin", "prob": 0.43}
        ]}],
        "STEERED_LOGITS_BY_TOKEN": [{"token": " is", "top_logits": [
            {"token": " Albany", "prob": 0.08}
        ]}],
    }
    request_path = tmp_path / "request.json"
    response_path = tmp_path / "response.json"
    manifest_path = tmp_path / "manifest.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    response_path.write_text(json.dumps(response), encoding="utf-8")
    manifest = {
        "attribution_id": new_ulid(), "target": " Austin",
        "expected_direction": "decrease", "minimum_absolute_change": 1,
        "request_sha256": hashlib.sha256(request_path.read_bytes()).hexdigest(),
        "runner_revision": "ead3c677",
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    artifact = import_neuronpedia_result(
        request_path, response_path, manifest_path,
        graph_id=new_ulid(), node_id=new_ulid(),
        source_uri="https://www.neuronpedia.org/api/steer-logits",
    )
    assert artifact.result == "supports"
    assert artifact.baseline == {"target_value": 1.0, "top_token": " Austin"}
    assert artifact.intervened == {"target_value": 0.0, "top_token": " Albany"}
    assert artifact.edit["operation"] == "add_delta"
    validate_schema("neural-intervention.schema.json", artifact.to_dict())
    request_path.write_text(json.dumps({**request, "seed": 99}), encoding="utf-8")
    with pytest.raises(Exception, match="request_sha256"):
        import_neuronpedia_result(
            request_path, response_path, manifest_path,
            graph_id=new_ulid(), node_id=new_ulid(), source_uri="result://changed",
        )


def test_neuronpedia_activation_import_preserves_measurement_without_semantic_label(tmp_path: Path):
    request_path = tmp_path / "activation-request.json"
    response_path = tmp_path / "activation-response.json"
    request_path.write_text(json.dumps({
        "feature": {"modelId": "gemma-2-2b",
                    "source": "14-gemmascope-transcoder-16k", "index": "2268"},
        "customText": "Fact: The capital of Texas is", "ignoreBos": False,
    }), encoding="utf-8")
    response_path.write_text(json.dumps({
        "tokens": ["Fact", ":", " The", " capital", " of", " Texas", " is"],
        "values": [0, 0, 0, 0, 0, 29.375, 0],
        "maxValueTokenIndex": 5,
    }), encoding="utf-8")
    attr = import_neuronpedia_activation(
        request_path, response_path, graph_id=new_ulid(), node_id=new_ulid(),
        graph_position=6, target="Austin",
    )
    assert attr.supernodes[0].feature_ids == ("14_2268_6",)
    assert "activation 29.375" in attr.supernodes[0].label
    assert "no semantic meaning" in attr.supernodes[0].nla_sentence
    assert attr.provenance is not None and attr.provenance.request_sha256
    validate_schema("attribution.schema.json", attr.to_dict())


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
