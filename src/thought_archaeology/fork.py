from __future__ import annotations

import json

from thought_archaeology.compile_common import (
    SOURCE_FROM_MODE,
    STATUS_DEFAULTS,
    CompileError,
    bind_span,
)
from thought_archaeology.compile_structured import extract_thought_graph_json
from thought_archaeology.ids import new_ulid
from thought_archaeology.models import (
    SCHEMA_VERSION,
    ForkRef,
    ModelInfo,
    ThoughtEdge,
    ThoughtGraph,
    ThoughtNode,
)
from thought_archaeology.schema import policy_warnings

PENDING_PROSE = "(fork pending regeneration)"

# Causal walk from X (what X shaped / who depends on X):
#   outgoing taste_of and supports (X → target)
#   incoming depends_on (source of source --depends_on→ X)
# Do not follow outgoing depends_on.
CAUSAL_OUTGOING = frozenset({"taste_of", "supports"})


class ForkError(Exception):
    """Fork or veto cannot proceed."""


def omit_set(graph: ThoughtGraph, node_id: str) -> set[str]:
    """Return {node_id} union causal descendants in `graph`."""
    node_ids = {n.id for n in graph.nodes}
    if node_id not in node_ids:
        raise ForkError(f"node {node_id} not in graph {graph.id}")

    walk: dict[str, set[str]] = {nid: set() for nid in node_ids}
    for edge in graph.edges:
        if edge.source_id not in node_ids or edge.target_id not in node_ids:
            continue
        if edge.kind in CAUSAL_OUTGOING:
            walk[edge.source_id].add(edge.target_id)
        elif edge.kind == "depends_on":
            walk[edge.target_id].add(edge.source_id)

    omit: set[str] = set()
    stack = [node_id]
    while stack:
        cur = stack.pop()
        if cur in omit:
            continue
        omit.add(cur)
        stack.extend(walk.get(cur, ()))
    return omit


def _copy_node(node: ThoughtNode, *, prose: str) -> ThoughtNode:
    return ThoughtNode(
        id=node.id,
        kind=node.kind,
        text=node.text,
        status=node.status,
        agent=node.agent,
        created_at=node.created_at,
        source=node.source,
        confidence=node.confidence,
        span=bind_span(prose, node.text),
        tags=node.tags,
        notes=node.notes,
        probe_ids=node.probe_ids,
        sensor_ids=node.sensor_ids,
    )


def _copy_edge(edge: ThoughtEdge, *, now: str) -> ThoughtEdge:
    return ThoughtEdge(
        id=new_ulid(),
        source_id=edge.source_id,
        target_id=edge.target_id,
        kind=edge.kind,
        created_at=now,
        notes=edge.notes,
    )


def parse_regen(text: str) -> tuple[str, list[dict], list[dict]]:
    """Parse a fork-regenerate emit into (prose, raw_nodes, raw_edges)."""
    stripped = text.strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        prose, payload, _offset = extract_thought_graph_json(text)
        return prose, list(payload["nodes"]), list(payload["edges"])
    if not isinstance(payload, dict):
        raise CompileError("thought-graph JSON must be an object")
    if "nodes" not in payload or "edges" not in payload:
        raise CompileError("thought-graph JSON must contain nodes and edges")
    if not isinstance(payload["nodes"], list) or not isinstance(payload["edges"], list):
        raise CompileError("nodes and edges must be arrays")
    return str(payload.get("prose") or ""), list(payload["nodes"]), list(payload["edges"])


def fork_regen_prompt(
    g0: ThoughtGraph,
    target: ThoughtNode,
    *,
    reason: str | None,
    now: str,
) -> str:
    omit = omit_set(g0, target.id)
    copied_nodes, copied_edges = _split_copy(g0, omit, prose=PENDING_PROSE, now=now)
    return regeneration_user_prompt(
        target=target,
        copied_nodes=tuple(copied_nodes),
        copied_edges=tuple(copied_edges),
        reason=reason,
    )


