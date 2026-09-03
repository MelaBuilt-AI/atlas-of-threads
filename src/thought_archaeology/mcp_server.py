from __future__ import annotations

import json
import sys
from typing import Any, TextIO
from urllib.parse import unquote, urlparse

from thought_archaeology import __version__
from thought_archaeology.agent_bridge import (
    AgentBridgeError,
    AgentCollaborator,
    acknowledge_memory_receipt,
    append_agent_path,
    begin_threadwalk,
    require_scope,
)
from thought_archaeology.compile_common import CompileError
from thought_archaeology.fork import ForkError
from thought_archaeology.inhabit import inhabit
from thought_archaeology.models import SCHEMA_VERSION
from thought_archaeology.schema import ValidationError
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

WRITE_SERVER_INSTRUCTIONS = (
    "Atlas of Threads exposes this person's local Personal Atlas to one explicitly "
    "registered collaborator. Reads and inbound contributions stay private and local. "
    "Use begin_threadwalk only for a new seed and preserve whether it came from a human "
    "instruction or an agent proposal. Use append_agent_path only with the exact source "
    "IDs returned by that interaction. Every mutation needs a stable client_request_id. "
    "Send final user-visible prose and a structured thought graph, never credentials or "
    "hidden chain-of-thought. Preserve returned memory_candidate fields only through "
    "your own memory system; acknowledge_memory_receipt records an opaque receipt and "
    "never gives Atlas access to that memory. Inbound writes never publish or invoke "
    "an outbound harness."
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


def atlas_status(
    store: Store, collaborator: AgentCollaborator | None = None
) -> dict[str, Any]:
    ready = store.exists()
    write_enabled = collaborator is not None and bool(
        {
            "atlas:write:threadwalk",
            "atlas:write:path",
            "atlas:memory:ack",
        }.intersection(
            collaborator.scopes
        )
    )
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
            "slice": (
                "C"
                if collaborator is not None
                and "atlas:memory:ack" in collaborator.scopes
                else "B" if write_enabled else "A"
            ),
            "read_only": not write_enabled,
            "network": False,
            "publication": False,
            **(
                {
                    "collaborator_id": collaborator.id,
                    "scopes": list(collaborator.scopes),
                }
                if collaborator is not None
                else {}
            ),
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


def _tools(collaborator: AgentCollaborator | None = None) -> list[dict[str, Any]]:
    read_annotations = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    tools = [
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
    if collaborator is None:
        return tools
    if "atlas:read" not in collaborator.scopes:
        tools = []
    write_annotations = {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    if "atlas:write:threadwalk" in collaborator.scopes:
        tools.append(
            {
                "name": "begin_threadwalk",
                "title": "Begin a private Threadwalk",
                "description": (
                    "Create one private opening graph and inbound collaboration receipt."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "seed": {"type": "string", "minLength": 1, "maxLength": 4000},
                        "title": {"type": "string", "minLength": 1, "maxLength": 200},
                        "seed_origin": {
                            "type": "string",
                            "enum": ["human_instruction", "agent_proposal"],
                        },
                        "client_request_id": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 200,
                        },
                    },
                    "required": ["seed", "seed_origin", "client_request_id"],
                    "additionalProperties": False,
                },
                "annotations": write_annotations,
            }
        )
    if "atlas:write:path" in collaborator.scopes:
        public_metadata = {
            "type": "object",
            "properties": {
                "provider": {"type": "string", "minLength": 1, "maxLength": 200},
                "name": {"type": "string", "minLength": 1, "maxLength": 200},
                "version": {"type": "string", "minLength": 1, "maxLength": 200},
            },
            "additionalProperties": False,
        }
        tools.append(
            {
                "name": "append_agent_path",
                "title": "Append an attributed agent path",
                "description": (
                    "Validate and append final prose plus one structured graph "
                    "to an open interaction."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "interaction_id": ULID_SCHEMA,
                        "source_graph_id": ULID_SCHEMA,
                        "source_node_id": ULID_SCHEMA,
                        "prose": {"type": "string", "minLength": 1},
                        "thought_graph": {
                            "type": "object",
                            "properties": {
                                "nodes": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "object"},
                                },
                                "edges": {
                                    "type": "array",
                                    "items": {"type": "object"},
                                },
                            },
                            "required": ["nodes", "edges"],
                            "additionalProperties": False,
                        },
                        "client_request_id": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 200,
                        },
                        "model": public_metadata,
                        "harness": public_metadata,
                    },
                    "required": [
                        "interaction_id",
                        "source_graph_id",
                        "source_node_id",
                        "prose",
                        "thought_graph",
                        "client_request_id",
                    ],
                    "additionalProperties": False,
                },
                "annotations": write_annotations,
            }
        )
    if "atlas:memory:ack" in collaborator.scopes:
        tools.append(
            {
                "name": "acknowledge_memory_receipt",
                "title": "Acknowledge client-owned memory",
                "description": (
                    "Record that the client preserved an Atlas memory candidate "
                    "without exposing or mutating the external memory."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "receipt_id": ULID_SCHEMA,
                        "client_request_id": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 200,
                        },
                        "external_memory_ref": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 500,
                        },
                    },
                    "required": ["receipt_id", "client_request_id"],
                    "additionalProperties": False,
                },
                "annotations": write_annotations,
            }
        )
    return tools


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


