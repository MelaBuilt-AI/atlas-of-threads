"""Manual client configuration and a bounded, read-only stdio connection check."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from thought_archaeology.agent_bridge import AgentBridgeError
from thought_archaeology.store import Store

CLIENTS = ("codex", "claude", "grok", "opencode", "opencode-v2", "prime-agent", "openclaw", "hermes")
CONFIG_PATHS = {
    "codex": "~/.codex/config.toml",
    "claude": ".mcp.json (project scope; review in Claude Code)",
    "grok": "~/.grok/config.toml",
    "opencode": "opencode.json (v1)",
    "opencode-v2": "opencode.json (v2)",
    "prime-agent": "~/.prime/agent/settings.json",
    "openclaw": "~/.openclaw/openclaw.json",
    "hermes": "~/.hermes/config.yaml",
}


def server_command(store: Store, collaborator_id: str | None, executable: str | None = None) -> list[str]:
    if collaborator_id:
        store.load_agent_collaborator(collaborator_id)
    if executable:
        command = [str(Path(executable).expanduser().resolve())]
    elif getattr(sys, "frozen", False):
        binary = Path(sys.executable)
        if sys.platform == "win32":
            binary = binary.with_name("AtlasOfThreadsMCP.exe")
        command = [str(binary)]
    else:
        command = [sys.executable, "-m", "thought_archaeology.cli"]
    command += ["--store", str(store.root.resolve()), "mcp", "serve"]
    if collaborator_id:
        command += ["--collaborator", collaborator_id]
    return command


def client_config(client: str, command: list[str]) -> str:
    """Return a mergeable fragment; never read or rewrite the client's config."""
    server = {"command": command[0], "args": command[1:]}
    name = "atlas-of-threads"
    if client in ("codex", "grok"):
        return (
            f"[mcp_servers.{name}]\n"
            f"command = {json.dumps(command[0])}\n"
            f"args = {json.dumps(command[1:])}\n"
            "startup_timeout_sec = 30\n"
        )
    if client == "hermes":
        return (
            f"mcp_servers:\n  {name}:\n"
            f"    command: {json.dumps(command[0])}\n"
            f"    args: {json.dumps(command[1:])}\n"
        )
    if client in ("opencode", "opencode-v2"):
        timeout = 30000 if client == "opencode" else {"startup": 30000, "catalog": 30000}
        entries = {name: {"type": "local", "command": command, "timeout": timeout}}
        config = {"mcp": entries if client == "opencode" else {"servers": entries}}
    elif client == "openclaw":
        config = {"mcp": {"servers": {name: {**server, "transport": "stdio", "connectionTimeoutMs": 30000}}}}
    elif client in ("claude", "prime-agent"):
        config = {"mcpServers": {name: {"type": "stdio", **server}}}
        if client == "prime-agent":
            config["mcpServers"][name]["startupTimeoutMs"] = 30000
    else:
        raise AgentBridgeError(f"unknown MCP client: {client}")
    return json.dumps(config, indent=2) + "\n"


def check_connection(command: list[str]) -> dict:
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "atlas-connection-check", "version": "1"},
        }},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "atlas_status", "arguments": {}}},
    ]
    try:
        process = subprocess.run(
            command, input="".join(json.dumps(item) + "\n" for item in messages).encode("utf-8"),
            capture_output=True, timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise AgentBridgeError("MCP connection timed out after 30 seconds") from exc
    if process.returncode:
        raise AgentBridgeError(f"MCP process exited {process.returncode}: " + process.stderr.decode("utf-8", errors="replace")[-2000:])
    try:
        replies = {item["id"]: item for line in process.stdout.decode("utf-8").splitlines() if (item := json.loads(line)).get("id") is not None}
        for request_id in (1, 2, 3):
            if "error" in replies[request_id] or replies[request_id]["result"].get("isError"):
                raise ValueError(f"MCP request {request_id} failed: {replies[request_id]}")
        status = replies[3]["result"]["structuredContent"]
        if status["product"] != "Atlas of Threads":
            raise ValueError("the command did not connect to Atlas")
        return {
            "connected": True, "protocol_version": replies[1]["result"]["protocolVersion"],
            "tools": [tool["name"] for tool in replies[2]["result"]["tools"]],
            "atlas": status, "clean_shutdown": True,
        }
    except (UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise AgentBridgeError(f"Invalid Atlas MCP response: {exc}") from exc
