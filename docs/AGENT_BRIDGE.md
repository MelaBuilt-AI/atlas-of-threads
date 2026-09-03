# Atlas Agent Bridge

The Atlas Agent Bridge lets an external, memory-bearing agent enter the same
local Personal Atlas that the Atlas of Threads application uses. The transport
is local stdio MCP. It opens no port, performs no remote call, receives no
provider credential, and never publishes a Threadwalk.

Slice A is intentionally read-only. Slice B adds explicit local collaborator
registration, one private root, and one attributed child path. Slice C adds a
bounded memory candidate and an opaque client-owned acknowledgement. A
connected Codex harness can also bind that same collaborator identity to one
resumable, read-only session in a user-approved memory workspace.

## Direction and recursion boundary

Atlas has two distinct collaboration directions:

```text
Atlas -> registered harness -> model -> Atlas continuation
agent -> MCP -> Atlas read or attributed contribution
```

One action has one initiator. The inbound MCP bridge does not enqueue an Atlas
continuation or invoke a registered harness. That boundary prevents an agent
from silently calling itself through Atlas.

## Server modes

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

The command above remains read-only. To authorize Slice B, register a distinct
inbound collaborator in the same store:

```bash
ta --store /path/to/personal-atlas mcp collaborator register \
  --name Codex \
  --client-family codex \
  --scope atlas:read \
  --scope atlas:write:threadwalk \
  --scope atlas:write:path
```

The command returns an immutable collaborator record and ID. Start the scoped
server with that exact ID:

```bash
ta --store /path/to/personal-atlas mcp serve --collaborator COLLABORATOR_ID
```

Registration is a local human-approved CLI action; an MCP client cannot
self-register or expand its own scopes. Grant `atlas:memory:ack` only when the
client will preserve the returned memory candidate in its own second brain.
There is no publication scope.

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

For the authorized Slice B server, use a separately named client entry while
testing and append the registered identity:

```bash
codex mcp add atlas-of-threads-write -- ta --store /path/to/personal-atlas \
  mcp serve --collaborator COLLABORATOR_ID
```

For the installed Linux binary, replace the command after `--` with its exact
installed path and the same arguments. `codex mcp list` shows the configured
server, and `/mcp` shows it in the Codex terminal UI.

Do not add Atlas to a person's client configuration without their explicit
approval. Slice A does not need environment-carried tokens or OAuth.

## Slice B inbound write contract

The tools below are exposed only when the selected collaborator has their
matching scope. Both are append-only, private, non-destructive, idempotent, and
closed-world MCP tools.

### `begin_threadwalk`

Required input:

- `seed`: the exact question, topic, or statement;
- `seed_origin`: `human_instruction` or `agent_proposal`;
- `client_request_id`: caller-created idempotency key.

Optional input: `title`.

It creates one private root and one immutable open inbound interaction receipt.
The root node and turn preserve whether the seed was a human instruction or an
agent proposal. It does not publish or enqueue the outbound harness watcher.

### `append_agent_path`

Required input:

- open `interaction_id`;
- exact `source_graph_id` and `source_node_id`;
- final user-visible `prose`;
- a structured `thought_graph` with `nodes` and `edges`;
- caller-created `client_request_id`.

Optional input: public `model` and harness name/version metadata when the client
can report them. The graph passes through Atlas's existing compiler and
validation path. Atlas records `provider: none` for its own execution because
the inbound client—not an Atlas provider adapter—ran the model; the reported
provider and model remain in Agent Bridge provenance. Hidden chain-of-thought,
credential fields, and unrecognized graph fields are rejected.

Every mutation requires a caller-created `client_request_id`. Repeating the
same key with the same canonical content returns the original receipt and IDs.
Repeating it with different content fails closed. Keys are scoped to the
registered collaborator and persist across server restarts.

Inbound interactions and completions live under the store's `agent-bridge/`
ledger, separate from `continuations/`. Consequently the outbound watcher never
sees or invokes an inbound MCP request.

## Slice C memory contract

`begin_threadwalk` and `append_agent_path` return a compact
`memory_candidate`. It contains the collaborator identity, stable Atlas IDs,
private visibility, publication state, a bounded Threadwalk subject, and a
short user-visible action summary.
It deliberately omits the full seed/prose, hidden reasoning, credentials,
temporary chatter, and external memory contents.

### `acknowledge_memory_receipt`

Required input: Atlas `receipt_id` and `client_request_id`. Optional input: one
opaque `external_memory_ref` of at most 500 characters. Atlas records only the
client's acknowledgement and never reads or mutates the external second brain.
An exact retry returns the original acknowledgement; conflicting reuse fails
closed. A second acknowledgement of the same receipt is rejected.

The tool appears only for a collaborator with `atlas:memory:ack`. Publication
remains a separate future capability and cannot be implicit.

## Connect one named Codex agent in both directions

First register the stable collaborator identity with the inbound scopes the
person approves:

```bash
ta --store /path/to/personal-atlas mcp collaborator register \
  --name Indy \
  --client-family codex \
  --scope atlas:read \
  --scope atlas:write:threadwalk \
  --scope atlas:write:path \
  --scope atlas:memory:ack
```

Then bind that returned ID to a distinct outbound harness. The memory root must
be a directory the person intentionally approves for read-only recall:

```bash
ta --store /path/to/personal-atlas harness register indy \
  --adapter "$(command -v ta-harness-codex)" \
  --collaborator COLLABORATOR_ID \
  --memory-root /path/to/agent-workspace \
  --model gpt-5.6-sol \
  --default

ta --store /path/to/personal-atlas harness doctor indy
```

The first Atlas question starts one persisted Codex session in that workspace;
later questions resume the exact session ID. Codex loads workspace guidance,
including `AGENTS.md`, and can read durable memory the person placed inside the
approved root. It ignores the ordinary Codex user configuration so unrelated
MCP servers cannot re-enter Atlas through the outbound path. It runs in a
read-only sandbox and is instructed not to browse, modify files, make network
calls, or delegate. The private session-state file
lives beside the user-owned harness registry under `agent-sessions/`, not in
the Personal Atlas store, and is mode `0600`.

Atlas records the stable collaborator ID and display name separately from the
model actually used for each answer. Workspace shows the agent name, model,
and whether its resumable memory session has started. This supports asking a
named agent questions from Atlas based on the context available to that agent;
it records the visible answer and structured story graph, never hidden
chain-of-thought or a claim about the model's private internal state.

## Acceptance boundary

Slice A is complete when a supported client can initialize over stdio, list and
read a real isolated Personal Atlas, recover exact stable IDs, and leave every
file byte and modification time unchanged. No account, network identity,
publication, continuation request, collaborator worker, or memory write may be
created.

Slice B is complete when a physically configured client creates exactly one
private root and one attributed child, retrying both calls without duplicates,
and inspection confirms stable provenance, no continuation request, no network
call, and no publication artifact. Slice C is source-complete when memory
candidates and acknowledgements pass local verification. The full Agent Bridge
is not live-accepted until a physically configured client preserves a candidate
in its own second brain, acknowledges it, reconnects, and recovers the stable
receipt and Threadwalk IDs.
