from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Self

from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import SCHEMA_VERSION

if TYPE_CHECKING:
    from thought_archaeology.store import Store


RENDERING_VERSION = "1"
PRIVACY_WARNING = (
    "Review this complete inquiry snapshot before sharing it; it may contain "
    "private or sensitive human and model-authored text."
)
OMISSIONS = (
    "hidden chain-of-thought and other hidden reasoning",
    "credentials and provider-owned private state",
    "browser-local atmosphere, unread state, and animation state",
    "raw sensor sources and unrelated sessions",
    "automatic claims of truth, importance, agreement, or consensus",
    "a lossless import or round-trip backup bundle",
)

ArtifactKind = Literal[
    "turn",
    "graph",
    "continuation_request",
    "continuation_attempt",
    "continuation_completion",
    "continuation_failure",
    "continuation_cancellation",
    "parallel_continuation_batch",
    "field_note",
    "field_note_revision",
    "knowledge_capsule_launcher",
    "probe",
    "graph_diff",
    "evidence_binding",
    "attribution",
    "neural_intervention",
    "training_provenance",
]


@dataclass(frozen=True)
class CapsuleArtifact:
    kind: ArtifactKind
    id: str
    path: str
    sha256: str

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            kind=data["kind"],
            id=data["id"],
            path=data["path"],
            sha256=data["sha256"],
        )

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "id": self.id,
            "path": self.path,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class KnowledgeCapsuleManifest:
    schema_version: str
    id: str
    created_at: str
    author: Literal["human"]
    comparison_request_id: str | None
    session_id: str
    session_title: str
    source_graph_id: str
    source_node_id: str
    head_graph_id: str
    head_turn_id: str
    field_note_id: str
    field_note_revision_id: str
    stored_launcher_id: str | None
    earning_graph_id: str | None
    earning_node_id: str | None
    rendering_version: str
    privacy_warning: str
    omissions: tuple[str, ...]
    artifacts: tuple[CapsuleArtifact, ...]

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            id=data["id"],
            created_at=data["created_at"],
            author=data["author"],
            comparison_request_id=data["comparison_request_id"],
            session_id=data["session_id"],
            session_title=data["session_title"],
            source_graph_id=data["source_graph_id"],
            source_node_id=data["source_node_id"],
            head_graph_id=data["head_graph_id"],
            head_turn_id=data["head_turn_id"],
            field_note_id=data["field_note_id"],
            field_note_revision_id=data["field_note_revision_id"],
            stored_launcher_id=data.get("stored_launcher_id"),
            earning_graph_id=data.get("earning_graph_id"),
            earning_node_id=data.get("earning_node_id"),
            rendering_version=data["rendering_version"],
            privacy_warning=data["privacy_warning"],
            omissions=tuple(data["omissions"]),
            artifacts=tuple(
                CapsuleArtifact.from_dict(item) for item in data["artifacts"]
            ),
        )

    def to_dict(self) -> dict:
        payload = {
            "schema_version": self.schema_version,
            "id": self.id,
            "created_at": self.created_at,
            "author": self.author,
            "comparison_request_id": self.comparison_request_id,
            "session_id": self.session_id,
            "session_title": self.session_title,
            "source_graph_id": self.source_graph_id,
            "source_node_id": self.source_node_id,
            "head_graph_id": self.head_graph_id,
            "head_turn_id": self.head_turn_id,
            "field_note_id": self.field_note_id,
            "field_note_revision_id": self.field_note_revision_id,
            "rendering_version": self.rendering_version,
            "privacy_warning": self.privacy_warning,
            "omissions": list(self.omissions),
            "artifacts": [item.to_dict() for item in self.artifacts],
        }
        if self.stored_launcher_id is not None:
            payload["stored_launcher_id"] = self.stored_launcher_id
        if self.earning_graph_id is not None:
            payload["earning_graph_id"] = self.earning_graph_id
        if self.earning_node_id is not None:
            payload["earning_node_id"] = self.earning_node_id
        return payload


@dataclass(frozen=True)
class KnowledgeCapsuleLauncher:
    schema_version: str
    id: str
    stored_at: str
    author: Literal["human"]
    session_id: str
    earning_graph_id: str
    earning_node_id: str
    field_note_id: str
    field_note_revision_id: str
    comparison_request_id: str | None

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            id=data["id"],
            stored_at=data["stored_at"],
            author=data["author"],
            session_id=data["session_id"],
            earning_graph_id=data["earning_graph_id"],
            earning_node_id=data["earning_node_id"],
            field_note_id=data["field_note_id"],
            field_note_revision_id=data["field_note_revision_id"],
            comparison_request_id=data.get("comparison_request_id"),
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "stored_at": self.stored_at,
            "author": self.author,
            "session_id": self.session_id,
            "earning_graph_id": self.earning_graph_id,
            "earning_node_id": self.earning_node_id,
            "field_note_id": self.field_note_id,
            "field_note_revision_id": self.field_note_revision_id,
            "comparison_request_id": self.comparison_request_id,
        }


