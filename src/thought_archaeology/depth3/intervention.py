from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Literal, Self

from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import SCHEMA_VERSION

InterventionResult = Literal["supports", "contradicts", "inconclusive"]


class InterventionError(Exception):
    """A claimed neural intervention lacks a verifiable causal result."""


@dataclass(frozen=True)
class NeuralIntervention:
    schema_version: str
    id: str
    attribution_id: str
    graph_id: str
    node_id: str
    prompt: str
    target: str
    edit: dict
    hypothesis: dict
    baseline: dict
    intervened: dict
    observed_delta: float
    result: InterventionResult
    execution: dict
    created_at: str

    @classmethod
    def from_dict(cls, d: dict) -> Self:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            id=d["id"],
            attribution_id=d["attribution_id"],
            graph_id=d["graph_id"],
            node_id=d["node_id"],
            prompt=d["prompt"],
            target=d["target"],
            edit=dict(d["edit"]),
            hypothesis=dict(d["hypothesis"]),
            baseline=dict(d["baseline"]),
            intervened=dict(d["intervened"]),
            observed_delta=float(d["observed_delta"]),
            result=d["result"],
            execution=dict(d["execution"]),
            created_at=d["created_at"],
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "attribution_id": self.attribution_id,
            "graph_id": self.graph_id,
            "node_id": self.node_id,
            "prompt": self.prompt,
            "target": self.target,
            "edit": self.edit,
            "hypothesis": self.hypothesis,
            "baseline": self.baseline,
            "intervened": self.intervened,
            "observed_delta": self.observed_delta,
            "result": self.result,
            "execution": self.execution,
            "created_at": self.created_at,
        }


def _classify(delta: float, direction: str, minimum: float) -> InterventionResult:
    if abs(delta) < minimum:
        return "inconclusive"
    if direction == "change":
        return "supports"
    if direction == "increase":
        return "supports" if delta > 0 else "contradicts"
    if direction == "decrease":
        return "supports" if delta < 0 else "contradicts"
    raise InterventionError(f"unsupported expected_direction: {direction}")


