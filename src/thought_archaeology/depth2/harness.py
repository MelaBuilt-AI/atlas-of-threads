from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal

from thought_archaeology.fingerprint import MERGE_THRESHOLD, jaccard, normalize, token_set
from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.fork import detect_regen_compile_mode, fork_from, fork_regen_prompt
from thought_archaeology.models import SCHEMA_VERSION, ModelInfo, ThoughtGraph, ThoughtNode
from thought_archaeology.providers.base import Provider
from thought_archaeology.schema import read_prompt

ProbeKind = Literal["drop_premise", "invert_constraint", "resample", "steer_later"]
PROBE_KINDS: tuple[ProbeKind, ...] = (
    "drop_premise",
    "invert_constraint",
    "resample",
    "steer_later",
)

STABLE_THRESHOLD = MERGE_THRESHOLD  # 0.8; same Jaccard as dual archaeology
NULL_PROBE_MESSAGE = "Depth 2 probe runner is not implemented"
STORY_FALSIFIED = "story falsified under intervention; not a weight-level proof"


class ProbeError(Exception):
    """Probe plan / spec failure (I/O or missing target)."""


@dataclass(frozen=True)
class ProbeSpec:
    schema_version: str
    id: str
    kind: ProbeKind
    target_node_id: str
    target_graph_id: str
    params: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    created_at: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProbeSpec:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            id=d["id"],
            kind=d["kind"],
            target_node_id=d["target_node_id"],
            target_graph_id=d["target_graph_id"],
            params=MappingProxyType(dict(d.get("params") or {})),
            created_at=d["created_at"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "kind": self.kind,
            "target_node_id": self.target_node_id,
            "target_graph_id": self.target_graph_id,
            "params": json.loads(json.dumps(dict(self.params))),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class GraphDiff:
    schema_version: str
    id: str
    a_graph_id: str
    b_graph_id: str
    stable_node_ids: tuple[str, ...]  # same id, or same kind + Jaccard ≥ 0.8
    changed_node_ids: tuple[str, ...]
    vanished_node_ids: tuple[str, ...]  # in A not matched in B
    appeared_node_ids: tuple[str, ...]
    notes: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GraphDiff:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            id=d["id"],
            a_graph_id=d["a_graph_id"],
            b_graph_id=d["b_graph_id"],
            stable_node_ids=tuple(d.get("stable_node_ids") or ()),
            changed_node_ids=tuple(d.get("changed_node_ids") or ()),
            vanished_node_ids=tuple(d.get("vanished_node_ids") or ()),
            appeared_node_ids=tuple(d.get("appeared_node_ids") or ()),
            notes=d.get("notes"),
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "id": self.id,
            "a_graph_id": self.a_graph_id,
            "b_graph_id": self.b_graph_id,
            "stable_node_ids": list(self.stable_node_ids),
            "changed_node_ids": list(self.changed_node_ids),
            "vanished_node_ids": list(self.vanished_node_ids),
            "appeared_node_ids": list(self.appeared_node_ids),
        }
        if self.notes is not None:
            d["notes"] = self.notes
        return d


def _node_in(graph: ThoughtGraph, node_id: str) -> ThoughtNode | None:
    for node in graph.nodes:
        if node.id == node_id:
            return node
    return None


def _kind_text_equal(a: ThoughtNode, b: ThoughtNode) -> bool:
    return a.kind == b.kind and normalize(a.text) == normalize(b.text)


def _best_jaccard_match(
    node: ThoughtNode, candidates: list[ThoughtNode]
) -> ThoughtNode | None:
    """Highest same-kind Jaccard ≥ threshold; ties → smallest id."""
    best: ThoughtNode | None = None
    best_score = STABLE_THRESHOLD
    toks = token_set(node.text)
    for other in candidates:
        if other.kind != node.kind:
            continue
        score = jaccard(toks, token_set(other.text))
        if score < STABLE_THRESHOLD:
            continue
        if (
            best is None
            or score > best_score
            or (score == best_score and other.id < best.id)
        ):
            best = other
            best_score = score
    return best


def _conclusions_of(graph: ThoughtGraph, premise_id: str) -> list[ThoughtNode]:
    """Claims the dropped premise was supposed to explain.

    Outgoing `supports` from the premise, plus nodes with incoming
    `depends_on` pointing at it. Falls back to every `claim` if none.
    """
    ids: set[str] = set()
    for edge in graph.edges:
        if edge.kind == "supports" and edge.source_id == premise_id:
            ids.add(edge.target_id)
        if edge.kind == "depends_on" and edge.target_id == premise_id:
            ids.add(edge.source_id)
    by_id = {n.id: n for n in graph.nodes}
    out = [by_id[i] for i in sorted(ids) if i in by_id]
    if out:
        return out
    return [n for n in graph.nodes if n.kind == "claim"]


def _node_stable_in_b(
    node: ThoughtNode, b: ThoughtGraph, *, stable_ids: set[str]
) -> bool:
    if node.id in stable_ids:
        return True
    match = _best_jaccard_match(node, list(b.nodes))
    return match is not None