@dataclass(frozen=True)
class KnowledgeCapsuleLaunch:
    schema_version: str
    id: str
    capsule_id: str
    launched_at: str
    markdown_path: str
    markdown_sha256: str
    success: Literal[True]

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            id=data["id"],
            capsule_id=data["capsule_id"],
            launched_at=data["launched_at"],
            markdown_path=data["markdown_path"],
            markdown_sha256=data["markdown_sha256"],
            success=data["success"],
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "capsule_id": self.capsule_id,
            "launched_at": self.launched_at,
            "markdown_path": self.markdown_path,
            "markdown_sha256": self.markdown_sha256,
            "success": self.success,
        }


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _turn_records(store: Store, session_id: str) -> list[tuple[dict, bytes]]:
    path = store.session_dir(session_id) / "turns.jsonl"
    records = []
    for line in path.read_bytes().splitlines(keepends=True):
        if not line.strip():
            continue
        data = json.loads(line)
        records.append((data, line))
    return records


def capsule_artifact_bytes(store: Store, artifact: CapsuleArtifact) -> bytes:
    """Resolve one exact immutable artifact named by a server-authored manifest."""
    from thought_archaeology.store import StoreError

    if artifact.kind == "turn":
        parts = Path(artifact.path).parts
        if len(parts) != 3 or parts[0] != "sessions" or parts[2] != "turns.jsonl":
            raise StoreError(f"invalid Capsule turn path: {artifact.path}")
        for data, raw in _turn_records(store, parts[1]):
            if data.get("id") == artifact.id:
                return raw
        raise StoreError(f"Capsule turn not found: {artifact.id}")
    path = (store.root / artifact.path).resolve()
    if store.root not in path.parents:
        raise StoreError(f"Capsule artifact path leaves the store: {artifact.path}")
    if not path.is_file():
        raise StoreError(f"Capsule artifact missing: {artifact.path}")
    return path.read_bytes()


def _file_artifact(store: Store, kind: ArtifactKind, path: Path) -> CapsuleArtifact:
    data = json.loads(path.read_text(encoding="utf-8"))
    return CapsuleArtifact(
        kind=kind,
        id=data["id"],
        path=str(path.relative_to(store.root)),
        sha256=_digest(path.read_bytes()),
    )


def capsule_session_artifacts(
    store: Store, session_id: str
) -> tuple[CapsuleArtifact, ...]:
    artifacts: list[CapsuleArtifact] = []
    turn_path = f"sessions/{session_id}/turns.jsonl"
    artifacts.extend(
        CapsuleArtifact("turn", data["id"], turn_path, _digest(raw))
        for data, raw in _turn_records(store, session_id)
    )
    artifacts.extend(
        _file_artifact(
            store,
            "graph",
            store.session_dir(session_id) / "graphs" / f"{graph.id}.json",
        )
        for graph in store.iter_graphs(session_id)
    )

    requests = [
        item for item in store.iter_continuation_requests() if item.session_id == session_id
    ]
    request_ids = {item.id for item in requests}
    artifact_groups = (
        (
            "continuation_request",
            requests,
            store.continuation_requests_dir,
        ),
        (
            "continuation_attempt",
            [
                item
                for item in store.iter_continuation_attempts()
                if item.request_id in request_ids
            ],
            store.continuation_attempts_dir,
        ),
        (
            "continuation_completion",
            [
                item
                for item in store.iter_continuation_completions()
                if item.request_id in request_ids
            ],
            store.continuation_completions_dir,
        ),
        (
            "continuation_failure",
            [
                item
                for item in store.iter_continuation_failures()
                if item.request_id in request_ids
            ],
            store.continuation_failures_dir,
        ),
        (
            "continuation_cancellation",
            [
                item
                for item in store.iter_continuation_cancellations()
                if item.request_id in request_ids
            ],
            store.continuation_cancellations_dir,
        ),
        (
            "parallel_continuation_batch",
            [item for item in store.iter_parallel_batches() if item.session_id == session_id],
            store.parallel_batches_dir,
        ),
    )
    for kind, items, directory in artifact_groups:
        artifacts.extend(
            _file_artifact(store, kind, directory / f"{item.id}.json")
            for item in items
        )

    from thought_archaeology.field_notes import field_note_versions

    for note in store.iter_field_notes():
        versions = field_note_versions(store, note)
        if not any(
            reference.session_id == session_id
            for version in versions
            for reference in version.references
        ):
            continue
        artifacts.append(
            _file_artifact(
                store, "field_note", store.field_notes_dir / f"{note.id}.json"
            )
        )
        artifacts.extend(
            _file_artifact(
                store,
                "field_note_revision",
                store.field_note_revisions_dir(note.id) / f"{revision.id}.json",
            )
            for revision in versions[1:]
        )

    artifacts.extend(
        _file_artifact(
            store,
            "knowledge_capsule_launcher",
            store.knowledge_capsule_launchers_dir / f"{launcher.id}.json",
        )
        for launcher in store.iter_knowledge_capsule_launchers()
        if launcher.session_id == session_id
    )

    local_groups = (
        ("probe", store.probes_dir(session_id)),
        ("graph_diff", store.diffs_dir(session_id)),
        ("evidence_binding", store.evidence_dir(session_id)),
        ("attribution", store.attributions_dir(session_id)),
        ("neural_intervention", store.neural_interventions_dir(session_id)),
        ("training_provenance", store.training_provenance_dir(session_id)),
    )
    for kind, directory in local_groups:
        if directory.is_dir():
            artifacts.extend(
                _file_artifact(store, kind, path)
                for path in sorted(directory.glob("*.json"))
            )

    order = {kind: index for index, kind in enumerate(
        (
            "turn",
            "graph",
            "continuation_request",
            "continuation_attempt",
            "continuation_completion",
            "continuation_failure",
            "continuation_cancellation",
            "parallel_continuation_batch",
            "field_note",
            "field_note_revision",
            "knowledge_capsule_launcher",
            "probe",
            "graph_diff",
            "evidence_binding",
            "attribution",
            "neural_intervention",
            "training_provenance",
        )
    )}
    artifacts.sort(key=lambda item: (order[item.kind], item.id))
    return tuple(artifacts)