def regeneration_user_prompt(
    *,
    target: ThoughtNode,
    copied_nodes: tuple[ThoughtNode, ...],
    copied_edges: tuple[ThoughtEdge, ...],
    reason: str | None,
) -> str:
    discarded = {
        "id": target.id,
        "kind": target.kind,
        "text": target.text,
        "status": target.status,
    }
    surviving = {
        "nodes": [n.to_dict() for n in copied_nodes],
        "edges": [
            {
                "id": e.id,
                "source_id": e.source_id,
                "target_id": e.target_id,
                "kind": e.kind,
            }
            for e in copied_edges
        ],
    }
    reason_line = reason or ""
    return (
        "Discarded node:\n"
        f"{json.dumps(discarded, ensure_ascii=False)}\n\n"
        f"Reason: {reason_line}\n\n"
        "Surviving graph (node ids are stable; emit ONLY new nodes; "
        "edges may reference these ids):\n"
        f"{json.dumps(surviving, indent=2, ensure_ascii=False)}\n"
    )


def _add_regen_nodes(
    *,
    copied: list[ThoughtNode],
    raw_nodes: list[dict],
    raw_edges: list[dict],
    omit: set[str],
    prose: str,
    model: ModelInfo,
    now: str,
) -> tuple[list[ThoughtNode], list[ThoughtEdge], list[str]]:
    warnings: list[str] = []
    source = SOURCE_FROM_MODE[model.compile_mode]
    by_kt = {(n.kind, n.text): n for n in copied}
    id_map: dict[str, str] = {n.id: n.id for n in copied}
    new_nodes: list[ThoughtNode] = []

    for raw in raw_nodes:
        kind = raw.get("kind")
        text = raw.get("text")
        if not kind or not text:
            raise CompileError("each node requires kind and text")
        local = raw.get("local_id")
        existing_id = raw.get("id")

        if isinstance(existing_id, str) and existing_id in omit:
            if local:
                id_map[str(local)] = existing_id
            warnings.append(
                f"regen node {existing_id} is in the omit-set; not copied into the fork"
            )
            continue

        if isinstance(existing_id, str) and existing_id in id_map:
            if local:
                id_map[str(local)] = existing_id
            continue

        match = by_kt.get((kind, str(text)))
        if match is not None:
            if local:
                id_map[str(local)] = match.id
            if existing_id:
                id_map[str(existing_id)] = match.id
            continue

        nid = new_ulid()
        if local:
            id_map[str(local)] = nid
        if existing_id:
            id_map[str(existing_id)] = nid
        id_map[nid] = nid

        if raw.get("status"):
            status = raw["status"]
        else:
            status = STATUS_DEFAULTS.get(kind, "accepted")

        node = ThoughtNode(
            id=nid,
            kind=kind,
            text=str(text),
            status=status,
            agent=raw.get("agent") or "model",
            created_at=now,
            source=raw.get("source") or source,
            confidence=raw.get("confidence"),
            span=bind_span(prose, str(text)),
            tags=tuple(raw["tags"]) if raw.get("tags") else (),
            notes=raw.get("notes"),
            probe_ids=tuple(raw["probe_ids"]) if raw.get("probe_ids") else (),
            sensor_ids=tuple(raw["sensor_ids"]) if raw.get("sensor_ids") else (),
        )
        new_nodes.append(node)
        by_kt[(node.kind, node.text)] = node

    node_ids = {n.id for n in copied} | {n.id for n in new_nodes}
    new_edges: list[ThoughtEdge] = []
    for raw in raw_edges:
        src_key = raw.get("from") or raw.get("source_id")
        tgt_key = raw.get("to") or raw.get("target_id")
        kind = raw.get("kind")
        if not kind:
            raise CompileError("each edge requires kind")
        src = id_map.get(str(src_key), src_key)
        tgt = id_map.get(str(tgt_key), tgt_key)
        if src in omit or tgt in omit:
            warnings.append(
                f"regen edge {src_key!r} -> {tgt_key!r} touches omit-set; dropped"
            )
            continue
        if src not in node_ids or tgt not in node_ids:
            raise CompileError(
                f"edge endpoint missing: {src_key!r} -> {tgt_key!r} (kind {kind})"
            )
        new_edges.append(
            ThoughtEdge(
                id=new_ulid(),
                source_id=src,
                target_id=tgt,
                kind=kind,
                created_at=now,
                notes=raw.get("notes"),
            )
        )
    return new_nodes, new_edges, warnings


