"""Private prose discussions, independent of canonical graph/turn lineage."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from thought_archaeology.harness import (
    HARNESS_PROTOCOL_VERSION, HarnessError, HarnessRegistry, _adapter_call,
    describe_harness,
)
from thought_archaeology.ids import now_iso
from thought_archaeology.inhabit import inhabit
from thought_archaeology.store import Store, _mkdir, _write_private_json_atomic

_lock = threading.RLock()
_running: set[tuple[str, str]] = set()


def guide_payload(registry: HarnessRegistry | None = None) -> dict | None:
    registry = registry or HarnessRegistry()
    name = registry.guide_name()
    if not name:
        return None
    spec = registry.get(name)
    return {"name": name, "display_name": spec.agent_name or name,
            "model": spec.model, "memory_mode": spec.memory_mode}


def assign_roles(store: Store, body: dict) -> None:
    registry = HarnessRegistry()
    name = body.get("harness")
    if not isinstance(name, str):
        raise HarnessError("Choose a registered agent first.")
    if not isinstance(body.get("collaborator"), bool) or not isinstance(body.get("guide"), bool):
        raise HarnessError("Choose the collaborator and guide roles explicitly.")
    if list(store.iter_continuation_requests(pending=True)):
        raise HarnessError("Finish the pending collaborator response before changing roles.")
    with _lock:
        if any(root == str(store.root) for root, _ in _running):
            raise HarnessError("Finish the guide response before changing roles.")
        if body["guide"]:
            description = describe_harness(registry.get(name), timeout=30)
            if "discuss" not in description.get("capabilities", []):
                raise HarnessError("This adapter does not support guide discussion yet. OpenCode supports it.")
            registry.record_model(name, description["default_model"], cli_version=description.get("cli_version"))
        registry.set_agent_roles(name, collaborator=body["collaborator"], guide=body["guide"])


def _path(store: Store, name: str) -> Path:
    # name is resolved through the validated harness registry, never a raw path.
    return store.root / "guide-discussions" / (name + ".json")


def _read(store: Store, name: str) -> dict:
    path = _path(store, name)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"turns": []}
    for turn in data["turns"]:
        if turn["status"] == "pending" and (str(store.root), turn["id"]) not in _running:
            turn["status"] = "interrupted"
            turn["error"] = "Atlas stopped before this response finished. Send again to retry."
    return data


def discussion_payload(store: Store) -> dict:
    with _lock:
        guide = guide_payload()
        return {"guide": guide, "turns": _read(store, guide["name"])["turns"] if guide else []}


def clear_discussion(store: Store) -> None:
    with _lock:
        guide = guide_payload()
        if not guide:
            return
        if any(root == str(store.root) for root, _ in _running):
            raise HarnessError("Wait for the guide response before clearing the discussion.")
        path = _path(store, guide["name"])
        if path.exists():
            _write_private_json_atomic(path, {"turns": []})


def begin_discussion(store: Store, body: dict) -> dict:
    prompt = body.get("prompt")
    request_id = body.get("request_id")
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 8000:
        raise HarnessError("Write a question of up to 8,000 characters.")
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 80:
        raise HarnessError("A request ID is required.")
    registry = HarnessRegistry()
    guide = guide_payload(registry)
    if not guide:
        raise HarnessError("Set up an agent as guide first.")
    spec = registry.get(guide["name"])
    graph = store.load_graph(str(body.get("graph_id") or ""))
    standing = inhabit(store, str(body.get("node_id") or ""), graph_id=graph.id).to_dict()
    source = {"session_id": graph.session_id, "graph_id": graph.id,
              "node_id": standing["node"]["id"], "text": standing["node"]["text"]}
    with _lock:
        data = _read(store, spec.name)
        for turn in data["turns"]:
            if turn["id"] == request_id:
                if turn["prompt"] != prompt.strip() or turn["source"] != source:
                    raise HarnessError("This request ID belongs to a different question.")
                return turn
        if any(root == str(store.root) for root, _ in _running):
            raise HarnessError("Your guide is still responding.")
        public_graph = graph.to_dict()
        public_graph.pop("hidden_reasoning", None)
        envelope = {"protocol_version": HARNESS_PROTOCOL_VERSION, "operation": "discuss",
                    "request": {"id": request_id, "prompt": prompt.strip()},
                    "session": store.load_session(graph.session_id).to_dict(),
                    "graph": public_graph, "standing": standing,
                    "discussion": [{"prompt": t["prompt"], "response": t.get("response"),
                                    "source": t["source"]}
                                   for t in data["turns"][-12:] if t["status"] == "completed"]}
        turn = {"id": request_id, "created_at": now_iso(), "prompt": prompt.strip(),
                "source": source, "agent": guide, "status": "pending"}
        data["turns"].append(turn)
        path = _path(store, spec.name)
        _mkdir(path.parent)
        _write_private_json_atomic(path, data)
        _running.add((str(store.root), request_id))
        threading.Thread(target=_respond, args=(store, spec, envelope), daemon=True).start()
        return turn


def _respond(store, spec, envelope):
    request_id = envelope["request"]["id"]
    try:
        result = _adapter_call(spec, "discuss", envelope, timeout=360)
        response, model = result.get("response"), result.get("model_name")
        if not isinstance(response, str) or not response.strip() or len(response) > 64_000 or not isinstance(model, str) or not model.strip():
            raise HarnessError("Guide returned an invalid prose response.")
        update = {"status": "completed", "response": response, "model": model,
                  "completed_at": now_iso()}
    except Exception:
        update = {"status": "failed", "error": "The guide could not finish. Check the agent connection and try again; it may be busy with a collaborator response."}
    with _lock:
        try:
            data = _read(store, spec.name)
            next(t for t in data["turns"] if t["id"] == request_id).update(update)
            _write_private_json_atomic(_path(store, spec.name), data)
        finally:
            _running.discard((str(store.root), request_id))