def active_stored_launcher(store: Store) -> KnowledgeCapsuleLauncher | None:
    consumed = {
        manifest.stored_launcher_id
        for manifest in store.iter_knowledge_capsules()
        if manifest.stored_launcher_id
    }
    return next(
        (
            launcher
            for launcher in store.iter_knowledge_capsule_launchers()
            if launcher.id not in consumed
        ),
        None,
    )


def stored_launcher_read(
    store: Store, launcher: KnowledgeCapsuleLauncher, *, session_id: str | None = None
) -> dict:
    return {
        **launcher.to_dict(),
        "state": "stored",
        "available_here": session_id is None or launcher.session_id == session_id,
    }


def _knowledge_capsule_milestone(
    store: Store, *, graph_id: str, node_id: str
) -> dict | None:
    from thought_archaeology.continuation import parallel_group_summaries
    from thought_archaeology.field_notes import (
        field_note_comparison_request_id,
        field_note_read,
        field_notes_for_graphs,
    )

    graph = store.load_graph(graph_id)
    pending = {
        item.id
        for item in store.iter_continuation_requests(pending=True)
        if item.session_id == graph.session_id
    }
    if pending:
        return None
    for group in parallel_group_summaries(
        store, session_id=graph.session_id, graph_id=graph_id, node_id=node_id
    ):
        if group["completed_count"] < 2 or group["counts"]["pending"]:
            continue
        notes = field_notes_for_graphs(store, set(group["graph_ids"]))
        if len(notes) != 1:
            continue
        note = store.load_field_note(notes[0]["id"])
        reading = field_note_read(store, note)
        if reading["integrity"] != "verified":
            continue
        if any(
            item.comparison_request_id == group["representative_request_id"]
            and item.field_note_id == note.id
            for item in store.iter_knowledge_capsules()
        ):
            continue
        session = store.load_session(graph.session_id)
        if not session.head_graph_id or not session.head_turn_id:
            continue
        return {
            "mode": "parallel",
            "comparison_request_id": group["representative_request_id"],
            "session_id": graph.session_id,
            "source_graph_id": graph_id,
            "source_node_id": node_id,
            "earning_graph_id": graph_id,
            "earning_node_id": node_id,
            "completed_count": group["completed_count"],
            "field_note_id": note.id,
            "field_note_revision_id": reading["current_revision_id"],
            "head_graph_id": session.head_graph_id,
            "head_turn_id": session.head_turn_id,
            "prompt": group["prompt"],
        }
    if not any(
        completion.graph_id == graph.id
        for completion in store.iter_continuation_completions()
    ):
        return None
    for note in store.iter_field_notes():
        if field_note_comparison_request_id(store, note) is not None:
            continue
        if {reference.graph_id for reference in note.references} != {graph.id}:
            continue
        reading = field_note_read(store, note)
        if reading["integrity"] != "verified":
            continue
        if any(
            item.field_note_id == note.id
            for item in store.iter_knowledge_capsules()
        ):
            continue
        session = store.load_session(graph.session_id)
        if not session.head_graph_id or not session.head_turn_id:
            continue
        return {
            "mode": "single_path",
            "comparison_request_id": None,
            "session_id": graph.session_id,
            "source_graph_id": graph.id,
            "source_node_id": node_id,
            "earning_graph_id": graph.id,
            "earning_node_id": node_id,
            "completed_count": 1,
            "field_note_id": note.id,
            "field_note_revision_id": reading["current_revision_id"],
            "head_graph_id": session.head_graph_id,
            "head_turn_id": session.head_turn_id,
            "prompt": "Completed collaborator path",
        }
    return None


