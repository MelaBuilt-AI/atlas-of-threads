# MCP compatibility evidence

Recorded September 6, 2026. These are development-build checks, not a new public
release. Follow [Agent onboarding](AGENT_ONBOARDING.md) for generated configuration.

## What has been exercised

| Client | Version | Evidence | Limits |
|---|---|---|---|
| Codex | CLI 0.153.0 | Previously accepted native Windows source reads, attributed contributions, client-owned memory, restart and exact replays | New 0.153.4 Linux app-server probe cannot start in the development session's read-only Codex state directory; no new client acceptance claimed from that attempt |
| Claude Code | 2.1.259 | Linux client `mcp get` reports connected to the frozen Atlas executable using an isolated user configuration | This check establishes startup/discovery, not an agent memory workflow |
| Grok Build | 1.0.13 | Linux `mcp doctor`: executable found, process started, protocol `2025-11-25`, six tools, healthy | No new model-generated contribution or memory acceptance |
| OpenCode | 1.18.29 | Linux `mcp list` connects using the generated v1 configuration and frozen Atlas executable | v2 configuration is separately generated from current upstream documentation, not exercised with a v2 binary |
| Prime Agent | 0.9.1 | CLI loads the generated user configuration. Its installed kernel MCP transport discovers tools, reads status, contributes, reads back, acknowledges a synthetic client-file memory candidate, replays, and reloads/reconnects | Probe supplies the generated config through the kernel's host-config callback; no model turn or native Prime memory-store claim |
| OpenClaw | 2026.9.2 | Isolated Linux CLI `mcp probe` discovers six Atlas tools and resources without diagnostics | Agent runtime tool visibility/profile and memory behavior require a real agent session |
| Hermes Agent | 0.21.0, source `5106e939e0b32d3cd70a6acf33943fd2d9ab58d7` | Its actual MCP transport with SDK 2.0.0 loads generated YAML, discovers ten scoped tools, reads status, contributes, reads back, acknowledges a synthetic client-file memory candidate and replays | Tested through its transport class, not a model turn or a full Hermes persona/native-memory session |

Client checks used synthetic or absent stores and separate client configuration
directories. Existing provider authentication and real memory were not copied
or modified. Client health commands and direct client transports make no model
call. A synthetic client-file write proves the receipt protocol; it does not
prove any client's native memory feature or the identity of an existing persona.

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
| Outbound Atlas calls | Existing Claude, Codex, Grok, OpenCode, Prime Agent adapters; not inferred from inbound MCP discovery |
| Runtime resume | Existing adapter/client-specific behavior; stable Atlas IDs survive MCP reconnect |
| Approved memory projection | Existing tested Codex reverse route; not automatic for the other clients |
| Client-owned memory acknowledgement | Available with explicit scope; tested synthetic protocol and earlier real Codex loop |
| OpenClaw/Hermes personas | No credential extraction, persona migration, or automatic connection to an existing named runtime |
| In-app companion | Separate next slice; this pass does not implement the discussion panel |

Before claiming a new client/platform's complete lived-use acceptance, use its
actual agent session to read an existing thought, append an explicitly requested
path, reconnect and retrieve exact IDs. Test native memory separately if offered.
The published `v0.2.0` installers still lack this development bridge.
