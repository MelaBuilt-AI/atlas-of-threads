from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from thought_archaeology.continuation import parallel_comparison
from thought_archaeology.field_notes import create_field_note, edit_field_note
from thought_archaeology.knowledge_capsules import (
    capsule_artifact_bytes,
    capsule_integrity,
    construct_knowledge_capsule,
    knowledge_capsule_eligibility,
    knowledge_capsule_read,
    launch_knowledge_capsule,
)
from thought_archaeology.schema import ValidationError, validate_schema
from thought_archaeology.serve import InhabitHandler
from thought_archaeology.store import StoreError

from tests.test_cli import run
from tests.test_continuation import _parallel_study


def _capsule_study(path: Path):
    store, source_node, request_ids = _parallel_study(path)
    comparison = parallel_comparison(store, request_ids[0])
    references = tuple(
        (
            comparison["session_id"],
            item["graph_id"],
            item["selectable_thoughts"][0]["id"],
        )
        for item in comparison["paths"][:2]
    )
    note = create_field_note(
        store,
        kind="conclusion",
        text="Plural paths are useful precisely because the human reading stays explicit.",
        references=references,
        comparison_request_id=request_ids[0],
    )
    return store, source_node, request_ids[0], comparison, note, references


def _session_bytes(store, session_id: str) -> dict[str, bytes]:
    root = store.session_dir(session_id)
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_capsule_eligibility_and_construction_freeze_exact_scope(tmp_path: Path):
    store, source_node, request_id, comparison, note, references = _capsule_study(
        tmp_path / "data"
    )
    eligibility = knowledge_capsule_eligibility(
        store,
        graph_id=comparison["source_graph_id"],
        node_id=source_node.id,
    )
    assert eligibility["comparison_request_id"] == request_id
    assert eligibility["field_note_id"] == note.id
    assert knowledge_capsule_eligibility(
        store,
        graph_id=references[0][1],
        node_id=references[0][2],
    ) is None

    revision = edit_field_note(
        store,
        note_id=note.id,
        kind="observation",
        text="The frozen reading should pin this exact current revision.",
        references=references,
        comparison_request_id=request_id,
    )
    session_before = _session_bytes(store, comparison["session_id"])
    manifest = construct_knowledge_capsule(
        store, comparison_request_id=request_id
    )
    path = store.knowledge_capsules_dir / f"{manifest.id}.json"

    assert manifest.author == "human"
    assert manifest.session_title == store.load_session(manifest.session_id).title
    assert manifest.field_note_revision_id == revision.id
    assert manifest.head_graph_id == store.load_session(manifest.session_id).head_graph_id
    assert manifest.head_turn_id == store.load_session(manifest.session_id).head_turn_id
    assert oct(path.stat().st_mode & 0o777) == oct(0o600)
    assert _session_bytes(store, comparison["session_id"]) == session_before
    assert capsule_integrity(store, manifest)["status"] == "verified"
    assert {item.kind for item in manifest.artifacts} >= {
        "turn", "graph", "continuation_request", "continuation_completion",
        "field_note", "field_note_revision",
    }
    for artifact in manifest.artifacts:
        assert hashlib.sha256(capsule_artifact_bytes(store, artifact)).hexdigest() == artifact.sha256
    assert knowledge_capsule_eligibility(
        store,
        graph_id=comparison["source_graph_id"],
        node_id=source_node.id,
    ) is None
    with pytest.raises(StoreError, match="earned|already exists"):
        construct_knowledge_capsule(store, comparison_request_id=request_id)