def _call_tool(
    store: Store, params: Any, collaborator: AgentCollaborator | None = None
) -> dict[str, Any]:
    if not isinstance(params, dict) or not isinstance(params.get("name"), str):
        raise McpError(-32602, "tools/call requires a tool name")
    name = params["name"]
    arguments = params.get("arguments", {})
    try:
        if name == "atlas_status":
            _require_arguments(arguments, ())
            if collaborator is not None:
                require_scope(collaborator, "atlas:read")
            return _tool_result(atlas_status(store, collaborator))
        if name == "list_threadwalks":
            _require_arguments(arguments, ())
            if collaborator is not None:
                require_scope(collaborator, "atlas:read")
            return _tool_result(list_threadwalks(store))
        if name == "read_threadwalk":
            values = _require_arguments(arguments, ("session_id",))
            if collaborator is not None:
                require_scope(collaborator, "atlas:read")
            return _tool_result(read_threadwalk(store, values["session_id"]))
        if name == "read_chamber":
            values = _require_arguments(arguments, ("graph_id", "node_id"))
            if collaborator is not None:
                require_scope(collaborator, "atlas:read")
            return _tool_result(
                read_chamber(store, values["graph_id"], values["node_id"])
            )
        if name == "begin_threadwalk":
            if collaborator is None:
                raise AgentBridgeError(
                    "begin_threadwalk requires a registered collaborator"
                )
            if not isinstance(arguments, dict):
                raise McpError(-32602, "tool arguments must be an object")
            expected = {"seed", "seed_origin", "client_request_id", "title"}
            required = expected - {"title"}
            if set(arguments) - expected or any(
                not isinstance(arguments.get(field), str) for field in required
            ) or ("title" in arguments and not isinstance(arguments["title"], str)):
                raise McpError(-32602, "invalid begin_threadwalk arguments")
            return _tool_result(begin_threadwalk(store, collaborator, **arguments))
        if name == "append_agent_path":
            if collaborator is None:
                raise AgentBridgeError(
                    "append_agent_path requires a registered collaborator"
                )
            if not isinstance(arguments, dict):
                raise McpError(-32602, "tool arguments must be an object")
            expected = {
                "interaction_id",
                "source_graph_id",
                "source_node_id",
                "prose",
                "thought_graph",
                "client_request_id",
                "model",
                "harness",
            }
            required = expected - {"model", "harness"}
            string_fields = required - {"thought_graph"}
            if set(arguments) - expected or any(
                not isinstance(arguments.get(field), str) for field in string_fields
            ) or "thought_graph" not in arguments:
                raise McpError(-32602, "invalid append_agent_path arguments")
            return _tool_result(append_agent_path(store, collaborator, **arguments))
        if name == "acknowledge_memory_receipt":
            if collaborator is None:
                raise AgentBridgeError(
                    "acknowledge_memory_receipt requires a registered collaborator"
                )
            if not isinstance(arguments, dict):
                raise McpError(-32602, "tool arguments must be an object")
            expected = {
                "receipt_id",
                "client_request_id",
                "external_memory_ref",
            }
            required = expected - {"external_memory_ref"}
            if set(arguments) - expected or any(
                not isinstance(arguments.get(field), str) for field in required
            ) or (
                "external_memory_ref" in arguments
                and not isinstance(arguments["external_memory_ref"], str)
            ):
                raise McpError(-32602, "invalid acknowledge_memory_receipt arguments")
            return _tool_result(
                acknowledge_memory_receipt(store, collaborator, **arguments)
            )
    except (
        StoreError,
        ForkError,
        AgentBridgeError,
        CompileError,
        ValidationError,
    ) as exc:
        return _tool_error(str(exc))
    raise McpError(-32602, f"unknown tool: {name}")


