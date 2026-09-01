from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Self

from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import SCHEMA_VERSION

if TYPE_CHECKING:
    from thought_archaeology.store import Store

FieldNoteKind = Literal["conclusion", "unresolved_question", "observation"]


@dataclass(frozen=True)
class ThoughtReference:
    session_id: str
    graph_id: str
    node_id: str
    graph_sha256: str

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            session_id=data["session_id"],
            graph_id=data["graph_id"],
            node_id=data["node_id"],
            graph_sha256=data["graph_sha256"],
        )

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "graph_id": self.graph_id,
            "node_id": self.node_id,
            "graph_sha256": self.graph_sha256,
        }


@dataclass(frozen=True)
class FieldNote:
    schema_version: str
    id: str
    created_at: str
    author: Literal["human"]
    kind: FieldNoteKind
    text: str
    references: tuple[ThoughtReference, ...]

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            id=data["id"],
            created_at=data["created_at"],
            author=data["author"],
            kind=data["kind"],
            text=data["text"],
            references=tuple(
                ThoughtReference.from_dict(item) for item in data["references"]
            ),
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "created_at": self.created_at,
            "author": self.author,
            "kind": self.kind,
            "text": self.text,
            "references": [item.to_dict() for item in self.references],
        }


def field_note(
    store: Store,
    *,
    kind: FieldNoteKind,
    text: str,
    references: tuple[tuple[str, str, str], ...],
) -> FieldNote:
    resolved = tuple(
        ThoughtReference(
            session_id=session_id,
            graph_id=graph_id,
            node_id=node_id,
            graph_sha256=store.graph_sha256(graph_id),
        )
        for session_id, graph_id, node_id in references
    )
    return FieldNote(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        created_at=now_iso(),
        author="human",
        kind=kind,
        text=text.strip(),
        references=resolved,
    )


def create_field_note(
    store: Store,
    *,
    kind: FieldNoteKind,
    text: str,
    references: tuple[tuple[str, str, str], ...],
    comparison_request_id: str,
) -> FieldNote:
    """Create one human note guarded by an exact parallel comparison."""
    from thought_archaeology.continuation import parallel_comparison
    from thought_archaeology.store import StoreError

    comparison = parallel_comparison(store, comparison_request_id)
    allowed_graphs = {path["graph_id"] for path in comparison["paths"]}
    selected_graphs = {graph_id for _session_id, graph_id, _node_id in references}
    if not selected_graphs.issubset(allowed_graphs):
        raise StoreError("every Field Note reference must come from the comparison")
    note = field_note(store, kind=kind, text=text, references=references)
    store.write_field_note(note)
    return note


def field_note_read(store: Store, note: FieldNote) -> dict:
    from thought_archaeology.schema import ValidationError
    from thought_archaeology.store import StoreError

    completions = {
        completion.graph_id: completion.harness
        for completion in store.iter_continuation_completions()
    }
    references = []
    for reference in note.references:
        payload = {**reference.to_dict(), "integrity": "missing"}
        try:
            actual = store.graph_sha256(reference.graph_id)
            payload.update(
                {
                    "integrity": (
                        "verified"
                        if actual == reference.graph_sha256
                        else "mismatch"
                    ),
                    "actual_graph_sha256": actual,
                }
            )
            graph = store.load_graph(reference.graph_id)
            session = store.load_session(reference.session_id)
        except (StoreError, ValidationError, json.JSONDecodeError, OSError):
            references.append(payload)
            continue
        node = next(
            (item for item in graph.nodes if item.id == reference.node_id), None
        )
        if graph.session_id != reference.session_id or node is None:
            references.append(payload)
            continue
        payload.update(
            {
                "session_title": session.title,
                "thought": {
                    "id": node.id,
                    "kind": (
                        "judgment_call" if node.kind == "taste_call" else node.kind
                    ),
                    "text": node.text,
                    "status": node.status,
                    "agent": node.agent,
                },
                "model": graph.model.to_dict(),
                "harness": completions.get(graph.id),
                "entry": {"graph_id": graph.id, "node_id": node.id},
            }
        )
        references.append(payload)
    return {
        **note.to_dict(),
        "kind_label": note.kind.replace("_", " "),
        "reference_count": len(note.references),
        "referenced_graph_count": len({item.graph_id for item in note.references}),
        "integrity": (
            "verified"
            if all(item["integrity"] == "verified" for item in references)
            else "failed"
        ),
        "references": references,
    }


def field_note_summaries(
    store: Store,
    *,
    session_id: str | None = None,
    graph_id: str | None = None,
    node_id: str | None = None,
) -> list[dict]:
    summaries = []
    for note in store.iter_field_notes():
        matching = [
            item
            for item in note.references
            if (session_id is None or item.session_id == session_id)
            and (graph_id is None or item.graph_id == graph_id)
            and (node_id is None or item.node_id == node_id)
        ]
        if not matching:
            continue
        read = field_note_read(store, note)
        summaries.append(
            {
                "id": note.id,
                "created_at": note.created_at,
                "author": note.author,
                "kind": note.kind,
                "kind_label": read["kind_label"],
                "text": note.text,
                "reference_count": read["reference_count"],
                "referenced_graph_count": read["referenced_graph_count"],
                "integrity": read["integrity"],
            }
        )
    return summaries


def field_notes_for_graphs(store: Store, graph_ids: set[str]) -> list[dict]:
    summaries = []
    for note in store.iter_field_notes():
        touched = {item.graph_id for item in note.references if item.graph_id in graph_ids}
        if len(touched) < 2:
            continue
        read = field_note_read(store, note)
        summaries.append(
            {
                "id": note.id,
                "created_at": note.created_at,
                "author": note.author,
                "kind": note.kind,
                "kind_label": read["kind_label"],
                "text": note.text,
                "reference_count": read["reference_count"],
                "referenced_graph_count": read["referenced_graph_count"],
                "integrity": read["integrity"],
            }
        )
    return summaries


def field_note_eligibility(
    store: Store, *, graph_id: str, node_id: str
) -> dict | None:
    """Resolve the exact parallel comparison available from this chamber."""
    from thought_archaeology.continuation import parallel_group_summaries

    graph = store.load_graph(graph_id)
    for group in parallel_group_summaries(store, session_id=graph.session_id):
        if graph_id not in group["graph_ids"]:
            continue
        return {
            "comparison_request_id": group["representative_request_id"],
            "completed_count": group["completed_count"],
            "prompt": group["prompt"],
            "standing_reference": {
                "session_id": graph.session_id,
                "graph_id": graph.id,
                "node_id": node_id,
            },
        }
    return None
