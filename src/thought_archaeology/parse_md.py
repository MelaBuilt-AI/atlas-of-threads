from __future__ import annotations

import re

from thought_archaeology.ids import is_ulid, new_ulid
from thought_archaeology.models import (
    SCHEMA_VERSION,
    ForkRef,
    ModelInfo,
    ThoughtEdge,
    ThoughtGraph,
    ThoughtNode,
)

DUMMY_TS = "1970-01-01T00:00:00Z"
DUMMY_SOURCE = "posthoc_compile"

HEADING_TO_KIND = {
    "Claims": "claim",
    "Premises": "premise",
    "Analogies": "analogy",
    "Judgment calls": "judgment_call",
    "Taste-calls": "judgment_call",
    "Uncertainties": "uncertainty",
    "Negative space": "rejected_alternative",
}

ULID = r"[0123456789ABCDEFGHJKMNPQRSTVWXYZ]{26}"
BULLET_RE = re.compile(
    rf"^- `({ULID})` · (\S+) · (\S+) — (.+)$"
)
EDGE_RE = re.compile(
    rf"^\| `({ULID})` \| (\S+) \| `({ULID})` \|$"
)
FORK_RE = re.compile(
    rf"^- (parent graph|fork node|discarded): (?:`({ULID})`|none)\s*$"
)
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


class ParseError(Exception):
    """Canvas markdown could not be parsed."""


def _unquote(value: str) -> str | None:
    v = value.strip()
    if v in ("null", "~", ""):
        return None
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        return v[1:-1]
    return v


def _parse_frontmatter(block: str) -> dict[str, object]:
    result: dict[str, object] = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("tags:"):
            tags: list[str] = []
            i += 1
            while i < len(lines) and lines[i].startswith("  - "):
                tags.append(lines[i][4:].strip())
                i += 1
            result["tags"] = tags
            continue
        if ":" not in line:
            i += 1
            continue
        key, raw = line.split(":", 1)
        result[key.strip()] = _unquote(raw)
        i += 1
    return result


def _sections(body: str) -> dict[str, str]:
    parts = re.split(r"^## ", body, flags=re.MULTILINE)
    sections: dict[str, str] = {}
    for part in parts[1:]:
        title, _, rest = part.partition("\n")
        sections[title.strip()] = rest
    return sections


def _parse_prose(body: str) -> str:
    lines = body.splitlines()
    quoted = [ln for ln in lines if ln.strip() != ""]
    if quoted and all(ln.startswith(">") for ln in quoted):
        out = []
        for ln in lines:
            if ln.startswith("> "):
                out.append(ln[2:])
            elif ln.startswith(">"):
                out.append(ln[1:])
            elif ln.strip() == "":
                out.append("")
        return "\n".join(out).strip("\n")
    return body.strip("\n")


def _parse_bullets(body: str) -> list[tuple[str, str, str, str]]:
    found = []
    for line in body.splitlines():
        m = BULLET_RE.match(line)
        if m:
            found.append((m.group(1), m.group(2), m.group(3), m.group(4)))
    return found


def _parse_edges(body: str) -> list[tuple[str, str, str]]:
    found = []
    for line in body.splitlines():
        m = EDGE_RE.match(line.strip())
        if m:
            found.append((m.group(1), m.group(2), m.group(3)))
    return found


def _parse_forks(body: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {
        "parent graph": None,
        "fork node": None,
        "discarded": None,
    }
    for line in body.splitlines():
        m = FORK_RE.match(line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def parse_md(text: str) -> ThoughtGraph:
    """Parse a canvas into a schema-valid ThoughtGraph with dummy fills.

    Never write the result back to the store. Roundtrip tests compare the
    documented projection only.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ParseError("canvas is missing YAML frontmatter")
    fm = _parse_frontmatter(match.group(1))
    graph_id = fm.get("graph_id")
    session_id = fm.get("session_id")
    schema_version = fm.get("schema_version") or SCHEMA_VERSION
    parent_raw = fm.get("parent_graph_id")
    parent_graph_id = parent_raw if isinstance(parent_raw, str) and parent_raw else None
    if not isinstance(graph_id, str) or not is_ulid(graph_id):
        raise ParseError("frontmatter graph_id is not a ULID")
    if not isinstance(session_id, str) or not is_ulid(session_id):
        raise ParseError("frontmatter session_id is not a ULID")
    if parent_graph_id is not None and not is_ulid(parent_graph_id):
        raise ParseError("frontmatter parent_graph_id is not a ULID")

    body = text[match.end() :]
    sections = _sections(body)
    if "Prose" not in sections:
        raise ParseError("canvas is missing ## Prose")
    if "Edges" not in sections:
        raise ParseError("canvas is missing ## Edges")
    if "Forks and discarded branches" not in sections:
        raise ParseError("canvas is missing ## Forks and discarded branches")

    prose = _parse_prose(sections["Prose"])
    nodes: list[ThoughtNode] = []
    for heading, kind in HEADING_TO_KIND.items():
        for nid, status, agent, node_text in _parse_bullets(sections.get(heading, "")):
            nodes.append(
                ThoughtNode(
                    id=nid,
                    kind=kind,  # type: ignore[arg-type]
                    text=node_text,
                    status=status,  # type: ignore[arg-type]
                    agent=agent,  # type: ignore[arg-type]
                    created_at=DUMMY_TS,
                    source=DUMMY_SOURCE,  # type: ignore[arg-type]
                )
            )
    edges: list[ThoughtEdge] = []
    for src, kind, tgt in _parse_edges(sections["Edges"]):
        edges.append(
            ThoughtEdge(
                id=new_ulid(),
                source_id=src,
                target_id=tgt,
                kind=kind,  # type: ignore[arg-type]
                created_at=DUMMY_TS,
            )
        )

    forks = _parse_forks(sections["Forks and discarded branches"])
    parent = forks["parent graph"]
    fork_node = forks["fork node"]
    discarded = forks["discarded"]
    if parent_graph_id and parent and parent != parent_graph_id:
        raise ParseError("frontmatter parent_graph_id disagrees with fork section")
    if parent is None and fork_node is None and discarded is None:
        fork = None
        parent_graph_id = None
    else:
        if parent and not fork_node:
            raise ParseError("parent graph is set but fork node is none")
        if not parent or not fork_node:
            raise ParseError("fork requires parent graph and fork node")
        if parent != (parent_graph_id or parent):
            raise ParseError("fork.from_graph_id must equal parent_graph_id")
        fork = ForkRef(
            from_graph_id=parent,
            from_node_id=fork_node,
            discarded_graph_id=discarded,
            reason=None,
        )
        parent_graph_id = parent

    return ThoughtGraph(
        schema_version=str(schema_version),
        id=graph_id,
        session_id=session_id,
        turn_id=graph_id,
        created_at=DUMMY_TS,
        prose=prose,
        nodes=tuple(nodes),
        edges=tuple(edges),
        model=ModelInfo("none", "unknown", "posthoc"),
        parent_graph_id=parent_graph_id,
        fork=fork,
        hidden_reasoning=None,
    )