def import_intervention_result(
    path: Path,
    *,
    graph_id: str,
    node_id: str,
    source_uri: str,
) -> NeuralIntervention:
    """Build a checked artifact from raw baseline/intervention observations."""
    source = path.read_bytes()
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InterventionError(f"intervention result is not JSON: {exc}") from exc
    required = {
        "attribution_id", "model", "prompt", "target", "method",
        "runner_revision", "device", "edit", "hypothesis", "baseline", "intervened",
    }
    missing = sorted(required - raw.keys())
    if missing:
        raise InterventionError(f"intervention result missing: {', '.join(missing)}")
    for observation in ("baseline", "intervened"):
        value = raw[observation].get("target_value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InterventionError(f"{observation}.target_value must be numeric")
    baseline = float(raw["baseline"]["target_value"])
    intervened = float(raw["intervened"]["target_value"])
    delta = intervened - baseline
    minimum = raw["hypothesis"].get("minimum_absolute_change")
    if isinstance(minimum, bool) or not isinstance(minimum, (int, float)) or minimum < 0:
        raise InterventionError("hypothesis.minimum_absolute_change must be >= 0")
    result = _classify(delta, raw["hypothesis"].get("expected_direction"), float(minimum))
    execution = {
        "model": raw["model"],
        "method": raw["method"],
        "runner_revision": raw["runner_revision"],
        "device": raw["device"],
        "source_uri": source_uri,
        "source_sha256": hashlib.sha256(source).hexdigest(),
    }
    return NeuralIntervention(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        attribution_id=raw["attribution_id"],
        graph_id=graph_id,
        node_id=node_id,
        prompt=raw["prompt"],
        target=raw["target"],
        edit=dict(raw["edit"]),
        hypothesis=dict(raw["hypothesis"]),
        baseline=dict(raw["baseline"]),
        intervened=dict(raw["intervened"]),
        observed_delta=delta,
        result=result,
        execution=execution,
        created_at=now_iso(),
    )


def import_neuronpedia_result(
    request_path: Path,
    response_path: Path,
    manifest_path: Path,
    *,
    graph_id: str,
    node_id: str,
    source_uri: str,
) -> NeuralIntervention:
    """Verify a preregistered Neuronpedia graph-steering request and response."""
    request_bytes = request_path.read_bytes()
    response_bytes = response_path.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    request = json.loads(request_bytes)
    response = json.loads(response_bytes)
    manifest = json.loads(manifest_bytes)
    request_digest = hashlib.sha256(request_bytes).hexdigest()
    if manifest.get("request_sha256") != request_digest:
        raise InterventionError("manifest request_sha256 does not match exact request bytes")
    features = request.get("features")
    if not isinstance(features, list) or len(features) != 1:
        raise InterventionError("first causal slice requires exactly one steered feature")
    feature = features[0]
    target = manifest.get("target")
    if not isinstance(target, str) or not target:
        raise InterventionError("manifest target must be a non-empty token string")
    prompt = request.get("prompt")
    default_generation = response.get("DEFAULT_GENERATION")
    steered_generation = response.get("STEERED_GENERATION")
    if not all(isinstance(value, str) for value in (prompt, default_generation, steered_generation)):
        raise InterventionError("Neuronpedia response lacks default or steered generation")
    prefix = "<bos>" + prompt
    if not default_generation.startswith(prefix) or not steered_generation.startswith(prefix):
        raise InterventionError("response generations do not continue the exact request prompt")
    default_continuation = default_generation[len(prefix):]
    steered_continuation = steered_generation[len(prefix):]
    baseline_value = 1.0 if default_continuation.startswith(target) else 0.0
    intervened_value = 1.0 if steered_continuation.startswith(target) else 0.0
    hypothesis = {
        "metric": "target_token_generated",
        "expected_direction": manifest.get("expected_direction"),
        "minimum_absolute_change": manifest.get("minimum_absolute_change"),
    }
    minimum = hypothesis["minimum_absolute_change"]
    if isinstance(minimum, bool) or not isinstance(minimum, (int, float)) or minimum < 0:
        raise InterventionError("manifest minimum_absolute_change must be >= 0")
    delta = intervened_value - baseline_value
    result = _classify(delta, hypothesis["expected_direction"], float(minimum))

    def first_top_token(key: str) -> str:
        rows = response.get(key)
        if not isinstance(rows, list):
            raise InterventionError(f"response lacks {key}")
        for row in rows:
            logits = row.get("top_logits") if isinstance(row, dict) else None
            if isinstance(logits, list) and logits:
                token = logits[0].get("token")
                if isinstance(token, str) and token:
                    return token
        raise InterventionError(f"response {key} has no top-token observation")

    ablate = feature.get("ablate") is True
    edit = {
        "operation": "ablate" if ablate else "add_delta",
        "layer": feature.get("layer"),
        "position": feature.get("token_active_position"),
        "feature_index": feature.get("index"),
        "baseline_activation": None,
        "set_to": 0.0 if ablate else None,
        "delta": None if ablate else feature.get("delta"),
    }
    execution = {
        "model": request.get("modelId"),
        "method": "Neuronpedia /api/steer-logits feature intervention",
        "runner_revision": manifest.get("runner_revision"),
        "device": "Neuronpedia remote service (device undisclosed)",
        "source_uri": source_uri,
        "source_sha256": hashlib.sha256(response_bytes).hexdigest(),
        "request_sha256": request_digest,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
    }
    return NeuralIntervention(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        attribution_id=manifest["attribution_id"],
        graph_id=graph_id,
        node_id=node_id,
        prompt=prompt,
        target=target,
        edit=edit,
        hypothesis=hypothesis,
        baseline={"target_value": baseline_value, "top_token": first_top_token("DEFAULT_LOGITS_BY_TOKEN")},
        intervened={"target_value": intervened_value, "top_token": first_top_token("STEERED_LOGITS_BY_TOKEN")},
        observed_delta=delta,
        result=result,
        execution=execution,
        created_at=now_iso(),
    )
