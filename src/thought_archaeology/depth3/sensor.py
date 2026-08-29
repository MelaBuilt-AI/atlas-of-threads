from __future__ import annotations

from dataclasses import dataclass
import gzip
import hashlib
import json
from pathlib import Path
from typing import Protocol

from thought_archaeology.models import SCHEMA_VERSION, Span, ThoughtGraph
from thought_archaeology.ids import new_ulid, now_iso

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
class AttributionProvenance:
    artifact_kind: str  # "measured_attribution" | "deterministic_fixture"
    model: str
    method: str
    source_uri: str
    source_sha256: str
    producer_revision: str | None = None
    prompt: str | None = None
    target: str | None = None
    request_sha256: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> AttributionProvenance:
        return cls(
            artifact_kind=d["artifact_kind"],
            model=d["model"],
            method=d["method"],
            source_uri=d["source_uri"],
            source_sha256=d["source_sha256"],
            producer_revision=d.get("producer_revision"),
            prompt=d.get("prompt"),
            target=d.get("target"),
            request_sha256=d.get("request_sha256"),
        )

    def to_dict(self) -> dict:
        data = {
            "artifact_kind": self.artifact_kind,
            "model": self.model,
            "method": self.method,
            "source_uri": self.source_uri,
            "source_sha256": self.source_sha256,
        }
        for key in ("producer_revision", "prompt", "target", "request_sha256"):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        return data


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
    provenance: AttributionProvenance | None = None

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
            provenance=(
                AttributionProvenance.from_dict(d["provenance"])
                if d.get("provenance") is not None
                else None
            ),
        )

    def to_dict(self) -> dict:
        data = {
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
        if self.provenance is not None:
            data["provenance"] = self.provenance.to_dict()
        return data


def import_circuit_tracer_graph(
    path: Path,
    *,
    graph_id: str,
    node_id: str,
    span: Span,
    source_uri: str,
    producer_revision: str,
) -> Attribution:
    """Collapse an official circuit-tracer graph by recorded node type.

    This intentionally does not invent semantic feature labels. The exact
    source bytes are hashed; gzip content is detected independently of suffix.
    """
    source = path.read_bytes()
    payload = gzip.decompress(source) if source.startswith(b"\x1f\x8b") else source
    raw = json.loads(payload)
    metadata = raw.get("metadata") or {}
    nodes = raw.get("nodes")
    links = raw.get("links")
    if not isinstance(nodes, list) or not isinstance(links, list):
        raise SensorError("circuit-tracer artifact requires nodes and links arrays")
    if not nodes:
        raise SensorError("circuit-tracer artifact has no nodes")
    grouped: dict[str, list[dict]] = {}
    for node in nodes:
        feature_type = node.get("feature_type")
        node_ref = node.get("node_id")
        if not isinstance(feature_type, str) or not isinstance(node_ref, str):
            raise SensorError("circuit-tracer node lacks feature_type or node_id")
        grouped.setdefault(feature_type, []).append(node)
    supernodes = []
    for index, (feature_type, members) in enumerate(sorted(grouped.items()), start=1):
        exemplars = tuple(
            str(member["clerp"])
            for member in members
            if isinstance(member.get("clerp"), str) and member["clerp"]
        )[:3]
        supernodes.append(
            Supernode(
                id=f"structural-{index}",
                label=f"{len(members)} {feature_type} nodes",
                nla_sentence=(
                    "Structural grouping from the measured graph; no semantic "
                    "feature interpretation was supplied by the source artifact."
                ),
                feature_ids=tuple(str(member["node_id"]) for member in members),
                exemplars=exemplars,
            )
        )
    target_nodes = [node for node in nodes if node.get("is_target_logit") is True]
    target = target_nodes[0].get("clerp") if len(target_nodes) == 1 else None
    return Attribution(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        graph_id=graph_id,
        node_id=node_id,
        span=span,
        supernodes=tuple(supernodes),
        raw_feature_count=len(nodes),
        vendor="custom",
        created_at=now_iso(),
        provenance=AttributionProvenance(
            artifact_kind="measured_attribution",
            model=str(metadata.get("scan") or "unknown"),
            method="circuit-tracer cross-layer transcoder attribution graph",
            source_uri=source_uri,
            source_sha256=hashlib.sha256(source).hexdigest(),
            producer_revision=producer_revision,
            prompt=metadata.get("prompt"),
            target=str(target) if target is not None else None,
        ),
    )


def import_neuronpedia_activation(
    request_path: Path,
    response_path: Path,
    *,
    graph_id: str,
    node_id: str,
    graph_position: int,
    target: str,
    attribution_id: str | None = None,
    source_uri: str = "https://www.neuronpedia.org/api/activation/new",
) -> Attribution:
    """Bind one naturally measured feature activation without semantic inference."""
    request_bytes = request_path.read_bytes()
    response_bytes = response_path.read_bytes()
    request = json.loads(request_bytes)
    response = json.loads(response_bytes)
    feature = request.get("feature") or request.get("neuron")
    if not isinstance(feature, dict):
        raise SensorError("activation request lacks feature identity")
    source = str(feature.get("source") or feature.get("layer") or "")
    try:
        layer = int(source.split("-", 1)[0])
        index = int(feature["index"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SensorError("activation feature layer/index is invalid") from exc
    tokens = response.get("tokens")
    values = response.get("values")
    if not isinstance(tokens, list) or not isinstance(values, list) or len(tokens) != len(values):
        raise SensorError("activation response requires aligned tokens and values")
    response_index = response.get("maxValueTokenIndex")
    if not isinstance(response_index, int) or not (0 <= response_index < len(tokens)):
        raise SensorError("activation response maxValueTokenIndex is invalid")
    activation = values[response_index]
    if isinstance(activation, bool) or not isinstance(activation, (int, float)):
        raise SensorError("measured activation must be numeric")
    if activation <= 0:
        raise SensorError("activation correlation requires a positive measured activation")
    prompt = request.get("customText")
    model = feature.get("modelId")
    if not isinstance(prompt, str) or not isinstance(model, str):
        raise SensorError("activation request requires model and prompt")
    feature_id = f"{layer}_{index}_{graph_position}"
    return Attribution(
        schema_version=SCHEMA_VERSION,
        id=attribution_id or new_ulid(),
        graph_id=graph_id,
        node_id=node_id,
        span=Span(0, len(target), "char"),
        supernodes=(Supernode(
            id="measured-feature",
            label=(
                f"Feature {layer}:{index} activation {float(activation):g} "
                f"at token {tokens[response_index]!r}"
            ),
            nla_sentence=(
                "Direct activation observation; no semantic meaning is inferred "
                "from the feature value."
            ),
            feature_ids=(feature_id,),
            exemplars=(prompt,),
        ),),
        raw_feature_count=1,
        vendor="neuronpedia",
        created_at=now_iso(),
        provenance=AttributionProvenance(
            artifact_kind="measured_attribution",
            model=model,
            method="Neuronpedia single-feature activation measurement",
            source_uri=source_uri,
            source_sha256=hashlib.sha256(response_bytes).hexdigest(),
            prompt=prompt,
            target=target,
            request_sha256=hashlib.sha256(request_bytes).hexdigest(),
        ),
    )


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
    if attr.provenance is not None:
        lines.append(
            f"  source {attr.provenance.model} via {attr.provenance.method}  "
            f"sha256={attr.provenance.source_sha256}"
        )
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
