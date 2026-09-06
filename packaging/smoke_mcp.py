"""Exercise an installed/frozen MCP host with synthetic data; no model or app imports.

Usage: python packaging/smoke_mcp.py /absolute/path/to/AtlasOfThreadsMCP.exe
Source: python packaging/smoke_mcp.py /path/to/python -m thought_archaeology.cli
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def smoke(command: list[str], root: Path):
    env = {**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252:strict"}
    base = [*command, "--store", str(root / "Synthetic Café Atlas")]

    def run(args, messages=None):
        process = subprocess.run(
            [*base, *args],
            input=None if messages is None else "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in messages).encode("utf-8"),
            capture_output=True, timeout=60, env=env,
        )
        assert process.returncode == 0, process.stderr.decode("utf-8", errors="replace")
        return process.stdout.decode("utf-8")

    def snapshot():
        return {str(p.relative_to(root)): (p.stat().st_mtime_ns, p.read_bytes()) for p in root.rglob("*") if p.is_file()}

    report = json.loads(run(["mcp", "check"]))
    assert report["connected"] and report["clean_shutdown"]
    assert not report["atlas"]["store"]["ready"] and not snapshot()
    registration = ["mcp", "collaborator", "register", "--name", "Synthetic Café 🌿", "--client-family", "package-smoke"]
    for scope in ("atlas:read", "atlas:write:threadwalk", "atlas:write:path", "atlas:memory:ack"):
        registration += ["--scope", scope]
    collaborator = json.loads(run(registration))["id"]

    def rpc(method, params, version="2025-11-25"):
        replies = [json.loads(line) for line in run(["mcp", "serve", "--collaborator", collaborator], [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": version, "capabilities": {}, "clientInfo": {"name": "synthetic-package-client", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": method, "params": params},
        ]).splitlines()]
        assert len(replies) == 2 and replies[0]["result"]["protocolVersion"] == version
        result = replies[1]["result"]
        assert not result.get("isError"), result
        return result

    def call(name, arguments):
        return rpc("tools/call", {"name": name, "arguments": arguments})["structuredContent"]

    before = snapshot()
    for version in ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"):
        assert len(rpc("tools/list", {}, version)["tools"]) == 10
    assert snapshot() == before
    begin_args = {"seed": "Café garden – 植物 🌿", "seed_origin": "human_instruction", "client_request_id": "synthetic-begin"}
    begin = call("begin_threadwalk", begin_args)
    assert begin["public_context"]["seed"] == begin_args["seed"]
    append_args = begin["response_contract"]["example_arguments"]
    append_args["prose"] = begin_args["seed"]
    append_args["thought_graph"] = {"nodes": [{"local_id": "garden", "kind": "claim", "text": begin_args["seed"]}], "edges": []}
    completion = call("append_agent_path", append_args)
    assert completion["publication"] is False and completion["outbound_harness_queued"] is False
    memory = root / "synthetic-client-memory.json"
    memory.write_text(json.dumps(completion["memory_candidate"], ensure_ascii=False), encoding="utf-8")
    assert json.loads(memory.read_text(encoding="utf-8")) == completion["memory_candidate"]
    ack_args = {"receipt_id": completion["receipt"]["id"], "client_request_id": "synthetic-ack", "external_memory_ref": "synthetic-local-receipt"}
    call("acknowledge_memory_receipt", ack_args)
    before = snapshot()
    assert call("begin_threadwalk", begin_args)["idempotent_replay"]
    replay = call("append_agent_path", append_args)
    assert replay["graph_id"] == completion["graph_id"] and replay["idempotent_replay"]
    assert call("acknowledge_memory_receipt", ack_args)["idempotent_replay"]
    thread = call("read_threadwalk", {"session_id": begin["session_id"]})
    assert thread["head_graph_id"] == completion["graph_id"]
    chamber = call("read_chamber", {"graph_id": completion["graph_id"], "node_id": completion["receipt"]["node_id"]})
    assert chamber["node"]["text"] == begin_args["seed"]
    report = json.loads(run(["mcp", "check", "--collaborator", collaborator]))
    assert report["atlas"]["store"]["session_count"] == 1 and report["atlas"]["store"]["graph_count"] == 2
    assert snapshot() == before
    print("PASS: packaged MCP reads, four protocol versions, Unicode, contribution, memory acknowledgement, fresh-process replays, unchanged read/replay files, and clean EOF shutdown.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Pass the MCP executable and any source-launch arguments.")
    with tempfile.TemporaryDirectory(prefix="atlas-mcp-smoke-") as directory:
        smoke(sys.argv[1:], Path(directory))