def knowledge_capsule_eligibility(
    store: Store, *, graph_id: str, node_id: str
) -> dict | None:
    """Return the one server-authored opportunity at an earned chamber."""
    if active_stored_launcher(store) is not None:
        return None
    return _knowledge_capsule_milestone(store, graph_id=graph_id, node_id=node_id)


def store_knowledge_capsule_launcher(
    store: Store, *, graph_id: str, node_id: str, field_note_id: str
) -> KnowledgeCapsuleLauncher:
    """Bank one earned launcher without freezing the Threadwalk."""
    from thought_archaeology.store import StoreError

    with store.knowledge_capsules_lock():
        if active_stored_launcher(store) is not None:
            raise StoreError("one Knowledge Capsule launcher is already stored")
        eligibility = _knowledge_capsule_milestone(
            store, graph_id=graph_id, node_id=node_id
        )
        if not eligibility or eligibility["field_note_id"] != field_note_id:
            raise StoreError("this chamber has not earned a Knowledge Capsule launcher")
        launcher = KnowledgeCapsuleLauncher(
            schema_version=SCHEMA_VERSION,
            id=new_ulid(),
            stored_at=now_iso(),
            author="human",
            session_id=eligibility["session_id"],
            earning_graph_id=eligibility["earning_graph_id"],
            earning_node_id=eligibility["earning_node_id"],
            field_note_id=eligibility["field_note_id"],
            field_note_revision_id=eligibility["field_note_revision_id"],
            comparison_request_id=eligibility["comparison_request_id"],
        )
        store.write_knowledge_capsule_launcher(launcher)
        return launcher


def construct_knowledge_capsule(
    store: Store,
    *,
    comparison_request_id: str | None = None,
    graph_id: str | None = None,
    node_id: str | None = None,
    field_note_id: str | None = None,
    stored_launcher_id: str | None = None,
) -> KnowledgeCapsuleManifest:
    """Freeze one complete session milestone without rendering or launching it."""
    from thought_archaeology.continuation import parallel_comparison
    from thought_archaeology.store import StoreError

    with store.knowledge_capsules_lock():
        launcher = None
        if stored_launcher_id:
            launcher = active_stored_launcher(store)
            if launcher is None or launcher.id != stored_launcher_id:
                raise StoreError("stored Knowledge Capsule launcher is not available")
            if not graph_id or not node_id:
                raise StoreError("stored launcher deployment requires a chamber")
            graph = store.load_graph(graph_id)
            if graph.session_id != launcher.session_id:
                raise StoreError("stored launcher can only deploy in its earning Threadwalk")
            if node_id not in {node.id for node in graph.nodes}:
                raise StoreError("stored launcher deployment node is not in its graph")
            if any(
                request.session_id == launcher.session_id
                for request in store.iter_continuation_requests(pending=True)
            ):
                raise StoreError("stored launcher cannot deploy while a continuation is pending")
            note = store.load_field_note(launcher.field_note_id)
            from thought_archaeology.field_notes import field_note_read

            reading = field_note_read(store, note)
            if reading["integrity"] != "verified":
                raise StoreError("stored launcher Field Note source integrity failed")
            session = store.load_session(launcher.session_id)
            if not session.head_graph_id or not session.head_turn_id:
                raise StoreError("stored launcher Threadwalk has no current head")
            eligibility = {
                "comparison_request_id": launcher.comparison_request_id,
                "session_id": launcher.session_id,
                "source_graph_id": graph_id,
                "source_node_id": node_id,
                "earning_graph_id": launcher.earning_graph_id,
                "earning_node_id": launcher.earning_node_id,
                "field_note_id": launcher.field_note_id,
                "field_note_revision_id": reading["current_revision_id"],
                "head_graph_id": session.head_graph_id,
                "head_turn_id": session.head_turn_id,
            }
        else:
            if comparison_request_id and (not graph_id or not node_id):
                comparison = parallel_comparison(store, comparison_request_id)
                graph_id = comparison["source_graph_id"]
                node_id = comparison["source_node_id"]
            if not graph_id or not node_id:
                raise StoreError("Knowledge Capsule construction requires a chamber")
            eligibility = knowledge_capsule_eligibility(
                store, graph_id=graph_id, node_id=node_id
            )
            if (
                not eligibility
                or (field_note_id and eligibility["field_note_id"] != field_note_id)
                or eligibility["comparison_request_id"] != comparison_request_id
            ):
                raise StoreError("this chamber has not earned a Knowledge Capsule")
        manifest = KnowledgeCapsuleManifest(
            schema_version=SCHEMA_VERSION,
            id=new_ulid(),
            created_at=now_iso(),
            author="human",
            comparison_request_id=eligibility["comparison_request_id"],
            session_id=eligibility["session_id"],
            session_title=store.load_session(eligibility["session_id"]).title,
            source_graph_id=eligibility["source_graph_id"],
            source_node_id=eligibility["source_node_id"],
            head_graph_id=eligibility["head_graph_id"],
            head_turn_id=eligibility["head_turn_id"],
            field_note_id=eligibility["field_note_id"],
            field_note_revision_id=eligibility["field_note_revision_id"],
            stored_launcher_id=launcher.id if launcher else None,
            earning_graph_id=eligibility["earning_graph_id"],
            earning_node_id=eligibility["earning_node_id"],
            rendering_version=RENDERING_VERSION,
            privacy_warning=PRIVACY_WARNING,
            omissions=OMISSIONS,
            artifacts=capsule_session_artifacts(store, eligibility["session_id"]),
        )
        store.write_knowledge_capsule(manifest)
        return manifest


