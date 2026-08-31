from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Self

from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import SCHEMA_VERSION, ThoughtGraph, ThoughtNode
from thought_archaeology.schema import policy_warnings

if TYPE_CHECKING:
    from thought_archaeology.store import Store

ContinuationSource = Literal["inhabit_space", "workspace", "cli"]


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
class ContinuationAttempt:
    """Append-only receipt that a named harness began handling a request."""

    schema_version: str
    id: str
    request_id: str
    created_at: str
    harness: str

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            id=data["id"],
            request_id=data["request_id"],
            created_at=data["created_at"],
            harness=data["harness"],
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "request_id": self.request_id,
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


def continuation_attempt(request_id: str, harness: str) -> ContinuationAttempt:
    return ContinuationAttempt(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        request_id=request_id,
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


def harness_display_name(name: str) -> str:
    return {
        "grok": "Grok",
        "codex": "Codex",
        "claude": "Claude",
        "opencode": "OpenCode",
        "prime-agent": "Prime Agent",
    }.get(name, name.replace("-", " ").title())


def _node_read(node: ThoughtNode) -> dict:
    return {
        "id": node.id,
        "kind": node.kind,
        "text": node.text,
        "status": node.status,
    }


def _completed_groups(
    store: Store,
) -> tuple[dict[tuple[str, str, str, str], list], dict]:
    requests = {item.id: item for item in store.iter_continuation_requests()}
    completions = {
        item.request_id: item for item in store.iter_continuation_completions()
    }
    groups: dict[tuple[str, str, str, str], list] = {}
    for request_id, completion in completions.items():
        request = requests.get(request_id)
        if request is None:
            continue
        key = (
            request.session_id,
            request.graph_id,
            request.node_id,
            request.prompt,
        )
        groups.setdefault(key, []).append((request, completion))
    for paths in groups.values():
        paths.sort(key=lambda item: (item[1].created_at, item[1].id))
    return groups, requests


def parallel_group_summaries(
    store: Store,
    *,
    session_id: str | None = None,
    graph_id: str | None = None,
    node_id: str | None = None,
) -> list[dict]:
    """Read-only exact-source, exact-prompt continuation groups."""
    groups, requests = _completed_groups(store)
    cancellations = {
        item.request_id for item in store.iter_continuation_cancellations()
    }
    summaries = []
    for key, paths in groups.items():
        sid, gid, nid, prompt = key
        if len(paths) < 2:
            continue
        if session_id is not None and sid != session_id:
            continue
        if graph_id is not None and gid != graph_id:
            continue
        if node_id is not None and nid != node_id:
            continue
        source_graph = store.load_graph(gid)
        source_node = next(
            (node for node in source_graph.nodes if node.id == nid), None
        )
        if source_node is None:
            continue
        matching_requests = [
            request
            for request in requests.values()
            if (
                request.session_id,
                request.graph_id,
                request.node_id,
                request.prompt,
            )
            == key
        ]
        completed_ids = {request.id for request, _completion in paths}
        canceled_count = sum(
            request.id in cancellations for request in matching_requests
        )
        pending_count = sum(
            request.id not in completed_ids and request.id not in cancellations
            for request in matching_requests
        )
        harnesses = []
        seen_harnesses = set()
        for _request, completion in paths:
            if completion.harness in seen_harnesses:
                continue
            seen_harnesses.add(completion.harness)
            harnesses.append(
                {
                    "name": completion.harness,
                    "display_name": harness_display_name(completion.harness),
                }
            )
        representative = paths[0][0]
        summaries.append(
            {
                "representative_request_id": representative.id,
                "session_id": sid,
                "source_graph_id": gid,
                "source_node_id": nid,
                "source_thought": _node_read(source_node),
                "prompt": prompt,
                "completed_count": len(paths),
                "counts": {
                    "completed": len(paths),
                    "failed": 0,
                    "canceled": canceled_count,
                    "pending": pending_count,
                },
                "harnesses": harnesses,
                "request_ids": [request.id for request, _completion in paths],
                "graph_ids": [completion.graph_id for _request, completion in paths],
            }
        )
    summaries.sort(
        key=lambda item: (
            item["session_id"],
            item["source_graph_id"],
            item["source_node_id"],
            item["prompt"],
            item["representative_request_id"],
        )
    )
    return summaries


def parallel_comparison(
    store: Store,
    request_id: str,
    *,
    graph_id: str | None = None,
    node_id: str | None = None,
) -> dict:
    """Return the complete server-authored reading for one eligible group."""
    from thought_archaeology.inhabit import entry_node
    from thought_archaeology.store import StoreError

    request = store.load_continuation_request(request_id)
    if graph_id is not None and request.graph_id != graph_id:
        raise StoreError(f"request {request_id} is not from graph {graph_id}")
    if node_id is not None and request.node_id != node_id:
        raise StoreError(f"request {request_id} is not from node {node_id}")

    groups, _requests = _completed_groups(store)
    key = (
        request.session_id,
        request.graph_id,
        request.node_id,
        request.prompt,
    )
    paths = groups.get(key, [])
    if not any(item.id == request.id for item, _completion in paths):
        raise StoreError(f"continuation request {request_id} is not completed")
    if len(paths) < 2:
        raise StoreError(f"continuation request {request_id} has no parallel paths")

    summary = next(
        item
        for item in parallel_group_summaries(
            store,
            session_id=request.session_id,
            graph_id=request.graph_id,
            node_id=request.node_id,
        )
        if request.id in item["request_ids"]
    )
    recorded_by_request = {}
    for event in store.iter_log_entries():
        if event.get("op") != "harness_continue":
            continue
        event_request = event.get("request_id")
        warnings = event.get("warnings")
        if isinstance(event_request, str) and isinstance(warnings, list):
            recorded_by_request[event_request] = [
                warning for warning in warnings if isinstance(warning, str)
            ]

    readings = []
    for path_request, completion in paths:
        graph = store.load_graph(completion.graph_id)
        entry = entry_node(graph)
        readings.append(
            {
                "request_id": path_request.id,
                "completion_id": completion.id,
                "graph_id": graph.id,
                "harness": completion.harness,
                "harness_display_name": harness_display_name(completion.harness),
                "model": graph.model.name,
                "created_at": completion.created_at,
                "entry_node": _node_read(entry) if entry else None,
                "judgment_calls": [
                    _node_read(node)
                    for node in graph.nodes
                    if node.kind in {"judgment_call", "taste_call"}
                ],
                "uncertainties": [
                    _node_read(node)
                    for node in graph.nodes
                    if node.kind == "uncertainty"
                ],
                "rejected_alternatives": [
                    _node_read(node)
                    for node in graph.nodes
                    if node.kind == "rejected_alternative"
                ],
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "recorded_warnings": recorded_by_request.get(path_request.id, []),
                "current_policy_warnings": policy_warnings(graph),
            }
        )
    return {**summary, "paths": readings}
