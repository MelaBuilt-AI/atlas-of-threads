from __future__ import annotations

import hashlib
import json
from pathlib import Path

from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import SCHEMA_VERSION


class TrainingProvenanceError(Exception):
    """Training provenance is incomplete or overclaims its evidence level."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_checkpoint_emergence(
    measurements_path: Path,
    checkpoint_map_path: Path,
    model_card_path: Path,
    training_docs_path: Path,
    *,
    graph_id: str,
    node_id: str,
    corpus_name: str,
    model_card_uri: str,
    training_docs_uri: str,
) -> dict:
    """Build bounded checkpoint evidence; never infer record or weight influence."""
    rows = [json.loads(line) for line in measurements_path.read_text().splitlines() if line.strip()]
    checkpoint_map = json.loads(checkpoint_map_path.read_text())
    if len(rows) < 2:
        raise TrainingProvenanceError("checkpoint emergence requires at least two measurements")
    models = {row.get("model") for row in rows}
    prompts = {row.get("prompt") for row in rows}
    targets = {row.get("target") for row in rows}
    if len(models) != 1 or len(prompts) != 1 or len(targets) != 1:
        raise TrainingProvenanceError("measurements must share exact model, prompt, and target")
    measurements = []
    seen_revisions = set()
    for row in rows:
        revision = row.get("revision")
        if revision in seen_revisions:
            raise TrainingProvenanceError(f"duplicate checkpoint revision: {revision}")
        seen_revisions.add(revision)
        provenance = checkpoint_map.get(revision)
        if not isinstance(provenance, dict):
            raise TrainingProvenanceError(f"checkpoint map lacks revision: {revision}")
        measurements.append({
            "revision": revision,
            "commit": provenance["commit"],
            "training_tokens": int(provenance["training_tokens"]),
            "weight_sha256": provenance["weight_sha256"],
            "target_probability": float(row["target_probability"]),
            "target_rank": int(row["target_rank"]),
            "generation": row["generation"],
        })
    measurements.sort(key=lambda item: item["training_tokens"])
    if measurements[0]["training_tokens"] != 0:
        raise TrainingProvenanceError("checkpoint trajectory must include initialization")
    if len({item["training_tokens"] for item in measurements}) != len(measurements):
        raise TrainingProvenanceError("checkpoint token counts must be distinct")
    first, last = measurements[0], measurements[-1]
    prompt = next(iter(prompts))
    target = next(iter(targets))
    continuation = last["generation"][len(prompt):] if last["generation"].startswith(prompt) else ""
    observed = {
        "initial_rank": first["target_rank"],
        "final_rank": last["target_rank"],
        "rank_improvement": first["target_rank"] - last["target_rank"],
        "initial_probability": first["target_probability"],
        "final_probability": last["target_probability"],
        "target_generated_at_final": continuation.startswith(target),
    }
    result = (
        "supports"
        if observed["rank_improvement"] > 0
        and observed["final_probability"] > observed["initial_probability"]
        else "inconclusive"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "id": new_ulid(),
        "level": "checkpoint_emergence",
        "graph_id": graph_id,
        "node_id": node_id,
        "model": next(iter(models)),
        "training_corpus": {
            "name": corpus_name,
            "relationship": "declared_by_model_publisher",
        },
        "prompt": prompt,
        "target": target,
        "measurements": measurements,
        "observed": observed,
        "boundaries": {
            "record_membership": "not_tested",
            "example_influence": "not_measured",
            "weight_attribution": "not_measured",
            "analysis_mode": "exploratory",
        },
        "sources": [
            {"role": "model_card", "uri": model_card_uri, "sha256": _sha(model_card_path)},
            {"role": "training_documentation", "uri": training_docs_uri, "sha256": _sha(training_docs_path)},
            {"role": "checkpoint_measurements", "uri": f"file:{measurements_path.name}", "sha256": _sha(measurements_path)},
            {"role": "checkpoint_map", "uri": f"file:{checkpoint_map_path.name}", "sha256": _sha(checkpoint_map_path)},
        ],
        "result": result,
        "created_at": now_iso(),
    }
