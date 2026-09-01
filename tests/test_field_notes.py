from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from thought_archaeology.continuation import parallel_comparison
from thought_archaeology.field_notes import (
    create_field_note,
    field_note,
    field_note_eligibility,
    field_note_read,
    field_note_summaries,
)
from thought_archaeology.ids import new_ulid
from thought_archaeology.inhabit import inhabit
from thought_archaeology.schema import ValidationError, validate_schema
from thought_archaeology.serve import InhabitHandler, thread_payload
from thought_archaeology.store import StoreError

from tests.test_cli import run
from tests.test_continuation import _parallel_study


def _references(comparison: dict, count: int = 2) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (
            comparison["session_id"],
            path["graph_id"],
            path["selectable_thoughts"][0]["id"],
        )
        for path in comparison["paths"][:count]
    )


def _source_hashes(store, graph_ids: list[str]) -> dict[str, str]:
    return {graph_id: store.graph_sha256(graph_id) for graph_id in graph_ids}


def test_field_note_is_write_once_exact_and_non_mutating(tmp_path: Path):
    store, _source_node, request_ids = _parallel_study(tmp_path / "data")
    comparison = parallel_comparison(store, request_ids[0])
    references = _references(comparison)
    graph_ids = [path["graph_id"] for path in comparison["paths"]]
    graph_hashes = _source_hashes(store, graph_ids)
    sessions_before = {
        session_id: (store.session_dir(session_id) / "session.json").read_bytes()
        for session_id in store.iter_session_ids()
    }
    turns_before = {
        session_id: (store.session_dir(session_id) / "turns.jsonl").read_bytes()
        for session_id in store.iter_session_ids()
    }
    pending_before = [item.to_dict() for item in store.iter_continuation_requests(pending=True)]

    note = create_field_note(
        store,
        kind="observation",
        text="  The difference is useful because neither path erases the other.  ",
        references=references,
        comparison_request_id=request_ids[0],
    )
    assert note.author == "human"
    assert note.text == "The difference is useful because neither path erases the other."
    assert [item.graph_sha256 for item in note.references] == [
        graph_hashes[item.graph_id] for item in note.references
    ]
    assert store.load_field_note(note.id) == note
    assert oct((store.field_notes_dir / f"{note.id}.json").stat().st_mode & 0o777) == oct(0o600)
    with pytest.raises(StoreError, match="write-once"):
        store.write_field_note(note)

    assert _source_hashes(store, graph_ids) == graph_hashes
    assert {
        session_id: (store.session_dir(session_id) / "session.json").read_bytes()
        for session_id in store.iter_session_ids()
    } == sessions_before
    assert {
        session_id: (store.session_dir(session_id) / "turns.jsonl").read_bytes()
        for session_id in store.iter_session_ids()
    } == turns_before
    assert [item.to_dict() for item in store.iter_continuation_requests(pending=True)] == pending_before

    read = field_note_read(store, note)
    assert read["integrity"] == "verified"
    assert [item["harness"] for item in read["references"]] == ["grok", "codex"]
    assert all(item["thought"]["text"] for item in read["references"])
    assert field_note_summaries(
        store,
        graph_id=note.references[0].graph_id,
        node_id=note.references[0].node_id,
    )[0]["id"] == note.id
    assert parallel_comparison(store, request_ids[0])["field_notes"][0]["id"] == note.id
    lineage = thread_payload(
        store,
        comparison["session_id"],
        graph_id=note.references[0].graph_id,
        node_id=note.references[0].node_id,
    )
    assert lineage["standing_field_notes"][0]["kind"] == "observation"
    assert lineage["parallel_groups"][0]["field_notes"][0]["id"] == note.id


def test_field_note_validation_and_comparison_guard(tmp_path: Path):
    store, _source_node, request_ids = _parallel_study(tmp_path / "data")
    comparison = parallel_comparison(store, request_ids[0])
    references = _references(comparison)

    empty = field_note(store, kind="conclusion", text="   ", references=references)
    with pytest.raises(ValidationError, match="non-empty"):
        store.write_field_note(empty)

    untrimmed = replace(
        field_note(store, kind="conclusion", text="trimmed", references=references),
        text=" not trimmed ",
    )
    with pytest.raises(ValidationError, match="must be trimmed"):
        store.write_field_note(untrimmed)

    same_graph = (
        references[0],
        (
            references[0][0],
            references[0][1],
            comparison["paths"][0]["selectable_thoughts"][1]["id"],
        ),
    )
    with pytest.raises(StoreError, match="at least two graphs"):
        store.write_field_note(
            field_note(store, kind="observation", text="two thoughts", references=same_graph)
        )

    outside = store.load_graph(comparison["source_graph_id"])
    with pytest.raises(StoreError, match="come from the comparison"):
        create_field_note(
            store,
            kind="unresolved_question",
            text="Does the source itself change the comparison?",
            references=(references[0], (outside.session_id, outside.id, outside.nodes[0].id)),
            comparison_request_id=request_ids[0],
        )

    wrong_session = field_note(store, kind="observation", text="wrong", references=references)
    broken = wrong_session.to_dict()
    broken["references"][0]["session_id"] = request_ids[0]
    from thought_archaeology.field_notes import FieldNote

    with pytest.raises(StoreError, match="is not in session"):
        store.write_field_note(FieldNote.from_dict(broken))