def capsule_integrity(store: Store, manifest: KnowledgeCapsuleManifest) -> dict:
    results = []
    for artifact in manifest.artifacts:
        try:
            actual = _digest(capsule_artifact_bytes(store, artifact))
            status = "verified" if actual == artifact.sha256 else "mismatch"
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            actual = None
            status = "missing"
        except Exception as exc:
            from thought_archaeology.store import StoreError

            if not isinstance(exc, StoreError):
                raise
            actual = None
            status = "missing"
        results.append(
            {
                **artifact.to_dict(),
                "integrity": status,
                "actual_sha256": actual,
            }
        )
    return {
        "status": (
            "verified"
            if all(item["integrity"] == "verified" for item in results)
            else "failed"
        ),
        "artifacts": results,
    }


def _artifact_payload(store: Store, artifact: CapsuleArtifact) -> dict:
    return json.loads(capsule_artifact_bytes(store, artifact))


def _quote(text: str) -> list[str]:
    lines = text.splitlines() or [""]
    return [f"> {line}" if line else ">" for line in lines]


def render_knowledge_capsule_markdown(
    store: Store,
    manifest: KnowledgeCapsuleManifest,
    *,
    launched_at: str,
) -> str:
    integrity = capsule_integrity(store, manifest)
    if integrity["status"] != "verified":
        from thought_archaeology.store import StoreError

        raise StoreError("Knowledge Capsule source integrity failed")

    by_kind: dict[str, list[tuple[CapsuleArtifact, dict]]] = {}
    for artifact in manifest.artifacts:
        by_kind.setdefault(artifact.kind, []).append(
            (artifact, _artifact_payload(store, artifact))
        )
    graphs = {data["id"]: data for _artifact, data in by_kind.get("graph", [])}
    requests = {
        data["id"]: data
        for _artifact, data in by_kind.get("continuation_request", [])
    }
    completions = {
        data["request_id"]: data
        for _artifact, data in by_kind.get("continuation_completion", [])
    }
    attempts = {
        data["request_id"]: data
        for _artifact, data in by_kind.get("continuation_attempt", [])
    }
    failures = {
        data["request_id"]: data
        for _artifact, data in by_kind.get("continuation_failure", [])
    }
    cancellations = {
        data["request_id"]: data
        for _artifact, data in by_kind.get("continuation_cancellation", [])
    }
    harness_by_graph = {
        item["graph_id"]: item["harness"] for item in completions.values()
    }

    lines = [
        "# Knowledge Capsule",
        "",
        f"> **Private review warning:** {manifest.privacy_warning}",
        "",
        "## Capsule identity",
        "",
        f"- Capsule: `{manifest.id}`",
        f"- Constructed: `{manifest.created_at}`",
        f"- Launched: `{launched_at}`",
        f"- Human author: `{manifest.author}`",
        f"- Session: `{manifest.session_id}` — {manifest.session_title}",
        f"- Frozen head graph: `{manifest.head_graph_id}`",
        f"- Frozen head turn: `{manifest.head_turn_id}`",
        (
            f"- Parallel comparison: `{manifest.comparison_request_id}`"
            if manifest.comparison_request_id
            else "- Earning route: `single completed collaborator path`"
        ),
        f"- Deployment chamber: `{manifest.source_graph_id}/{manifest.source_node_id}`",
        (
            f"- Earning chamber: `{manifest.earning_graph_id}/{manifest.earning_node_id}`"
            if manifest.earning_graph_id and manifest.earning_node_id
            else "- Earning chamber: `legacy comparison source`"
        ),
        f"- Pinned Field Note revision: `{manifest.field_note_id}/{manifest.field_note_revision_id}`",
        f"- Rendering version: `{manifest.rendering_version}`",
        "",
        "This is a readable snapshot of recorded public thought-objects and human interpretation. It does not certify truth, importance, agreement, consensus, or causal explanation.",
        "",
        "## Conversation turns",
        "",
    ]
    turns = sorted(
        (data for _artifact, data in by_kind.get("turn", [])),
        key=lambda item: (item["seq"], item["id"]),
    )
    for turn in turns:
        attribution = ""
        graph = graphs.get(turn.get("graph_id"))
        if graph:
            model = graph["model"]
            harness = harness_by_graph.get(graph["id"])
            attribution = (
                f" · model `{model['name']}` · provider `{model['provider']}`"
                + (f" · harness `{harness}`" if harness else "")
            )
        lines.extend(
            [
                f"### Turn {turn['seq'] + 1} · {turn['role']}{attribution}",
                "",
                f"`{turn['id']}` · `{turn['created_at']}`",
                "",
                *_quote(turn.get("prose", "")),
                "",
            ]
        )
    if not turns:
        lines.extend(["No turn records were included.", ""])

    lines.extend(["## Public graph generations", ""])
    for _artifact, graph in by_kind.get("graph", []):
        model = graph["model"]
        harness = harness_by_graph.get(graph["id"])
        title = f"### Graph `{graph['id']}`"
        lines.extend(
            [
                title,
                "",
                f"- Created: `{graph['created_at']}`",
                f"- Turn: `{graph['turn_id']}`",
                f"- Parent graph: `{graph.get('parent_graph_id') or 'none'}`",
                f"- Model: `{model['name']}` · provider `{model['provider']}` · compile `{model['compile_mode']}`",
                f"- Harness: `{harness or 'not recorded'}`",
                "",
                "#### Public response",
                "",
                *_quote(graph.get("prose", "")),
                "",
                "#### Thought-objects",
                "",
            ]
        )
        for index, node in enumerate(graph.get("nodes", []), start=1):
            kind = "judgment_call" if node["kind"] == "taste_call" else node["kind"]
            lines.extend(
                [
                    f"{index}. `{node['id']}` · **{kind.replace('_', ' ')}** · {node['status']} · {node['agent']}",
                    "",
                    *[f"   {line}" for line in _quote(node["text"])],
                    "",
                ]
            )
        lines.extend(["#### Typed edges", ""])
        if graph.get("edges"):
            lines.extend(
                f"- `{edge['id']}` · `{edge['source_id']}` → `{edge['target_id']}` · **{edge['kind']}**"
                for edge in graph["edges"]
            )
            lines.append("")
        else:
            lines.extend(["No typed edges recorded.", ""])

    lines.extend(["## Inquiry and intervention history", ""])
    for request_id, request in sorted(
        requests.items(), key=lambda item: (item[1]["created_at"], item[0])
    ):
        if request_id in completions:
            closing = completions[request_id]
            status = f"completed as graph `{closing['graph_id']}` by `{closing['harness']}`"
        elif request_id in failures:
            closing = failures[request_id]
            status = f"failed · {closing['reason_code']} · {closing['public_summary']}"
        elif request_id in cancellations:
            status = "canceled"
        else:
            status = "not terminal in frozen scope"
        attempt = attempts.get(request_id)
        lines.extend(
            [
                f"### Continuation `{request_id}`",
                "",
                f"- Source: `{request['graph_id']}/{request['node_id']}`",
                f"- Requested harness: `{request.get('requested_harness') or 'not pinned'}`",
                f"- Attempt: `{attempt['id'] if attempt else 'none recorded'}`",
                f"- Status: {status}",
                f"- Parallel batch: `{request.get('parallel_batch_id') or 'none'}`",
                "",
                "Question:",
                "",
                *_quote(request.get("prompt", "") or "(continued without a new question)"),
                "",
            ]
        )
    for _artifact, batch in by_kind.get("parallel_continuation_batch", []):
        lines.extend(
            [
                f"### Parallel comparison batch `{batch['id']}`",
                "",
                f"- Exact source: `{batch['graph_id']}/{batch['node_id']}`",
                f"- Ordered jobs: {len(batch['jobs'])}",
                "",
                *[
                    f"- {job['position'] + 1}. `{job['harness']}` · request `{job['request_id']}`"
                    for job in batch["jobs"]
                ],
                "",
            ]
        )
    edits = [
        graph
        for _artifact, graph in by_kind.get("graph", [])
        if graph.get("fork")
        or any(
            node.get("agent") == "human" and node.get("status") == "vetoed"
            for node in graph.get("nodes", [])
        )
    ]
    if edits:
        lines.extend(["### Cuts and human vetoes", ""])
        for graph in edits:
            fork = graph.get("fork") or {}
            mode = "human veto" if any(
                node.get("agent") == "human" and node.get("status") == "vetoed"
                for node in graph.get("nodes", [])
            ) else "cut or fork"
            lines.append(
                f"- `{graph['id']}` · {mode} · parent `{graph.get('parent_graph_id') or 'none'}` · reason: {fork.get('reason') or 'not recorded'}"
            )
        lines.append("")

    lines.extend(["## Human Field Notes", ""])
    notes = {
        data["id"]: data for _artifact, data in by_kind.get("field_note", [])
    }
    revisions: dict[str, list[dict]] = {}
    for _artifact, revision in by_kind.get("field_note_revision", []):
        revisions.setdefault(revision["note_id"], []).append(revision)
    for note_id, note in notes.items():
        versions = [note, *sorted(
            revisions.get(note_id, []), key=lambda item: (item["created_at"], item["id"])
        )]
        lines.extend([f"### Human Field Note `{note_id}`", ""])
        for index, version in enumerate(versions, start=1):
            lines.extend(
                [
                    f"#### Revision {index}/{len(versions)} · {version['kind'].replace('_', ' ')} · `{version['id']}`",
                    "",
                    f"Human-authored at `{version['created_at']}`.",
                    "",
                    *_quote(version["text"]),
                    "",
                    "Exact selected sources:",
                    "",
                ]
            )
            for ref in version["references"]:
                node = next(
                    (
                        item
                        for item in graphs.get(ref["graph_id"], {}).get("nodes", [])
                        if item["id"] == ref["node_id"]
                    ),
                    None,
                )
                text = f" — {node['text']}" if node else ""
                lines.append(
                    f"- `{ref['session_id']}/{ref['graph_id']}/{ref['node_id']}` · graph SHA-256 `{ref['graph_sha256']}`{text}"
                )
            lines.append("")
    if not notes:
        lines.extend(["No Field Notes were included.", ""])

    lines.extend(["## Bounded evidence and provenance", ""])
    evidence = by_kind.get("evidence_binding", [])
    for _artifact, binding in evidence:
        lines.extend(
            [
                f"### {binding['kind'].replace('_', ' ')} · {binding['result']} · `{binding['id']}`",
                "",
                f"- Thought: `{binding['graph_id']}/{binding['node_id']}`",
                f"- Parent evidence: `{binding.get('parent_evidence_id') or 'none'}`",
                "",
                *_quote(binding["summary"]),
                "",
                "Artifact references:",
                "",
                *[f"- `{reference}`" for reference in binding["artifact_refs"]],
                "",
            ]
        )
    if not evidence:
        lines.extend([
            "No evidence binding was present in the frozen session scope. Absence is not evidence.",
            "",
        ])
    provenance_kinds = (
        "probe",
        "graph_diff",
        "attribution",
        "neural_intervention",
        "training_provenance",
    )
    counts = Counter(
        artifact.kind
        for artifact in manifest.artifacts
        if artifact.kind in provenance_kinds
    )
    if counts:
        lines.extend(["### Included provenance artifacts", ""])
        for kind in provenance_kinds:
            if counts[kind]:
                ids = [
                    artifact.id for artifact in manifest.artifacts if artifact.kind == kind
                ]
                lines.append(
                    f"- {kind.replace('_', ' ')} ({counts[kind]}): "
                    + ", ".join(f"`{item}`" for item in ids)
                )
        lines.append("")

    lines.extend(["## Integrity appendix", ""])
    lines.append(
        f"All {len(manifest.artifacts)} included immutable artifact records verified at launch."
    )
    lines.extend(
        [
            "",
            "| Kind | ID | SHA-256 | Store-relative source |",
            "|---|---|---|---|",
            *[
                f"| {item.kind} | `{item.id}` | `{item.sha256}` | `{item.path}` |"
                for item in manifest.artifacts
            ],
            "",
            "## Explicit omissions",
            "",
            *[f"- {item}" for item in manifest.omissions],
            "",
        ]
    )
    return "\n".join(lines)


