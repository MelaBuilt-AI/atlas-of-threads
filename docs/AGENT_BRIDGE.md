# Atlas Agent Bridge

The Atlas Agent Bridge lets an external, memory-bearing agent enter the same
local Personal Atlas that the Atlas of Threads application uses. The transport
is local stdio MCP. It opens no port, performs no remote call, receives no
provider credential, and never publishes a Threadwalk.

Slice A is intentionally read-only. Slice B adds explicit local collaborator
registration, one private root, and one attributed child path. Slice C adds a
bounded memory candidate and an opaque client-owned acknowledgement. A
connected Codex harness can also bind that same collaborator identity to one
resumable session backed by a bounded projection of explicitly approved,
read-only memory files.

The development guide slice adds local thought search, bounded cited context,
and an explicit inbound question at an existing thought. It does not yet add an
in-app discussion panel, control the browser, or invoke a personal agent from
Atlas. It can support guidance in the connected agent's own client today.

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

Start with [Connect your agent](AGENT_ONBOARDING.md) for the seven client
recipes, permission choices, generated configuration, and a read-only connection
check. [Compatibility evidence](MCP_COMPATIBILITY.md) separates client discovery,
packaged contributions, and agent-owned memory acceptance.

Run the bridge against the same store used by Atlas:

```bash
ta --store /path/to/personal-atlas mcp serve
```

A Linux package built from this source accepts the same command:

```bash
atlas-of-threads --store /path/to/personal-atlas mcp serve
```

The released `v0.2.0` packages predate this bridge. New Windows development
installers include `AtlasOfThreadsMCP.exe`, a console-capable host alongside the
windowed desktop executable. Use the console host for registration, configuration,
checks, and `mcp serve`. Linux uses the same executable for desktop and stdio.

The process reads one UTF-8 JSON-RPC message per stdin line and writes only MCP
messages to stdout. Diagnostics go to stderr. It supports MCP protocol versions
`2025-11-25`, `2025-06-18`, `2025-03-26`, and `2024-11-05`, negotiating the
client's requested version when supported. The server explicitly configures
both standard text pipes as UTF-8, independent of the host's locale or code
page. This preserves Unicode tool descriptions, questions, and responses on
native Windows. For source checkpoint `89412c1`, which predates this fix,
launch the bridge with `python -X utf8 -m thought_archaeology.cli ...`;
without that workaround Codex may time out during `tools/list`.

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
same canonical reads plus local guide discovery:

| Tool | Input |
|---|---|
| `atlas_status` | `{}` |
| `list_threadwalks` | `{}` |
| `read_threadwalk` | `{ "session_id": "ULID" }` |
| `read_chamber` | `{ "graph_id": "ULID", "node_id": "ULID" }` |
| `search_thoughts` | `{ "query": "weight access", "kind": "rejected_alternative", "limit": 10 }`; optional `session_id` |
| `read_guide_context` | `{ "references": [{ "graph_id": "ULID", "node_id": "ULID" }] }` |

Every tool is marked read-only, non-destructive, idempotent, and closed-world.
Domain failures are returned as MCP tool errors; malformed protocol requests
remain JSON-RPC errors.

## Local guide workflow (development)

1. In the agent's own client, ask it to find relevant earlier thoughts. Search
   is literal, case-insensitive AND matching across thought text and session
   title; it is not semantic retrieval or an evidence-strength score. Query
   length is 1–300 characters, at most 12 distinct terms, and results are capped
   at 20. Narrow by session or thought kind when results are truncated.
2. Read cited context for 1–4 selected exact graph/node pairs. It returns the
   thought (up to 4,000 characters), up to 12 directly recorded relationships
   with bounded peer excerpts, and up to 12 evidence IDs/kinds/results. Every
   omission is flagged. Use `read_chamber` for further inspection. No whole
   graph prose, hidden reasoning, raw evidence artifact paths, or external
   memory is included by this tool.
3. The agent can discuss relevance and offer `atlas://chamber/...` citations
   and relative `#/g/.../n/...` links for the human to open in the local Atlas.
   This does not move the browser or send another request automatically. The
   client still owns its own memory; Atlas cannot claim that memory was read.
4. Only after the human asks for a contribution at a chosen thought, call
   `open_chamber_interaction` with `session_id`, `graph_id`, `node_id`,
   `question`, `question_origin` (`human_instruction` or `agent_proposal`), and
   stable `client_request_id`. Both `atlas:read` and `atlas:write:path` are
   required. This adds one private interaction receipt, plus the normal bridge
   lock if absent; it creates no graph or turn, moves no session head, and never
   queues the outbound watcher. Mere discussion requires no write operation.
