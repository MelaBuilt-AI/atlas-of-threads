from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Literal

from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import SCHEMA_VERSION, ThoughtGraph, ThoughtNode

MERGE_THRESHOLD = 0.8
DIVERGENCE_THRESHOLD = 0.5
DEFAULT_MIN_SESSIONS = 2

_PUNCT = re.compile(r"[^\w\s-]", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    s = unicodedata.normalize("NFKC", text)
    s = s.casefold()
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s


def token_set(text: str) -> frozenset[str]:
    n = normalize(text)
    if not n:
        return frozenset()
    return frozenset(n.split())


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def recompute_canonical(texts: list[str]) -> str:
    """Most frequent exact text; tie → shortest; remaining tie → lexicographically smallest."""
    counts = Counter(texts)
    max_c = max(counts.values())
    tied = [t for t, c in counts.items() if c == max_c]
    min_len = min(len(t) for t in tied)
    tied = [t for t in tied if len(t) == min_len]
    return min(tied)


@dataclass
class _Cluster:
    members: list[tuple[ThoughtGraph, ThoughtNode]]
    canonical: str

    def add(self, graph: ThoughtGraph, node: ThoughtNode) -> None:
        self.members.append((graph, node))
        self.canonical = recompute_canonical([n.text for _, n in self.members])


def cluster_nodes(
    items: list[tuple[ThoughtGraph, ThoughtNode]],
    *,
    threshold: float = MERGE_THRESHOLD,
) -> list[_Cluster]:
    """Greedy single-pass. Sort by node id (ULID = time). No two-pass recluster."""
    ordered = sorted(items, key=lambda pair: pair[1].id)
    clusters: list[_Cluster] = []
    for graph, node in ordered:
        toks = token_set(node.text)
        assigned = False
        for cluster in clusters:
            if jaccard(toks, token_set(cluster.canonical)) >= threshold:
                cluster.add(graph, node)
                assigned = True
                break
        if not assigned:
            clusters.append(_Cluster(members=[(graph, node)], canonical=node.text))
    return clusters


def _unique_nodes(
    graphs: Iterable[ThoughtGraph],
    pred,
) -> list[tuple[ThoughtGraph, ThoughtNode]]:
    seen: set[str] = set()
    out: list[tuple[ThoughtGraph, ThoughtNode]] = []
    for graph in graphs:
        for node in graph.nodes:
            if node.id in seen:
                continue
            if pred(graph, node):
                seen.add(node.id)
                out.append((graph, node))
    return out


def _is_model_taste(_graph: ThoughtGraph, node: ThoughtNode) -> bool:
    return node.kind == "taste_call" and node.agent == "model"


def _is_human_veto(graph: ThoughtGraph, node: ThoughtNode) -> bool:
    if node.status == "vetoed":
        return True
    return any(e.kind == "vetoes" and e.source_id == node.id for e in graph.edges)


def _recurrence(
    member_sessions: set[str], *, total_sessions: int, min_sessions: int
) -> Literal["recurring", "emerging"]:
    if total_sessions < min_sessions:
        return "emerging"
    if len(member_sessions) >= min_sessions:
        return "recurring"
    return "emerging"


@dataclass(frozen=True)
class TasteCluster:
    canonical: str
    normalized: str
    count: int
    session_ids: tuple[str, ...]
    node_ids: tuple[str, ...]
    recurrence: Literal["recurring", "emerging"]

    def to_dict(self) -> dict:
        return {
            "canonical": self.canonical,
            "normalized": self.normalized,
            "count": self.count,
            "session_ids": list(self.session_ids),
            "node_ids": list(self.node_ids),
            "recurrence": self.recurrence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TasteCluster:
        return cls(
            canonical=d["canonical"],
            normalized=d["normalized"],
            count=int(d["count"]),
            session_ids=tuple(d.get("session_ids") or ()),
            node_ids=tuple(d.get("node_ids") or ()),
            recurrence=d["recurrence"],
        )


@dataclass(frozen=True)
class Divergence:
    taste_canonical: str
    veto_canonical: str
    jaccard: float

    def to_dict(self) -> dict:
        return {
            "taste_canonical": self.taste_canonical,
            "veto_canonical": self.veto_canonical,
            "jaccard": self.jaccard,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Divergence:
        return cls(
            taste_canonical=d["taste_canonical"],
            veto_canonical=d["veto_canonical"],
            jaccard=float(d["jaccard"]),
        )


def _emit_clusters(
    raw: list[_Cluster], *, total_sessions: int, min_sessions: int
) -> tuple[TasteCluster, ...]:
    out: list[TasteCluster] = []
    for cluster in raw:
        sessions = sorted({g.session_id for g, _n in cluster.members})
        node_ids = sorted({n.id for _g, n in cluster.members})
        out.append(
            TasteCluster(
                canonical=cluster.canonical,
                normalized=normalize(cluster.canonical),
                count=len(cluster.members),
                session_ids=tuple(sessions),
                node_ids=tuple(node_ids),
                recurrence=_recurrence(
                    set(sessions),
                    total_sessions=total_sessions,
                    min_sessions=min_sessions,
                ),
            )
        )
    return tuple(out)


def _divergence(
    tastes: tuple[TasteCluster, ...], vetoes: tuple[TasteCluster, ...]
) -> tuple[Divergence, ...]:
    rows: list[Divergence] = []
    for taste in tastes:
        tt = token_set(taste.canonical)
        for veto in vetoes:
            score = jaccard(tt, token_set(veto.canonical))
            if score >= DIVERGENCE_THRESHOLD:
                rows.append(
                    Divergence(
                        taste_canonical=taste.canonical,
                        veto_canonical=veto.canonical,
                        jaccard=round(score, 6),
                    )
                )
    return tuple(rows)


@dataclass(frozen=True)
class Fingerprint:
    schema_version: str
    id: str
    created_at: str
    session_ids: tuple[str, ...]
    min_sessions: int
    merge_threshold: float
    model_taste: tuple[TasteCluster, ...]
    human_vetoes: tuple[TasteCluster, ...]
    divergence: tuple[Divergence, ...]

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "created_at": self.created_at,
            "session_ids": list(self.session_ids),
            "min_sessions": self.min_sessions,
            "merge_threshold": self.merge_threshold,
            "model_taste": [c.to_dict() for c in self.model_taste],
            "human_vetoes": [c.to_dict() for c in self.human_vetoes],
            "divergence": [d.to_dict() for d in self.divergence],
        }

    @classmethod
    def from_dict(cls, d: dict) -> Fingerprint:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            id=d["id"],
            created_at=d["created_at"],
            session_ids=tuple(d.get("session_ids") or ()),
            min_sessions=int(d["min_sessions"]),
            merge_threshold=float(d["merge_threshold"]),
            model_taste=tuple(TasteCluster.from_dict(c) for c in d.get("model_taste") or ()),
            human_vetoes=tuple(
                TasteCluster.from_dict(c) for c in d.get("human_vetoes") or ()
            ),
            divergence=tuple(Divergence.from_dict(x) for x in d.get("divergence") or ()),
        )


def fingerprint(
    graphs: Iterable[ThoughtGraph],
    *,
    session_ids: Iterable[str],
    min_sessions: int = DEFAULT_MIN_SESSIONS,
    now: str | None = None,
    fingerprint_id: str | None = None,
) -> Fingerprint:
    graph_list = list(graphs)
    sessions = tuple(session_ids)
    total = len(sessions)
    tastes = _emit_clusters(
        cluster_nodes(_unique_nodes(graph_list, _is_model_taste)),
        total_sessions=total,
        min_sessions=min_sessions,
    )
    vetoes = _emit_clusters(
        cluster_nodes(_unique_nodes(graph_list, _is_human_veto)),
        total_sessions=total,
        min_sessions=min_sessions,
    )
    return Fingerprint(
        schema_version=SCHEMA_VERSION,
        id=fingerprint_id or new_ulid(),
        created_at=now or now_iso(),
        session_ids=sessions,
        min_sessions=min_sessions,
        merge_threshold=MERGE_THRESHOLD,
        model_taste=tastes,
        human_vetoes=vetoes,
        divergence=_divergence(tastes, vetoes),
    )
