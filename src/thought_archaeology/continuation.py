from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Self

from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import SCHEMA_VERSION, ThoughtGraph, ThoughtNode

ContinuationSource = Literal["inhabit_space", "cli"]


@dataclass(frozen=True)
class ContinuationRequest:
    """A provider-neutral request for an AI harness to continue from a chamber."""

    schema_version: str
    id: str
    session_id: str
    graph_id: str
    node_id: str
    created_at: str
    prompt: str
    source: ContinuationSource

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            id=data["id"],
            session_id=data["session_id"],
            graph_id=data["graph_id"],
            node_id=data["node_id"],
            created_at=data["created_at"],
            prompt=data.get("prompt", ""),
            source=data["source"],
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "session_id": self.session_id,
            "graph_id": self.graph_id,
            "node_id": self.node_id,
            "created_at": self.created_at,
            "prompt": self.prompt,
            "source": self.source,
        }


@dataclass(frozen=True)
class ContinuationCompletion:
    """Append-only receipt linking a request to the graph a harness produced."""

    schema_version: str
    id: str
    request_id: str
    graph_id: str
    created_at: str
    harness: str

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            id=data["id"],
            request_id=data["request_id"],
            graph_id=data["graph_id"],
            created_at=data["created_at"],
            harness=data["harness"],
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "request_id": self.request_id,
            "graph_id": self.graph_id,
            "created_at": self.created_at,
            "harness": self.harness,
        }


@dataclass(frozen=True)
class ContinuationCancellation:
    """Append-only receipt withdrawing a request before harness completion."""

    schema_version: str
    id: str
    request_id: str
    created_at: str
    source: ContinuationSource

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            id=data["id"],
            request_id=data["request_id"],
            created_at=data["created_at"],
            source=data["source"],
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "request_id": self.request_id,
            "created_at": self.created_at,
            "source": self.source,
        }


def continuation_request(
    graph: ThoughtGraph,
    node: ThoughtNode,
    *,
    prompt: str = "",
    source: ContinuationSource = "cli",
) -> ContinuationRequest:
    return ContinuationRequest(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        session_id=graph.session_id,
        graph_id=graph.id,
        node_id=node.id,
        created_at=now_iso(),
        prompt=prompt.strip(),
        source=source,
    )


def continuation_completion(
    request_id: str,
    graph_id: str,
    harness: str,
) -> ContinuationCompletion:
    return ContinuationCompletion(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        request_id=request_id,
        graph_id=graph_id,
        created_at=now_iso(),
        harness=harness.strip(),
    )


def continuation_cancellation(
    request_id: str,
    *,
    source: ContinuationSource = "cli",
) -> ContinuationCancellation:
    return ContinuationCancellation(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        request_id=request_id,
        created_at=now_iso(),
        source=source,
    )
