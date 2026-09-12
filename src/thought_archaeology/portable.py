"""Reviewed inquiry snapshots, stored separately from the recipient's own graphs."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from thought_archaeology.ids import is_ulid, new_ulid
from thought_archaeology.inhabit import entry_node
from thought_archaeology.models import SCHEMA_VERSION, Session, ThoughtGraph, Turn
from thought_archaeology.schema import validate_graph, validate_schema
from thought_archaeology.store import Store, StoreError, _mkdir, _write_json

MAX_BYTES = 8 * 1024 * 1024
MAX_GRAPHS = 256
FORMAT = "atlas-inquiry"
GRAPH_FIELDS = {"schema_version", "id", "session_id", "turn_id", "created_at", "prose",
                "nodes", "edges", "model", "parent_graph_id", "fork", "metadata"}
EXCLUDED = ["Agent conversations and memory", "Unattached conversation turns",
            "Field Notes and Knowledge Capsules", "Local evidence files and executable assets",
            "Hidden reasoning, private graph metadata, settings and credentials"]


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _origin(store: Store) -> str:
    path = store.root / "portable-origin.json"
    store._require()
    try:
        with path.open("x", encoding="utf-8") as stream:
            os.chmod(path, 0o600)
            json.dump({"id": new_ulid()}, stream)
    except FileExistsError:
        pass
    origin = json.loads(path.read_text(encoding="utf-8"))["id"]
    if not is_ulid(origin):
        raise StoreError("Invalid local publication identity")
    return origin


def _public_url(ref: str) -> bool:
    try:
        parsed = urlsplit(ref)
        return parsed.scheme in {"https", "http"} and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def project_graph(graph: ThoughtGraph) -> dict:
    public = graph.to_dict()
    public.pop("hidden_reasoning", None)
    public["metadata"] = {"workspace_origin": True} if graph.metadata.get("workspace_origin") else {}
    for node in public["nodes"]:
        node.pop("probe_ids", None)
        node.pop("sensor_ids", None)
    return public


def export_inquiry(store: Store, session_id: str, *, author: str, description: str = "") -> dict:
    """Project one selected Threadwalk; never scan/copy its enclosing directory."""
    if not is_ulid(session_id):
        raise StoreError("Choose a Threadwalk")
    if not isinstance(author, str) or not 1 <= len(author.strip()) <= 120:
        raise StoreError("Enter a sharing name of up to 120 characters")
    if not isinstance(description, str) or len(description) > 2000:
        raise StoreError("Description must be at most 2,000 characters")
    session = store.load_session(session_id)
    graphs = sorted(store.iter_graphs(session_id), key=lambda g: (g.created_at, g.id))
    if not graphs or len(graphs) > MAX_GRAPHS:
        raise StoreError(f"Choose a Threadwalk with 1–{MAX_GRAPHS} answers")
    turns = {t.id: t for t in store.iter_turns(session_id)}
    sources = {}
    for completion in store.iter_continuation_completions():
        if completion.graph_id not in {g.id for g in graphs}:
            continue
        request = store.load_continuation_request(completion.request_id)
        sources[completion.graph_id] = {"graph_id": request.graph_id, "node_id": request.node_id,
                                        "question": request.prompt,
                                        "author": completion.agent_name or completion.harness}
    records = []
    for graph in graphs:
        bridge = graph.metadata.get("agent_bridge", {})
        if bridge.get("source_graph_id") and bridge.get("source_node_id"):
            sources[graph.id] = {"graph_id": bridge["source_graph_id"],
                "node_id": bridge["source_node_id"], "question": bridge.get("question", ""),
                "author": bridge.get("harness") or bridge.get("client_family") or "Agent"}
        public = project_graph(graph)
        turn = turns.get(graph.turn_id)
        records.append({"graph": public, "source_sha256": store.graph_sha256(graph.id),
                        "shared_sha256": digest(public), "role": turn.role if turn else "assistant",
                        "source": sources.get(graph.id)})
    evidence = []
    omitted_evidence = 0
    graph_ids = {g.id for g in graphs}
    for binding in store.iter_evidence(session_id):
        refs = binding.get("artifact_refs", [])
        if binding["graph_id"] in graph_ids and refs and all(_public_url(ref) for ref in refs):
            public = {k: binding[k] for k in ("schema_version", "id", "graph_id", "node_id", "kind",
                      "result", "summary", "artifact_refs", "created_at")}
            evidence.append(public)
        else:
            omitted_evidence += 1
    content = {"origin_id": _origin(store), "author": author.strip(), "description": description.strip(),
               "session": {"id": session.id, "title": session.title, "created_at": session.created_at,
                           "updated_at": session.updated_at, "head_graph_id": session.head_graph_id},
               "graphs": records, "evidence": sorted(evidence, key=lambda e: e["id"]),
               "omitted_evidence_count": omitted_evidence}
    bundle = {"format": FORMAT, "version": 1, "id": digest(content), "content": content}
    validate_bundle(bundle)
    return bundle


def read_bundle(path: Path) -> dict:
    if path.stat().st_size > MAX_BYTES:
        raise StoreError("Inquiry file exceeds 8 MiB")
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise StoreError("Choose a valid Atlas inquiry JSON file") from exc
    validate_bundle(bundle)
    return bundle


def validate_bundle(bundle: dict) -> None:
    """External data boundary: schema, hashes, closed references, bounded content."""
    try:
        size = len(canonical(bundle))
    except (ValueError, RecursionError) as exc:
        raise StoreError("Inquiry must contain ordinary JSON values") from exc
    if size > MAX_BYTES:
        raise StoreError("Inquiry file exceeds 8 MiB")
    validate_schema("portable-inquiry.schema.json", bundle)
    content = bundle["content"]
    if digest(content) != bundle["id"]:
        raise StoreError("Inquiry checksum does not match its contents")
    session_id = content["session"]["id"]
    graphs = {}
    turn_ids = set()
    for record in content["graphs"]:
        graph = record["graph"]
        validate_graph(graph)
        if set(graph) - GRAPH_FIELDS or set(graph.get("metadata", {})) - {"workspace_origin"}:
            raise StoreError("Inquiry contains unsupported private graph fields")
        if graph.get("metadata", {}).get("workspace_origin", True) is not True:
            raise StoreError("Invalid inquiry opening marker")
        if any("probe_ids" in n or "sensor_ids" in n for n in graph["nodes"]):
            raise StoreError("Inquiry contains unshared sensor references")
        if graph["session_id"] != session_id or not graph["nodes"]:
            raise StoreError("Inquiry graph has an invalid session or no thoughts")
        if digest(graph) != record["shared_sha256"]:
            raise StoreError("Shared graph checksum does not match")
        if graph["id"] in graphs or graph["turn_id"] in turn_ids:
            raise StoreError("Inquiry repeats a graph or turn identity")
        graphs[graph["id"]] = graph
        turn_ids.add(graph["turn_id"])
    if content["session"]["head_graph_id"] not in graphs:
        raise StoreError("Inquiry head is missing")
    for graph in graphs.values():
        fork = graph.get("fork")
        if fork:
            source = graphs.get(fork["from_graph_id"])
            if not source or fork["from_node_id"] not in {n["id"] for n in source["nodes"]}:
                raise StoreError("Fork source refers outside this inquiry")
            if fork.get("discarded_graph_id") and fork["discarded_graph_id"] not in graphs:
                raise StoreError("Discarded fork graph is missing")
        seen = {graph["id"]}
        parent = graph.get("parent_graph_id")
        while parent:
            if parent not in graphs or parent in seen:
                raise StoreError("Inquiry ancestry is incomplete or cyclic")
            seen.add(parent)
            parent = graphs[parent].get("parent_graph_id")
    for record in content["graphs"]:
        source = record["source"]
        if source:
            graph = graphs.get(source["graph_id"])
            if not graph or source["node_id"] not in {n["id"] for n in graph["nodes"]}:
                raise StoreError("Continuation source refers outside this inquiry")
    evidence_ids = set()
    for binding in content["evidence"]:
        validate_schema("evidence-binding.schema.json", binding)
        graph = graphs.get(binding["graph_id"])
        if not graph or binding["node_id"] not in {n["id"] for n in graph["nodes"]}:
            raise StoreError("Evidence refers outside this inquiry")
        if binding["id"] in evidence_ids or not binding["artifact_refs"] or not all(_public_url(r) for r in binding["artifact_refs"]):
            raise StoreError("Evidence must have a unique identity and public web references")
        evidence_ids.add(binding["id"])


def summary(bundle: dict) -> dict:
    content = bundle["content"]
    first = content["graphs"][0]["graph"]
    # Prefer the first authored answer over a bare opening question.
    first = next((r["graph"] for r in content["graphs"] if r["role"] == "assistant"), first)
    spawn_node = entry_node(ThoughtGraph.from_dict(first))
    return {"id": bundle["id"], "title": content["session"]["title"], "author": content["author"],
            "description": content["description"], "origin_id": content["origin_id"],
            "session_id": content["session"]["id"], "graph_count": len(content["graphs"]),
            "thought_count": sum(len(r["graph"]["nodes"]) for r in content["graphs"]),
            "evidence_count": len(content["evidence"]), "omitted_evidence_count": content["omitted_evidence_count"],
            "excluded": EXCLUDED, "spawn": {"graph_id": first["id"], "node_id": spawn_node.id},
            "url": f"/inquiries/{bundle['id']}/#/g/{first['id']}/n/{spawn_node.id}"}


def arrivals(bundle: dict, graph_id: str) -> list[dict]:
    """Existing chamber-door presentation, authored from reviewed source references."""
    result = []
    for record in bundle["content"]["graphs"]:
        graph, source = record["graph"], record["source"]
        if source and source["graph_id"] == graph_id and graph["id"] != graph_id:
            node = entry_node(ThoughtGraph.from_dict(graph)).to_dict()
            result.append({"sessionId": graph["session_id"], "graphId": graph["id"],
                "nodeId": node["id"], "anchorGraphId": graph_id, "kind": node["kind"],
                "text": node["text"], "title": source["question"] or "Shared continuation",
                "harness": source["author"], "modelName": graph["model"]["name"], "seen": True})
    return result


def inquiry_path(store: Store, inquiry_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{64}", inquiry_id):
        raise StoreError("Invalid inquiry identity")
    return store.root / "imported-inquiries" / inquiry_id


def imported_inquiry(store: Store, inquiry_id: str) -> tuple[dict, Store]:
    path = inquiry_path(store, inquiry_id)
    bundle = read_bundle(path / "inquiry.json")
    return bundle, Store(path / "data")


def list_inquiries(store: Store) -> list[dict]:
    root = store.root / "imported-inquiries"
    return [summary(read_bundle(p / "inquiry.json")) for p in sorted(root.glob("[a-f0-9]" * 64))
            if p.is_dir()]


def import_inquiry(store: Store, bundle: dict) -> dict:
    validate_bundle(bundle)
    store._require()
    destination = inquiry_path(store, bundle["id"])
    _mkdir(destination.parent)
    if destination.exists():
        existing, _ = imported_inquiry(store, bundle["id"])
        if existing != bundle:
            raise StoreError("An inquiry with this identity has different contents")
        return {**summary(bundle), "already_imported": True}
    staging = Path(tempfile.mkdtemp(prefix=".import-", dir=destination.parent))
    try:
        content = bundle["content"]
        imported = Store(staging / "data")
        imported.initialize()
        session = content["session"]
        graphs = {r["graph"]["id"]: ThoughtGraph.from_dict(r["graph"]) for r in content["graphs"]}
        head = graphs[session["head_graph_id"]]
        sdir = imported.session_dir(session["id"])
        _mkdir(sdir / "graphs")
        _write_json(sdir / "session.json", Session(SCHEMA_VERSION, session["id"], session["title"],
                    session["created_at"], session["updated_at"], origin=f"imported:{content['origin_id']}",
                    head_graph_id=head.id, head_turn_id=head.turn_id).to_dict())
        (sdir / "turns.jsonl").touch(mode=0o600)
        for seq, record in enumerate(content["graphs"]):
            graph = graphs[record["graph"]["id"]]
            imported.write_graph(graph)
            parent = graphs.get(graph.parent_graph_id)
            imported.append_turn(Turn(SCHEMA_VERSION, graph.turn_id, session["id"], seq, record["role"],
                                     graph.created_at, graph.prose, graph.id,
                                     parent.turn_id if parent else None, None, graph.model.provider))
        for binding in content["evidence"]:
            imported.write_evidence(session["id"], binding)
        errors = imported.validate_session(session["id"])
        if errors:
            raise StoreError("Invalid imported inquiry: " + "; ".join(errors))
        _write_json(staging / "inquiry.json", bundle)
        try:
            staging.rename(destination)
        except OSError:
            if not destination.exists():
                raise
            existing, _ = imported_inquiry(store, bundle["id"])
            if existing != bundle:
                raise StoreError("Concurrent inquiry import has different contents")
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {**summary(bundle), "already_imported": False}
