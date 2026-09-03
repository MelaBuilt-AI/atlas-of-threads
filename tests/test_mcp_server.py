from __future__ import annotations

import io
import json
from pathlib import Path

from thought_archaeology.mcp_server import serve_stdio
from thought_archaeology.store import Store

from tests.test_cli import run


def _bridge(store: Store, messages: list[dict]) -> list[dict]:
    source = io.StringIO(
        "".join(json.dumps(message) + "\n" for message in messages)
    )
    sink = io.StringIO()
    serve_stdio(store, input_stream=source, output_stream=sink)
    return [json.loads(line) for line in sink.getvalue().splitlines()]


def _initialize() -> list[dict]:
    return [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "synthetic-client", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    ]


def _store_snapshot(root: Path) -> dict[str, tuple[int, bytes]]:
    return {
        str(path.relative_to(root)): (path.stat().st_mtime_ns, path.read_bytes())
        for path in root.rglob("*")
        if path.is_file()
    }


def test_slice_a_stdio_reads_threadwalk_and_chamber_without_writes(
    tmp_path: Path, fixtures_dir: Path
):
    store_path = tmp_path / "data"
    code, out, err = run(["init", "--title", "Bridge study"], store=store_path)
    assert code == 0, err
    session_id = out.strip()
    code, out, err = run(
        [
            "compile",
            "--session",
            session_id,
            "--mode",
            "posthoc",
            "--transcript",
            str(fixtures_dir / "transcripts" / "simple-freeform.jsonl"),
            "--from-graph",
            str(fixtures_dir / "graphs" / "simple.gold.json"),
        ],
        store=store_path,
    )
    assert code == 0, err
    graph_id = out.strip()
    graph = Store(store_path).load_graph(graph_id)
    node_id = graph.nodes[0].id
    before = _store_snapshot(store_path)

    replies = _bridge(
        Store(store_path),
        [
            *_initialize(),
            {"jsonrpc": "2.0", "id": 2, "method": "resources/list"},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "resources/read",
                "params": {"uri": f"atlas://threadwalk/{session_id}"},
            },
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "read_chamber",
                    "arguments": {"graph_id": graph_id, "node_id": node_id},
                },
            },
        ],
    )

    assert replies[0]["result"]["protocolVersion"] == "2025-11-25"
    assert replies[0]["result"]["capabilities"] == {
        "resources": {"subscribe": False, "listChanged": False},
        "tools": {"listChanged": False},
    }
    resources = replies[1]["result"]["resources"]
    assert "atlas://status" in {item["uri"] for item in resources}
    assert f"atlas://threadwalk/{session_id}" in {
        item["uri"] for item in resources
    }
    threadwalk = json.loads(replies[2]["result"]["contents"][0]["text"])
    assert threadwalk["session_id"] == session_id
    assert threadwalk["head_graph_id"] == graph_id
    chamber = replies[3]["result"]["structuredContent"]
    assert chamber["graph_id"] == graph_id
    assert chamber["node"]["id"] == node_id
    assert "hidden_reasoning" not in json.dumps(threadwalk)
    assert "hidden_reasoning" not in json.dumps(chamber)
    assert _store_snapshot(store_path) == before


def test_slice_a_tools_are_explicitly_read_only(tmp_path: Path):
    replies = _bridge(
        Store(tmp_path / "missing"),
        [
            *_initialize(),
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "atlas_status", "arguments": {}},
            },
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "list_threadwalks", "arguments": {}},
            },
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "resources/templates/list",
            },
        ],
    )

    tools = replies[1]["result"]["tools"]
    assert [tool["name"] for tool in tools] == [
        "atlas_status",
        "list_threadwalks",
        "read_threadwalk",
        "read_chamber",
    ]
    assert all(tool["annotations"]["readOnlyHint"] is True for tool in tools)
    assert replies[2]["result"]["structuredContent"]["store"]["ready"] is False
    assert replies[3]["result"]["structuredContent"] == {"threadwalks": []}
    assert [
        template["uriTemplate"]
        for template in replies[4]["result"]["resourceTemplates"]
    ] == [
        "atlas://threadwalk/{session_id}",
        "atlas://chamber/{graph_id}/{node_id}",
    ]
    assert not (tmp_path / "missing").exists()


def test_stdio_protocol_errors_are_bounded(tmp_path: Path):
    source = io.StringIO(
        "not json\n"
        + json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        + "\n"
    )
    sink = io.StringIO()

    serve_stdio(Store(tmp_path / "missing"), input_stream=source, output_stream=sink)

    replies = [json.loads(line) for line in sink.getvalue().splitlines()]
    assert replies[0]["error"]["code"] == -32700
    assert replies[1]["error"]["message"] == "server is not initialized"


def test_cli_exposes_mcp_serve_help():
    code, out, err = run(["mcp", "serve", "--help"])
    assert code == 0
    assert "read-only Atlas Agent Bridge" in out
    assert err == ""