def _read_resource(
    store: Store,
    params: Any,
    collaborator: AgentCollaborator | None = None,
) -> dict[str, Any]:
    if not isinstance(params, dict) or not isinstance(params.get("uri"), str):
        raise McpError(-32602, "resources/read requires a uri")
    uri = params["uri"]
    parsed = urlparse(uri)
    parts = [unquote(part) for part in parsed.path.split("/") if part]
    try:
        if parsed.scheme != "atlas":
            raise McpError(-32002, f"resource not found: {uri}")
        if parsed.netloc == "status" and not parts:
            payload = atlas_status(store, collaborator)
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
    def __init__(
        self, store: Store, collaborator: AgentCollaborator | None = None
    ):
        self.store = store
        self.collaborator = collaborator
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
                    "description": (
                        "Scoped local collaboration with one Personal Atlas."
                        if self.collaborator is not None
                        else "Read-only access to one local Personal Atlas."
                    ),
                    "websiteUrl": "https://atlasofthreads.com",
                },
                "instructions": (
                    WRITE_SERVER_INSTRUCTIONS
                    if self.collaborator is not None
                    and {
                        "atlas:write:threadwalk",
                        "atlas:write:path",
                        "atlas:memory:ack",
                    }.intersection(self.collaborator.scopes)
                    else SERVER_INSTRUCTIONS
                ),
            }

        if not self.initialized:
            raise McpError(-32002, "server is not initialized")
        if method == "ping":
            return {}
        if method == "resources/list":
            if (
                self.collaborator is not None
                and "atlas:read" not in self.collaborator.scopes
            ):
                return {"resources": []}
            return {"resources": _resources(self.store)}
        if method == "resources/templates/list":
            if (
                self.collaborator is not None
                and "atlas:read" not in self.collaborator.scopes
            ):
                return {"resourceTemplates": []}
            return {"resourceTemplates": _resource_templates()}
        if method == "resources/read":
            if self.collaborator is not None:
                try:
                    require_scope(self.collaborator, "atlas:read")
                except AgentBridgeError as exc:
                    raise McpError(-32003, str(exc)) from exc
            return _read_resource(
                self.store, message.get("params"), self.collaborator
            )
        if method == "tools/list":
            return {"tools": _tools(self.collaborator)}
        if method == "tools/call":
            return _call_tool(
                self.store, message.get("params"), self.collaborator
            )
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
    collaborator_id: str | None = None,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> None:
    source = input_stream or sys.stdin
    sink = output_stream or sys.stdout
    collaborator = (
        store.load_agent_collaborator(collaborator_id)
        if collaborator_id is not None
        else None
    )
    server = AtlasMcpServer(store, collaborator)
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
