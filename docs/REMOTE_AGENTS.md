# Existing agents on another machine

The SSH adapter connects Atlas to an existing **Hermes** or **OpenClaw**
installation. The agent can contribute a path or serve as the Spark guide.
The native installation, provider authentication, persona files and conversation
remain on that host. Atlas keeps the canonical store on its own machine.
This is an explicit private SSH connection, not a hosted/shared Atlas service.

The remote helper supports Python 3.11+ on Linux, macOS or WSL. Live acceptance
used Linux Atlas and both agents in Ubuntu WSL on another LAN PC: Hermes 0.21.0
(`245e4800`) and OpenClaw 2026.9.2 (`3928bad`). Native Windows remote execution
is not implemented. No duplicate agent installation is needed on the Atlas PC.

## Discover and connect from Workspace

Open **Workspace → Set up collaborators**. Atlas automatically checks installed
local CLIs when this screen opens; **Scan this PC again** refreshes it. Codex,
Claude Code, Grok, OpenCode and Prime Agent use their existing adapters. Discovery
also lists the configured default Hermes installation and named OpenClaw agents.
Common per-user executable directories are checked when the desktop PATH omits
them. Detection is read-only and calls no model. Choose **Connect** before Atlas
registers an agent; existing connections and selected roles are preserved.

Local Hermes/OpenClaw session adapters require a POSIX host. A Windows-native
installation can be detected but is not presented as connectable through that
adapter. The other five retain their existing Windows support and explicit WSL
fallback rules. Hermes is shown under its harness name; choose its display name
when connecting. OpenClaw supplies its configured agent identity. Display names
are labels, not a substitute for native persona context.

For another machine, expand **Add Remote Agent**:

1. Enter hostname/IP, SSH login, port, host type, and optionally the existing
   private-key path on the Atlas PC. Blank uses default keys or your SSH agent.
2. Choose **Check connection and find agents**. Atlas checks that one destination;
   it does not scan the LAN. A new host shows an Ed25519 fingerprint. Compare it
   with the host itself before selecting **Trust verified host**. Changed trusted
   keys stop the flow; they are never automatically replaced.
3. Select a discovered Hermes/OpenClaw agent, review its display and connection
   names, and connect it. Atlas copies its bundled stdlib helper and a private
   config to a new directory on that host, then checks the native CLI. A failed
   health check removes the registration; private setup files remain for diagnosis.
4. Assign a collaborator slot, guide role, or both in Workspace. The first model
   request starts a dedicated native conversation. No ordinary session is taken
   over, and no global native MCP configuration is edited.

Local connection configs and Atlas-specific `known_hosts` are stored beside the
harness registry under `connections/`. Remote helper/config/session receipts live
under `~/.local/share/atlas-of-threads/connections/<connection-id>/`. Retain these
session directories for continuity. The UI uses direct SSH settings and does not
load SSH config aliases/ProxyCommand; advanced manual configuration remains below.
Setup does not install native agents, copy credentials, sign in or change billing.

### Connection and firewall assistance

The form includes help before or after a connection check. Reachable-host checks
supply the Atlas PC's routed source IP. Rules target only that source and the
chosen SSH port; no rule exposes Atlas's web server or OpenClaw's Gateway.

Failures distinguish a refused service, unreachable host/port, unknown/changed
host key, authentication failure, and missing host runtime. Timeout alone does
not establish a firewall problem. Confirm host power, address, route, SSH service
and login first. Authentication failures explicitly direct users away from
firewall changes.

Guidance covers Ubuntu/Debian SSH service setup, existing UFW or firewalld rules,
macOS Remote Login, Windows Private-profile rules, and WSL's Hyper-V firewall.
WSL mirrored and NAT routing are explained separately; NAT requires an explicit
port proxy and may need its WSL IP refreshed after restart. Commands are shown
for review/copy on the host, with undo instructions. Atlas does not execute
firewall or administrator commands, disable protections, or modify WSL settings.