def test_capsule_launch_is_deterministic_private_and_one_shot(tmp_path: Path):
    store, _source_node, request_id, comparison, _note, _references = _capsule_study(
        tmp_path / "data"
    )
    legacy_graph_path = (
        store.session_dir(comparison["session_id"])
        / "graphs"
        / f"{comparison['source_graph_id']}.json"
    )
    legacy_graph = json.loads(legacy_graph_path.read_text(encoding="utf-8"))
    legacy_graph["hidden_reasoning"] = "NEVER_RENDER_THIS_PRIVATE_LEGACY_REASONING"
    legacy_graph_path.write_text(
        json.dumps(legacy_graph, indent=2) + "\n", encoding="utf-8"
    )
    manifest = construct_knowledge_capsule(store, comparison_request_id=request_id)
    session_path = store.session_dir(manifest.session_id) / "session.json"
    mutable_session = json.loads(session_path.read_text(encoding="utf-8"))
    mutable_session["title"] = "a later mutable session title"
    session_path.write_text(json.dumps(mutable_session), encoding="utf-8")

    launch = launch_knowledge_capsule(store, manifest.id)
    markdown_path = store.root / launch.markdown_path
    receipt_path = store.knowledge_capsule_launches_dir / f"{manifest.id}.json"
    markdown = markdown_path.read_text(encoding="utf-8")

    assert oct(markdown_path.stat().st_mode & 0o777) == oct(0o600)
    assert oct(receipt_path.stat().st_mode & 0o777) == oct(0o600)
    assert launch.markdown_sha256 == hashlib.sha256(markdown_path.read_bytes()).hexdigest()
    assert manifest.session_title in markdown
    assert "a later mutable session title" not in markdown
    assert "## Conversation turns" in markdown
    assert "## Public graph generations" in markdown
    assert "#### Thought-objects" in markdown
    assert "#### Typed edges" in markdown
    assert "## Inquiry and intervention history" in markdown
    assert "## Human Field Notes" in markdown
    assert "## Integrity appendix" in markdown
    assert "## Explicit omissions" in markdown
    assert "hidden_reasoning" not in markdown
    assert "NEVER_RENDER_THIS_PRIVATE_LEGACY_REASONING" not in markdown
    assert str(store.root) not in markdown
    assert comparison["source_graph_id"] in markdown
    assert knowledge_capsule_read(store, manifest)["markdown_integrity"] == "verified"
    with pytest.raises(StoreError, match="already launched"):
        launch_knowledge_capsule(store, manifest.id)


def test_capsule_launch_failures_remain_retryable_and_tamper_blocks(tmp_path: Path, monkeypatch):
    store, _source_node, request_id, _comparison, _note, _references = _capsule_study(
        tmp_path / "write-failure"
    )
    manifest = construct_knowledge_capsule(store, comparison_request_id=request_id)
    original_write = store.write_knowledge_capsule_markdown

    def fail_markdown(_capsule_id, _markdown):
        raise OSError("disk full")

    monkeypatch.setattr(store, "write_knowledge_capsule_markdown", fail_markdown)
    with pytest.raises(OSError, match="disk full"):
        launch_knowledge_capsule(store, manifest.id)
    assert not store.knowledge_capsule_export_path(manifest.id).exists()
    assert not store.knowledge_capsule_launch_exists(manifest.id)
    monkeypatch.setattr(store, "write_knowledge_capsule_markdown", original_write)
    assert launch_knowledge_capsule(store, manifest.id).success is True

    recovery, _source, recovery_request, _comparison, _note, _refs = _capsule_study(
        tmp_path / "receipt-failure"
    )
    recovery_manifest = construct_knowledge_capsule(
        recovery, comparison_request_id=recovery_request
    )
    original_receipt = recovery.write_knowledge_capsule_launch

    def fail_receipt(_launch):
        raise OSError("interrupted receipt")

    monkeypatch.setattr(recovery, "write_knowledge_capsule_launch", fail_receipt)
    with pytest.raises(OSError, match="interrupted receipt"):
        launch_knowledge_capsule(recovery, recovery_manifest.id)
    exported = recovery.knowledge_capsule_export_path(recovery_manifest.id).read_bytes()
    assert not recovery.knowledge_capsule_launch_exists(recovery_manifest.id)
    monkeypatch.setattr(recovery, "write_knowledge_capsule_launch", original_receipt)
    recovered = launch_knowledge_capsule(recovery, recovery_manifest.id)
    assert recovery.knowledge_capsule_export_path(recovery_manifest.id).read_bytes() == exported
    assert recovered.success is True

    tampered, _source, tamper_request, _comparison, _note, _refs = _capsule_study(
        tmp_path / "tamper"
    )
    tamper_manifest = construct_knowledge_capsule(
        tampered, comparison_request_id=tamper_request
    )
    graph_artifact = next(item for item in tamper_manifest.artifacts if item.kind == "graph")
    graph_path = tampered.root / graph_artifact.path
    graph_path.write_bytes(graph_path.read_bytes() + b"\n")
    with pytest.raises(StoreError, match="source integrity failed"):
        launch_knowledge_capsule(tampered, tamper_manifest.id)
    assert not tampered.knowledge_capsule_launch_exists(tamper_manifest.id)


