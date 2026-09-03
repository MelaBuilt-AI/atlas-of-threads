# Atlas Agent Bridge

The Atlas Agent Bridge lets an external, memory-bearing agent enter the same
local Personal Atlas that the Atlas of Threads application uses. The transport
is local stdio MCP. It opens no port, performs no remote call, receives no
provider credential, and never publishes a Threadwalk.

The first implemented slice is intentionally read-only. It proves that an MCP
client can discover exact local Threadwalk and chamber context without creating
or modifying any Atlas artifact. Inbound collaboration writes and the memory
receipt handshake remain subsequent slices.

## Direction and recursion boundary

Atlas has two distinct collaboration directions:

```text
Atlas -> registered harness -> model -> Atlas continuation
agent -> MCP -> Atlas read or attributed contribution
```

One action has one initiator. The inbound MCP bridge does not enqueue an Atlas
continuation or invoke a registered harness. That boundary prevents an agent
from silently calling itself through Atlas.

## Slice A server

Run the bridge against the same store used by Atlas:

```bash
ta --store /path/to/personal-atlas mcp serve
```

A Linux package built from this source accepts the same command:

```bash
atlas-of-threads --store /path/to/personal-atlas mcp serve
```

The released `v0.2.0` packages predate this bridge. The Windows desktop
executable is also a windowed application and is not yet a supported stdio
host. Windows packaging must add a console-capable bridge entry point before
Agent Bridge compatibility is claimed for the installer.

The process reads one UTF-8 JSON-RPC message per stdin line and writes only MCP
messages to stdout. Diagnostics go to stderr. It supports MCP protocol versions
`2025-11-25`, `2025-06-18`, `2025-03-26`, and `2024-11-05`, negotiating the
client's requested version when supported.

Server instructions establish these rules for the client:

- check status before assuming a Personal Atlas exists;
- use stable Atlas IDs when reading exact context;
- treat reads as private local inspection, never publication;
- do not request credentials, hidden chain-of-thought, or unrelated memory;
- do not imply that Slice A has write tools.

## Resources

| URI | Meaning |
|---|---|
| `atlas://status` | Application, schema, bridge, and store readiness |
| `atlas://threadwalks` | Local Threadwalk IDs and entry chambers |
| `atlas://threadwalk/{session_id}` | One complete server-authored generation lineage |
| `atlas://chamber/{graph_id}/{node_id}` | One thought and its recorded relations |

`resources/list` returns status, the Threadwalk list, and one resource for each
current Threadwalk. `resources/templates/list` advertises the parameterized
Threadwalk and chamber forms. Resource contents are canonical compact JSON.

The bridge reuses the same server-authored payloads as the local application.
It does not expose `ThoughtGraph.hidden_reasoning`, raw provider credentials, or
arbitrary filesystem paths.

## Read-only tools

Some clients use tools more consistently than resources, so Slice A mirrors the
same canonical reads as four tools:

| Tool | Input |
|---|---|
| `atlas_status` | `{}` |
| `list_threadwalks` | `{}` |
| `read_threadwalk` | `{ "session_id": "ULID" }` |
| `read_chamber` | `{ "graph_id": "ULID", "node_id": "ULID" }` |

Every tool is marked read-only, non-destructive, idempotent, and closed-world.
Domain failures are returned as MCP tool errors; malformed protocol requests
remain JSON-RPC errors.

## Codex reference configuration

Codex CLI, the ChatGPT desktop app, and the Codex IDE extension share MCP
configuration on the same host. For a source installation:

```bash
codex mcp add atlas-of-threads -- ta --store /path/to/personal-atlas mcp serve
```

For the installed Linux binary, replace the command after `--` with its exact
installed path and the same arguments. `codex mcp list` shows the configured
server, and `/mcp` shows it in the Codex terminal UI.

Do not add Atlas to a person's client configuration without their explicit
approval. Slice A does not need environment-carried tokens or OAuth.

## Frozen inbound write contract

The names and boundaries below are reserved for the next implementation slices;
they are not exposed by Slice A.

### `begin_threadwalk`

Required input:

- `seed`: the exact question, topic, or statement;
- `seed_origin`: `human_instruction` or `agent_proposal`;
- `client_request_id`: caller-created idempotency key.

Optional input: `title`.

It will create one private root and one open inbound collaboration interaction.
It must not publish or enqueue the outbound harness watcher.

### `append_agent_path`

Required input:

- open `interaction_id`;
- exact `source_graph_id` and `source_node_id`;
- final user-visible `prose`;
- a structured `thought_graph` with `nodes` and `edges`;
- caller-created `client_request_id`.

Optional input: actual `model` and harness metadata when the client can report
them. The graph will pass through Atlas's existing compiler and validation path.
Hidden chain-of-thought and credentials are never accepted.

### `acknowledge_memory_receipt`

Required input: Atlas `receipt_id`. Optional input: one opaque external-memory
reference. Atlas records only the client's acknowledgement and never reads or
mutates the external second brain.

The write slices require a distinct inbound collaborator registry, explicit
`atlas:read`, `atlas:write:threadwalk`, `atlas:write:path`, and
`atlas:memory:ack` scopes, immutable interaction receipts, and idempotency keyed
by collaborator plus `client_request_id`. Publication remains a separate future
scope and cannot be implicit.

## Acceptance boundary

Slice A is complete when a supported client can initialize over stdio, list and
read a real isolated Personal Atlas, recover exact stable IDs, and leave every
file byte and modification time unchanged. No account, network identity,
publication, continuation request, collaborator worker, or memory write may be
created.

The full Agent Bridge is not accepted until later slices add one private root,
one attributed child path, duplicate-safe retries, append-only receipts, a
client-owned second-brain acknowledgement, restart persistence, and physical
client testing.
