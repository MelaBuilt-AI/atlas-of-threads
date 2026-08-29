from __future__ import annotations

import json
from pathlib import Path

import pytest

from thought_archaeology.ids import new_ulid
from thought_archaeology.schema import validate_schema
from thought_archaeology.store import Store
from thought_archaeology.training import TrainingProvenanceError, build_checkpoint_emergence
from tests.test_cli import run


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    measurements = tmp_path / "measurements.jsonl"
    measurements.write_text("\n".join(json.dumps(row) for row in [
        {"model": "EleutherAI/pythia-14m", "revision": "step0",
         "prompt": "The capital of France is", "target": " Paris",
         "target_probability": 0.00001, "target_rank": 28000,
         "generation": "The capital of France is noise"},
        {"model": "EleutherAI/pythia-14m", "revision": "main",
         "prompt": "The capital of France is", "target": " Paris",
         "target_probability": 0.0004, "target_rank": 276,
         "generation": "The capital of France is the United States"},
    ]) + "\n")
    checkpoint_map = tmp_path / "map.json"
    checkpoint_map.write_text(json.dumps({
        "step0": {"training_tokens": 0, "commit": "a" * 40,
                  "weight_sha256": "b" * 64},
        "main": {"training_tokens": 299892736000, "commit": "c" * 40,
                 "weight_sha256": "d" * 64},
    }))
    model_card = tmp_path / "model-card.md"
    model_card.write_text("trained on the Pile")
    docs = tmp_path / "training.md"
    docs.write_text("exact same data order; checkpoints released")
    return measurements, checkpoint_map, model_card, docs


def test_checkpoint_emergence_is_bounded_and_computed(tmp_path: Path):
    paths = _write_inputs(tmp_path)
    artifact = build_checkpoint_emergence(
        *paths, graph_id=new_ulid(), node_id=new_ulid(), corpus_name="The Pile",
        model_card_uri="https://example.test/model", training_docs_uri="https://example.test/docs",
    )
    assert artifact["result"] == "supports"
    assert artifact["observed"]["rank_improvement"] == 27724
    assert artifact["observed"]["target_generated_at_final"] is False
    assert artifact["boundaries"] == {
        "record_membership": "not_tested",
        "example_influence": "not_measured",
        "weight_attribution": "not_measured",
        "analysis_mode": "exploratory",
    }
    validate_schema("training-provenance.schema.json", artifact)


def test_checkpoint_emergence_rejects_mixed_models(tmp_path: Path):
    measurements, checkpoint_map, model_card, docs = _write_inputs(tmp_path)
    rows = [json.loads(line) for line in measurements.read_text().splitlines()]
    rows[-1]["model"] = "another-model"
    measurements.write_text("\n".join(json.dumps(row) for row in rows))
    with pytest.raises(TrainingProvenanceError, match="exact model"):
        build_checkpoint_emergence(
            measurements, checkpoint_map, model_card, docs,
            graph_id=new_ulid(), node_id=new_ulid(), corpus_name="The Pile",
            model_card_uri="model", training_docs_uri="docs",
        )


def test_cli_checkpoint_provenance_preserves_sources_by_role(tmp_path: Path):
    measurements, checkpoint_map, model_card, docs = _write_inputs(tmp_path)
    store_path = tmp_path / "data"
    code, out, err = run(["init", "--title", "checkpoint provenance"], store=store_path)
    assert code == 0, err
    session_id = out.strip()
    claim = (
        "Across EleutherAI/pythia-14m training, target ' Paris' improved "
        "from rank 28,000 to 276, but final generation did not emit it."
    )
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(json.dumps({"role": "assistant", "text": claim}) + "\n")
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({
        "nodes": [{"local_id": "trajectory", "kind": "claim", "text": claim,
                   "status": "accepted"}],
        "edges": [],
    }))
    code, out, err = run([
        "compile", "--session", session_id, "--mode", "posthoc",
        "--transcript", str(transcript), "--from-graph", str(gold),
    ], store=store_path)
    assert code == 0, err
    store = Store(store_path)
    graph = store.load_graph(out.strip())
    code, out, err = run([
        "provenance", "checkpoint", "--graph", graph.id, "--node", graph.nodes[0].id,
        "--session", session_id, "--measurements", str(measurements),
        "--checkpoint-map", str(checkpoint_map), "--model-card", str(model_card),
        "--model-card-uri", "https://example.test/model", "--training-docs", str(docs),
        "--training-docs-uri", "https://example.test/docs", "--corpus", "The Pile",
    ], store=store_path)
    assert code == 0, err
    artifact = next(store.training_provenance_dir(session_id).glob("*.json"))
    stored = json.loads(artifact.read_text())
    for source in stored["sources"]:
        preserved = store.sensor_sources_dir(session_id) / f"{source['sha256']}.bin"
        assert preserved.exists()
    evidence = list(store.iter_evidence(session_id, graph_id=graph.id))
    assert evidence[0]["kind"] == "checkpoint_emergence"
