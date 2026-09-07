# Connect your agent to your Personal Atlas

This development build provides local MCP connections for **Codex, Claude Code,
Grok Build, OpenCode, Prime Agent, OpenClaw, and Hermes Agent**. The published
`v0.2.0` installers predate MCP; use a build containing the bridge.

Your agent's client starts Atlas's stdio process. Atlas does not install a
provider, sign you in, or open a network listener. Use the same OS environment
and Personal Atlas store as your client. A remote/cloud-only agent cannot spawn
an executable on your PC through this configuration.

## 1. Find the executable and your store

On **Windows**, this build's installer includes both the desktop application
and `AtlasOfThreadsMCP.exe`. Use the latter for every command below. In PowerShell:

```powershell
$atlas = "$env:LOCALAPPDATA\Programs\Atlas of Threads\AtlasOfThreadsMCP.exe"
$store = "$env:LOCALAPPDATA\MelaBuilt AI\Atlas of Threads\Personal Atlas"
& $atlas --store $store mcp check
```

On **Linux**, the installed application is also the MCP executable:

```bash
atlas="$HOME/.local/share/atlas-of-threads/atlas-of-threads"
store="$HOME/.local/share/atlas-of-threads/personal-atlas"
"$atlas" --store "$store" mcp check
```

If you installed elsewhere, use those paths. If Atlas was launched with a
custom `--store`, use that exact store. `mcp check` reports readiness, graph and
Threadwalk counts, advertised tools, and clean process shutdown. It makes no
writes and calls no model. An empty or missing store is reported honestly;
compare the counts with your Atlas before giving an agent access.

Source installations can substitute the editable installation's `ta` command
or `python -m thought_archaeology.cli`. Generated source configuration points
to that Python interpreter, so retain its environment. No UTF-8 launch flag
is needed. Packaged connections require neither Python nor an activated venv.

## 2. Choose the agent and permissions

Start read-only: omit `--collaborator` in the next step. It exposes status,
Threadwalk/chamber reads, local search, and cited guide context.

For attributed contributions, explicitly register one collaborator per agent.
Example for Hermes on Windows (replace the name/client family for your agent):

```powershell
& $atlas --store $store mcp collaborator register --name "My Hermes agent" --client-family hermes --scope atlas:read --scope atlas:write:threadwalk --scope atlas:write:path
```

The corresponding Linux command is:

```bash
"$atlas" --store "$store" mcp collaborator register --name "My Hermes agent" --client-family hermes --scope atlas:read --scope atlas:write:threadwalk --scope atlas:write:path
```

Keep the returned `id`. Registration creates an immutable local record; reuse
that ID when reconnecting instead of registering again. Recover existing IDs
with `mcp collaborator list`.

| Scope | Allows |
|---|---|
| `atlas:read` | Read and search local Atlas context |
| `atlas:write:threadwalk` | Begin a private Threadwalk |
| `atlas:write:path` | Append a path; with read scope, open a question at an existing thought |
| `atlas:memory:ack` | Acknowledge a memory candidate saved by the client itself |

Add the last scope at registration only when you intend to test the client's
own memory-write workflow. No scope grants publication or vault access. The
client launches this process as your OS user; the scopes constrain bridge
tools, not the client's unrelated filesystem permissions.

## 3. Generate and merge the client configuration

For example, on Windows:

```powershell
& $atlas --store $store mcp config --client hermes --collaborator COLLABORATOR_ID
```

On Linux:

```bash
"$atlas" --store "$store" mcp config --client hermes --collaborator COLLABORATOR_ID
```

Replace `COLLABORATOR_ID` with the saved ID, or omit that option for read-only
access. Choose a client from this table. Output contains absolute executable
and store paths, with quoting appropriate to the client's configuration file.
The command only prints a fragment; merge its single `atlas-of-threads` entry
into the existing section, preserving your other settings and servers. If that
name already exists, inspect it before replacing it. Do not create duplicate
TOML tables or replace the whole file with the fragment.

| `--client` | Configuration destination | Reconnect / inspect |
|---|---|---|
| `codex` | `~/.codex/config.toml`, `mcp_servers` | New client session; `/mcp` |
| `claude` | Project `.mcp.json`, `mcpServers` | Approve this project server in Claude Code; `/mcp` |
| `grok` | `~/.grok/config.toml`, `mcp_servers` | `grok mcp doctor atlas-of-threads`; `/mcps` |
| `opencode` | `opencode.json`, v1 `mcp` | `opencode mcp list` |
| `opencode-v2` | `opencode.json`, v2 `mcp.servers` | Restart OpenCode; verify tools |
| `prime-agent` | User `~/.prime/agent/settings.json`, `mcpServers` | `prime-agent mcp get atlas-of-threads`; Python API below |
| `openclaw` | `~/.openclaw/openclaw.json`, `mcp.servers` | `openclaw mcp probe atlas-of-threads --json`; restart the owning runtime |
| `hermes` | `~/.hermes/config.yaml`, `mcp_servers` | `/reload-mcp` or new `hermes chat` |

