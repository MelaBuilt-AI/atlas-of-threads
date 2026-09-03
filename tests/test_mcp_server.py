from __future__ import annotations

import io
import json
from pathlib import Path

from thought_archaeology.agent_bridge import register_collaborator
from thought_archaeology.mcp_server import serve_stdio
from thought_archaeology.serve import thread_payload
from thought_archaeology.store import Store

from tests.test_cli import run


def _bridge(
    store: Store, messages: list[dict], *, collaborator_id: str | None = None
) -> list[dict]:
    source = io.StringIO(
        "".join(json.dumps(message) + "\n" for message in messages)
    )
    sink = io.StringIO()
    serve_stdio(
        store,
        collaborator_id=collaborator_id,
        input_stream=source,
        output_stream=sink,
    )
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


def test_cli_registers_and_lists_inbound_collaborator(tmp_path: Path):
    store_path = tmp_path / "data"
    code, out, err = run(
        [
            "mcp",
            "collaborator",
            "register",
            "--name",
            "Codex",
            "--client-family",
            "codex",
            "--scope",
            "atlas:read",
            "--scope",
            "atlas:write:threadwalk",
            "--scope",
            "atlas:write:path",
        ],
        store=store_path,
    )
    assert code == 0, err
    registered = json.loads(out)
    assert registered["display_name"] == "Codex"
    assert registered["scopes"] == [
        "atlas:read",
        "atlas:write:path",
        "atlas:write:threadwalk",
    ]

    code, out, err = run(
        ["mcp", "collaborator", "list"], store=store_path
    )
    assert code == 0, err
    assert json.loads(out) == [registered]


def test_slice_b_registered_collaborator_appends_one_private_path_idempotently(
    tmp_path: Path,
):
    store = Store(tmp_path / "data")
    collaborator = register_collaborator(
        store,
        display_name="Codex",
        client_family="codex",
        scopes=["atlas:read", "atlas:write:threadwalk", "atlas:write:path"],
    )
    begin_arguments = {
        "seed": "Invent the medium first.",
        "title": "Agent Bridge acceptance",
        "seed_origin": "human_instruction",
        "client_request_id": "begin-acceptance-1",
    }
    begin_replies = _bridge(
        store,
        [
            *_initialize(),
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "begin_threadwalk", "arguments": begin_arguments},
            },
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "begin_threadwalk", "arguments": begin_arguments},
            },
        ],
        collaborator_id=collaborator.id,
    )

    assert [item["name"] for item in begin_replies[1]["result"]["tools"]] == [
        "atlas_status",
        "list_threadwalks",
        "read_threadwalk",
        "read_chamber",
        "begin_threadwalk",
        "append_agent_path",
    ]
    begin = begin_replies[2]["result"]["structuredContent"]
    replay = begin_replies[3]["result"]["structuredContent"]
    assert begin["visibility"] == "private"
    assert begin["publication"] is False
    assert begin["outbound_harness_queued"] is False
    assert replay["root_graph_id"] == begin["root_graph_id"]
    assert replay["idempotent_replay"] is True

    path_arguments = {
        "interaction_id": begin["interaction_id"],
        "source_graph_id": begin["root_graph_id"],
        "source_node_id": begin["root_node_id"],
        "prose": "The medium should make judgment calls traversable.",
        "thought_graph": {
            "nodes": [
                {
                    "local_id": "claim-1",
                    "kind": "claim",
                    "text": "The medium should make judgment calls traversable.",
                },
                {
                    "local_id": "alternative-1",
                    "kind": "rejected_alternative",
                    "text": "A flat transcript would hide the route.",
                },
            ],
            "edges": [
                {
                    "from": "alternative-1",
                    "to": "claim-1",
                    "kind": "shapes",
                }
            ],
        },
        "client_request_id": "path-acceptance-1",
        "model": {"provider": "openai", "name": "gpt-5"},
        "harness": {"name": "codex", "version": "test"},
    }
    path_replies = _bridge(
        store,
        [
            *_initialize(),
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "append_agent_path", "arguments": path_arguments},
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "append_agent_path", "arguments": path_arguments},
            },
        ],
        collaborator_id=collaborator.id,
    )
    completion = path_replies[1]["result"]["structuredContent"]
    completion_replay = path_replies[2]["result"]["structuredContent"]

    assert completion_replay["graph_id"] == completion["graph_id"]
    assert completion_replay["idempotent_replay"] is True
    assert len(list(store.iter_session_ids())) == 1
    assert len(list(store.iter_graphs(begin["session_id"]))) == 2
    assert len(list(store.iter_turns(begin["session_id"]))) == 2
    assert list(store.iter_continuation_requests()) == []
    assert store.validate_session(begin["session_id"]) == []

    root = store.load_graph(begin["root_graph_id"])
    child = store.load_graph(completion["graph_id"])
    assert completion["memory_candidate"]["atlas_ids"]["node_id"] == child.nodes[0].id
    assert completion["memory_candidate"]["outcome"] == "completed"
    assert root.nodes[0].agent == "human"
    assert root.metadata["agent_bridge"]["seed_origin"] == "human_instruction"
    assert child.parent_graph_id == root.id
    assert child.model.provider == "none"
    assert child.model.name == "gpt-5"
    assert child.metadata["agent_bridge"]["model"] == {
        "provider": "openai",
        "name": "gpt-5",
    }
    assert all(node.agent == "model" for node in child.nodes)
    threadwalk = thread_payload(store, begin["session_id"])
    assert [entry["kind"] for entry in threadwalk["entries"]] == [
        "origin",
        "continuation",
    ]
    assert threadwalk["latest_ai_graph_id"] == child.id
    assert threadwalk["entries"][1]["source_graph_id"] == root.id
    assert threadwalk["entries"][1]["source_node_id"] == begin["root_node_id"]


