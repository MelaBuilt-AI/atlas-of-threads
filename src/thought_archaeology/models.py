from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, Self

SCHEMA_VERSION = "1.0.0"

NodeKind = Literal[
    "claim",
    "premise",
    "analogy",
    "judgment_call",
    "taste_call",  # legacy graphs
    "uncertainty",
    "rejected_alternative",
]
# v1 does not include "discarded": fork omits the target node rather than
# marking it. "vetoed" is written only by `ta veto`.
NodeStatus = Literal["accepted", "rejected", "uncertain", "vetoed"]
Agent = Literal["model", "human"]
Source = Literal[
    "structured_emit",
    "posthoc_compile",
    "human",
    "intervention",  # Depth 2
    "sensor",  # Depth 3
]
# v1 has no source="fork". Fork-ness lives on ForkRef / parent_graph_id.
# Copied nodes keep their original source. Regenerated nodes use compile_mode.
# v1 edges are in-graph only. Cross-graph relations live on ForkRef.
# Do not add forks_from or replaces in v1.
EdgeKind = Literal[
    "supports",
    "contradicts",
    "analogizes",
    "qualifies",
    "rejects",
    "depends_on",
    "shapes",
    "taste_of",  # legacy graphs
    "vetoes",
]
CompileMode = Literal["structured_emit", "posthoc"]
ProviderName = Literal["none", "file", "stdin", "shell"]
TurnRole = Literal["user", "assistant", "human_edit", "system"]


def _omit_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _as_tuple(value: Any) -> tuple:
    if value is None:
        return ()
    return tuple(value)


@dataclass(frozen=True)
class Span:
    start: int  # inclusive char offset into ThoughtGraph.prose
    end: int  # exclusive
    unit: Literal["char"] = "char"

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> Span | None:
        if not d:
            return None
        return cls(start=int(d["start"]), end=int(d["end"]), unit=d.get("unit", "char"))

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start, "end": self.end, "unit": self.unit}


@dataclass(frozen=True)
class ThoughtNode:
    id: str
    kind: NodeKind
    text: str
    status: NodeStatus
    agent: Agent
    created_at: str  # UTC, seconds + Z only: YYYY-MM-DDTHH:MM:SSZ
    source: Source
    confidence: float | None = None  # 0.0–1.0 if present
    span: Span | None = None
    tags: tuple[str, ...] = ()
    notes: str | None = None
    probe_ids: tuple[str, ...] = ()  # ULIDs; empty at Depth 1
    sensor_ids: tuple[str, ...] = ()  # ULIDs; empty at Depth 1

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        return cls(
            id=d["id"],
            kind=d["kind"],
            text=d["text"],
            status=d["status"],
            agent=d["agent"],
            created_at=d["created_at"],
            source=d["source"],
            confidence=d.get("confidence"),
            span=Span.from_dict(d.get("span")),
            tags=_as_tuple(d.get("tags")),
            notes=d.get("notes"),
            probe_ids=_as_tuple(d.get("probe_ids")),
            sensor_ids=_as_tuple(d.get("sensor_ids")),
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "status": self.status,
            "agent": self.agent,
            "created_at": self.created_at,
            "source": self.source,
        }
        if self.confidence is not None:
            d["confidence"] = self.confidence
        if self.span is not None:
            d["span"] = self.span.to_dict()
        if self.tags:
            d["tags"] = list(self.tags)
        if self.notes is not None:
            d["notes"] = self.notes
        if self.probe_ids:
            d["probe_ids"] = list(self.probe_ids)
        if self.sensor_ids:
            d["sensor_ids"] = list(self.sensor_ids)
        return d


@dataclass(frozen=True)
class ThoughtEdge:
    id: str
    source_id: str  # from-node
    target_id: str  # to-node
    kind: EdgeKind
    created_at: str
    notes: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        return cls(
            id=d["id"],
            source_id=d["source_id"],
            target_id=d["target_id"],
            kind=d["kind"],
            created_at=d["created_at"],
            notes=d.get("notes"),
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "kind": self.kind,
            "created_at": self.created_at,
        }
        if self.notes is not None:
            d["notes"] = self.notes
        return d