def _split_copy(
    g0: ThoughtGraph, omit: set[str], *, prose: str, now: str
) -> tuple[list[ThoughtNode], list[ThoughtEdge]]:
    copied_nodes = [_copy_node(n, prose=prose) for n in g0.nodes if n.id not in omit]
    keep = {n.id for n in copied_nodes}
    copied_edges = [
        _copy_edge(e, now=now)
        for e in g0.edges
        if e.source_id in keep and e.target_id in keep
    ]
    return copied_nodes, copied_edges


def fork_from(
    g0: ThoughtGraph,
    target: ThoughtNode,
    *,
    session_id: str,
    turn_id: str,
    now: str,
    model: ModelInfo,
    reason: str | None = None,
    regen_text: str | None = None,
) -> tuple[ThoughtGraph, list[str]]:
    """Build G1. G0 is not mutated. Regenerated nodes get new ULIDs."""
    omit = omit_set(g0, target.id)
    prose = PENDING_PROSE
    extra_nodes: list[ThoughtNode] = []
    extra_edges: list[ThoughtEdge] = []
    warnings: list[str] = []

    if regen_text:
        prose, raw_nodes, raw_edges = parse_regen(regen_text)
        if not prose:
            prose = PENDING_PROSE
            warnings.append("prose is empty")
        copied_nodes, copied_edges = _split_copy(g0, omit, prose=prose, now=now)
        extra_nodes, extra_edges, regen_warnings = _add_regen_nodes(
            copied=copied_nodes,
            raw_nodes=raw_nodes,
            raw_edges=raw_edges,
            omit=omit,
            prose=prose,
            model=model,
            now=now,
        )
        warnings.extend(regen_warnings)
    else:
        copied_nodes, copied_edges = _split_copy(g0, omit, prose=prose, now=now)

    graph = ThoughtGraph(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        session_id=session_id,
        turn_id=turn_id,
        created_at=now,
        prose=prose,
        nodes=tuple(copied_nodes + extra_nodes),
        edges=tuple(copied_edges + extra_edges),
        model=model,
        parent_graph_id=g0.id,
        fork=ForkRef(
            from_graph_id=g0.id,
            from_node_id=target.id,
            discarded_graph_id=g0.id,
            reason=reason,
        ),
        hidden_reasoning=None,
    )
    warnings.extend(policy_warnings(graph))
    return graph, warnings


def veto_from(
    g0: ThoughtGraph,
    target: ThoughtNode,
    *,
    session_id: str,
    turn_id: str,
    now: str,
    reason: str,
) -> tuple[ThoughtGraph, list[str]]:
    """Copy every node; add a human veto node + vetoes edge. G0 unchanged."""
    if target.id not in {n.id for n in g0.nodes}:
        raise ForkError(f"node {target.id} not in graph {g0.id}")
    if not reason:
        raise ForkError("veto requires a reason")

    copied_nodes = [_copy_node(n, prose=g0.prose) for n in g0.nodes]
    copied_edges = [_copy_edge(e, now=now) for e in g0.edges]
    veto_node = ThoughtNode(
        id=new_ulid(),
        kind="rejected_alternative",
        text=reason,
        status="vetoed",
        agent="human",
        created_at=now,
        source="human",
        span=bind_span(g0.prose, reason),
    )
    veto_edge = ThoughtEdge(
        id=new_ulid(),
        source_id=veto_node.id,
        target_id=target.id,
        kind="vetoes",
        created_at=now,
    )
    graph = ThoughtGraph(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        session_id=session_id,
        turn_id=turn_id,
        created_at=now,
        prose=g0.prose,
        nodes=tuple(copied_nodes + [veto_node]),
        edges=tuple(copied_edges + [veto_edge]),
        model=g0.model,
        parent_graph_id=g0.id,
        fork=ForkRef(
            from_graph_id=g0.id,
            from_node_id=target.id,
            discarded_graph_id=None,
            reason=reason,
        ),
        hidden_reasoning=g0.hidden_reasoning,
    )
    return graph, policy_warnings(graph)


def detect_regen_compile_mode(text: str) -> str:
    """structured_emit if a thought-graph fence is present, else posthoc."""
    try:
        json.loads(text.strip())
        return "posthoc"
    except json.JSONDecodeError:
        return "structured_emit"
