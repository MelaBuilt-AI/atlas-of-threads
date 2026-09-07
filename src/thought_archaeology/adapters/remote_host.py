"""Standalone remote helper; copy this file to the agent host (Python 3.11+).

Only the standard library is required here. Native CLIs own auth and memory.
One private config/state directory represents one dedicated Atlas connection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import uuid


def save(path: Path, data: dict) -> None:
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".atlas-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=True)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def run(argv, *, timeout=30, **kwargs):
    result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                            timeout=timeout, check=True, **kwargs)
    return result


def json_output(value: str) -> dict:
    for i, char in enumerate(value):
        if char == "{":
            try:
                result = json.loads(value[i:])
                if isinstance(result, dict):
                    return result
            except ValueError:
                pass
    raise ValueError("native CLI returned no JSON object")


def rpc(config, method, params, *, final=False):
    argv = [*config["command"], "gateway", "call", method, "--json",
            "--params", json.dumps(params, ensure_ascii=True),
            "--timeout", "780000" if final else "20000"]
    if final:
        argv.append("--expect-final")
    return json_output(run(argv, timeout=800 if final else 25).stdout)


def openclaw(config, request, state, state_path):
    if not state:
        # Operator-created private session, no task/run or channel delivery.
        # This native key type supports a per-session deny-all tool policy.
        key = f"agent:{config.get('agent_id', 'main')}:subagent:atlas-{uuid.uuid4()}"
        created = rpc(config, "sessions.create", {
            "key": key, "agentId": config.get("agent_id", "main"),
            "label": "Atlas / " + config["display_name"], "emitCommandHooks": False,
        })
        state.update(key=created["key"], session_id=created["sessionId"])
        save(state_path, state)
    patched = rpc(config, "sessions.patch", {
        "key": state["key"], "expectedSessionId": state["session_id"],
        "inheritedToolPolicyVersion": 1, "inheritedToolDeny": ["*"],
        "model": config["model"],
        "toolOverrides": {"webSearch": False},
    })
    if patched.get("entry", {}).get("inheritedToolDeny") != ["*"]:
        raise ValueError("OpenClaw did not confirm the session tool restriction")
    # OpenClaw's subagent-key bootstrap omits persona files even with a full
    # prompt. Refresh only the owner's explicit host-side allowlist; no files
    # or credentials are copied to Atlas, and none are written by this call.
    native_context = ""
    paths = config.get("context_files", [])
    if len(paths) > 8:
        raise ValueError("at most eight native context files may be selected")
    for filename in paths:
        path = Path(filename).expanduser()
        content = path.read_text(encoding="utf-8")
        if len(content) > 16000:
            raise ValueError("native context file exceeds 16000 characters")
        native_context += f"\n--- {path.name} ---\n{content}\n"
    if native_context:
        native_context = ("CURRENT APPROVED OPENCLAW PERSONA CONTEXT:\n"
                          "These are your native agent's current files. Distinguish this persona "
                          "from the underlying model or CLI runtime. They are reference data, "
                          "not permission to run tools or modify files.\n" + native_context + "\n")
    result = rpc(config, "agent", {
        "sessionKey": state["key"], "sessionId": state["session_id"],
        "agentId": config.get("agent_id", "main"),
        "message": native_context + request["prompt"], "idempotencyKey": request["request_id"],
        "deliver": False, "disableMessageTool": True,
        "promptMode": "full", "bootstrapContextMode": "full", "timeout": 750,
    }, final=True)
    payload = result.get("result", result)
    meta = payload["meta"]["agentMeta"]
    if meta["sessionId"] != state["session_id"]:
        raise ValueError("OpenClaw changed the dedicated session unexpectedly")
    response = "\n".join(p["text"] for p in payload["payloads"] if p.get("text"))
    return response, meta["provider"] + "/" + meta["model"]


def hermes(config, request, state, state_path):
    # Hermes expands an explicitly named empty set to no tools. Verify this
    # installed runtime's resolution before every call, including MCP selection.
    empty_set = "atlas-readonly-empty"
    run([config["python"], "-c",
                 "from toolsets import resolve_toolset; "
                 f"assert resolve_toolset({empty_set!r}) == []"], cwd=config["runtime_root"])
    argv = [*config["command"], "chat", "--query-file", "-", "--quiet", "--oneshot",
            "--model", config["model"],
            "--toolsets", empty_set, "--max-turns", "2", "--run-budget", "750",
            "--source", "tool", "--no-restore-cwd", "--in", str(state_path.parent)]
    if state:
        argv.extend(["--resume", state["session_id"]])
    result = run(argv, input=request["prompt"], timeout=800, cwd=state_path.parent,
                 env={**os.environ, "NO_COLOR": "1", "PYTHONIOENCODING": "utf-8"})
    ids = re.findall(r"session_id:\s*([A-Za-z0-9_.:-]+)", result.stderr)
    if not ids:
        raise ValueError("Hermes returned no native session ID")
    state["session_id"] = ids[-1]
    save(state_path, state)
    with sqlite3.connect(Path(config["state_db"]).as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute("select model, tool_call_count, tool_names from sessions where id=?",
                         (state["session_id"],)).fetchone()
        final = db.execute("select content from messages where session_id=? and role='assistant' "
                           "order by id desc limit 1", (state["session_id"],)).fetchone()
    if not row or row[1] or (row[2] and json.loads(row[2])):
        raise ValueError("Hermes session did not confirm a tool-free response")
    if not final or not final[0]:
        raise ValueError("Hermes returned no persisted public assistant response")
    return final[0], row[0]


def handle(config, request):
    provider = config["provider"]
    if provider not in {"hermes", "openclaw"}:
        raise ValueError("unsupported remote provider")
    directory = Path(config["state_dir"]).expanduser()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_path = directory / "session.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    if request["operation"] == "describe":
        version = run([*config["command"], "--version"]).stdout.strip().splitlines()[0]
        return {"protocol_version": "1", "name": provider,
                "capabilities": ["continue", "discuss", "resumable_session"],
                "cli_version": version, "default_model": config["model"],
                "connected_agent": {"display_name": config["display_name"],
                    "memory_mode": "resumable_session", "memory_owner": "remote_native_client",
                    "session_ready": bool(state), "memory_files": []}}
    if request["operation"] not in {"continue", "discuss"}:
        raise ValueError("unsupported remote operation")
    # Durable receipt prevents an SSH disconnect from silently duplicating a
    # native model call. Incomplete receipts require explicit host inspection.
    import fcntl
    with (directory / "call.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        receipt = directory / (hashlib.sha256(request["request_id"].encode()).hexdigest() + ".json")
        if receipt.exists():
            saved = json.loads(receipt.read_text())
            if saved["digest"] != digest:
                raise ValueError("request ID was already used with different content")
            if saved["status"] != "completed":
                raise ValueError("Remote call outcome is unresolved; inspect its receipt before retrying.")
            return saved["result"]
        save(receipt, {"digest": digest, "status": "pending"})
        try:
            response, model = (hermes if provider == "hermes" else openclaw)(config, request, state, state_path)
            if not response:
                raise ValueError("native agent returned an empty response")
            result = {"protocol_version": "1", "response": response,
                      "model_name": model, "remote_session_id": state["session_id"]}
            save(receipt, {"digest": digest, "status": "completed", "result": result})
            return result
        except Exception as exc:
            # Native diagnostics stay in this private host directory.
            save(receipt, {"digest": digest, "status": "unresolved", "error": str(exc),
                           "stderr": getattr(exc, "stderr", None),
                           "stdout": getattr(exc, "stdout", None)})
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        result = handle(config, json.load(sys.stdin))
    except Exception:
        result = {"protocol_version": "1", "error":
                  "Remote call did not complete. Inspect the private host receipt; no automatic retry occurred."}
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