Firewall/network references: [Microsoft WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking)
and [Hyper-V firewall](https://learn.microsoft.com/en-us/windows/security/operating-system-security/network-security/windows-firewall/hyper-v-firewall).
Native inventory references: [OpenClaw agents](https://docs.openclaw.ai/cli/agents)
and [Hermes configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration/).

## Manual connection configuration

1. Establish normal key-based SSH and verify the host key independently.
2. Install this source checkout with `pip install -e .` on the Atlas machine.
3. Copy `src/thought_archaeology/adapters/remote_host.py` to a private directory
   on the remote host. This standalone helper uses only Python's standard library.
4. Create one private host config and state directory per connected agent. Use
   absolute paths appropriate to that machine; examples below are placeholders.

The v0.3.0 standalone application includes this adapter. Substitute
`atlas-of-threads adapter ssh` (Linux) or `AtlasOfThreadsMCP.exe adapter ssh`
(Windows) for `ta-harness-ssh`. Register that executable with the fixed arguments
`adapter`, `ssh`, `--config`, and the local connection-file path. The console
executable is required for Windows JSON stdio. SSH must be available on the Atlas
machine; no local Hermes/OpenClaw runtime is required.

Hermes host config:

```json
{
  "provider": "hermes",
  "display_name": "My Hermes agent",
  "model": "your-native-model",
  "command": ["/home/user/.local/bin/hermes"],
  "python": "/home/user/.hermes/hermes-agent/venv/bin/python",
  "runtime_root": "/home/user/.hermes/hermes-agent",
  "state_db": "/home/user/.hermes/state.db",
  "state_dir": "/home/user/.local/state/atlas/hermes"
}
```

OpenClaw host config:

```json
{
  "provider": "openclaw",
  "display_name": "My OpenClaw agent",
  "model": "provider/your-native-model",
  "command": ["/absolute/path/to/openclaw"],
  "agent_id": "main",
  "context_files": [
    "/home/user/.openclaw/workspace/IDENTITY.md",
    "/home/user/.openclaw/workspace/SOUL.md",
    "/home/user/.openclaw/workspace/USER.md"
  ],
  "state_dir": "/home/user/.local/state/atlas/openclaw"
}
```

Select existing files explicitly; at most eight files of 16,000 characters each.
They are refreshed on the remote host, supplied to its native runtime, and never
projected into a local Atlas memory directory. The OpenClaw restricted-session
bootstrap does not reliably include persona files: without this list the model
may name its underlying CLI instead of the configured agent. Other native
memory outside the supplied context is not guaranteed available.

Create a local connection config (it contains executable authority, not tokens):

```json
{
  "ssh_argv": ["ssh", "-i", "/home/user/.ssh/agent-key", "-o", "IdentitiesOnly=yes"],
  "host": "user@agent-host",
  "remote_command": [
    "python3", "/home/user/atlas/remote_host.py",
    "--config", "/home/user/atlas/hermes.json"
  ]
}
```

```sh
ta-harness-ssh --config /absolute/local/connection.json describe
ta --store /absolute/local/atlas mcp collaborator register \
  --name "My Hermes agent" --client-family hermes --scope atlas:read
ta --store /absolute/local/atlas harness register my-remote-agent \
  --adapter /absolute/local/bin/ta-harness-ssh \
  --arg=--config --arg=/absolute/local/connection.json \
  --collaborator COLLABORATOR_ID --session-only
```

Use `openclaw` as the client family for an OpenClaw registration. In Workspace,
assign a collaborator slot, the guide role, or both. Existing five-slot limits
apply; a guide-only agent consumes no collaborator slot. The host config selects
the model; describe reports that selection and responses report native serving
metadata. Global client model settings are not edited.

Hermes uses a dedicated CLI session, resolves a reserved empty toolset before
calling, and checks the native session's tool list/count. It reads only the final
public assistant message and model metadata from that session, excluding CLI
warnings and hidden reasoning. OpenClaw uses its authenticated loopback Gateway,
an operator-created private `subagent:` session key, a confirmed per-session
deny-all tool policy and no channel delivery. This key permits scoped restrictions;
the helper does not ask another agent to spawn a worker. Model selection is set
through `sessions.patch`, not backend-only `agent` override fields.

The saved local state identifies the remote session. The host owns the actual
transcript and serializes requests. Completed request receipts replay without
another model call. A disconnected, timed-out or failed request is left unresolved
and is not automatically rerun. Inspect its private receipt/native session before
issuing a new request; changing an ID is not proof that the prior call did nothing.
Retain state directories across restarts. Do not copy provider credentials.

## Remote MCP clients read the Atlas store

MCP stdio can travel back through an SSH Unix-socket forward. This keeps one
Atlas store and requires no HTTP server or inbound SSH login to the Atlas PC.
This optional route uses `socat` on the Atlas machine and the standalone
`adapters/stdio_socket.py` helper on the remote agent host.

1. Create private directories (mode `0700`) for both socket endpoints.
2. Write an executable local script whose sole command is the fixed, scoped
   MCP host, for example `exec /absolute/bin/ta --store /absolute/atlas mcp serve
   --collaborator COLLABORATOR_ID`.
3. Run these foreground processes on the Atlas PC, replacing placeholder paths:

```sh
socat UNIX-LISTEN:/private/local/atlas.sock,fork,mode=600 EXEC:/private/local/mcp-server
ssh -N -o BatchMode=yes -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes \
  -R /private/remote/atlas.sock:/private/local/atlas.sock user@agent-host
```

4. Generate/merge the normal client recipe with this command and argument list:

```json
{"command":"python3","args":["/private/remote/stdio_socket.py","/private/remote/atlas.sock"]}
```

Use the Hermes `mcp_servers` or OpenClaw `mcp.servers` wrapper documented in
[Agent onboarding](AGENT_ONBOARDING.md). Each endpoint fixes the local store and
collaborator scope; remote requests cannot select a different executable or store.
The SSH forward is available only while both foreground processes run. On
reconnect, remove a stale socket only after confirming no process listens on it.
Do not make the directories or sockets accessible to other OS users.

Live inbound acceptance also exercised both native agents with contribution and
memory-acknowledgement scopes. Each model created one Threadwalk/path, wrote the
exact completion candidate to a dedicated native memory note, read it back and
acknowledged it. A fresh native session recovered IDs from that note and replayed
the three original requests without changing any Atlas file bytes or mtimes.
The follow-up supplied the note path, not receipt IDs: this proves deliberate
file-memory retrieval, not automatic recall from every future conversation.

Hermes used process-local `register_mcp_servers` and its normal CLI, with only
file tools and the Atlas toolset selected. OpenClaw used `agent exec --config`
with separate retained run state and its existing credentials/plugins. The test
config was a sibling of the native config and used its supported `$include`,
leaving the ordinary Gateway and native global MCP configuration unchanged.
OpenClaw `agent exec` requires exclusive ownership of its run-state directory;
do not point it at a directory owned by the live Gateway. See the native
[Hermes MCP documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp/)
and [OpenClaw agent-exec documentation](https://docs.openclaw.ai/cli/agent#agent-exec).

These isolated configurations are acceptance fixtures; they are not permanent
MCP activation in the ordinary interactive clients. See
[compatibility results](MCP_COMPATIBILITY.md).
