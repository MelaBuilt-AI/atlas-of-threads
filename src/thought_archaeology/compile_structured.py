from __future__ import annotations

import json
import re
from typing import Any

from thought_archaeology.compile_common import CompileError, finalize
from thought_archaeology.models import ForkRef, ModelInfo, ThoughtGraph

_THOUGHT_FENCE = re.compile(
    r"```[ \t]*thought-graph[^\n]*\r?\n(.*?)```",
    re.DOTALL,
)
_THOUGHT_PAIR = re.compile(
    r"---thought-graph---\s*(.*?)\s*---end-thought-graph---",
    re.DOTALL,
)
_JSON_FENCE = re.compile(
    r"```[ \t]*json[^\n]*\r?\n(.*?)```",
    re.DOTALL,
)


def _byte_offset(text: str, char_index: int) -> int:
    return len(text[:char_index].encode("utf-8"))


def _loads_nodes_edges(blob: str, offset: int | None = None) -> dict[str, Any]:
    try:
        payload = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise CompileError(f"invalid thought-graph JSON: {exc}", offset=offset) from exc
    if not isinstance(payload, dict):
        raise CompileError("thought-graph JSON must be an object", offset=offset)
    if "nodes" not in payload or "edges" not in payload:
        raise CompileError(
            "thought-graph JSON must contain nodes and edges", offset=offset
        )
    if not isinstance(payload["nodes"], list) or not isinstance(payload["edges"], list):
        raise CompileError("nodes and edges must be arrays", offset=offset)
    return payload


def extract_thought_graph_json(text: str) -> tuple[str, dict[str, Any], int]:
    """Locate the last thought-graph emit.

    Returns (prose, payload, byte_offset).
    """
    fences = list(_THOUGHT_FENCE.finditer(text))
    if fences:
        match = fences[-1]
        offset = _byte_offset(text, match.start(1))
        payload = _loads_nodes_edges(match.group(1), offset=offset)
        prose = text[: match.start()].strip()
        return prose, payload, offset

    pairs = list(_THOUGHT_PAIR.finditer(text))
    if pairs:
        match = pairs[-1]
        offset = _byte_offset(text, match.start(1))
        payload = _loads_nodes_edges(match.group(1), offset=offset)
        prose = text[: match.start()].strip()
        return prose, payload, offset

    json_fences = list(_JSON_FENCE.finditer(text))
    for match in reversed(json_fences):
        offset = _byte_offset(text, match.start(1))
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if (
            isinstance(payload, dict)
            and isinstance(payload.get("nodes"), list)
            and isinstance(payload.get("edges"), list)
        ):
            prose = text[: match.start()].strip()
            return prose, payload, offset

    raise CompileError("no thought-graph JSON found")


def parse_graph_payload(text: str) -> tuple[dict[str, Any], int | None]:
    """Posthoc / --from-graph parse order: json.loads whole string, then delimiters."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as first_exc:
        try:
            _, payload, offset = extract_thought_graph_json(text)
            return payload, offset
        except CompileError as fence_exc:
            offset = fence_exc.offset
            raise CompileError(
                f"invalid thought-graph JSON: {first_exc}", offset=offset
            ) from first_exc
    if not isinstance(payload, dict):
        raise CompileError("thought-graph JSON must be an object")
    if "nodes" not in payload or "edges" not in payload:
        raise CompileError("thought-graph JSON must contain nodes and edges")
    return payload, 0


def compile_structured(
    raw_text: str,
    *,
    session_id: str,
    turn_id: str,
    model: ModelInfo,
    now: str,
    parent_graph_id: str | None = None,
    fork: ForkRef | None = None,
    hidden_reasoning: str | None = None,
    drop_orphan_edges: bool = False,
) -> tuple[ThoughtGraph, list[str]]:
    prose, payload, _offset = extract_thought_graph_json(raw_text)
    warnings: list[str] = []
    if not prose:
        warnings.append("prose is empty")
    graph = finalize(
        session_id=session_id,
        turn_id=turn_id,
        prose=prose,
        raw_nodes=list(payload["nodes"]),
        raw_edges=list(payload["edges"]),
        model=model,
        now=now,
        parent_graph_id=parent_graph_id,
        fork=fork,
        hidden_reasoning=hidden_reasoning or payload.get("hidden_reasoning"),
        drop_orphan_edges=drop_orphan_edges,
    )
    from thought_archaeology.compile_common import policy_warnings

    warnings.extend(policy_warnings(graph))
    return graph, warnings
