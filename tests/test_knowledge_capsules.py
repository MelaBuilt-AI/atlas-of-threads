from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from thought_archaeology.continuation import (
    continuation_completion,
    continuation_request,
    parallel_comparison,
)
from thought_archaeology.field_notes import (
    create_field_note,
    edit_field_note,
    field_note_eligibility,
)
from thought_archaeology.ids import new_ulid
from thought_archaeology.knowledge_capsules import (
    active_stored_launcher,
    capsule_artifact_bytes,
    capsule_integrity,
    construct_knowledge_capsule,
    knowledge_capsule_eligibility,
    knowledge_capsule_read,
    launch_knowledge_capsule,
    store_knowledge_capsule_launcher,
)
from thought_archaeology.schema import ValidationError, validate_schema
from thought_archaeology.serve import InhabitHandler
from thought_archaeology.store import Store, StoreError

from tests.test_cli import run
from tests.test_continuation import _compiled, _parallel_study


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


def _single_path_study(path: Path):
    session_id, source_graph_id = _compiled(path)
    store = Store(path)
    source = store.load_graph(source_graph_id)
    source_node = source.nodes[0]
    request = continuation_request(
        source,
        source_node,
        prompt="Follow this question with one collaborator.",
        source="inhabit_space",
    )
    store.write_continuation_request(request)
    child = replace(
        source,
        id=new_ulid(),
        turn_id=new_ulid(),
        parent_graph_id=source.id,
        hidden_reasoning=None,
    )
    store.write_graph(child)
    store.write_continuation_completion(
        continuation_completion(request.id, child.id, "codex")
    )
    return store, session_id, source, source_node, child


def test_single_path_launcher_can_be_stored_and_deployed_only_in_its_threadwalk(
    tmp_path: Path, monkeypatch,
):
    store, session_id, source, source_node, child = _single_path_study(
        tmp_path / "single"
    )
    earning_node = child.nodes[0]
    field_eligibility = field_note_eligibility(
        store, graph_id=child.id, node_id=earning_node.id
    )
    assert field_eligibility["mode"] == "single_path"
    assert field_eligibility["completed_count"] == 1

    note = create_field_note(
        store,
        kind="conclusion",
        text="This one collaborator path reached a milestone worth preserving later.",
        references=((session_id, child.id, earning_node.id),),
        source_graph_id=child.id,
        source_node_id=earning_node.id,
    )
    eligibility = knowledge_capsule_eligibility(
        store, graph_id=child.id, node_id=earning_node.id
    )
    assert eligibility["mode"] == "single_path"
    assert eligibility["comparison_request_id"] is None

    launcher = store_knowledge_capsule_launcher(
        store,
        graph_id=child.id,
        node_id=earning_node.id,
        field_note_id=note.id,
    )
    assert active_stored_launcher(store) == launcher
    assert knowledge_capsule_eligibility(
        store, graph_id=child.id, node_id=earning_node.id
    ) is None
    assert oct(
        (store.knowledge_capsule_launchers_dir / f"{launcher.id}.json").stat().st_mode
        & 0o777
    ) == oct(0o600)

    other_store, _other_session, other_source, other_node, _other_child = (
        _single_path_study(tmp_path / "single")
    )
    assert other_store.root == store.root
    with pytest.raises(StoreError, match="earning Threadwalk"):
        construct_knowledge_capsule(
            store,
            stored_launcher_id=launcher.id,
            graph_id=other_source.id,
            node_id=other_node.id,
        )
    assert active_stored_launcher(store) == launcher

    original_manifest_write = store.write_knowledge_capsule

    def fail_manifest_write(_manifest):
        raise OSError("disk full before manifest publish")

    monkeypatch.setattr(store, "write_knowledge_capsule", fail_manifest_write)
    with pytest.raises(OSError, match="disk full"):
        construct_knowledge_capsule(
            store,
            stored_launcher_id=launcher.id,
            graph_id=source.id,
            node_id=source_node.id,
        )
    assert active_stored_launcher(store) == launcher
    monkeypatch.setattr(store, "write_knowledge_capsule", original_manifest_write)

    manifest = construct_knowledge_capsule(
        store,
        stored_launcher_id=launcher.id,
        graph_id=source.id,
        node_id=source_node.id,
    )
    assert manifest.session_id == session_id
    assert manifest.source_graph_id == source.id
    assert manifest.source_node_id == source_node.id
    assert manifest.earning_graph_id == child.id
    assert manifest.earning_node_id == earning_node.id
    assert manifest.stored_launcher_id == launcher.id
    assert manifest.comparison_request_id is None
    assert "knowledge_capsule_launcher" in {item.kind for item in manifest.artifacts}
    assert active_stored_launcher(store) is None
    with pytest.raises(StoreError, match="not available"):
        construct_knowledge_capsule(
            store,
            stored_launcher_id=launcher.id,
            graph_id=source.id,
            node_id=source_node.id,
        )


def test_stored_launcher_server_surface_persists_and_deploys(tmp_path: Path):
    store, session_id, source, source_node, child = _single_path_study(
        tmp_path / "server-launcher"
    )
    earning_node = child.nodes[0]
    note = create_field_note(
        store,
        kind="observation",
        text="Store this milestone until a later chamber makes the boundary useful.",
        references=((session_id, child.id, earning_node.id),),
        source_graph_id=child.id,
        source_node_id=earning_node.id,
    )
    replies = []
    handler = object.__new__(InhabitHandler)
    handler.store = store
    handler._json = lambda status, body: replies.append((status, body))
    handler._read_json = lambda: {
        "graph_id": child.id,
        "node_id": earning_node.id,
        "field_note_id": note.id,
    }
    handler._knowledge_capsule_launcher_store()
    launcher = replies[-1][1]["launcher"]
    assert replies[-1][0] == 200
    assert launcher["available_here"] is True

    handler.path = f"/api/inhabit/{source_node.id}?graph={source.id}"
    handler.do_GET()
    assert replies[-1][1]["stored_knowledge_capsule_launcher"]["id"] == launcher["id"]
    handler._read_json = lambda: {
        "stored_launcher_id": launcher["id"],
        "graph_id": source.id,
        "node_id": source_node.id,
    }
    handler._knowledge_capsule_construct()
    assert replies[-1][0] == 200
    assert replies[-1][1]["capsule"]["source_graph_id"] == source.id
    assert replies[-1][1]["capsule"]["earning_graph_id"] == child.id
    assert active_stored_launcher(store) is None


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
    assert "K · construct here" in html
    assert "J · store launcher" in html
    assert "Stored Launcher ×1" in html
    assert "Press Enter to Launch Capsule" in html
    assert "Launch Capsule" in js
    assert "duration: 18" in js
    assert "/api/knowledge-capsules" in js
    assert "/api/knowledge-capsule-launcher/store" in js
    assert "visibleNeuronIndex(group)" in js
    assert "readyCapsuleTarget" in js
    assert "launchReadyCapsule" in js
    assert "!capsuleConstruction && !readyCapsuleTarget()" in js
    assert "addCapsuleConstructionEffects" in js
    assert "beginCapsuleCompletionBurst" in js
    assert "const count = 156" in js
    assert "smokeTrail" in js
    assert "setFromUnitVectors(flight.upAxis, flight.tangent)" in js
    assert "outerFlame" in js
    assert "exhaustLight" in js
    assert "function capsuleSlot(occupied)" in js
    assert "occupiedSlots.push(arrivalSlot(index))" in js
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
