from __future__ import annotations

from thought_archaeology.ids import is_ulid, new_ulid
from thought_archaeology.models import (
    SCHEMA_VERSION,
    ForkRef,
    ModelInfo,
    Span,
    ThoughtEdge,
    ThoughtGraph,
    ThoughtNode,
)
from thought_archaeology.schema import policy_warnings as graph_policy_warnings

SOURCE_FROM_MODE = {
    "structured_emit": "structured_emit",
    "posthoc": "posthoc_compile",
}

STATUS_DEFAULTS = {
    "rejected_alternative": "rejected",
    "uncertainty": "uncertain",
}


class CompileError(Exception):
    """Unparseable emit or unrecoverable compile failure."""

    def __init__(self, message: str, offset: int | None = None):
        self.offset = offset
        if offset is not None:
            message = f"{message} (offset {offset})"
        super().__init__(message)


def bind_span(prose: str, node_text: str) -> Span | None:
    if not prose or not node_text:
        return None
    idx = prose.find(node_text)
    if idx >= 0:
        return Span(idx, idx + len(node_text))
    # try first 80 chars of node_text if longer
    needle = node_text[:80]
    idx = prose.find(needle)
    if idx >= 0:
        return Span(idx, idx + len(needle))
    return None


def finalize(
    *,
    session_id: str,
    turn_id: str,
    prose: str,
    raw_nodes: list[dict],
    raw_edges: list[dict],
    model: ModelInfo,
    now: str,
    parent_graph_id: str | None = None,
    fork: ForkRef | None = None,
    hidden_reasoning: str | None = None,
    reuse_node_ids: bool = False,
    drop_orphan_edges: bool = False,
) -> ThoughtGraph:
    graph_id = new_ulid()
    source = SOURCE_FROM_MODE[model.compile_mode]
    id_map: dict[str, str] = {}
    nodes: list[ThoughtNode] = []

    for raw in raw_nodes:
        kind = raw.get("kind")
        text = raw.get("text")
        if not kind or not text:
            raise CompileError("each node requires kind and text")
        existing_id = raw.get("id")
        if reuse_node_ids and isinstance(existing_id, str) and is_ulid(existing_id):
            nid = existing_id
        else:
            nid = new_ulid()
        local = raw.get("local_id")
        if local:
            id_map[str(local)] = nid
        if existing_id:
            id_map[str(existing_id)] = nid
        id_map[nid] = nid

        if raw.get("status"):
            status = raw["status"]
        else:
            status = STATUS_DEFAULTS.get(kind, "accepted")

        span = None
        if isinstance(raw.get("span"), dict):
            span = Span.from_dict(raw["span"])
        else:
            span = bind_span(prose, str(text))

        nodes.append(
            ThoughtNode(
                id=nid,
                kind=kind,
                text=str(text),
                status=status,
                agent=raw.get("agent") or "model",
                created_at=raw.get("created_at") if raw.get("created_at") else now,
                source=raw.get("source") or source,
                confidence=raw.get("confidence"),
                span=span,
                tags=tuple(raw["tags"]) if raw.get("tags") else (),
                notes=raw.get("notes"),
                probe_ids=tuple(raw["probe_ids"]) if raw.get("probe_ids") else (),
                sensor_ids=tuple(raw["sensor_ids"]) if raw.get("sensor_ids") else (),
            )
        )

    node_ids = {n.id for n in nodes}
    edges: list[ThoughtEdge] = []
    for raw in raw_edges:
        src_key = raw.get("from") or raw.get("source_id")
        tgt_key = raw.get("to") or raw.get("target_id")
        kind = raw.get("kind")
        if not kind:
            raise CompileError("each edge requires kind")
        src = id_map.get(str(src_key), src_key)
        tgt = id_map.get(str(tgt_key), tgt_key)
        if src not in node_ids or tgt not in node_ids:
            if drop_orphan_edges:
                continue
            raise CompileError(
                f"edge endpoint missing: {src_key!r} -> {tgt_key!r} (kind {kind})"
            )
        edges.append(
            ThoughtEdge(
                id=new_ulid(),
                source_id=src,
                target_id=tgt,
                kind=kind,
                created_at=now,
                notes=raw.get("notes"),
            )
        )

    return ThoughtGraph(
        schema_version=SCHEMA_VERSION,
        id=graph_id,
        session_id=session_id,
        turn_id=turn_id,
        created_at=now,
        prose=prose,
        nodes=tuple(nodes),
        edges=tuple(edges),
        model=model,
        parent_graph_id=parent_graph_id,
        fork=fork,
        hidden_reasoning=hidden_reasoning,
    )


def policy_warnings(graph: ThoughtGraph) -> list[str]:
    return graph_policy_warnings(graph)
