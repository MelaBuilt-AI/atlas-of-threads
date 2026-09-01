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


@dataclass(frozen=True)
class FieldNoteRevision:
    schema_version: str
    id: str
    note_id: str
    previous_revision_id: str
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
            note_id=data["note_id"],
            previous_revision_id=data["previous_revision_id"],
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
            "note_id": self.note_id,
            "previous_revision_id": self.previous_revision_id,
            "created_at": self.created_at,
            "author": self.author,
            "kind": self.kind,
            "text": self.text,
            "references": [item.to_dict() for item in self.references],
        }


FieldNoteVersion = FieldNote | FieldNoteRevision


def _resolve_references(
    store: Store, references: tuple[tuple[str, str, str], ...]
) -> tuple[ThoughtReference, ...]:
    return tuple(
        ThoughtReference(
            session_id=session_id,
            graph_id=graph_id,
            node_id=node_id,
            graph_sha256=store.graph_sha256(graph_id),
        )
        for session_id, graph_id, node_id in references
    )


def field_note(
    store: Store,
    *,
    kind: FieldNoteKind,
    text: str,
    references: tuple[tuple[str, str, str], ...],
) -> FieldNote:
    return FieldNote(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        created_at=now_iso(),
        author="human",
        kind=kind,
        text=text.strip(),
        references=_resolve_references(store, references),
    )


def create_field_note(
    store: Store,
    *,
    kind: FieldNoteKind,
    text: str,
    references: tuple[tuple[str, str, str], ...],
    comparison_request_id: str,
) -> FieldNote:
    """Create the one human note belonging to an exact parallel comparison."""
    from thought_archaeology.continuation import parallel_comparison
    from thought_archaeology.store import StoreError

    with store.field_notes_lock():
        comparison = parallel_comparison(store, comparison_request_id)
        if comparison["field_notes"]:
            raise StoreError(
                f"parallel comparison already has Field Note "
                f"{comparison['field_notes'][0]['id']}; edit that note"
            )
        _validate_comparison_references(comparison, references)
        note = field_note(store, kind=kind, text=text, references=references)
        store.write_field_note(note)
    return note


def edit_field_note(
    store: Store,
    *,
    note_id: str,
    kind: FieldNoteKind,
    text: str,
    references: tuple[tuple[str, str, str], ...],
    comparison_request_id: str,
) -> FieldNoteRevision:
    """Append one linear human revision without rewriting the base note."""
    from thought_archaeology.continuation import parallel_comparison
    from thought_archaeology.store import StoreError

    with store.field_notes_lock():
        note = store.load_field_note(note_id)
        comparison = parallel_comparison(store, comparison_request_id)
        if note_id not in {item["id"] for item in comparison["field_notes"]}:
            raise StoreError("Field Note does not belong to this parallel comparison")
        _validate_comparison_references(comparison, references)
        revisions = list(store.iter_field_note_revisions(note_id))
        previous_revision_id = revisions[-1].id if revisions else note.id
        revision = FieldNoteRevision(
            schema_version=SCHEMA_VERSION,
            id=new_ulid(),
            note_id=note.id,
            previous_revision_id=previous_revision_id,
            created_at=now_iso(),
            author="human",
            kind=kind,
            text=text.strip(),
            references=_resolve_references(store, references),
        )
        store.write_field_note_revision(revision)
    return revision


def _validate_comparison_references(
    comparison: dict, references: tuple[tuple[str, str, str], ...]
) -> None:
    from thought_archaeology.store import StoreError

    allowed_graphs = {path["graph_id"] for path in comparison["paths"]}
    selected_graphs = {graph_id for _session_id, graph_id, _node_id in references}
    if not selected_graphs.issubset(allowed_graphs):
        raise StoreError("every Field Note reference must come from the comparison")


def field_note_versions(store: Store, note: FieldNote) -> list[FieldNoteVersion]:
    return [note, *store.iter_field_note_revisions(note.id)]


