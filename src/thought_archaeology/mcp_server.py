from __future__ import annotations

import json
import sys
from typing import Any, TextIO
from urllib.parse import unquote, urlparse

from thought_archaeology import __version__
from thought_archaeology.fork import ForkError
from thought_archaeology.inhabit import inhabit
from thought_archaeology.models import SCHEMA_VERSION
from thought_archaeology.serve import bootstrap_payload, thread_payload
from thought_archaeology.store import Store, StoreError

PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = (
    PROTOCOL_VERSION,
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
)

SERVER_INSTRUCTIONS = (
    "Atlas of Threads exposes this person's local Personal Atlas read-only. "
    "Use atlas_status before assuming a store exists, list_threadwalks to find "
    "stable IDs, then read_threadwalk or read_chamber for exact context. Reading "
    "never means publication. Do not request credentials, hidden chain-of-thought, "
    "or unrelated private memory. This Slice A bridge has no write tools."
)

EMPTY_OBJECT_SCHEMA = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}
ULID_SCHEMA = {
    "type": "string",
    "pattern": "^[0123456789ABCDEFGHJKMNPQRSTVWXYZ]{26}$",
}


class McpError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


def atlas_status(store: Store) -> dict[str, Any]:
    ready = store.exists()
    session_count = 0
    graph_count = 0
    if ready:
        session_ids = list(store.iter_session_ids())
        session_count = len(session_ids)
        graph_count = sum(1 for _ in store.iter_graphs())
    return {
        "product": "Atlas of Threads",
        "application_version": __version__,
        "schema_version": SCHEMA_VERSION,
        "bridge": {
            "transport": "stdio",
            "slice": "A",
            "read_only": True,
            "network": False,
            "publication": False,
        },
        "store": {
            "ready": ready,
            "session_count": session_count,
            "graph_count": graph_count,
        },
    }


def list_threadwalks(store: Store) -> dict[str, Any]:
    if not store.exists():
        return {"threadwalks": []}
    sessions = bootstrap_payload(store)["sessions"]
    return {"threadwalks": sessions}


def read_threadwalk(store: Store, session_id: str) -> dict[str, Any]:
    return thread_payload(store, session_id)


def read_chamber(store: Store, graph_id: str, node_id: str) -> dict[str, Any]:
    return inhabit(store, node_id, graph_id=graph_id).to_dict()


def _resources(store: Store) -> list[dict[str, Any]]:
    resources = [
        {
            "uri": "atlas://status",
            "name": "atlas-status",
            "title": "Personal Atlas status",
            "description": "Read-only local bridge and store status.",
            "mimeType": "application/json",
        },
        {
            "uri": "atlas://threadwalks",
            "name": "atlas-threadwalks",
            "title": "Personal Atlas Threadwalks",
            "description": "Stable IDs and entry chambers for local Threadwalks.",
            "mimeType": "application/json",
        },
    ]
    if store.exists():
        for item in list_threadwalks(store)["threadwalks"]:
            resources.append(
                {
                    "uri": f"atlas://threadwalk/{item['id']}",
                    "name": f"threadwalk-{item['id']}",
                    "title": item["title"],
                    "description": (
                        "One private, local Threadwalk and its generation lineage."
                    ),
                    "mimeType": "application/json",
                }
            )
    return resources


def _resource_templates() -> list[dict[str, Any]]:
    return [
        {
            "uriTemplate": "atlas://threadwalk/{session_id}",
            "name": "atlas-threadwalk",
            "title": "Threadwalk by session ID",
            "description": "Read one complete local Threadwalk lineage.",
            "mimeType": "application/json",
        },
        {
            "uriTemplate": "atlas://chamber/{graph_id}/{node_id}",
            "name": "atlas-chamber",
            "title": "Chamber by graph and node ID",
            "description": "Read the exact thought and its recorded local relations.",
            "mimeType": "application/json",
        },
    ]


def _tools() -> list[dict[str, Any]]:
    read_annotations = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    return [
        {
            "name": "atlas_status",
            "title": "Check Personal Atlas status",
            "description": (
                "Check whether the local Personal Atlas exists and count its contents."
            ),
            "inputSchema": EMPTY_OBJECT_SCHEMA,
            "annotations": read_annotations,
        },
        {
            "name": "list_threadwalks",
            "title": "List local Threadwalks",
            "description": (
                "List stable IDs and entry chambers without changing the Personal Atlas."
            ),
            "inputSchema": EMPTY_OBJECT_SCHEMA,
            "annotations": read_annotations,
        },
        {
            "name": "read_threadwalk",
            "title": "Read a Threadwalk",
            "description": (
                "Read the server-authored generation lineage of one local Threadwalk."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"session_id": ULID_SCHEMA},
                "required": ["session_id"],
                "additionalProperties": False,
            },
            "annotations": read_annotations,
        },
        {
            "name": "read_chamber",
            "title": "Read a chamber",
            "description": "Read one exact thought and the recorded relations around it.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "graph_id": ULID_SCHEMA,
                    "node_id": ULID_SCHEMA,
                },
                "required": ["graph_id", "node_id"],
                "additionalProperties": False,
            },
            "annotations": read_annotations,
        },
    ]


