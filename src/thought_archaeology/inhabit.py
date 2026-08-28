from __future__ import annotations

from dataclasses import dataclass

from thought_archaeology.fork import ForkError, omit_set
from thought_archaeology.models import ThoughtGraph, ThoughtNode
from thought_archaeology.store import Store, StoreError


def node_payload(node: ThoughtNode) -> dict:
    return {
        "id": node.id,
        "kind": node.kind,
        "text": node.text,
        "status": node.status,
        "agent": node.agent,
    }


@dataclass(frozen=True)
class InhabitView:
    graph: ThoughtGraph
    node: ThoughtNode
    shaped: tuple[ThoughtNode, ...]
    rejected_siblings: tuple[ThoughtNode, ...]
    vetoes: tuple[ThoughtNode, ...]
    fork_children: tuple[ThoughtGraph, ...]

    def to_dict(self) -> dict:
        return {
            "caption": "story graph, not a circuit trace",
            "graph_id": self.graph.id,
            "session_id": self.graph.session_id,
            "node": node_payload(self.node),
            "shaped": [node_payload(n) for n in self.shaped],
            "rejected_siblings": [node_payload(n) for n in self.rejected_siblings],
            "vetoes": [node_payload(n) for n in self.vetoes],
            "fork_children": [
                {
                    "id": g.id,
                    "from_node_id": g.fork.from_node_id if g.fork else None,
                    "discarded_graph_id": g.fork.discarded_graph_id if g.fork else None,
                    "reason": g.fork.reason if g.fork else None,
                }
                for g in self.fork_children
            ],
        }


def _node_in(graph: ThoughtGraph, node_id: str) -> ThoughtNode | None:
    for node in graph.nodes:
        if node.id == node_id:
            return node
    return None


def _newer(a: ThoughtGraph, b: ThoughtGraph) -> ThoughtGraph:
    if (a.created_at, a.id) >= (b.created_at, b.id):
        return a
    return b


def resolve_standing(
    store: Store,
    node_id: str,
    *,
    graph_id: str | None = None,
    session_id: str | None = None,
) -> tuple[ThoughtGraph, ThoughtNode]:
    """Default graph: newest graph containing NODE, preferring head_graph_id.

    Session-scoped: head if it contains NODE, else the newest graph in that
    session that does (by turn seq). Store-wide if session is omitted.
    """
    if graph_id:
        graph = store.load_graph(graph_id)
        node = _node_in(graph, node_id)
        if node is None:
            raise ForkError(f"node {node_id} not in graph {graph_id}")
        return graph, node

    if session_id:
        session = store.load_session(session_id)
        if session.head_graph_id:
            try:
                head = store.load_graph(session.head_graph_id)
            except StoreError:
                head = None
            if head is not None:
                node = _node_in(head, node_id)
                if node is not None:
                    return head, node
        turns = sorted(store.iter_turns(session_id), key=lambda t: t.seq, reverse=True)
        for turn in turns:
            if not turn.graph_id:
                continue
            try:
                graph = store.load_graph(turn.graph_id)
            except StoreError:
                continue
            node = _node_in(graph, node_id)
            if node is not None:
                return graph, node
        for graph in store.iter_graphs(session_id):
            node = _node_in(graph, node_id)
            if node is not None:
                return graph, node
        raise ForkError(f"node {node_id} not found in session {session_id}")

    found = store.find_nodes(node_id)
    if not found:
        raise ForkError(f"node {node_id} not found")

    heads: list[tuple[ThoughtGraph, ThoughtNode]] = []
    for graph, node in found:
        try:
            session = store.load_session(graph.session_id)
        except StoreError:
            continue
        if session.head_graph_id == graph.id:
            heads.append((graph, node))
    pool = heads or found
    best_g, best_n = pool[0]
    for graph, node in pool[1:]:
        if _newer(graph, best_g) is graph:
            best_g, best_n = graph, node
    return best_g, best_n


def inhabit(
    store: Store,
    node_id: str,
    *,
    graph_id: str | None = None,
    session_id: str | None = None,
) -> InhabitView:
    graph, node = resolve_standing(
        store, node_id, graph_id=graph_id, session_id=session_id
    )
    shaped_ids = omit_set(graph, node.id) - {node.id}
    shaped = tuple(n for n in graph.nodes if n.id in shaped_ids)

    sibling_by_id: dict[str, ThoughtNode] = {}
    veto_by_id: dict[str, ThoughtNode] = {}
    children: list[ThoughtGraph] = []
    for other in store.iter_graphs():
        if other.fork is not None and other.fork.from_node_id == node_id:
            children.append(other)
        by_id = {n.id: n for n in other.nodes}
        for edge in other.edges:
            if edge.target_id != node_id:
                continue
            src = by_id.get(edge.source_id)
            if src is None:
                continue
            if edge.kind == "rejects":
                sibling_by_id.setdefault(src.id, src)
            elif edge.kind == "vetoes":
                veto_by_id.setdefault(src.id, src)
        for n in other.nodes:
            if n.status == "vetoed" and n.id in by_id:
                # Vetoing node is the source of vetoes; status=vetoed is the
                # same object. Catch any status=vetoed node whose vetoes edge
                # we already recorded, and also isolated vetoed nodes.
                if n.id in veto_by_id or any(
                    e.kind == "vetoes" and e.source_id == n.id and e.target_id == node_id
                    for e in other.edges
                ):
                    veto_by_id.setdefault(n.id, n)

    children.sort(key=lambda g: (g.created_at, g.id))
    return InhabitView(
        graph=graph,
        node=node,
        shaped=shaped,
        rejected_siblings=tuple(sibling_by_id.values()),
        vetoes=tuple(veto_by_id.values()),
        fork_children=tuple(children),
    )


def _node_line(node: ThoughtNode, indent: str = "    ") -> str:
    text = " ".join(node.text.split())
    return f"{indent}{node.kind:<20} {node.id} {node.status:<9} {text}"


def format_inhabit(view: InhabitView) -> str:
    n = view.node
    lines = [
        f"node {n.id}  {n.kind}  {n.status}  {n.agent}",
        f"  {' '.join(n.text.split())}",
        (
            f"graph {view.graph.id}  session={view.graph.session_id}  "
            "(story graph, not a circuit trace)"
        ),
        "",
        "shaped",
    ]
    if view.shaped:
        lines.extend(_node_line(s) for s in view.shaped)
    else:
        lines.append("    (none)")
    lines.extend(["", "rejected siblings"])
    if view.rejected_siblings:
        lines.extend(_node_line(s) for s in view.rejected_siblings)
    else:
        lines.append("    (none)")
    lines.extend(["", "vetoes"])
    if view.vetoes:
        lines.extend(_node_line(s) for s in view.vetoes)
    else:
        lines.append("    (none)")
    lines.extend(["", "forks from here"])
    if view.fork_children:
        for child in view.fork_children:
            fork = child.fork
            discarded = (
                fork.discarded_graph_id
                if fork and fork.discarded_graph_id
                else "none"
            )
            reason = (fork.reason if fork and fork.reason else "-")
            lines.append(
                f"    graph {child.id}  discarded={discarded}  reason={reason}"
            )
    else:
        lines.append("    (none)")
    lines.append("")
    return "\n".join(lines)