def field_note_all_references(
    store: Store, note: FieldNote
) -> tuple[ThoughtReference, ...]:
    references = []
    seen = set()
    for version in field_note_versions(store, note):
        for reference in version.references:
            identity = (
                reference.session_id,
                reference.graph_id,
                reference.node_id,
            )
            if identity in seen:
                continue
            seen.add(identity)
            references.append(reference)
    return tuple(references)


def field_note_comparison_request_id(store: Store, note: FieldNote) -> str | None:
    from thought_archaeology.continuation import parallel_group_summaries

    graph_ids = {item.graph_id for item in note.references}
    session_ids = {item.session_id for item in note.references}
    if len(session_ids) != 1:
        return None
    for group in parallel_group_summaries(store, session_id=next(iter(session_ids))):
        if graph_ids.issubset(set(group["graph_ids"])):
            return group["representative_request_id"]
    return None


def field_note_read(
    store: Store, note: FieldNote, *, revision_id: str | None = None
) -> dict:
    from thought_archaeology.schema import ValidationError
    from thought_archaeology.store import StoreError

    versions = field_note_versions(store, note)
    latest = versions[-1]
    if revision_id is None:
        selected = latest
    else:
        selected = next((item for item in versions if item.id == revision_id), None)
        if selected is None:
            raise StoreError(f"Field Note revision not found: {revision_id}")
    completions = {
        completion.graph_id: completion.harness
        for completion in store.iter_continuation_completions()
    }
    references = []
    for reference in selected.references:
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
        "schema_version": note.schema_version,
        "id": note.id,
        "created_at": note.created_at,
        "updated_at": latest.created_at,
        "author": selected.author,
        "kind": selected.kind,
        "kind_label": selected.kind.replace("_", " "),
        "text": selected.text,
        "references": references,
        "reference_count": len(selected.references),
        "referenced_graph_count": len(
            {item.graph_id for item in selected.references}
        ),
        "integrity": (
            "verified"
            if all(item["integrity"] == "verified" for item in references)
            else "failed"
        ),
        "revision_id": selected.id,
        "revision_created_at": selected.created_at,
        "current_revision_id": latest.id,
        "revision_count": len(versions),
        "viewing_latest": selected.id == latest.id,
        "comparison_request_id": field_note_comparison_request_id(store, note),
        "revision_history": [
            {
                "revision_id": version.id,
                "previous_revision_id": (
                    version.previous_revision_id
                    if isinstance(version, FieldNoteRevision)
                    else None
                ),
                "created_at": version.created_at,
                "author": version.author,
                "kind": version.kind,
                "kind_label": version.kind.replace("_", " "),
                "text": version.text,
                "reference_count": len(version.references),
                "referenced_graph_count": len(
                    {item.graph_id for item in version.references}
                ),
                "current": version.id == latest.id,
            }
            for version in versions
        ],
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
            for item in field_note_all_references(store, note)
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
                "updated_at": read["updated_at"],
                "author": read["author"],
                "kind": read["kind"],
                "kind_label": read["kind_label"],
                "text": read["text"],
                "reference_count": read["reference_count"],
                "referenced_graph_count": read["referenced_graph_count"],
                "integrity": read["integrity"],
                "revision_count": read["revision_count"],
            }
        )
    return summaries


def field_notes_for_graphs(store: Store, graph_ids: set[str]) -> list[dict]:
    summaries = []
    for note in store.iter_field_notes():
        touched = {
            item.graph_id
            for item in field_note_all_references(store, note)
            if item.graph_id in graph_ids
        }
        if len(touched) < 2:
            continue
        read = field_note_read(store, note)
        summaries.append(
            {
                "id": note.id,
                "created_at": note.created_at,
                "updated_at": read["updated_at"],
                "author": read["author"],
                "kind": read["kind"],
                "kind_label": read["kind_label"],
                "text": read["text"],
                "reference_count": read["reference_count"],
                "referenced_graph_count": read["referenced_graph_count"],
                "integrity": read["integrity"],
                "revision_count": read["revision_count"],
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
        if field_notes_for_graphs(store, set(group["graph_ids"])):
            return None
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