def _require_arguments(arguments: Any, names: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise McpError(-32602, "tool arguments must be an object")
    extras = set(arguments) - set(names)
    missing = [name for name in names if not isinstance(arguments.get(name), str)]
    if extras or missing:
        details = []
        if missing:
            details.append("missing string fields: " + ", ".join(missing))
        if extras:
            details.append("unexpected fields: " + ", ".join(sorted(extras)))
        raise McpError(-32602, "; ".join(details))
    return arguments


def _tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": payload,
        "isError": False,
    }


def _tool_error(message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": message}],
        "isError": True,
    }


def _call_tool(store: Store, params: Any) -> dict[str, Any]:
    if not isinstance(params, dict) or not isinstance(params.get("name"), str):
        raise McpError(-32602, "tools/call requires a tool name")
    name = params["name"]
    arguments = params.get("arguments", {})
    try:
        if name == "atlas_status":
            _require_arguments(arguments, ())
            return _tool_result(atlas_status(store))
        if name == "list_threadwalks":
            _require_arguments(arguments, ())
            return _tool_result(list_threadwalks(store))
        if name == "read_threadwalk":
            values = _require_arguments(arguments, ("session_id",))
            return _tool_result(read_threadwalk(store, values["session_id"]))
        if name == "read_chamber":
            values = _require_arguments(arguments, ("graph_id", "node_id"))
            return _tool_result(
                read_chamber(store, values["graph_id"], values["node_id"])
            )
    except (StoreError, ForkError) as exc:
        return _tool_error(str(exc))
    raise McpError(-32602, f"unknown tool: {name}")


def _read_resource(store: Store, params: Any) -> dict[str, Any]:
    if not isinstance(params, dict) or not isinstance(params.get("uri"), str):
        raise McpError(-32602, "resources/read requires a uri")
    uri = params["uri"]
    parsed = urlparse(uri)
    parts = [unquote(part) for part in parsed.path.split("/") if part]
    try:
        if parsed.scheme != "atlas":
            raise McpError(-32002, f"resource not found: {uri}")
        if parsed.netloc == "status" and not parts:
            payload = atlas_status(store)
        elif parsed.netloc == "threadwalks" and not parts:
            payload = list_threadwalks(store)
        elif parsed.netloc == "threadwalk" and len(parts) == 1:
            payload = read_threadwalk(store, parts[0])
        elif parsed.netloc == "chamber" and len(parts) == 2:
            payload = read_chamber(store, parts[0], parts[1])
        else:
            raise McpError(-32002, f"resource not found: {uri}")
    except (StoreError, ForkError) as exc:
        raise McpError(-32002, str(exc)) from exc
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            }
        ]
    }


class AtlasMcpServer:
    def __init__(self, store: Store):
        self.store = store
        self.initialized = False

    def dispatch(self, message: Any) -> dict[str, Any] | None:
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            raise McpError(-32600, "invalid JSON-RPC request")
        method = message.get("method")
        request_id = message.get("id")
        if not isinstance(method, str):
            raise McpError(-32600, "request method must be a string")

        if request_id is None:
            if method == "notifications/initialized":
                self.initialized = True
            return None

        if method == "initialize":
            params = message.get("params")
            if not isinstance(params, dict):
                raise McpError(-32602, "initialize params must be an object")
            requested = params.get("protocolVersion")
            negotiated = (
                requested if requested in SUPPORTED_PROTOCOL_VERSIONS else PROTOCOL_VERSION
            )
            return {
                "protocolVersion": negotiated,
                "capabilities": {
                    "resources": {"subscribe": False, "listChanged": False},
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": "atlas-of-threads",
                    "title": "Atlas of Threads Agent Bridge",
                    "version": __version__,
                    "description": "Read-only access to one local Personal Atlas.",
                    "websiteUrl": "https://atlasofthreads.com",
                },
                "instructions": SERVER_INSTRUCTIONS,
            }

        if not self.initialized:
            raise McpError(-32002, "server is not initialized")
        if method == "ping":
            return {}
        if method == "resources/list":
            return {"resources": _resources(self.store)}
        if method == "resources/templates/list":
            return {"resourceTemplates": _resource_templates()}
        if method == "resources/read":
            return _read_resource(self.store, message.get("params"))
        if method == "tools/list":
            return {"tools": _tools()}
        if method == "tools/call":
            return _call_tool(self.store, message.get("params"))
        raise McpError(-32601, f"method not found: {method}")


def _response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(request_id: Any, exc: McpError) -> dict[str, Any]:
    error: dict[str, Any] = {"code": exc.code, "message": exc.message}
    if exc.data is not None:
        error["data"] = exc.data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def serve_stdio(
    store: Store,
    *,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> None:
    source = input_stream or sys.stdin
    sink = output_stream or sys.stdout
    server = AtlasMcpServer(store)
    for line in source:
        request_id: Any = None
        try:
            message = json.loads(line)
            if isinstance(message, dict):
                request_id = message.get("id")
            result = server.dispatch(message)
            if result is None:
                continue
            response = _response(request_id, result)
        except json.JSONDecodeError:
            response = _error_response(None, McpError(-32700, "parse error"))
        except McpError as exc:
            response = _error_response(request_id, exc)
        except Exception as exc:
            print(f"Atlas Agent Bridge error: {type(exc).__name__}", file=sys.stderr)
            response = _error_response(
                request_id, McpError(-32603, "internal server error")
            )
        sink.write(
            json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        sink.flush()
