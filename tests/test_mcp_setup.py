from __future__ import annotations

import json
from pathlib import Path
import sys
import tomllib

import pytest
from jsonschema import Draft202012Validator

from thought_archaeology.agent_bridge import register_collaborator
from thought_archaeology.mcp_setup import CLIENTS, client_config, check_connection, server_command
from thought_archaeology.store import Store
from tests.test_cli import run
from tests.test_mcp_server import _bridge, _initialize, _store_snapshot


@pytest.mark.parametrize("client", CLIENTS)
def test_configs_preserve_command_arguments_and_special_paths(client):
    command = [r"C:\Apps\Atlas of Threads\AtlasOfThreadsMCP.exe", "--store", r"C:\Users\Synthetic\Café $atlas's data", "mcp", "serve"]
    text = client_config(client, command)
    if client in ("codex", "grok"):
        server = tomllib.loads(text)["mcp_servers"]["atlas-of-threads"]
    elif client == "hermes":
        # These YAML scalar/array values intentionally use JSON's shared grammar.
        lines = text.splitlines()
        server = {"command": json.loads(lines[2].split(": ", 1)[1]), "args": json.loads(lines[3].split(": ", 1)[1])}
    else:
        config = json.loads(text)
        if client in ("opencode-v2", "openclaw"):
            server = config["mcp"]["servers"]["atlas-of-threads"]
        elif client == "opencode":
            server = config["mcp"]["atlas-of-threads"]
        else:
            server = config["mcpServers"]["atlas-of-threads"]
    actual = server["command"] if client.startswith("opencode") else [server["command"], *server["args"]]
    assert actual == command


def test_config_and_check_do_not_create_or_mutate_store(tmp_path):
    root = tmp_path / "absent"
    code, out, err = run(["mcp", "config", "--client", "claude"], store=root)
    assert code == 0, err
    server = json.loads(out)["mcpServers"]["atlas-of-threads"]
    report = check_connection([server["command"], *server["args"]])
    assert report["connected"] and report["clean_shutdown"]
    assert not report["atlas"]["store"]["ready"]
    assert len(report["tools"]) == 6
    assert not root.exists()
    store = Store(root)
    collaborator = register_collaborator(store, display_name="Synthetic", client_family="test", scopes=["atlas:read", "atlas:write:path"])
    before = _store_snapshot(root)
    report = check_connection(server_command(store, collaborator.id))
    assert report["atlas"]["bridge"]["collaborator_id"] == collaborator.id
    assert "append_agent_path" in report["tools"]
    assert _store_snapshot(root) == before
    code, _, _ = run(["mcp", "config", "--client", "hermes", "--collaborator", "0" * 26], store=root)
    assert code != 0
    assert _store_snapshot(root) == before


def test_windows_frozen_config_uses_sibling_console_host(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "AtlasOfThreads.exe"))
    assert server_command(Store(tmp_path / "store"), None)[0] == str(tmp_path / "AtlasOfThreadsMCP.exe")


def test_advertised_example_succeeds_and_invalid_kinds_still_leave_no_writes(tmp_path):
    store = Store(tmp_path / "data")
    collaborator = register_collaborator(store, display_name="Synthetic", client_family="test", scopes=["atlas:read", "atlas:write:threadwalk", "atlas:write:path"])
    def call(name, arguments):
        return _bridge(store, [*_initialize(), {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": arguments}}], collaborator_id=collaborator.id)[1]["result"]
    tools = _bridge(store, [*_initialize(), {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}], collaborator_id=collaborator.id)[1]["result"]["tools"]
    schema = next(tool["inputSchema"] for tool in tools if tool["name"] == "append_agent_path")
    Draft202012Validator.check_schema(schema)
    interaction = call("begin_threadwalk", {"seed": "Synthetic trial", "seed_origin": "human_instruction", "client_request_id": "begin"})["structuredContent"]
    example = interaction["response_contract"]["example_arguments"]
    Draft202012Validator(schema).validate(example)
    before = _store_snapshot(store.root)
    for field in ("bad-node-field", "bad-node-kind", "bad-edge-kind"):
        invalid = json.loads(json.dumps(example))
        if field == "bad-node-field":
            invalid["thought_graph"]["nodes"][0]["agent"] = "human"
        elif field == "bad-node-kind":
            invalid["thought_graph"]["nodes"][0]["kind"] = "fact"
        else:
            invalid["thought_graph"]["edges"][0]["kind"] = "followed_by"
        assert list(Draft202012Validator(schema).iter_errors(invalid))
        assert call("append_agent_path", invalid)["isError"]
        assert _store_snapshot(store.root) == before
    result = call("append_agent_path", example)["structuredContent"]
    graph = store.load_graph(result["graph_id"])
    assert len(graph.nodes) == 2 and graph.edges[0].kind == "qualifies"
    assert graph.nodes[0].agent == "model"
    assert call("append_agent_path", example)["structuredContent"]["idempotent_replay"]