5. Use the returned response contract with `append_agent_path` to explicitly
   append one attributed child. The receipt pins the original source even if
   another process advances the head. Exact retries reuse the same interaction
   or path; changed content with the same request ID is rejected. The question
   and whether it was human-instructed or agent-proposed remain in provenance.

The optional interaction `action` field distinguishes opening at an existing
thought from `begin_threadwalk`; old receipts without the field keep their
original meaning. The historical `root_*` receipt fields designate the pinned
source for both actions and do not imply that a new root was created.

Read-only clients now see six tools. Clients with all read, threadwalk, path,
and memory-ack scopes see ten. Reconnect/re-list tools after upgrading; older
four/six-tool acceptance notes describe the earlier implementation. No scope
is automatically added to an existing collaborator. The tested native Windows
Codex memory loop and UTF-8 correction have passed acceptance. Other clients'
memory and the callable companion remain separate; automated protocol checks
do not establish original-runtime continuity or external-memory writes.

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

## Connect one named Codex or OpenCode agent in both directions

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
be a directory the person intentionally approves for read-only recall. Name at
least one exact UTF-8 text file inside that root with repeated `--memory-file`
options; absolute paths, parent traversal, missing files, duplicates, more than
eight files, files larger than 64 KiB, and projections larger than 192 KiB are
rejected:

```bash
ta --store /path/to/personal-atlas harness register indy \
  --adapter "$(command -v ta-harness-codex)" \
  --collaborator COLLABORATOR_ID \
  --memory-root /path/to/agent-workspace \
  --memory-file AGENTS.md \
  --memory-file index.md \
  --memory-file handoffs/latest-handoff.md \
  --model gpt-5.6-sol \
  --default

ta --store /path/to/personal-atlas harness doctor indy
```

The adapter reads only those approved files, revalidates that they remain
inside the root, and projects their current text into each request. Codex runs
from a temporary directory with project-rule discovery disabled, so it does not
need shell access to the vault. This is required for consistent behavior on
native Windows, where Codex CLI `0.153.0` physically rejected PowerShell and
cmd file reads under its `read-only`/`never` execution policy. Atlas does not
grant workspace-write, danger-full-access, or full-disk-read permission as a
workaround.

The first Atlas question starts one persisted Codex session; later questions
resume the exact session ID. The current approved projection is authoritative
over stale recollection already in that session. Ordinary Codex user
configuration is ignored so unrelated MCP servers cannot re-enter Atlas
through the outbound path. Codex remains in its read-only sandbox and is
instructed not to inspect other files, browse, modify files, make network calls,
or delegate. The private session-state file
lives beside the user-owned harness registry under `agent-sessions/`, not in
the Personal Atlas store, and is mode `0600`.

Atlas records the stable collaborator ID and display name separately from the
model actually used for each answer. Workspace shows the agent name, model,
and whether its resumable memory session has started. This supports asking a
named agent questions from Atlas based on the context available to that agent;
it records the visible answer and structured story graph, never hidden
chain-of-thought or a claim about the model's private internal state.

### OpenCode return route

The same registration and approved-file contract works with
`ta-harness-opencode`. Reuse the existing inbound collaborator ID, select the
agent's actual memory files, and pin its provider/model:

```bash
ta --store /path/to/personal-atlas harness register my-opencode \
  --adapter /path/to/ta-harness-opencode \
  --collaborator COLLABORATOR_ID \
  --memory-root /path/to/agent-memory \
  --memory-file AGENTS.md \
  --memory-file Home.md \
  --memory-file wiki/Entities/agent.md \
  --memory-file wiki/Daily/latest.md \
  --model openai/your-selected-model \
  --default

ta --store /path/to/personal-atlas harness doctor my-opencode
```

Set `TA_OPENCODE_VARIANT` in the Atlas launch environment if the chosen model
uses an explicit variant. `TA_HARNESS_MODEL` from the saved registration takes
precedence over the ordinary OpenCode model setting. This route is exercised
with OpenCode 1.18.29 on Linux; native Windows and v2 return calls have not been
live-accepted.

The first return call starts a dedicated OpenCode conversation. Later calls,
including questions from different Atlas Threadwalks, pass its exact saved
`--session` ID and refresh the approved memory projection. This does not take
over the user's existing interactive conversation. No memory files are written
by the return route. The connected session is retained; ordinary unbound
OpenCode calls still delete their transient sessions.

