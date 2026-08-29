from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal, Self

from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import SCHEMA_VERSION, ThoughtGraph, ThoughtNode, Turn

EvidenceKind = Literal[
    "story_report",
    "context_provenance",
    "behavioral_intervention",
    "activation_correlation",
    "neural_intervention",
    "recurring_circuit",
    "training_influence",
    "training_provenance",
    "checkpoint_emergence",
]
EvidenceResult = Literal["supports", "contradicts", "inconclusive"]


@dataclass(frozen=True)
class EvidenceBinding:
    """A typed evidence link to a thought-node, never an identity claim."""

    schema_version: str
    id: str
    graph_id: str
    node_id: str
    kind: EvidenceKind
    result: EvidenceResult
    summary: str
    artifact_refs: tuple[str, ...]
    created_at: str
    parent_evidence_id: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> Self:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            id=d["id"],
            graph_id=d["graph_id"],
            node_id=d["node_id"],
            kind=d["kind"],
            result=d["result"],
            summary=d["summary"],
            artifact_refs=tuple(d["artifact_refs"]),
            created_at=d["created_at"],
            parent_evidence_id=d.get("parent_evidence_id"),
        )

    def to_dict(self) -> dict:
        data = {
            "schema_version": self.schema_version,
            "id": self.id,
            "graph_id": self.graph_id,
            "node_id": self.node_id,
            "kind": self.kind,
            "result": self.result,
            "summary": self.summary,
            "artifact_refs": list(self.artifact_refs),
            "created_at": self.created_at,
        }
        if self.parent_evidence_id is not None:
            data["parent_evidence_id"] = self.parent_evidence_id
        return data


def context_provenance_binding(
    graph: ThoughtGraph,
    node: ThoughtNode,
    turn: Turn,
    *,
    parent_evidence_id: str | None = None,
    evidence_id: str | None = None,
    created_at: str | None = None,
) -> EvidenceBinding:
    """Bind an immutable preceding turn without claiming causal influence."""
    canonical = json.dumps(
        turn.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    return EvidenceBinding(
        schema_version=SCHEMA_VERSION,
        id=evidence_id or new_ulid(),
        graph_id=graph.id,
        node_id=node.id,
        kind="context_provenance",
        result="inconclusive",
        summary=(
            f"Stored {turn.role} turn {turn.seq} preceded this graph; "
            "provenance alone does not show causal influence."
        ),
        artifact_refs=(f"turn:{turn.id}", f"sha256:{digest}"),
        created_at=created_at or now_iso(),
        parent_evidence_id=parent_evidence_id,
    )