@dataclass(frozen=True)
class ForkRef:
    from_graph_id: str  # ULID; always == parent_graph_id
    from_node_id: str  # ULID; the node we stood on in G0
    discarded_graph_id: str | None = None  # G0.id for fork; null for veto
    reason: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> ForkRef | None:
        if not d:
            return None
        return cls(
            from_graph_id=d["from_graph_id"],
            from_node_id=d["from_node_id"],
            discarded_graph_id=d.get("discarded_graph_id"),
            reason=d.get("reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        return _omit_none(
            {
                "from_graph_id": self.from_graph_id,
                "from_node_id": self.from_node_id,
                "discarded_graph_id": self.discarded_graph_id,
                "reason": self.reason,
            }
        )


@dataclass(frozen=True)
class ModelInfo:
    provider: ProviderName  # not "grok-tui" — that belongs on Session.origin
    name: str  # e.g. "grok-4.6-build"; default "unknown"
    compile_mode: CompileMode

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        return cls(
            provider=d["provider"],
            name=d["name"],
            compile_mode=d["compile_mode"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "name": self.name,
            "compile_mode": self.compile_mode,
        }


@dataclass(frozen=True)
class ThoughtGraph:
    schema_version: str
    id: str
    session_id: str
    turn_id: str
    created_at: str
    prose: str
    nodes: tuple[ThoughtNode, ...]
    edges: tuple[ThoughtEdge, ...]
    model: ModelInfo
    parent_graph_id: str | None = None
    fork: ForkRef | None = None
    hidden_reasoning: str | None = None  # never exported to wiki by default
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            id=d["id"],
            session_id=d["session_id"],
            turn_id=d["turn_id"],
            created_at=d["created_at"],
            prose=d.get("prose", ""),
            nodes=tuple(ThoughtNode.from_dict(n) for n in d.get("nodes") or ()),
            edges=tuple(ThoughtEdge.from_dict(e) for e in d.get("edges") or ()),
            model=ModelInfo.from_dict(d["model"]),
            parent_graph_id=d.get("parent_graph_id"),
            fork=ForkRef.from_dict(d.get("fork")),
            hidden_reasoning=d.get("hidden_reasoning"),
            metadata=MappingProxyType(dict(d.get("metadata") or {})),
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "id": self.id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "created_at": self.created_at,
            "prose": self.prose,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "model": self.model.to_dict(),
        }
        if self.parent_graph_id is not None:
            d["parent_graph_id"] = self.parent_graph_id
        if self.fork is not None:
            d["fork"] = self.fork.to_dict()
        if self.hidden_reasoning is not None:
            d["hidden_reasoning"] = self.hidden_reasoning
        d["metadata"] = json.loads(json.dumps(dict(self.metadata)))
        return d


@dataclass(frozen=True)
class Turn:
    schema_version: str
    id: str
    session_id: str
    seq: int  # 0-based, dense in the session file
    role: TurnRole  # `ta veto` writes human_edit; compile writes user|assistant
    created_at: str
    prose: str
    graph_id: str | None
    parent_turn_id: str | None
    fork_of_node_id: str | None
    provider: ProviderName | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            id=d["id"],
            session_id=d["session_id"],
            seq=int(d["seq"]),
            role=d["role"],
            created_at=d["created_at"],
            prose=d.get("prose", ""),
            graph_id=d.get("graph_id"),
            parent_turn_id=d.get("parent_turn_id"),
            fork_of_node_id=d.get("fork_of_node_id"),
            provider=d.get("provider"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "session_id": self.session_id,
            "seq": self.seq,
            "role": self.role,
            "created_at": self.created_at,
            "prose": self.prose,
            "graph_id": self.graph_id,
            "parent_turn_id": self.parent_turn_id,
            "fork_of_node_id": self.fork_of_node_id,
            "provider": self.provider,
        }


@dataclass(frozen=True)
class Session:
    schema_version: str
    id: str
    title: str
    created_at: str
    updated_at: str  # mutated on each compile/fork/veto
    tags: tuple[str, ...] = ()
    origin: str | None = None  # e.g. "example:synthetic-origin"
    head_graph_id: str | None = None
    head_turn_id: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            id=d["id"],
            title=d["title"],
            created_at=d["created_at"],
            updated_at=d["updated_at"],
            tags=_as_tuple(d.get("tags")),
            origin=d.get("origin"),
            head_graph_id=d.get("head_graph_id"),
            head_turn_id=d.get("head_turn_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": list(self.tags),
            "origin": self.origin,
            "head_graph_id": self.head_graph_id,
            "head_turn_id": self.head_turn_id,
        }
        return d