def test_field_note_schema_boundaries(tmp_path: Path):
    store, _source_node, request_ids = _parallel_study(tmp_path / "data")
    comparison = parallel_comparison(store, request_ids[0])
    valid = field_note(
        store,
        kind="conclusion",
        text="The selected paths remain distinct.",
        references=_references(comparison),
    ).to_dict()

    invalid = []
    for key, value in (
        ("kind", "summary"),
        ("text", ""),
        ("text", "x" * 4001),
    ):
        candidate = deepcopy(valid)
        candidate[key] = value
        invalid.append(candidate)
    malformed_hash = deepcopy(valid)
    malformed_hash["references"][0]["graph_sha256"] = "not-a-digest"
    invalid.append(malformed_hash)
    duplicate = deepcopy(valid)
    duplicate["references"] = [duplicate["references"][0]] * 2
    invalid.append(duplicate)
    too_few = deepcopy(valid)
    too_few["references"] = too_few["references"][:1]
    invalid.append(too_few)
    too_many = deepcopy(valid)
    too_many["references"] = [
        {
            **too_many["references"][index % 2],
            "node_id": new_ulid(),
        }
        for index in range(13)
    ]
    invalid.append(too_many)

    for candidate in invalid:
        with pytest.raises(ValidationError):
            validate_schema("field-note.schema.json", candidate)


def test_field_note_cli_and_server_surfaces(tmp_path: Path):
    store_path = tmp_path / "data"
    store, _source_node, request_ids = _parallel_study(store_path)
    comparison = parallel_comparison(store, request_ids[0])
    references = _references(comparison)
    ref_args = [
        item
        for reference in references
        for item in ("--reference", "/".join(reference))
    ]
    code, out, err = run(
        [
            "field-note",
            "create",
            "--kind",
            "conclusion",
            "--comparison",
            request_ids[0],
            *ref_args,
            "--text",
            "Plural paths should remain addressably different.",
        ],
        store=store_path,
    )
    assert code == 0, err
    note_id = out.strip()
    log = list(store.iter_log_entries())[-1]
    assert log["op"] == "field_note_create"
    assert "Plural paths" not in json.dumps(log)

    code, out, err = run(
        ["field-note", "show", note_id, "--format", "json"], store=store_path
    )
    assert code == 0, err
    assert json.loads(out)["integrity"] == "verified"
    code, out, err = run(["validate", note_id], store=store_path)
    assert code == 0, err
    code, out, err = run(
        [
            "field-note",
            "list",
            "--graph",
            references[0][1],
            "--node",
            references[0][2],
            "--format",
            "json",
        ],
        store=store_path,
    )
    assert code == 0, err
    assert [item["id"] for item in json.loads(out)] == [note_id]

    replies = []
    handler = object.__new__(InhabitHandler)
    handler.store = store
    handler._json = lambda status, body: replies.append((status, body))
    handler._read_json = lambda: {
        "kind": "unresolved_question",
        "text": "Which fracture deserves another inquiry?",
        "comparison_request_id": request_ids[0],
        "references": [
            {"session_id": session, "graph_id": graph, "node_id": node}
            for session, graph, node in references
        ],
    }
    handler._field_note_create()
    assert replies[-1][0] == 200
    second = replies[-1][1]["note"]
    assert second["kind_label"] == "unresolved question"
    assert second["integrity"] == "verified"

    handler.path = f"/api/field-notes/{second['id']}"
    handler.do_GET()
    assert replies[-1][1]["text"] == "Which fracture deserves another inquiry?"
    handler.path = f"/api/inhabit/{references[0][2]}?graph={references[0][1]}"
    handler.do_GET()
    inhabit_payload = replies[-1][1]
    assert len(inhabit_payload["field_notes"]) == 2
    assert "inspect in Thread Compass" in inhabit_payload["read"]["field_note_line"]

    graph_id = comparison["paths"][0]["graph_id"]
    graph = store.load_graph(graph_id)
    terminal = next(
        node
        for node in graph.nodes
        if not inhabit(store, node.id, graph_id=graph.id).forward
    )
    eligibility = field_note_eligibility(
        store, graph_id=graph.id, node_id=terminal.id
    )
    assert eligibility["comparison_request_id"] == request_ids[0]
    assert eligibility["standing_reference"] == {
        "session_id": graph.session_id,
        "graph_id": graph.id,
        "node_id": terminal.id,
    }
    handler.path = f"/api/inhabit/{terminal.id}?graph={graph.id}"
    handler.do_GET()
    assert replies[-1][1]["field_note_eligibility"] == eligibility
    nonterminal = next(
        node
        for node in graph.nodes
        if inhabit(store, node.id, graph_id=graph.id).forward
    )
    handler.path = f"/api/inhabit/{nonterminal.id}?graph={graph.id}"
    handler.do_GET()
    assert replies[-1][1]["field_note_eligibility"] is None


def test_field_note_digest_is_exact_graph_bytes(tmp_path: Path):
    store, _source_node, request_ids = _parallel_study(tmp_path / "data")
    comparison = parallel_comparison(store, request_ids[0])
    note = create_field_note(
        store,
        kind="observation",
        text="Exact bytes remain the local integrity boundary.",
        references=_references(comparison),
        comparison_request_id=request_ids[0],
    )
    for reference in note.references:
        path = store.session_dir(reference.session_id) / "graphs" / f"{reference.graph_id}.json"
        assert reference.graph_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()

    first = note.references[0]
    path = store.session_dir(first.session_id) / "graphs" / f"{first.graph_id}.json"
    path.write_bytes(path.read_bytes() + b" ")
    read = field_note_read(store, note)
    assert read["integrity"] == "failed"
    assert read["references"][0]["integrity"] == "mismatch"
    assert store.load_field_note(note.id) == note
