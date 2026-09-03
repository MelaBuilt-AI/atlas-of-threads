from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, Self

from thought_archaeology.compile_common import finalize, policy_warnings
from thought_archaeology.ids import new_ulid, now_iso
from thought_archaeology.models import (
    SCHEMA_VERSION,
    ModelInfo,
    Span,
    ThoughtGraph,
    ThoughtNode,
    Turn,
)
from thought_archaeology.schema import validate_graph

if TYPE_CHECKING:
    from thought_archaeology.store import Store

AgentBridgeScope = Literal[
    "atlas:read",
    "atlas:write:threadwalk",
    "atlas:write:path",
    "atlas:memory:ack",
]
SeedOrigin = Literal["human_instruction", "agent_proposal"]

KNOWN_SCOPES = frozenset(
    {
        "atlas:read",
        "atlas:write:threadwalk",
        "atlas:write:path",
        "atlas:memory:ack",
    }
)


class AgentBridgeError(Exception):
    """A bounded inbound-collaboration contract failure."""


def request_sha256(action: str, arguments: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"action": action, "arguments": arguments},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class AgentCollaborator:
    schema_version: str
    id: str
    created_at: str
    display_name: str
    client_family: str
    scopes: tuple[AgentBridgeScope, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            id=data["id"],
            created_at=data["created_at"],
            display_name=data["display_name"],
            client_family=data["client_family"],
            scopes=tuple(data["scopes"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "created_at": self.created_at,
            "display_name": self.display_name,
            "client_family": self.client_family,
            "scopes": list(self.scopes),
        }


@dataclass(frozen=True)
class AgentInteraction:
    schema_version: str
    id: str
    collaborator_id: str
    created_at: str
    client_request_id: str
    request_sha256: str
    session_id: str
    root_turn_id: str
    root_graph_id: str
    root_node_id: str
    seed: str
    seed_origin: SeedOrigin
    title: str
    visibility: Literal["private"] = "private"
    transport: Literal["mcp"] = "mcp"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "collaborator_id": self.collaborator_id,
            "created_at": self.created_at,
            "client_request_id": self.client_request_id,
            "request_sha256": self.request_sha256,
            "session_id": self.session_id,
            "root_turn_id": self.root_turn_id,
            "root_graph_id": self.root_graph_id,
            "root_node_id": self.root_node_id,
            "seed": self.seed,
            "seed_origin": self.seed_origin,
            "title": self.title,
            "visibility": self.visibility,
            "transport": self.transport,
        }


@dataclass(frozen=True)
class AgentPathCompletion:
    schema_version: str
    id: str
    interaction_id: str
    collaborator_id: str
    created_at: str
    client_request_id: str
    request_sha256: str
    session_id: str
    source_graph_id: str
    source_node_id: str
    graph_id: str
    turn_id: str
    model: dict[str, str]
    harness: dict[str, str]
    warnings: tuple[str, ...]
    visibility: Literal["private"] = "private"
    transport: Literal["mcp"] = "mcp"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            **{
                **data,
                "model": dict(data.get("model", {})),
                "harness": dict(data.get("harness", {})),
                "warnings": tuple(data.get("warnings", ())),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "interaction_id": self.interaction_id,
            "collaborator_id": self.collaborator_id,
            "created_at": self.created_at,
            "client_request_id": self.client_request_id,
            "request_sha256": self.request_sha256,
            "session_id": self.session_id,
            "source_graph_id": self.source_graph_id,
            "source_node_id": self.source_node_id,
            "graph_id": self.graph_id,
            "turn_id": self.turn_id,
            "model": self.model,
            "harness": self.harness,
            "warnings": list(self.warnings),
            "visibility": self.visibility,
            "transport": self.transport,
        }


def register_collaborator(
    store: Store, *, display_name: str, client_family: str, scopes: list[str]
) -> AgentCollaborator:
    display_name = display_name.strip()
    client_family = client_family.strip()
    normalized_scopes = tuple(sorted(set(scopes)))
    if not display_name or not client_family:
        raise AgentBridgeError("collaborator name and client family are required")
    if not normalized_scopes or any(scope not in KNOWN_SCOPES for scope in normalized_scopes):
        raise AgentBridgeError("collaborator scopes must be known Atlas scopes")
    if not store.exists():
        store.initialize()
    collaborator = AgentCollaborator(
        schema_version=SCHEMA_VERSION,
        id=new_ulid(),
        created_at=now_iso(),
        display_name=display_name,
        client_family=client_family,
        scopes=normalized_scopes,  # type: ignore[arg-type]
    )
    store.write_agent_collaborator(collaborator)
    store.log(
        "agent_bridge_collaborator_registered",
        collaborator_id=collaborator.id,
        client_family=collaborator.client_family,
        scopes=list(collaborator.scopes),
        warnings=[],
    )
    return collaborator


def require_scope(collaborator: AgentCollaborator, scope: str) -> None:
    if scope not in collaborator.scopes:
        raise AgentBridgeError(
            f"collaborator {collaborator.id} lacks required scope {scope}"
        )


def _existing_request(
    store: Store, collaborator_id: str, client_request_id: str
) -> tuple[str, AgentInteraction | AgentPathCompletion] | None:
    for interaction in store.iter_agent_interactions():
        if (
            interaction.collaborator_id == collaborator_id
            and interaction.client_request_id == client_request_id
        ):
            return "begin_threadwalk", interaction
    for completion in store.iter_agent_path_completions():
        if (
            completion.collaborator_id == collaborator_id
            and completion.client_request_id == client_request_id
        ):
            return "append_agent_path", completion
    return None


def interaction_result(interaction: AgentInteraction, *, replayed: bool = False) -> dict[str, Any]:
    return {
        "status": "open",
        "interaction_id": interaction.id,
        "session_id": interaction.session_id,
        "root_turn_id": interaction.root_turn_id,
        "root_graph_id": interaction.root_graph_id,
        "root_node_id": interaction.root_node_id,
        "visibility": interaction.visibility,
        "public_context": {
            "seed": interaction.seed,
            "seed_origin": interaction.seed_origin,
            "title": interaction.title,
        },
        "response_contract": {
            "tool": "append_agent_path",
            "source_graph_id": interaction.root_graph_id,
            "source_node_id": interaction.root_node_id,
            "content": "final prose plus a structured thought graph",
            "forbidden": ["hidden chain-of-thought", "credentials"],
        },
        "receipt": interaction.to_dict(),
        "idempotent_replay": replayed,
        "publication": False,
        "outbound_harness_queued": False,
    }


def completion_result(
    completion: AgentPathCompletion, *, replayed: bool = False
) -> dict[str, Any]:
    return {
        "status": "completed",
        "interaction_id": completion.interaction_id,
        "session_id": completion.session_id,
        "source_graph_id": completion.source_graph_id,
        "source_node_id": completion.source_node_id,
        "graph_id": completion.graph_id,
        "turn_id": completion.turn_id,
        "visibility": completion.visibility,
        "model": completion.model,
        "harness": completion.harness,
        "warnings": list(completion.warnings),
        "receipt": completion.to_dict(),
        "idempotent_replay": replayed,
        "publication": False,
        "outbound_harness_queued": False,
    }


def _check_idempotency(
    store: Store,
    collaborator: AgentCollaborator,
    *,
    action: str,
    client_request_id: str,
    digest: str,
) -> dict[str, Any] | None:
    existing = _existing_request(store, collaborator.id, client_request_id)
    if existing is None:
        return None
    prior_action, receipt = existing
    if prior_action != action or receipt.request_sha256 != digest:
        raise AgentBridgeError(
            "client_request_id was already used with different content"
        )
    if isinstance(receipt, AgentInteraction):
        return interaction_result(receipt, replayed=True)
    return completion_result(receipt, replayed=True)


def begin_threadwalk(
    store: Store,
    collaborator: AgentCollaborator,
    *,
    seed: str,
    seed_origin: str,
    client_request_id: str,
    title: str | None = None,
) -> dict[str, Any]:
    require_scope(collaborator, "atlas:write:threadwalk")
    seed = seed.strip()
    client_request_id = client_request_id.strip()
    requested_title = title.strip() if title else ""
    if not seed or len(seed) > 4000:
        raise AgentBridgeError("seed must contain 1 to 4000 characters")
    if seed_origin not in {"human_instruction", "agent_proposal"}:
        raise AgentBridgeError(
            "seed_origin must be human_instruction or agent_proposal"
        )
    if not client_request_id or len(client_request_id) > 200:
        raise AgentBridgeError("client_request_id must contain 1 to 200 characters")
    if len(requested_title) > 200:
        raise AgentBridgeError("title must be 200 characters or fewer")
    arguments = {
        "seed": seed,
        "seed_origin": seed_origin,
        "client_request_id": client_request_id,
        **({"title": requested_title} if requested_title else {}),
    }
    digest = request_sha256("begin_threadwalk", arguments)
    with store.agent_bridge_lock():
        replay = _check_idempotency(
            store,
            collaborator,
            action="begin_threadwalk",
            client_request_id=client_request_id,
            digest=digest,
        )
        if replay is not None:
            return replay
        resolved_title = requested_title or seed.splitlines()[0].strip()
        if len(resolved_title) > 80:
            resolved_title = resolved_title[:77].rstrip() + "…"
        interaction_id = new_ulid()
        session = store.init_session(resolved_title, origin="agent-bridge:mcp")
        created_at = now_iso()
        turn_id = new_ulid()
        graph_id = new_ulid()
        node_id = new_ulid()
        is_human = seed_origin == "human_instruction"
        node = ThoughtNode(
            id=node_id,
            kind="uncertainty",
            text=seed,
            status="uncertain",
            agent="human" if is_human else "model",
            created_at=created_at,
            source="human" if is_human else "structured_emit",
            span=Span(0, len(seed)),
            notes="Agent Bridge opening seed",
        )
        bridge_metadata = {
            "direction": "inbound",
            "transport": "mcp",
            "interaction_id": interaction_id,
            "collaborator_id": collaborator.id,
            "client_family": collaborator.client_family,
            "seed_origin": seed_origin,
            "visibility": "private",
        }
        graph = ThoughtGraph(
            schema_version=SCHEMA_VERSION,
            id=graph_id,
            session_id=session.id,
            turn_id=turn_id,
            created_at=created_at,
            prose=seed,
            nodes=(node,),
            edges=(),
            model=ModelInfo(
                "none",
                "human instruction" if is_human else collaborator.display_name,
                "posthoc" if is_human else "structured_emit",
            ),
            metadata=MappingProxyType({"agent_bridge": bridge_metadata}),
        )
        turn = Turn(
            schema_version=SCHEMA_VERSION,
            id=turn_id,
            session_id=session.id,
            seq=0,
            role="user" if is_human else "assistant",
            created_at=created_at,
            prose=seed,
            graph_id=graph.id,
            parent_turn_id=None,
            fork_of_node_id=None,
            provider="none",
        )
        interaction = AgentInteraction(
            schema_version=SCHEMA_VERSION,
            id=interaction_id,
            collaborator_id=collaborator.id,
            created_at=created_at,
            client_request_id=client_request_id,
            request_sha256=digest,
            session_id=session.id,
            root_turn_id=turn.id,
            root_graph_id=graph.id,
            root_node_id=node.id,
            seed=seed,
            seed_origin=seed_origin,  # type: ignore[arg-type]
            title=resolved_title,
        )
        store.write_graph(graph)
        store.append_turn(turn)
        store.update_session_head(session.id, graph_id=graph.id, turn_id=turn.id)
        path = store.write_agent_interaction(interaction)
    store.log(
        "agent_bridge_begin_threadwalk",
        collaborator_id=collaborator.id,
        interaction_id=interaction.id,
        session_id=session.id,
        graph_id=graph.id,
        node_id=node.id,
        path=str(path),
        warnings=[],
    )
    return interaction_result(interaction)


def _public_mapping(value: Any, field: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or set(value) - {"provider", "name", "version"}:
        raise AgentBridgeError(
            f"{field} must be an object containing only provider, name, and version"
        )
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(item, str) or not item.strip() or len(item) > 200:
            raise AgentBridgeError(f"{field}.{key} must be a non-empty short string")
        result[key] = item.strip()
    return result


def _structured_graph(value: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(value, dict) or set(value) != {"nodes", "edges"}:
        raise AgentBridgeError("thought_graph must contain only nodes and edges")
    nodes = value["nodes"]
    edges = value["edges"]
    if not isinstance(nodes, list) or not nodes or not isinstance(edges, list):
        raise AgentBridgeError("thought_graph nodes must be non-empty and edges an array")
    normalized_nodes: list[dict[str, Any]] = []
    forbidden = {"hidden_reasoning", "chain_of_thought", "credentials", "secrets"}
    node_fields = {
        "id",
        "local_id",
        "kind",
        "text",
        "status",
        "confidence",
        "span",
        "tags",
        "notes",
    }
    for item in nodes:
        if (
            not isinstance(item, dict)
            or forbidden.intersection(item)
            or set(item) - node_fields
        ):
            raise AgentBridgeError("thought_graph contains a forbidden or malformed node")
        normalized_nodes.append(
            {
                **item,
                "agent": "model",
                "source": "structured_emit",
            }
        )
    edge_fields = {"from", "to", "source_id", "target_id", "kind", "notes"}
    if any(
        not isinstance(item, dict)
        or forbidden.intersection(item)
        or set(item) - edge_fields
        for item in edges
    ):
        raise AgentBridgeError("thought_graph contains a forbidden or malformed edge")
    return normalized_nodes, list(edges)


def append_agent_path(
    store: Store,
    collaborator: AgentCollaborator,
    *,
    interaction_id: str,
    source_graph_id: str,
    source_node_id: str,
    prose: str,
    thought_graph: Any,
    client_request_id: str,
    model: Any = None,
    harness: Any = None,
) -> dict[str, Any]:
    require_scope(collaborator, "atlas:write:path")
    prose = prose.strip()
    client_request_id = client_request_id.strip()
    if not prose:
        raise AgentBridgeError("prose must be non-empty final user-visible text")
    if not client_request_id or len(client_request_id) > 200:
        raise AgentBridgeError("client_request_id must contain 1 to 200 characters")
    reported_model = _public_mapping(model, "model")
    reported_harness = _public_mapping(harness, "harness")
    raw_nodes, raw_edges = _structured_graph(thought_graph)
    arguments = {
        "interaction_id": interaction_id,
        "source_graph_id": source_graph_id,
        "source_node_id": source_node_id,
        "prose": prose,
        "thought_graph": thought_graph,
        "client_request_id": client_request_id,
        **({"model": reported_model} if reported_model else {}),
        **({"harness": reported_harness} if reported_harness else {}),
    }
    digest = request_sha256("append_agent_path", arguments)
    with store.agent_bridge_lock():
        replay = _check_idempotency(
            store,
            collaborator,
            action="append_agent_path",
            client_request_id=client_request_id,
            digest=digest,
        )
        if replay is not None:
            return replay
        interaction = store.load_agent_interaction(interaction_id)
        if interaction.collaborator_id != collaborator.id:
            raise AgentBridgeError("interaction belongs to a different collaborator")
        if (
            interaction.root_graph_id != source_graph_id
            or interaction.root_node_id != source_node_id
        ):
            raise AgentBridgeError("source graph and node do not match the interaction")
        if any(
            item.interaction_id == interaction.id
            for item in store.iter_agent_path_completions()
        ):
            raise AgentBridgeError("interaction already has an appended agent path")
        source_graph = store.load_graph(source_graph_id)
        if source_graph.session_id != interaction.session_id:
            raise AgentBridgeError("interaction source is not in its Threadwalk")
        created_at = now_iso()
        turn_id = new_ulid()
        graph = finalize(
            session_id=interaction.session_id,
            turn_id=turn_id,
            prose=prose,
            raw_nodes=raw_nodes,
            raw_edges=raw_edges,
            model=ModelInfo(
                "none", reported_model.get("name", "unknown"), "structured_emit"
            ),
            now=created_at,
            parent_graph_id=source_graph_id,
        )
        bridge_metadata = {
            "direction": "inbound",
            "transport": "mcp",
            "interaction_id": interaction.id,
            "collaborator_id": collaborator.id,
            "client_family": collaborator.client_family,
            "source_graph_id": source_graph_id,
            "source_node_id": source_node_id,
            "model": reported_model,
            "harness": reported_harness,
            "visibility": "private",
        }
        graph = replace(
            graph, metadata=MappingProxyType({"agent_bridge": bridge_metadata})
        )
        validate_graph(graph)
        warnings = tuple(policy_warnings(graph))
        turn = Turn(
            schema_version=SCHEMA_VERSION,
            id=turn_id,
            session_id=interaction.session_id,
            seq=len(list(store.iter_turns(interaction.session_id))),
            role="assistant",
            created_at=created_at,
            prose=prose,
            graph_id=graph.id,
            parent_turn_id=source_graph.turn_id,
            fork_of_node_id=None,
            provider="none",
        )
        completion = AgentPathCompletion(
            schema_version=SCHEMA_VERSION,
            id=new_ulid(),
            interaction_id=interaction.id,
            collaborator_id=collaborator.id,
            created_at=created_at,
            client_request_id=client_request_id,
            request_sha256=digest,
            session_id=interaction.session_id,
            source_graph_id=source_graph_id,
            source_node_id=source_node_id,
            graph_id=graph.id,
            turn_id=turn.id,
            model=reported_model,
            harness=reported_harness,
            warnings=warnings,
        )
        store.write_graph(graph)
        store.append_turn(turn)
        path = store.write_agent_path_completion(completion)
        store.update_session_head(
            interaction.session_id, graph_id=graph.id, turn_id=turn.id
        )
    store.log(
        "agent_bridge_append_path",
        collaborator_id=collaborator.id,
        interaction_id=interaction.id,
        session_id=interaction.session_id,
        graph_id=graph.id,
        source_graph_id=source_graph_id,
        source_node_id=source_node_id,
        completion_id=completion.id,
        path=str(path),
        warnings=list(warnings),
    )
    return completion_result(completion)
