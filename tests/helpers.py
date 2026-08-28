from __future__ import annotations

from pathlib import Path

from thought_archaeology.models import (
    SCHEMA_VERSION,
    ForkRef,
    ModelInfo,
    ThoughtEdge,
    ThoughtGraph,
    ThoughtNode,
)

CANVAS_GRAPH_ID = "01M14CANVASAAAAAAAAAAA0001"
CANVAS_SESSION_ID = "01M14CANVASAAAAAAAAAAA0002"
CANVAS_CREATED = "2026-08-27T00:00:00Z"
CANVAS_NODES = {
    "c1": "01M14CANVASAAAAAAAAAAA00A1",
    "p1": "01M14CANVASAAAAAAAAAAA00A2",
    "t1": "01M14CANVASAAAAAAAAAAA00A3",
    "r1": "01M14CANVASAAAAAAAAAAA00A4",
    "r2": "01M14CANVASAAAAAAAAAAA00A5",
    "u1": "01M14CANVASAAAAAAAAAAA00A6",
}

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def node_triples(graph: ThoughtGraph) -> list[tuple[str, str, str]]:
    return [(n.kind, n.text, n.status) for n in graph.nodes]


def edge_triples(graph: ThoughtGraph) -> list[tuple[str, str, str]]:
    by_id = {n.id: n for n in graph.nodes}
    out = []
    for e in graph.edges:
        src = by_id[e.source_id]
        tgt = by_id[e.target_id]
        out.append((f"{src.kind}\0{src.text}", e.kind, f"{tgt.kind}\0{tgt.text}"))
    return out


def gold_node_triples(gold: dict) -> list[tuple[str, str, str]]:
    return [(n["kind"], n["text"], n["status"]) for n in gold["nodes"]]


def gold_edge_triples(gold: dict) -> list[tuple[str, str, str]]:
    by_local = {n["local_id"]: n for n in gold["nodes"]}
    out = []
    for e in gold["edges"]:
        src = by_local[e["from"]]
        tgt = by_local[e["to"]]
        out.append(
            (f"{src['kind']}\0{src['text']}", e["kind"], f"{tgt['kind']}\0{tgt['text']}")
        )
    return out


def canvas_projection(graph: ThoughtGraph) -> dict:
    fork = None
    if graph.fork is not None:
        fork = {
            "from_graph_id": graph.fork.from_graph_id,
            "from_node_id": graph.fork.from_node_id,
            "discarded_graph_id": graph.fork.discarded_graph_id,
        }
    return {
        "id": graph.id,
        "schema_version": graph.schema_version,
        "session_id": graph.session_id,
        "parent_graph_id": graph.parent_graph_id,
        "fork": fork,
        "prose": graph.prose,
        "nodes": sorted(
            (n.id, n.kind, n.text, n.status, n.agent) for n in graph.nodes
        ),
        "edges": sorted(
            (e.source_id, e.target_id, e.kind) for e in graph.edges
        ),
    }


def simple_canvas_graph(*, fork: ForkRef | None = None) -> ThoughtGraph:
    ids = CANVAS_NODES
    now = CANVAS_CREATED

    def node(key: str, kind: str, text: str, status: str) -> ThoughtNode:
        return ThoughtNode(
            id=ids[key],
            kind=kind,  # type: ignore[arg-type]
            text=text,
            status=status,  # type: ignore[arg-type]
            agent="model",
            created_at=now,
            source="posthoc_compile",
        )

    nodes = (
        node("c1", "claim", "The product is the medium, not the microscope.", "accepted"),
        node("p1", "premise", "A chat log has no named parts or causal tests.", "accepted"),
        node("t1", "taste_call", "Invent the medium first.", "accepted"),
        node("r1", "rejected_alternative", "A dashboard of neurons.", "rejected"),
        node("r2", "rejected_alternative", "Wait for weight access before building.", "rejected"),
        node("u1", "uncertainty", "Depth 3 needs open weights or a vendor API.", "uncertain"),
    )
    edges = (
        ThoughtEdge("01M14CANVASAAAAAAAAAAA00E1", ids["p1"], ids["c1"], "supports", now),
        ThoughtEdge("01M14CANVASAAAAAAAAAAA00E2", ids["t1"], ids["c1"], "taste_of", now),
        ThoughtEdge("01M14CANVASAAAAAAAAAAA00E3", ids["r1"], ids["c1"], "rejects", now),
        ThoughtEdge("01M14CANVASAAAAAAAAAAA00E4", ids["r2"], ids["c1"], "rejects", now),
        ThoughtEdge("01M14CANVASAAAAAAAAAAA00E5", ids["u1"], ids["c1"], "qualifies", now),
    )
    parent = fork.from_graph_id if fork is not None else None
    return ThoughtGraph(
        schema_version=SCHEMA_VERSION,
        id=CANVAS_GRAPH_ID,
        session_id=CANVAS_SESSION_ID,
        turn_id=CANVAS_GRAPH_ID,
        created_at=now,
        prose="The product is the medium, not the microscope.",
        nodes=nodes,
        edges=edges,
        model=ModelInfo("file", "unknown", "posthoc"),
        parent_graph_id=parent,
        fork=fork,
        hidden_reasoning="do not render me",
    )
