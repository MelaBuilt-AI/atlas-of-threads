# MCP compatibility evidence

Recorded September 6, 2026. These are development-build checks, not a new public
release. Follow [Agent onboarding](AGENT_ONBOARDING.md) for generated configuration.

## What has been exercised

| Client | Version | Evidence | Limits |
|---|---|---|---|
| Codex | CLI 0.153.0 | Previously accepted native Windows source reads, attributed contributions, client-owned memory, restart and exact replays | New 0.153.4 Linux app-server probe cannot start in the development session's read-only Codex state directory; no new client acceptance claimed from that attempt |
| Claude Code | 2.1.259 | Linux client `mcp get` reports connected to the frozen Atlas executable using an isolated user configuration | This check establishes startup/discovery, not an agent memory workflow |
| Grok Build | 1.0.13 | Linux `mcp doctor`: executable found, process started, protocol `2025-11-25`, six tools, healthy | No new model-generated contribution or memory acceptance |
| OpenCode | 1.18.29 | Linux inbound contribution, native Markdown save/readback/acknowledgement and fresh-session recall; connected return adapter answers from approved memory and recalls a conversation-only marker across Threadwalks using its saved runtime session | Return calls use a dedicated conversation and read-only memory projection. Native Windows and v2 return calls are not live-accepted |
| Prime Agent | 0.9.1 | CLI loads the generated user configuration. Its installed kernel MCP transport discovers tools, reads status, contributes, reads back, acknowledges a synthetic client-file memory candidate, replays, and reloads/reconnects | Probe supplies the generated config through the kernel's host-config callback; no model turn or native Prime memory-store claim |
| OpenClaw | 2026.9.2 | Isolated Linux CLI `mcp probe` discovers six Atlas tools and resources without diagnostics | Agent runtime tool visibility/profile and memory behavior require a real agent session |
| Hermes Agent | 0.21.0, source `5106e939e0b32d3cd70a6acf33943fd2d9ab58d7` | Its actual MCP transport with SDK 2.0.0 loads generated YAML, discovers ten scoped tools, reads status, contributes, reads back, acknowledges a synthetic client-file memory candidate and replays | Tested through its transport class, not a model turn or a full Hermes persona/native-memory session |

Transport checks used synthetic or absent stores and separate client configuration
directories. Client health commands and direct client transports make no model
call. A synthetic client-file write proves the receipt protocol; it does not
prove any client's native memory feature or the identity of an existing persona.

The subsequent OpenCode lived-use test used the existing client's authentication
and selected model, a fork of its saved conversation, a runtime MCP configuration
overlay, and a separate synthetic Atlas store. The agent itself read its own
Markdown second brain, created one private Threadwalk and one three-node path,
saved the exact compact completion candidate in a new memory note, read it back,
and acknowledged it. A new session with no conversation continuation recovered
the exact IDs from that note before calling the Atlas read tools. Exact
begin/path/ack arguments saved by the agent also replayed through fresh MCP
processes without changing store file bytes, modification times, or counts
(one Threadwalk, two graphs). The original conversation and project bookmark
were preserved; the new memory note and its index/log entries were intentional
native-memory changes. Global client configuration was not edited. This proves
the observed inbound file-memory loop, not automatic future recall.

The subsequent connected OpenCode return-adapter test used the same collaborator
identity and selected provider/model/variant. It answered from seven approved
memory files, then recovered a conversation-only marker in a separate Atlas
Threadwalk after an adapter-process restart. The marker was absent from the
second request's envelope and approved files. The exact saved OpenCode session
was reused, no runtime tools were called, and all source memory paths/hashes
remained unchanged by the return calls. The packaged desktop exposes the
configured external adapter as selected and memory-ready; its server starts
and quits cleanly. This uses a source-backed external adapter, not a new bundled
release.

Live testing found that OpenCode needs its original session directory on resume,
so connected calls retain a private workspace beside the state file. Serving
model verification uses bounded CLI database metadata instead of a whole-session
export, which can truncate on stdout as the conversation grows. The prompt
explicitly permits prior public conversation turns and gives refreshed approved
files precedence over stale recollections. Failed development attempts remain
in the private test ledger; they are not successful acceptance evidence.

## Packaged host verification

The standalone Linux executable and native Windows console executable are
exercised by `packaging/smoke_mcp.py`, which imports no Atlas source. It drives
only the executable passed to it and removes its temporary synthetic store:

- read-only initialization, status, tools, and shutdown without creating a store;
- collaborator registration, including a Unicode display name;
- `2025-11-25`, `2025-06-18`, `2025-03-26`, and `2024-11-05` negotiation;
- exact Unicode questions, node text, and read-back with `PYTHONUTF8=0` and
  `PYTHONIOENCODING=cp1252:strict`, without `-X utf8`;
- one private root and attributed child, client-file memory acknowledgement,
  and exact begin/append/ack retries from fresh processes;
- unchanged file bytes and modification times after read/replay checks,
  unchanged counts (one Threadwalk, two graphs), and no outbound harness/publication;
- process exit on closed input, including the frozen host's child processes.

Windows validation uses native Python 3.11.9 and real Windows executables through
WSL SSH, not Linux Python emulating Windows. The Inno Setup installer installs
both executables; the installed console host is exercised with the same smoke,
and its hash is compared with the built host. GUI startup is checked separately.
The package workflow repeats console and installed-host checks on Windows and
the standalone check on Linux. Local Linux builds target the local distribution;
the existing Ubuntu 22.04 workflow remains the portable release-build route.

MCP is served over local stdio using the listed handshake-era versions. Newer
clients must permit that negotiation; this build does not claim the modern-only
`2026-07-28` protocol, HTTP transport, or remote/cloud access. Hermes SDK 2.0.0
successfully negotiates the existing handshake with this server.