def test_capsule_schema_cli_server_and_inhabitation_surfaces(tmp_path: Path):
    store_path = tmp_path / "cli"
    store, source_node, request_id, comparison, _note, _references = _capsule_study(
        store_path
    )
    code, out, err = run(
        ["capsule", "construct", "--comparison", request_id], store=store_path
    )
    assert code == 0, err
    capsule_id = out.strip()
    assert list(store.iter_log_entries())[-1]["op"] == "knowledge_capsule_construct"
    assert "Plural paths" not in json.dumps(list(store.iter_log_entries())[-1])
    code, out, err = run(
        ["capsule", "show", capsule_id, "--format", "json"], store=store_path
    )
    assert code == 0, err
    assert json.loads(out)["state"] == "ready"
    code, out, err = run(
        ["capsule", "list", "--session", comparison["session_id"], "--format", "json"],
        store=store_path,
    )
    assert code == 0, err
    assert json.loads(out)[0]["id"] == capsule_id
    code, out, err = run(["capsule", "launch", capsule_id], store=store_path)
    assert code == 0, err
    assert Path(out.strip()).is_file()
    code, _out, err = run(["validate", capsule_id], store=store_path)
    assert code == 0, err

    server, server_source, server_request, server_comparison, _note, _refs = _capsule_study(
        tmp_path / "server"
    )
    replies = []
    handler = object.__new__(InhabitHandler)
    handler.store = server
    handler._json = lambda status, body: replies.append((status, body))
    handler._read_json = lambda: {"comparison_request_id": server_request}
    handler._knowledge_capsule_construct()
    assert replies[-1][0] == 200
    server_capsule = replies[-1][1]["capsule"]
    assert server_capsule["state"] == "ready"
    handler._knowledge_capsule_launch(server_capsule["id"])
    assert replies[-1][1]["capsule"]["state"] == "launched"
    handler.path = f"/api/inhabit/{server_source.id}?graph={server_comparison['source_graph_id']}"
    handler.do_GET()
    assert replies[-1][1]["knowledge_capsules"][0]["state"] == "launched"
    assert replies[-1][1]["knowledge_capsule_eligibility"] is None

    valid = server.load_knowledge_capsule(server_capsule["id"]).to_dict()
    validate_schema("knowledge-capsule-manifest.schema.json", valid)
    invalid = {**valid, "session_title": ""}
    with pytest.raises(ValidationError):
        validate_schema("knowledge-capsule-manifest.schema.json", invalid)


def test_capsule_assets_and_chamber_contract_are_present():
    dist = Path(__file__).parents[1] / "viz" / "dist"
    html = (dist / "index.html").read_text(encoding="utf-8")
    js = (dist / "space.js").read_text(encoding="utf-8")
    sound = (dist / "sound.js").read_text(encoding="utf-8")
    assert "Knowledge Capsule Earned" in html
    assert "press K to construct" in html
    assert "Launch Capsule" in js
    assert "duration: 18" in js
    assert "/api/knowledge-capsules" in js
    assert "visibleNeuronIndex(group)" in js
    for name in (
        "knowledge-capsule-launcher-earned.ogg",
        "launcher-construction-loop.ogg",
        "launcher-build-complete.ogg",
        "launcher-ready-hum-loop.ogg",
        "charged-capsule-launch.ogg",
    ):
        assert name in sound
        assert (dist / "assets" / "audio" / name).read_bytes().startswith(b"OggS")
    for name in (
        "knowledge-ark-launcher-hologram.glb",
        "knowledge-ark-launcher.glb",
        "knowledge-ark-launcher-post-launch.glb",
        "charged-knowledge-capsule.glb",
    ):
        assert (dist / "assets" / "models" / name).read_bytes().startswith(b"glTF")
