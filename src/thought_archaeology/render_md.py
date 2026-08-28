from __future__ import annotations

from thought_archaeology.fingerprint import Fingerprint
from thought_archaeology.models import ThoughtGraph, ThoughtNode

KIND_SECTIONS: tuple[tuple[str, str], ...] = (
    ("Claims", "claim"),
    ("Premises", "premise"),
    ("Analogies", "analogy"),
    ("Taste-calls", "taste_call"),
    ("Uncertainties", "uncertainty"),
    ("Negative space", "rejected_alternative"),
)

RELATED = """\
## Related

- [[wiki/Concepts/thought-archaeology|Thought archaeology]]
- [[wiki/Entities/thought-archaeology|thought-archaeology (tool)]]
- [[wiki/Sources/thought-archaeology-design|Design document]]
"""

SOURCES = """\
## Sources

- Graph JSON `graphs/{graph_id}.json` in the thought-archaeology store (not the wiki `raw/` tree until ingested).
"""


def canvas_title(graph: ThoughtGraph) -> str:
    for kind in ("taste_call", "claim"):
        for node in graph.nodes:
            if node.kind == kind:
                text = " ".join(node.text.split())
                if text.endswith("."):
                    text = text[:-1]
                cut = text.split(". ")[0]
                if len(cut) > 80:
                    cut = cut[:77] + "…"
                return f"Thought graph — {cut}"
    return "Thought graph — untitled"


def _yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _date(iso_z: str) -> str:
    return iso_z[:10] if len(iso_z) >= 10 else iso_z


def _frontmatter(graph: ThoughtGraph, title: str) -> str:
    parent = graph.parent_graph_id if graph.parent_graph_id else "null"
    return (
        "---\n"
        f"title: {_yaml_quote(title)}\n"
        "type: overview\n"
        f"created: {_date(graph.created_at)}\n"
        f"updated: {_date(graph.created_at)}\n"
        "sources: []\n"
        "tags:\n"
        "  - thought-archaeology\n"
        "  - depth-1\n"
        f'schema_version: "{graph.schema_version}"\n'
        f"graph_id: {graph.id}\n"
        f"session_id: {graph.session_id}\n"
        f"parent_graph_id: {parent}\n"
        "---\n"
    )


def _quote_prose(prose: str) -> str:
    if not prose:
        return ""
    lines = []
    for raw_line in prose.split("\n"):
        if raw_line == "":
            lines.append(">")
        else:
            lines.append("> " + raw_line)
    return "\n".join(lines) + "\n"


def _mermaid_label(kind: str, text: str) -> str:
    short = "rejected" if kind == "rejected_alternative" else kind
    t = " ".join(text.split())
    if len(t) > 40:
        t = t[:40] + "…"
    for a, b in (('"', "'"), ("[", "("), ("]", ")"), ("{", "("), ("}", ")")):
        t = t.replace(a, b)
    return f"{short}: {t}"


def _mermaid(graph: ThoughtGraph) -> str:
    lines = ["```mermaid", "flowchart TD"]
    for node in graph.nodes:
        label = _mermaid_label(node.kind, node.text)
        lines.append(f'  n{node.id}["{label}"]')
    for edge in graph.edges:
        lines.append(f"  n{edge.source_id} -->|{edge.kind}| n{edge.target_id}")
    lines.append("```")
    return "\n".join(lines) + "\n"


def _bullet(node: ThoughtNode) -> str:
    return f"- `{node.id}` · {node.status} · {node.agent} — {node.text}"


def _kind_section(title: str, kind: str, graph: ThoughtGraph) -> str:
    nodes = [n for n in graph.nodes if n.kind == kind]
    parts = [f"## {title}", ""]
    if kind == "rejected_alternative":
        parts.append(
            "Rejected alternatives are first-class. They stay even when the "
            "surviving chain moves on."
        )
        parts.append("")
    if nodes:
        parts.extend(_bullet(n) for n in nodes)
        parts.append("")
    return "\n".join(parts)


def _edges_table(graph: ThoughtGraph) -> str:
    lines = [
        "## Edges",
        "",
        "| from | kind | to |",
        "|---|---|---|",
    ]
    for edge in graph.edges:
        lines.append(f"| `{edge.source_id}` | {edge.kind} | `{edge.target_id}` |")
    lines.append("")
    return "\n".join(lines)


def _ref(value: str | None) -> str:
    return f"`{value}`" if value else "none"


def _forks_section(graph: ThoughtGraph) -> str:
    parent = graph.parent_graph_id
    fork_node = graph.fork.from_node_id if graph.fork else None
    discarded = graph.fork.discarded_graph_id if graph.fork else None
    if graph.fork is None:
        parent = None
        fork_node = None
        discarded = None
    return (
        "## Forks and discarded branches\n"
        "\n"
        f"- parent graph: {_ref(parent)}\n"
        f"- fork node: {_ref(fork_node)}\n"
        f"- discarded: {_ref(discarded)}\n"
    )


def _fingerprint_section(fp: Fingerprint) -> str:
    lines = ["## Dual archaeology", ""]
    for cluster in fp.model_taste:
        lines.append(f"- taste · `{cluster.recurrence}` — {cluster.canonical}")
    for cluster in fp.human_vetoes:
        lines.append(f"- veto · `{cluster.recurrence}` — {cluster.canonical}")
    for row in fp.divergence:
        lines.append(
            f"- divergence · jaccard {row.jaccard} — "
            f"{row.taste_canonical} ↔ {row.veto_canonical}"
        )
    if not (fp.model_taste or fp.human_vetoes or fp.divergence):
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)


def render_md(
    graph: ThoughtGraph, fingerprint: Fingerprint | None = None
) -> str:
    """Lossy markdown projection of a thought-graph. Hidden reasoning omitted."""
    title = canvas_title(graph)
    chunks = [
        _frontmatter(graph, title),
        f"# {title}\n",
        "## Summary\n",
        (
            "Depth-1 **story** graph (not a circuit trace). "
            f"Session `{graph.session_id}`. Graph `{graph.id}`.\n"
        ),
        "## Prose\n",
        _quote_prose(graph.prose),
        "## Graph\n",
        _mermaid(graph),
    ]
    for heading, kind in KIND_SECTIONS:
        chunks.append(_kind_section(heading, kind, graph))
    chunks.append(_edges_table(graph))
    chunks.append(_forks_section(graph))
    if fingerprint is not None:
        chunks.append(_fingerprint_section(fingerprint))
    chunks.append(RELATED)
    chunks.append(SOURCES.format(graph_id=graph.id))
    text = "\n".join(chunks)
    if not text.endswith("\n"):
        text += "\n"
    return text