def launch_knowledge_capsule(
    store: Store, capsule_id: str
) -> KnowledgeCapsuleLaunch:
    from thought_archaeology.store import StoreError

    with store.knowledge_capsules_lock():
        manifest = store.load_knowledge_capsule(capsule_id)
        if store.knowledge_capsule_launch_exists(capsule_id):
            raise StoreError(f"Knowledge Capsule {capsule_id} already launched")
        path = store.knowledge_capsule_export_path(capsule_id)
        launched_at = now_iso()
        if path.is_file():
            existing = path.read_text(encoding="utf-8")
            match = re.search(r"^- Launched: `([^`]+)`$", existing, re.MULTILINE)
            if not match:
                raise StoreError("existing Knowledge Capsule export is not recoverable")
            launched_at = match.group(1)
            markdown = render_knowledge_capsule_markdown(
                store, manifest, launched_at=launched_at
            )
            if existing != markdown:
                raise StoreError("existing Knowledge Capsule export bytes do not match")
        else:
            markdown = render_knowledge_capsule_markdown(
                store, manifest, launched_at=launched_at
            )
            store.write_knowledge_capsule_markdown(capsule_id, markdown)
        digest = _digest(markdown.encode("utf-8"))
        launch = KnowledgeCapsuleLaunch(
            schema_version=SCHEMA_VERSION,
            id=new_ulid(),
            capsule_id=capsule_id,
            launched_at=launched_at,
            markdown_path=str(path.relative_to(store.root)),
            markdown_sha256=digest,
            success=True,
        )
        store.write_knowledge_capsule_launch(launch)
        return launch