OpenCode runs in a private persistent `.workspace` directory beside its session
state with project configuration disabled,
`--pure`, sharing disabled, and all tool permissions denied. Configured v1 MCP
servers are explicitly disabled for that invocation to prevent re-entry into
Atlas. Its provider-owned authentication is retained. The adapter accepts only
public response text, excludes commentary/reasoning events, rejects tool calls,
and verifies the serving model/variant through a bounded CLI metadata query
before returning the answer. The working directory persists because OpenCode
requires its original session directory to exist on resume. A failed
resume never silently falls back to a fresh conversation or deletes the saved
session. The same private state-file binding and memory-size limits as Codex
apply.

Use the interactive inbound client for deliberate native-memory writes and
acknowledgements. The return adapter supplies read-only recall to Atlas; it
does not implement a new memory writer or the planned prose companion panel.

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

## Agent Spark — local guide discussion

Agent roles are independent. Workspace shows five collaborator slots with the
agent name and model, followed by **Agent as Guide**. Assign either role or both
for an already registered adapter; guide assignment requires its advertised
`discuss` capability. OpenCode is the first supported prose adapter. Registration
and provider authentication keep using the existing setup; selecting a guide
does not grant new files, tools, memory-write permissions, or MCP scopes.

A guide appears as a glowing 3D orb in the upper-right shoulder or C-overhead view.
Its gently pulsing cyan point light illuminates nearby surfaces and casts scene
shadows. The core casts shadows too, with a soft floor shadow keeping it grounded
where its own light fills them. In overhead view it stays near the floor while
preserving its apparent size. Click the
orb or press **G** to open **Agent Spark**, a separate 2D radial HUD linked by an
animated neural tether. Its gentle positional lag and hover continue under the pointer.
Curved four-sided ring segments preserve a circular silhouette; categories reveal
a concentric outer row. A category stays highlighted while open; clicking it
again closes it, with no Back buttons in submenus. Labels follow the arcs.
The inner aperture holds the agent name/model, selected thought, larger message
box, Send, and spaced status text. Left/right selects; Enter/up activates;
down returns to the main ring; Escape backs out or closes. G closes outside text
entry. Tab moves among the ring, transcript, and composer; Ctrl+Enter sends from
the composer. These keys do not traverse the underlying chamber while open.
Quiet synthesized sparkle/click cues share the existing master sound controls,
and Spark has a separate mute. Reduced motion suppresses drift and bezel motion.

The private persisted prose conversation appears outside the circle: the question
materializes in a sparking, gently hovering bubble to its right, followed by the
reply below. Trails connect the question to Send and the orb, and the reply to
the orb. History selects earlier/later/latest exchanges without another model
call. Long content scrolls within its own bubble rather than in the center. Each submitted question
pins exact session, graph, and thought IDs; source buttons let the user reselect
an earlier response's thought. Moving later does not retarget an in-flight call.
Handoffs prepare an editable collaborator question or an agent-assisted Field
Note/memory draft; copying includes the exact source link. Nothing is promoted,
queued to another collaborator, or written to native memory without a further
explicit user action. Draft Field Notes must still use the existing reviewed
Field Note flow; drafts are not independently human-authored evidence.

OpenCode `discuss` uses the tested return route, approved fresh memory projection,
and the same persistent conversation as its collaborator role, but asks for
ordinary prose instead of a thought-graph. A process lock prevents simultaneous
calls from altering the same runtime session. It retains the tool-denied and
MCP-disabled outbound configuration. Other adapters can adopt `discuss` without
changing the inbound MCP contribution contract.

The local JSON API adds `GET /api/guide`, `POST /api/agent/roles`,
`POST /api/guide/discuss`, and `POST /api/guide/clear`. Writes require the existing
same-origin local JSON checks. Role assignment takes `harness`, `collaborator`
and `guide` booleans. Discussion takes a client `request_id`, `prompt` (1–8,000
characters), `graph_id`, and `node_id`; returns a pending record immediately and
is polled through GET. Same-ID/same-content requests reuse the record; conflicting
reuse fails. Completed records include the actual reported model, visible prose,
and pinned source. Failures and interrupted responses remain visible. Restart
never silently reruns a model call.

Only visible questions, replies, statuses, attribution and exact references are
saved under private `guide-discussions/<harness>.json` in the Personal Atlas,
separate from canonical graphs, turns, and agent-bridge receipts. Recent visible
turns supply bounded conversational context; raw projected notes, credentials,
and reasoning events are not saved there. Clear has an explicit UI review and
clears only this local discussion; copied artifacts, native memory, and the
provider-owned persistent conversation remain separate. No public release or
native Windows return acceptance is implied by this local implementation.