On Windows, `~` means your Windows user profile for native clients. For WSL
clients it means your Linux home. Do not mix Windows executable/store paths
with a Linux process configuration. OpenCode's v1 and v2 layouts are different;
check `opencode --version` and use the matching option.

Prime Agent supports generic stdio servers through its kernel's pre-imported
`mcp` module; no custom Python skill is needed:

```python
tools = await mcp.list_tools("atlas-of-threads")
status = await mcp.call_tool("atlas-of-threads", "atlas_status", {})
```

For OpenClaw, use its **client registry**, not `openclaw mcp serve` (which exposes
OpenClaw as a server). Its `coding`/`messaging` profiles can expose MCP tools;
`minimal`, tool denials, or server filters can hide them. A CLI probe establishes
connectivity; the actual agent runtime must also have the tools enabled.

Keep manual setup available. Client-specific CLI commands such as `codex mcp
add`, `claude mcp add`, `grok mcp add`, and `prime-agent mcp add` can register
the same executable/argument list if preferred. Atlas does not silently edit
global client settings or register real agents for you.

For an existing agent on another machine, use the optional
[SSH connection and private MCP forward](REMOTE_AGENTS.md). The canonical
Atlas store stays on its original machine; neither agent credentials nor a
duplicate agent installation are needed there.

## 4. Verify from your agent

For inbound paths, the client-reported model/provider is preserved in the receipt
and `agent_bridge` metadata. The graph's execution provider remains `none`
because Atlas did not invoke a model itself; it does not mean the model is absent.

Start with: **“Use Atlas's atlas_status and list_threadwalks tools. Report the
store counts and available Threadwalks. Do not create or change anything.”**

Then select a real Threadwalk and ask for a cited reading of one thought.
For a contribution-enabled agent, explicitly request a new synthetic trial:

> Start a private Atlas Threadwalk titled Synthetic onboarding trial. Answer
> “What would make a small trial informative?” and append one attributed path.
> Read the response_contract and advertised node/edge schemas first. Use the
> exact source IDs and stable client_request_id values. Report the receipt and
> graph IDs, then read the saved path back. Do not invoke an outbound harness.

The response contract provides a valid example with your actual source IDs.
Replace its synthetic content with the answer. Nodes need `kind` and `text`;
use unique `local_id` labels when linking them. Edges use `from`, `to`, and a
listed relationship kind. `fact`, `conclusion`, and `followed_by` are not
canonical kinds. Atlas supplies attribution, timestamps, and permanent IDs.
Do not add `agent`, `created_at`, hidden reasoning, or credentials.

Close/reconnect the client and read the same IDs. Exact begin/append retries
with the saved request IDs and arguments must reuse the existing records;
changed content needs a new request ID.

## Optional memory and reverse calls

Inbound MCP does not grant Atlas access to your agent's memory or prove it can
call that agent back. The client must deliberately save the returned
`memory_candidate` using its own approved mechanism, read it back, then call
`acknowledge_memory_receipt` if that scope was granted. Acknowledgement records
an opaque reference, not the external memory contents or a verified durability
guarantee. Test recall from a fresh client before claiming memory integration.

Atlas's existing outbound adapters remain Claude, Codex, Grok, OpenCode, and
Prime Agent. This onboarding adds OpenClaw and Hermes as **inbound MCP clients**;
it does not add an outbound adapter or import their personas, authentication,
or private memory. Codex and OpenCode can additionally be bound to the same
collaborator ID for return calls with approved file-memory projection and a
dedicated resumable conversation. Register that route separately as described
in [Agent Bridge](AGENT_BRIDGE.md#connect-one-named-codex-or-opencode-agent-in-both-directions).

## Compatibility evidence

See [MCP compatibility checks](MCP_COMPATIBILITY.md) for exact tested versions,
platforms, transport/read/write evidence, and remaining acceptance limits.

## Client documentation

Configuration formats checked September 6, 2026:

- [Codex MCP](https://developers.openai.com/codex/mcp)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [Grok Build MCP](https://docs.x.ai/build/features/mcp-servers)
- [OpenCode v1 MCP](https://opencode.ai/docs/mcp-servers/) and [v2 MCP](https://opencode.ai/v2/docs/mcp-servers)
- [Prime Agent generic MCP](https://github.com/PrimeIntellect-ai/prime-agent/blob/main/packages/coding-agent/docs/mcp-integrations.md)
- [OpenClaw MCP client registry](https://docs.openclaw.ai/cli/mcp)
- [Hermes MCP](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)


## Local discovery and remote setup

Workspace → Set up collaborators scans the Atlas PC when opened, with a manual
rescan available. It includes configured default Hermes and named OpenClaw agents
alongside the five existing CLI families. Add Remote Agent checks one specified
SSH destination, verifies its host key, lists supported native agents, and
registers only the chosen agent after a health check. The included connection
and firewall guidance distinguishes service/network, trust and authentication
failures and provides scoped rules with undo instructions.

See [remote setup](REMOTE_AGENTS.md#discover-and-connect-from-workspace) for local
platform limits, host requirements, credential boundaries and firewall references.
