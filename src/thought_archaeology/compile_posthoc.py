from __future__ import annotations

from thought_archaeology.compile_common import finalize, policy_warnings
from thought_archaeology.compile_structured import parse_graph_payload
from thought_archaeology.models import ForkRef, ModelInfo, ThoughtGraph


def compile_posthoc(
    prose: str,
    raw_graph_text: str,
    *,
    session_id: str,
    turn_id: str,
    model: ModelInfo,
    now: str,
    parent_graph_id: str | None = None,
    fork: ForkRef | None = None,
    hidden_reasoning: str | None = None,
    drop_orphan_edges: bool = False,
) -> tuple[ThoughtGraph, list[str]]:
    payload, _offset = parse_graph_payload(raw_graph_text)
    graph = finalize(
        session_id=session_id,
        turn_id=turn_id,
        prose=prose,
        raw_nodes=list(payload["nodes"]),
        raw_edges=list(payload["edges"]),
        model=model,
        now=now,
        parent_graph_id=parent_graph_id,
        fork=fork,
        hidden_reasoning=hidden_reasoning or payload.get("hidden_reasoning"),
        drop_orphan_edges=drop_orphan_edges,
    )
    warnings = policy_warnings(graph)
    if not prose:
        warnings = ["prose is empty", *warnings]
    return graph, warnings
