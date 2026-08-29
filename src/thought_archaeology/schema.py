from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from jsonschema.validators import Draft202012Validator
from referencing import Registry, Resource

from thought_archaeology.ids import is_ulid
from thought_archaeology.models import ThoughtGraph

try:
    from importlib.resources import files
except ImportError:  # pragma: no cover
    from importlib_resources import files  # type: ignore[no-redef]

SCHEMA_DIR = files("thought_archaeology") / "schemas" / "v1"
PROMPTS_DIR = files("thought_archaeology") / "prompts"
ULID_PATTERN = r"^[0123456789ABCDEFGHJKMNPQRSTVWXYZ]{26}$"
ISO_Z_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"

SCHEMA_NAMES = (
    "thought-node.schema.json",
    "thought-edge.schema.json",
    "thought-graph.schema.json",
    "session.schema.json",
    "turn.schema.json",
    "attribution.schema.json",
    "fingerprint.schema.json",
    "probe.schema.json",
    "graph-diff.schema.json",
)

DAG_EDGE_KINDS = frozenset({"supports", "depends_on", "shapes", "taste_of"})


class ValidationError(Exception):
    """JSON Schema or referential integrity failure."""

    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("; ".join(messages))


def load_validator(name: str) -> Draft202012Validator:
    # Register every v1 schema so $ref: "thought-node.schema.json" resolves.
    # Also register each $id so relative refs from the mela.ai base URI resolve.
    resources: list[tuple[str, Resource]] = []
    for n in SCHEMA_NAMES:
        contents = json.loads(SCHEMA_DIR.joinpath(n).read_text(encoding="utf-8"))
        resource = Resource.from_contents(contents)
        resources.append((n, resource))
        schema_id = contents.get("$id")
        if schema_id:
            resources.append((schema_id, resource))
    registry = Registry().with_resources(resources)
    schema = json.loads(SCHEMA_DIR.joinpath(name).read_text(encoding="utf-8"))
    return Draft202012Validator(
        schema,
        registry=registry,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


@lru_cache(maxsize=None)
def validator_for(name: str) -> Draft202012Validator:
    return load_validator(name)


def schema_errors(name: str, data: Any) -> list[str]:
    v = validator_for(name)
    return sorted(f"{list(e.path)}: {e.message}" for e in v.iter_errors(data))


def validate_schema(name: str, data: Any) -> None:
    errors = schema_errors(name, data)
    if errors:
        raise ValidationError(errors)


def validate_graph(data: dict[str, Any] | ThoughtGraph) -> None:
    """JSON Schema plus in-graph referential integrity. Raises ValidationError."""
    raw = data.to_dict() if isinstance(data, ThoughtGraph) else data
    errors = schema_errors("thought-graph.schema.json", raw)
    errors.extend(_graph_integrity_errors(raw))
    if errors:
        raise ValidationError(errors)


def _graph_integrity_errors(raw: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if raw.get("schema_version") != "1.0.0":
        errors.append(f"schema_version must be 1.0.0, got {raw.get('schema_version')!r}")

    nodes = raw.get("nodes") or []
    edges = raw.get("edges") or []
    prose = raw.get("prose") or ""
    node_ids: list[str] = []
    seen_nodes: set[str] = set()
    for i, node in enumerate(nodes):
        nid = node.get("id")
        if nid in seen_nodes:
            errors.append(f"duplicate node id {nid}")
        seen_nodes.add(nid)
        node_ids.append(nid)
        span = node.get("span")
        if isinstance(span, dict):
            start, end = span.get("start"), span.get("end")
            if isinstance(start, int) and isinstance(end, int):
                if end <= start:
                    errors.append(f"node {nid} span.end must be > span.start")
                if end > len(prose):
                    errors.append(
                        f"node {nid} span.end {end} exceeds prose length {len(prose)}"
                    )

    seen_edges: set[str] = set()
    for edge in edges:
        eid = edge.get("id")
        if eid in seen_edges:
            errors.append(f"duplicate edge id {eid}")
        seen_edges.add(eid)
        src, tgt = edge.get("source_id"), edge.get("target_id")
        if src not in seen_nodes:
            errors.append(f"edge {eid} source_id {src} not in graph.nodes")
        if tgt not in seen_nodes:
            errors.append(f"edge {eid} target_id {tgt} not in graph.nodes")

    parent = raw.get("parent_graph_id")
    fork = raw.get("fork")
    if fork:
        from_g = fork.get("from_graph_id")
        if from_g != parent:
            errors.append("fork.from_graph_id must equal parent_graph_id")
        if parent is not None and not is_ulid(str(parent)):
            errors.append("parent_graph_id is not a ULID")

    return errors


def policy_warnings(graph: ThoughtGraph) -> list[str]:
    """Product policy (not schema). Empty list means clean."""
    warnings: list[str] = []
    kinds = [n.kind for n in graph.nodes]
    if "rejected_alternative" not in kinds:
        warnings.append("policy: graph has zero rejected_alternative nodes")
    if len(graph.nodes) > 40:
        warnings.append(f"policy: graph has {len(graph.nodes)} nodes (warn at 40)")
    if "claim" not in kinds:
        warnings.append("policy: graph has no claim node")
    if _has_dag_cycle(graph):
        warnings.append("policy: supports/depends_on/shapes cycle detected")
    return warnings


def _has_dag_cycle(graph: ThoughtGraph) -> bool:
    adj: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    for edge in graph.edges:
        if edge.kind not in DAG_EDGE_KINDS:
            continue
        if edge.source_id in adj:
            adj[edge.source_id].append(edge.target_id)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in adj}

    def dfs(nid: str) -> bool:
        color[nid] = GRAY
        for nxt in adj.get(nid, ()):
            if nxt not in color:
                continue
            if color[nxt] == GRAY:
                return True
            if color[nxt] == WHITE and dfs(nxt):
                return True
        color[nid] = BLACK
        return False

    return any(color[nid] == WHITE and dfs(nid) for nid in adj)


def read_prompt(name: str) -> str:
    """Load a packaged prompt. `name` is `structured`, `posthoc`, or `fork`."""
    filename = {
        "structured": "structured-emit.md",
        "posthoc": "posthoc-compile.md",
        "fork": "fork-regenerate.md",
    }.get(name, name)
    return PROMPTS_DIR.joinpath(filename).read_text(encoding="utf-8")
