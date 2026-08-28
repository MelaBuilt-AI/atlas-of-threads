from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from thought_archaeology.models import SCHEMA_VERSION, Span, ThoughtGraph

# Product display cap. Not a JSON Schema maxItems — storage may keep
# raw_feature_count as an integer and supernodes as the collapsed view.
MAX_SUPERNODES = 12
NULL_SENSOR_MESSAGE = (
    "Depth 3 requires open weights or a vendor interpretability API"
)


class SensorError(Exception):
    """Sensor attach or display failure."""


class DisplayRefused(SensorError):
    """Collapsed view would dump an unliveable attribution graph."""


@dataclass(frozen=True)
class Supernode:
    id: str
    label: str  # short, claim-bound
    nla_sentence: str | None = None  # Natural Language Autoencoder reading
    feature_ids: tuple[str, ...] = ()
    exemplars: tuple[str, ...] = ()
    suppressed: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> Supernode:
        return cls(
            id=d["id"],
            label=d["label"],
            nla_sentence=d.get("nla_sentence"),
            feature_ids=tuple(d.get("feature_ids") or ()),
            exemplars=tuple(d.get("exemplars") or ()),
            suppressed=bool(d.get("suppressed", False)),
        )

    def to_dict(self) -> dict:
        d: dict = {"id": self.id, "label": self.label}
        if self.nla_sentence is not None:
            d["nla_sentence"] = self.nla_sentence
        if self.feature_ids:
            d["feature_ids"] = list(self.feature_ids)
        if self.exemplars:
            d["exemplars"] = list(self.exemplars)
        if self.suppressed:
            d["suppressed"] = True
        return d


@dataclass(frozen=True)
class Attribution:
    schema_version: str
    id: str
    graph_id: str
    node_id: str
    span: Span
    supernodes: tuple[Supernode, ...]  # target ~12, never dump raw 4000
    raw_feature_count: int
    vendor: str  # "none" | "neuronpedia" | "anthropic" | "custom"
    created_at: str

    @classmethod
    def from_dict(cls, d: dict) -> Attribution:
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            id=d["id"],
            graph_id=d["graph_id"],
            node_id=d["node_id"],
            span=Span(
                start=int(d["span"]["start"]),
                end=int(d["span"]["end"]),
                unit=d["span"].get("unit", "char"),
            ),
            supernodes=tuple(Supernode.from_dict(s) for s in d.get("supernodes") or ()),
            raw_feature_count=int(d["raw_feature_count"]),
            vendor=d["vendor"],
            created_at=d["created_at"],
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "graph_id": self.graph_id,
            "node_id": self.node_id,
            "span": self.span.to_dict(),
            "supernodes": [s.to_dict() for s in self.supernodes],
            "raw_feature_count": self.raw_feature_count,
            "vendor": self.vendor,
            "created_at": self.created_at,
        }


class Sensor(Protocol):
    name: str

    def attach(
        self,
        graph: ThoughtGraph,
        node_id: str,
        *,
        include_raw: bool = False,
    ) -> Attribution:
        """Bind a collapsed attribution subgraph to a thought-node.

        Implementations must refuse to return more than max_supernodes
        (default 12) without an explicit include_raw=True escape hatch
        that the CLI hides.
        """
        ...


def enforce_collapse(
    attr: Attribution, *, include_raw: bool = False, max_supernodes: int = MAX_SUPERNODES
) -> Attribution:
    """Raise DisplayRefused if the supernode list is an unliveable dump."""
    if len(attr.supernodes) > max_supernodes and not include_raw:
        raise DisplayRefused(
            f"refusing to display {len(attr.supernodes)} supernodes "
            f"(cap {max_supernodes}); raw_feature_count="
            f"{attr.raw_feature_count} is an integer, not a dumped graph"
        )
    return attr


def format_attribution(
    attr: Attribution, *, include_raw: bool = False, max_supernodes: int = MAX_SUPERNODES
) -> str:
    """Human view of a collapsed attribution. Never prints feature id lists."""
    enforce_collapse(attr, include_raw=include_raw, max_supernodes=max_supernodes)
    lines = [
        (
            f"attribution {attr.id}  graph={attr.graph_id}  "
            f"node={attr.node_id}  vendor={attr.vendor}"
        ),
        (
            f"  span {attr.span.start}:{attr.span.end}  "
            f"raw_feature_count={attr.raw_feature_count}  "
            "(collapsed view bound to a thought-node, not a circuit dump)"
        ),
        f"  supernodes {len(attr.supernodes)}/{max_supernodes}",
    ]
    for i, sn in enumerate(attr.supernodes, start=1):
        flag = "  suppressed" if sn.suppressed else ""
        lines.append(f"    {i:>2}  {sn.label}{flag}")
        if sn.nla_sentence:
            lines.append(f"        {sn.nla_sentence}")
        if sn.exemplars:
            for ex in sn.exemplars:
                lines.append(f"        exemplar: {ex}")
        # feature_ids stay JSON-only. Printing them is how this idea dies
        # as a neuron dashboard.
    lines.append("")
    return "\n".join(lines)


class NullSensor:
    """Stub. Depth 3 needs open weights or a vendor interpretability API."""

    name = "none"

    def attach(
        self,
        graph: ThoughtGraph,
        node_id: str,
        *,
        include_raw: bool = False,
    ) -> Attribution:
        if node_id not in {n.id for n in graph.nodes}:
            raise SensorError(f"node {node_id} not in graph {graph.id}")
        raise NotImplementedError(NULL_SENSOR_MESSAGE)
