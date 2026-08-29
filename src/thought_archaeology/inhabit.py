from __future__ import annotations

from dataclasses import dataclass

from thought_archaeology.evidence import EvidenceBinding
from thought_archaeology.fingerprint import Fingerprint, climate_at
from thought_archaeology.fork import ForkError, omit_set
from thought_archaeology.models import ThoughtGraph, ThoughtNode
from thought_archaeology.store import Store, StoreError


def _spawn_id(graph: ThoughtGraph) -> str | None:
    for node in graph.nodes:
        if node.kind == "claim":
            return node.id
    return graph.nodes[0].id if graph.nodes else None


KIND_SENSE = {
    "claim": "a conclusion this answer is standing on",
    "premise": "a supporting belief",
    "judgment_call": "a judgment the premises did not force",
    "taste_call": "a judgment the premises did not force",
    "analogy": "a mapping used to think",
    "uncertainty": "a scoped unknown",
    "rejected_alternative": "a road not taken",
}


def _count_phrase(n: int, singular: str, plural: str) -> str:
    if n == 1:
        return f"1 {singular}"
    return f"{n} {plural}"


def story_path_read(view: InhabitView) -> dict:
    """Server-authored story relations around the standing node."""
    by_id = {node.id: node for node in view.graph.nodes}
    relation_ids: dict[str, set[str]] = {
        "stands on": set(),
        "shaped by": set(),
        "seen through": set(),
        "held within": set(),
    }
    for edge in view.graph.edges:
        if edge.target_id == view.node.id:
            heading = {
                "supports": "stands on",
                "shapes": "shaped by",
                "analogizes": "seen through",
                "qualifies": "held within",
            }.get(edge.kind)
            if heading:
                relation_ids[heading].add(edge.source_id)
        if edge.source_id == view.node.id and edge.kind == "depends_on":
            relation_ids["stands on"].add(edge.target_id)

    descriptions = {
        "stands on": "premises and claims recorded as support for this chamber",
        "shaped by": "judgments that selected this cut",
        "seen through": "analogies the answer used to think",
        "held within": "uncertainties that limit the claim",
        "this path made": "thoughts recorded as depending on this chamber",
        "chosen over": "roads the answer explicitly rejected",
    }

    def item(node: ThoughtNode) -> dict:
        kind = "judgment_call" if node.kind == "taste_call" else node.kind
        return {
            "kind_line": f"{kind.replace('_', ' ')} · {node.status}",
            "text": node.text,
        }

    groups = []
    for heading in ("stands on", "shaped by", "seen through", "held within"):
        nodes = [node for node in view.graph.nodes if node.id in relation_ids[heading]]
        if nodes:
            groups.append(
                {
                    "heading_line": heading,
                    "description_line": descriptions[heading],
                    "items": [item(node) for node in nodes],
                }
            )
    for heading, nodes in (
        ("this path made", view.shaped),
        ("chosen over", view.rejected_siblings),
    ):
        if nodes:
            groups.append(
                {
                    "heading_line": heading,
                    "description_line": descriptions[heading],
                    "items": [item(node) for node in nodes],
                }
            )
    return {
        "intro_line": (
            "relations recorded in the answer's story graph; these explain its "
            "construction, not neural causation"
        ),
        "empty_line": "this graph records no surrounding reasons for this chamber",
        "groups": groups,
    }