def test_slice_b_agent_proposal_is_not_attributed_to_human_and_conflicts_fail_closed(
    tmp_path: Path,
):
    store = Store(tmp_path / "data")
    collaborator = register_collaborator(
        store,
        display_name="Research agent",
        client_family="codex",
        scopes=["atlas:write:threadwalk"],
    )
    first = _bridge(
        store,
        [
            *_initialize(),
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "begin_threadwalk",
                    "arguments": {
                        "seed": "Explore a new representational medium.",
                        "seed_origin": "agent_proposal",
                        "client_request_id": "proposal-1",
                    },
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "begin_threadwalk",
                    "arguments": {
                        "seed": "Different content.",
                        "seed_origin": "agent_proposal",
                        "client_request_id": "proposal-1",
                    },
                },
            },
        ],
        collaborator_id=collaborator.id,
    )
    opened = first[1]["result"]["structuredContent"]
    root = store.load_graph(opened["root_graph_id"])
    root_turn = store.load_turn(opened["session_id"], opened["root_turn_id"])

    assert root.nodes[0].agent == "model"
    assert root.nodes[0].source == "structured_emit"
    assert root_turn.role == "assistant"
    assert first[2]["result"]["isError"] is True
    assert "different content" in first[2]["result"]["content"][0]["text"]
    assert len(list(store.iter_session_ids())) == 1


def test_slice_c_memory_candidate_and_opaque_acknowledgement_are_idempotent(
    tmp_path: Path,
):
    store = Store(tmp_path / "data")
    collaborator = register_collaborator(
        store,
        display_name="Indy",
        client_family="codex",
        scopes=[
            "atlas:read",
            "atlas:write:threadwalk",
            "atlas:memory:ack",
        ],
    )
    begin = _bridge(
        store,
        [
            *_initialize(),
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "begin_threadwalk",
                    "arguments": {
                        "seed": "What is your name and who is Aaron?",
                        "title": "Identity and collaborator context",
                        "seed_origin": "human_instruction",
                        "client_request_id": "memory-begin-1",
                    },
                },
            },
        ],
        collaborator_id=collaborator.id,
    )
    assert begin[0]["result"]["instructions"].count("memory_candidate") == 1
    assert [item["name"] for item in begin[1]["result"]["tools"]][-1] == (
        "acknowledge_memory_receipt"
    )
    opened = begin[2]["result"]["structuredContent"]
    candidate = opened["memory_candidate"]
    assert candidate["receipt_id"] == opened["interaction_id"]
    assert candidate["collaborator"]["display_name"] == "Indy"
    assert candidate["atlas_ids"]["session_id"] == opened["session_id"]
    assert candidate["publication"] is False
    assert candidate["subject"] == "Identity and collaborator context"
    assert "What is your name" not in json.dumps(candidate)

    arguments = {
        "receipt_id": candidate["receipt_id"],
        "client_request_id": "memory-ack-1",
        "external_memory_ref": "codex-session:opaque-test-ref",
    }
    replies = _bridge(
        store,
        [
            *_initialize(),
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "acknowledge_memory_receipt",
                    "arguments": arguments,
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "acknowledge_memory_receipt",
                    "arguments": arguments,
                },
            },
        ],
        collaborator_id=collaborator.id,
    )
    acknowledged = replies[1]["result"]["structuredContent"]
    replay = replies[2]["result"]["structuredContent"]
    assert acknowledged["status"] == "acknowledged"
    assert acknowledged["external_memory_read"] is False
    assert acknowledged["external_memory_written_by_atlas"] is False
    assert replay["acknowledgement"]["id"] == acknowledged["acknowledgement"]["id"]
    assert replay["idempotent_replay"] is True
    stored = list(store.iter_agent_memory_acknowledgements())
    assert len(stored) == 1
    assert stored[0].external_memory_ref == "codex-session:opaque-test-ref"