## Capability boundaries

| Capability | Scope of support |
|---|---|
| Inbound local MCP | Seven client recipes; platform/client evidence above |
| Outbound Atlas calls | Claude, Codex, Grok, OpenCode, Prime Agent; source SSH routes for existing Hermes/OpenClaw with separate live evidence below |
| Runtime resume | Existing adapter/client-specific behavior; stable Atlas IDs survive MCP reconnect |
| Approved memory projection | Tested Codex and Linux OpenCode return routes with dedicated saved sessions and explicitly approved files; not automatic for the other clients |
| Client-owned memory acknowledgement | Available with explicit scope; tested synthetic protocol, earlier real Codex loop, and OpenCode native Markdown save/readback plus fresh-session recall |
| OpenClaw/Hermes personas | Explicit SSH config connects existing remote native sessions; no credential extraction or persona migration; selected OpenClaw persona files refresh on the host |
| In-app companion | Agent Spark private prose discussion; OpenCode and the source remote Hermes/OpenClaw adapters support guide calls |

Linux OpenCode 1.18.29 live role acceptance (2026-09-07) exercised a GPT-5.6
Terra collaborator and a separate GPT-6 Astra guide, both with the `high`
variant. The collaborator created a synthetic path; the guide inspected its
exact thought, identified the other model's authorship, and supplied its own
critique without changing canonical Atlas files. After an application restart,
both roles, model settings, distinct runtime sessions and guide history persisted.
In a new Threadwalk, the collaborator recalled its earlier conversation marker
without receiving it in the new inquiry or approved memory file, and reported
the separate guide-only marker unavailable. The guide recovered its own marker
from private discussion context. Native guide-memory files remained unchanged.
This verifies this Linux arrangement; native Windows and OpenCode v2 return/guide
acceptance remain separate. Guide recall here includes the supplied persisted
discussion history, so it is not evidence of runtime-only recall.

## Remote Hermes and OpenClaw acceptance — September 7

Linux Atlas called an existing Hermes 0.21.0 (`245e4800`) and OpenClaw 2026.9.2
(`3928bad`) on another PC's Ubuntu WSL through verified key-based SSH.
Both produced compiled, attributed paths using GPT-6 Astra, answered as guides,
and recalled separate conversation-only markers and their earlier success
conditions in fresh Threadwalks after adapter-process restart. Final paths
correctly distinguished the native persona from the underlying runtime.
Saved native session IDs were unchanged, and each guide call left canonical
Atlas files unchanged. Seven snapshotted native identity/memory files remained
byte-identical. This is bounded file/session evidence, not a native memory-write
or arbitrary future-recall claim.

Hermes's native metadata confirmed zero tool calls and an empty tool list. Its
public final assistant record avoids a CLI warning being included in prose.
OpenClaw confirmed its per-session deny-all tool policy. Its restricted session
initially lacked persona context and named its underlying Codex runtime;
refreshing the explicitly selected native IDENTITY/SOUL/USER files on the remote
host corrected that. Gateway-rejected backend-only fields were removed, with
model selection moved to the public session-patch operation. Failed development
requests remain separate from successful acceptance results.

Inbound read-only MCP used SSH-forwarded private Unix sockets and fixed local
store/collaborator commands. Hermes's installed MCP transport discovered six
tools and read status/Threadwalks; OpenClaw's CLI probe discovered six tools plus
resources without diagnostics. No native global MCP config was changed, and no
model-driven inbound contribution or native memory save/acknowledgement is
claimed. These are source adapters; remote native Windows and packaged remote
onboarding are not accepted. [Setup and boundaries](REMOTE_AGENTS.md).

Before claiming a new client/platform's complete lived-use acceptance, use its
actual agent session to read an existing thought, append an explicitly requested
path, reconnect and retrieve exact IDs. Test native memory separately if offered.
Atlas v0.3.0 includes this bridge. The dated checks below distinguish live
client acceptance from isolated package smoke tests.

### Native inbound memory loop accepted

A subsequent live test used process-local Hermes MCP registration and OpenClaw's
isolated `agent exec --config` path with the existing installations, native
credentials and selected GPT-6 Astra. Each model created exactly one private
synthetic Threadwalk and one attributed path, read it back, saved the exact
completion memory candidate in its own dedicated native Markdown note, read the
note back and acknowledged the receipt. Existing identity/core-memory files were
unchanged; the two new notes were deliberate, authorized test writes.

Each fresh native session then read only its named memory note and the MCP host,
recovered the receipt/graph IDs without receiving those IDs in its prompt, and
replayed the saved begin/path/acknowledgement arguments using their original
request IDs. All three replays returned the original IDs. Independent snapshots
confirmed unchanged bytes and modification times for every Atlas store file,
with one Threadwalk, two graphs and one acknowledgement per agent. Native notes'
completion candidates exactly match the canonical receipts. This establishes
explicit native file-memory retrieval; it does not promise automatic retrieval
without the note path or acceptance of every other native memory backend.

Hermes's fresh session was distinct and used native file/MCP tools. OpenClaw's
fresh invocation had separate retained state, a different native session ID and
six successful read/replay calls with no file writes. Its ordinary Gateway and
native global MCP configuration were not changed. The earlier discovery-only
limits above are superseded for this isolated model-driven trial, not for
permanent activation in the agents' ordinary interactive clients.

The development package now includes `adapter ssh`. A frozen-application smoke
exercises describe, contribution and guide dispatch using a synthetic SSH
transport and Unicode input. The packaging workflow runs this beside MCP smoke
on Linux, Windows and the installed Windows console executable. It makes no
model call or credential claim; live LAN acceptance remains separately recorded.