def chamber_read(view: InhabitView) -> dict:
    """How the chamber speaks. Schema kinds stay; the human hears sense."""
    node = view.node
    display_kind = "judgment_call" if node.kind == "taste_call" else node.kind
    sense = KIND_SENSE.get(node.kind, display_kind.replace("_", " "))
    if node.status == "vetoed":
        sense = "a human no"
    shaped_n = len(view.shaped)
    keep_n = len(view.graph.nodes) - 1 - shaped_n
    if shaped_n == 0:
        drop = "only this chamber"
    else:
        drop = "this chamber and " + _count_phrase(
            shaped_n, "thought it made", "thoughts it made"
        )
    stay = _count_phrase(max(keep_n, 0), "other chamber stays", "other chambers stay")
    fork_line = (
        f"fork does not erase this. it opens a continuation that omits {drop} "
        f"({stay}). you remain in this chamber; a bronze ring is the path without it"
    )
    veto_line = (
        "veto does not erase this. it copies the whole graph and writes a human no "
        "on this chamber"
    )
    climate = view.climate
    kind = (climate or {}).get("kind")
    climate_line = {
        "divergence": "climate: you have challenged this judgment before",
        "recurring": "climate: the model reaches for this judgment again and again",
        "emerging": "climate: this judgment has only shown up in this sitting",
        "veto": "climate: a human no already lives on this thought",
        "calm": "climate: still air — this thought is not a habit yet",
    }.get(kind) if climate else None
    evidence_line = None
    evidence_layers = []
    if view.evidence:
        words = {
            "story_report": "the story says so",
            "context_provenance": "an earlier artifact points here",
            "behavioral_intervention": "an intervention tested this",
            "activation_correlation": "internal activity moved with this",
            "neural_intervention": "a neural intervention tested this",
            "recurring_circuit": "a recurring mechanism points here",
            "training_influence": "bounded training evidence points here",
            "training_provenance": "published training provenance reaches here",
            "checkpoint_emergence": "a checkpoint trajectory reaches here",
        }
        latest = view.evidence[-1]
        result = {
            "supports": "supports",
            "contradicts": "contradicts",
            "inconclusive": "does not settle",
        }[latest.result]
        evidence_line = (
            f"evidence: {words[latest.kind]} — {result} this thought "
            f"({len(view.evidence)} "
            f"{'binding' if len(view.evidence) == 1 else 'bindings'})"
        )
        for index, binding in enumerate(view.evidence, start=1):
            origin_line = None
            if binding.graph_id != view.graph.id or binding.node_id != view.node.id:
                origin_line = (
                    f"bound at graph {binding.graph_id} · node {binding.node_id}"
                )
            evidence_layers.append(
                {
                    "position_line": f"stratum {index} of {len(view.evidence)}",
                    "heading_line": (
                        f"{binding.kind.replace('_', ' ')} — {binding.result}"
                    ),
                    "summary": binding.summary,
                    "origin_line": origin_line,
                    "follows_line": (
                        f"follows {binding.parent_evidence_id}"
                        if binding.parent_evidence_id
                        else None
                    ),
                    "artifact_lines": list(binding.artifact_refs),
                }
            )
    here = ["you are here"]
    if shaped_n:
        here.append("ahead: what this thought made")
    if view.rejected_siblings:
        here.append("to the sides: roads not taken")
    if view.fork_children:
        here.append("bronze ring: a continuation you already cut")
    if view.graph.parent_graph_id and view.graph.fork is not None:
        here.append("violet ring: walk back to the cut")
    return {
        "kind_line": f"{display_kind.replace('_', ' ')} — {sense}",
        "here_line": " · ".join(here),
        "fork_line": fork_line,
        "veto_line": veto_line,
        "climate_line": climate_line,
        "evidence_line": evidence_line,
        "evidence_action_line": (
            f"e descends through {len(view.evidence)} evidence "
            f"{'stratum' if len(view.evidence) == 1 else 'strata'}"
            if view.evidence
            else "e checks beneath this thought"
        ),
        "evidence_empty_line": (
            "nothing is attached beneath this thought. absence is not evidence "
            "against it"
        ),
        "evidence_layers": evidence_layers,
        "story_path": story_path_read(view),
        "look_line": "left/right preview a path · enter walk it · up deeper · down or b retrace",
    }


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
    climate: dict | None = None
    evidence: tuple[EvidenceBinding, ...] = ()

    def to_dict(self) -> dict:
        fork = self.graph.fork
        parent = None
        if self.graph.parent_graph_id and fork is not None:
            parent = {
                "graph_id": self.graph.parent_graph_id,
                "node_id": fork.from_node_id,
                "discarded_graph_id": fork.discarded_graph_id,
                "reason": fork.reason,
            }
        return {
            "caption": "story graph, not a circuit trace",
            "graph_id": self.graph.id,
            "session_id": self.graph.session_id,
            "parent_graph_id": self.graph.parent_graph_id,
            "parent": parent,
            "node": node_payload(self.node),
            "shaped": [node_payload(n) for n in self.shaped],
            "rejected_siblings": [node_payload(n) for n in self.rejected_siblings],
            "vetoes": [node_payload(n) for n in self.vetoes],
            "climate": self.climate,
            "evidence": [binding.to_dict() for binding in self.evidence],
            "read": chamber_read(self),
            "fork_children": [
                {
                    "id": g.id,
                    "from_node_id": g.fork.from_node_id if g.fork else None,
                    "discarded_graph_id": g.fork.discarded_graph_id if g.fork else None,
                    "reason": g.fork.reason if g.fork else None,
                    "spawn_node_id": _spawn_id(g),
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
    raw_fp = store.latest_fingerprint()
    fp = Fingerprint.from_dict(raw_fp) if raw_fp else None
    evidence_by_id: dict[str, EvidenceBinding] = {}
    local_evidence = store.iter_evidence(
        graph.session_id, graph_id=graph.id, node_id=node.id
    )
    for leaf in local_evidence:
        for raw in store.evidence_chain(graph.session_id, leaf["id"]):
            evidence_by_id.setdefault(raw["id"], EvidenceBinding.from_dict(raw))
    evidence = tuple(evidence_by_id.values())
    return InhabitView(
        graph=graph,
        node=node,
        shaped=shaped,
        rejected_siblings=tuple(sibling_by_id.values()),
        vetoes=tuple(veto_by_id.values()),
        fork_children=tuple(children),
        climate=climate_at(node, fp),
        evidence=evidence,
    )


def _node_line(node: ThoughtNode, indent: str = "    ") -> str:
    text = " ".join(node.text.split())
    kind = "judgment_call" if node.kind == "taste_call" else node.kind
    return f"{indent}{kind:<20} {node.id} {node.status:<9} {text}"


def format_inhabit(view: InhabitView) -> str:
    n = view.node
    kind = "judgment_call" if n.kind == "taste_call" else n.kind
    lines = [
        f"node {n.id}  {kind}  {n.status}  {n.agent}",
        f"  {' '.join(n.text.split())}",
        (
            f"graph {view.graph.id}  session={view.graph.session_id}  "
            "(story graph, not a circuit trace)"
        ),
    ]
    spoken = chamber_read(view)
    lines.append(spoken["kind_line"])
    lines.append(spoken["here_line"])
    if spoken["climate_line"]:
        lines.append(spoken["climate_line"])
    if spoken["evidence_line"]:
        lines.append(spoken["evidence_line"])
    lines.append(spoken["fork_line"])
    lines.extend(["", "shaped"])
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
    lines.extend(["", "evidence beneath this thought"])
    if view.evidence:
        for binding in view.evidence:
            kind = binding.kind.replace("_", " ")
            lines.append(
                f"    {kind:<24} {binding.result:<12} {binding.id}"
            )
            if binding.graph_id != view.graph.id or binding.node_id != view.node.id:
                lines.append(
                    f"      at graph {binding.graph_id} node {binding.node_id}"
                )
            lines.append(f"      {binding.summary}")
            if binding.parent_evidence_id:
                lines.append(f"      follows {binding.parent_evidence_id}")
            for artifact in binding.artifact_refs:
                lines.append(f"      artifact {artifact}")
    else:
        lines.append("    (none attached; absence is not evidence)")
    lines.append("")
    return "\n".join(lines)