def falsification_notes(
    a: ThoughtGraph, b: ThoughtGraph, spec: ProbeSpec | None, diff: GraphDiff
) -> str | None:
    """Story lie: drop a 'why' premise and the conclusion still stands.

    Bookkeeping only. Not a weight-level proof.
    """
    if spec is None or spec.kind != "drop_premise":
        return None
    vanished = set(diff.vanished_node_ids)
    stable = set(diff.stable_node_ids)
    if spec.target_node_id not in vanished:
        return None
    if spec.target_node_id in stable:
        return None
    conclusions = _conclusions_of(a, spec.target_node_id)
    if any(_node_stable_in_b(c, b, stable_ids=stable) for c in conclusions):
        return STORY_FALSIFIED
    return None


def diff_graphs(
    a: ThoughtGraph,
    b: ThoughtGraph,
    *,
    spec: ProbeSpec | None = None,
    diff_id: str | None = None,
) -> GraphDiff:
    """Match by id, then leftover nodes by kind + Jaccard ≥ 0.8.

    This is bookkeeping, not model intervention. A's ids are used for
    stable / changed / vanished; B's ids for appeared.
    """
    b_by_id = {n.id: n for n in b.nodes}
    b_unmatched = {n.id: n for n in b.nodes}
    stable: list[str] = []
    changed: list[str] = []
    a_unmatched: list[ThoughtNode] = []

    for node in a.nodes:
        other = b_by_id.get(node.id)
        if other is None:
            a_unmatched.append(node)
            continue
        b_unmatched.pop(node.id, None)
        if _kind_text_equal(node, other):
            stable.append(node.id)
        else:
            changed.append(node.id)

    a_unmatched.sort(key=lambda n: n.id)
    vanished: list[str] = []
    for node in a_unmatched:
        candidates = list(b_unmatched.values())
        match = _best_jaccard_match(node, candidates)
        if match is None:
            vanished.append(node.id)
            continue
        b_unmatched.pop(match.id, None)
        stable.append(node.id)

    appeared = sorted(b_unmatched)
    draft = GraphDiff(
        schema_version=SCHEMA_VERSION,
        id=diff_id or new_ulid(),
        a_graph_id=a.id,
        b_graph_id=b.id,
        stable_node_ids=tuple(sorted(stable)),
        changed_node_ids=tuple(sorted(changed)),
        vanished_node_ids=tuple(sorted(vanished)),
        appeared_node_ids=tuple(appeared),
        notes=None,
    )
    notes = falsification_notes(a, b, spec, draft)
    return GraphDiff(
        schema_version=draft.schema_version,
        id=draft.id,
        a_graph_id=draft.a_graph_id,
        b_graph_id=draft.b_graph_id,
        stable_node_ids=draft.stable_node_ids,
        changed_node_ids=draft.changed_node_ids,
        vanished_node_ids=draft.vanished_node_ids,
        appeared_node_ids=draft.appeared_node_ids,
        notes=notes,
    )


class ProbeHarness:
    def plan(self, graph: ThoughtGraph, spec: ProbeSpec) -> ProbeSpec:
        """Validate target exists. Depth 2 implemented later."""
        if spec.target_graph_id != graph.id:
            raise ProbeError(
                f"spec target_graph_id {spec.target_graph_id} "
                f"does not match graph {graph.id}"
            )
        if _node_in(graph, spec.target_node_id) is None:
            raise ProbeError(
                f"node {spec.target_node_id} not in graph {graph.id}"
            )
        return spec

    def run(
        self, graph: ThoughtGraph, spec: ProbeSpec, provider: Provider
    ) -> ThoughtGraph:
        self.plan(graph, spec)
        if spec.kind != "drop_premise":
            raise NotImplementedError(NULL_PROBE_MESSAGE)
        target = _node_in(graph, spec.target_node_id)
        if target is None:  # plan already checked; keeps the type concrete
            raise ProbeError(f"node {spec.target_node_id} not in graph {graph.id}")
        now = now_iso()
        response = provider.complete(
            fork_regen_prompt(
                graph,
                target,
                reason="test the story without this premise",
                now=now,
            ),
            system=read_prompt("fork"),
        )
        model = ModelInfo(
            provider=provider.name,  # type: ignore[arg-type]
            name=graph.model.name or "unknown",
            compile_mode=detect_regen_compile_mode(response),
        )
        child, _warnings = fork_from(
            graph,
            target,
            session_id=graph.session_id,
            turn_id=new_ulid(),
            now=now,
            model=model,
            reason="probe: drop premise",
            regen_text=response,
        )
        return child

    def diff(self, a: ThoughtGraph, b: ThoughtGraph) -> GraphDiff:
        return diff_graphs(a, b)


def make_plan(
    graph: ThoughtGraph,
    *,
    kind: ProbeKind,
    node_id: str,
    params: dict[str, Any] | None = None,
    now: str | None = None,
    spec_id: str | None = None,
) -> ProbeSpec:
    spec = ProbeSpec(
        schema_version=SCHEMA_VERSION,
        id=spec_id or new_ulid(),
        kind=kind,
        target_node_id=node_id,
        target_graph_id=graph.id,
        params=MappingProxyType(dict(params or {})),
        created_at=now or now_iso(),
    )
    return ProbeHarness().plan(graph, spec)