def knowledge_capsule_read(store: Store, manifest: KnowledgeCapsuleManifest) -> dict:
    launch = (
        store.load_knowledge_capsule_launch(manifest.id)
        if store.knowledge_capsule_launch_exists(manifest.id)
        else None
    )
    integrity = capsule_integrity(store, manifest)
    markdown_integrity = None
    markdown_path = None
    if launch:
        path = store.root / launch.markdown_path
        markdown_path = str(path)
        if path.is_file():
            markdown_integrity = (
                "verified"
                if _digest(path.read_bytes()) == launch.markdown_sha256
                else "mismatch"
            )
        else:
            markdown_integrity = "missing"
    counts = Counter(item.kind for item in manifest.artifacts)
    return {
        **manifest.to_dict(),
        "state": "launched" if launch else "ready",
        "integrity": integrity["status"],
        "artifact_integrity": integrity["artifacts"],
        "artifact_counts": dict(sorted(counts.items())),
        "artifact_count": len(manifest.artifacts),
        "launch": launch.to_dict() if launch else None,
        "markdown_path": markdown_path,
        "markdown_integrity": markdown_integrity,
    }


def knowledge_capsule_summaries(
    store: Store,
    *,
    session_id: str | None = None,
    comparison_request_id: str | None = None,
    source_graph_id: str | None = None,
    source_node_id: str | None = None,
) -> list[dict]:
    summaries = []
    for manifest in store.iter_knowledge_capsules():
        if session_id is not None and manifest.session_id != session_id:
            continue
        if (
            comparison_request_id is not None
            and manifest.comparison_request_id != comparison_request_id
        ):
            continue
        if source_graph_id is not None and manifest.source_graph_id != source_graph_id:
            continue
        if source_node_id is not None and manifest.source_node_id != source_node_id:
            continue
        launch = (
            store.load_knowledge_capsule_launch(manifest.id)
            if store.knowledge_capsule_launch_exists(manifest.id)
            else None
        )
        summaries.append(
            {
                "id": manifest.id,
                "created_at": manifest.created_at,
                "author": manifest.author,
                "state": "launched" if launch else "ready",
                "comparison_request_id": manifest.comparison_request_id,
                "session_id": manifest.session_id,
                "session_title": manifest.session_title,
                "source_graph_id": manifest.source_graph_id,
                "source_node_id": manifest.source_node_id,
                "head_graph_id": manifest.head_graph_id,
                "head_turn_id": manifest.head_turn_id,
                "field_note_id": manifest.field_note_id,
                "field_note_revision_id": manifest.field_note_revision_id,
                "stored_launcher_id": manifest.stored_launcher_id,
                "earning_graph_id": manifest.earning_graph_id,
                "earning_node_id": manifest.earning_node_id,
                "artifact_count": len(manifest.artifacts),
                "launched_at": launch.launched_at if launch else None,
            }
        )
    return summaries
