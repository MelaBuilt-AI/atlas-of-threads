# Harness adapter protocol

Thought Archaeology does not select or authenticate an AI provider. A user
registers a local executable adapter, and the foreground TA worker passes
versioned JSON to it without a shell.

## Registration

```bash
ta harness register NAME --adapter /absolute/path/to/ADAPTER --default
ta harness doctor NAME
ta harness watch --harness NAME
ta harness service install --harness NAME
```

Use repeated `--arg VALUE` options only for non-secret, fixed adapter arguments.
Values beginning with a dash use `--arg=VALUE`. Credentials belong in the
provider's existing environment, keychain, login session, or configuration.

The user registry is outside both the cloned repository and the graph store:

1. `$TA_HARNESS_CONFIG`, when set;
2. `$XDG_CONFIG_HOME/thought-archaeology/harnesses.json`;
3. `~/.config/thought-archaeology/harnesses.json`.

The directory is mode `0700`; the file is mode `0600`. Registration resolves
the executable to an absolute path. TA stores an argv array and invokes it with
`shell=False`. Cloning or opening a project never launches an adapter.

Inhabit Space also offers a local-first browser setup for the five packaged
bridges. It detects their provider CLIs, accepts only the built-in collaborator
names, writes the same user-owned registry, and runs `describe` as a health
check. A failed check removes the new registration. Provider installation,
authentication, subscriptions, and model selection stay outside Atlas; the
browser never accepts credentials or arbitrary adapter paths. One click
connects, tests, and selects the first collaborator. Starting the first
Threadwalk initializes the private store if needed and starts the exact
store/collaborator worker through the platform backend. Linux uses the user
systemd service; Windows and macOS supervise the worker while Atlas is open.
The Online note is presentation scaffolding only and performs no networking.

On Windows, Atlas checks the native process path and common per-user CLI install
locations. It also checks the default WSL distribution for Codex, Claude Code,
and Grok Build, and forwards their health checks and model calls across the WSL
boundary with translated temporary paths. `TA_WSL_DISTRO` selects a non-default
distribution. A ChatGPT, Claude, or Grok desktop installation alone is not a
provider bridge: the corresponding supported CLI must be installed, callable,
and authenticated in the environment Atlas detects. Atlas does not inspect
vendor desktop-app state or drive desktop UI automation.

## Operations

TA appends one operation argument to the registered argv.

### `describe`

No stdin is supplied. The adapter writes exactly one JSON object to stdout:

```json
{
  "protocol_version": "1",
  "name": "example-adapter",
  "capabilities": ["continue"]
}
```

Human-readable logs go to stderr. A nonzero exit, non-JSON stdout, protocol
mismatch, or missing `continue` capability fails `ta harness doctor`.

### `continue`

The adapter receives one JSON object on stdin:

```json
{
  "protocol_version": "1",
  "operation": "continue",
  "request": {},
  "session": {},
  "graph": {},
  "standing": {},
  "response_contract": {}
}
```

- `request` is the immutable `ContinuationRequest`, including the optional
  exact prompt.
- `session` identifies the originating thought session.
- `graph` is the complete public source graph. TA removes stored
  `hidden_reasoning` before invocation.
- `standing` is the same server-authored chamber view used by Inhabit Space,
  including story relations and evidence descriptions.
- `response_contract` describes the required result fields.

The adapter invokes its AI harness by provider-specific means and writes exactly
one JSON object to stdout:

```json
{
  "protocol_version": "1",
  "response": "Final prose.\n\n```thought-graph\n{...}\n```",
  "model_name": "provider-model-identifier"
}
```

`response` follows the existing structured-emission contract printed by
`ta prompt structured`: final prose followed by exactly one fenced
`thought-graph` JSON object. TA, not the adapter, assigns canonical ULIDs,
validates the graph, appends turns, writes it, advances the session head, and
records the immutable completion receipt.

TA checks that the request is still pending after model invocation and again
after in-memory compilation. If the inhabitant canceled it, the response is
discarded before any graph is written.

In Inhabit Space, each registered collaborator has a separate **Refresh**
action. After the user chooses a model in the provider's own harness, Refresh
runs `describe` and stores only the returned model, CLI version, and refresh
timestamp as a display snapshot in the user-owned registry. It does not change
the default harness, restart a watcher, or alter any graph. The adapter still
re-reads the provider setting when `continue` runs, and the completion's
`model_name` remains the authority for new graph attribution.

## Worker behavior

- `ta harness run` processes the oldest pending request, or a named `--request`.
- `ta harness watch` stays in the foreground and polls the same durable inbox.
- `ta harness service install` is the explicit systemd-Linux opt-in that binds
  the selected harness and resolved store to one persistent user service,
  enables it, and starts it. Clone/open/register operations remain inert.
- `ta harness service status|start|stop|restart|remove` inspects and controls
  that unit. The foreground watcher remains the portable fallback.
- The packaged local application supervises the same one-watcher contract on
  Windows and macOS, starting it after the first Threadwalk and resuming it when
  Atlas reopens. It invokes the same `ta harness watch` path and changes no
  protocol or store artifact.
- `ta harness status` reports configuration, store availability, and pending
  count; it does not claim that a detached worker is alive.
- Immediately before adapter invocation, a worker appends a
  `ContinuationAttempt` naming the harness. It is an audit receipt for the
  queued → responding transition, not a claim about hidden model activity.
- Run one watcher per store in protocol version `1`. Multi-worker claiming and
  leasing are deliberately not implied by the append-only completion model.
- A request remains pending when no adapter is configured or no worker is
  running. Manual `ta continuation pending|complete` remains valid.

## Initial staged adapters

The first adapter set is intentionally staged so each real locally installed
harness can be tested against the same protocol before the next is added:

| Adapter | Stage |
|---|---|
| Grok | implemented as `ta-harness-grok`; deterministic CLI-contract coverage complete |
| Codex | implemented as `ta-harness-codex`; deterministic CLI-contract coverage complete |
| Claude Code | implemented as `ta-harness-claude`; deterministic CLI-contract coverage complete |
| OpenCode | implemented as `ta-harness-opencode`; deterministic CLI-contract coverage complete |
| Prime Agent | implemented as `ta-harness-prime-agent`; deterministic CLI-contract coverage complete |

These are optional adapter bridges, not provider dependencies of the TA
package. Each adapter owns its authentication, invocation flags, output
normalization, and model identifier. The TA core must not acquire their SDKs,
credentials, or vendor-specific schemas.

## Grok

`ta-harness-grok` requires the official `grok` executable. It prefers
`$GROK_HOME/bin/grok` (or `~/.grok/bin/grok`) over a managed launcher on PATH,
then `describe` reads
`grok --version` and the default reported by `grok models`; it never reads
Grok's credential or configuration files. `continue` writes the bounded TA
prompt to a private temporary file and invokes Grok with direct argv:

```text
grok --verbatim --no-plan --no-subagents --disable-web-search \
  --max-turns 10 --tools "" --output-format plain \
  --model MODEL --prompt-file PRIVATE_TEMP_FILE
```

The prompt tells Grok to use only the public continuation envelope and embeds
the packaged `ta prompt structured` contract. The temporary file is mode
`0600` and is removed after the call. The adapter wraps Grok's plain final
response in protocol `1` JSON; TA still performs graph parsing, ULID assignment,
validation, storage, completion, and session-head advancement.

Optional process environment:

- `TA_GROK_BIN` — alternate Grok executable;
- `TA_GROK_MODEL` — explicit model id, avoiding default-model discovery;
- `TA_GROK_TIMEOUT` — positive model-call timeout in seconds (default 840).

Grok authentication remains wherever the official CLI keeps it. Never place a
token in `--arg` or the TA harness registry.

## Codex

`ta-harness-codex` requires an authenticated `codex` executable. `describe`
reads `codex --version` and only the root `model` key from Codex's own
`config.toml`, unless `TA_CODEX_MODEL` explicitly pins one. When neither is
present it selects the priority-one visible model from
`codex debug models --bundled`. The same model is passed explicitly to
`continue` and returned as graph attribution.

Each continuation runs in a private empty temporary directory through direct
argv with an ephemeral session, ignored user/project rules, ignored user
configuration, read-only sandboxing, no web-search flag, and no git-repository
requirement. Authentication still belongs to the Codex CLI. The bounded TA
prompt is supplied on stdin, and the final response is read from Codex's
dedicated `--output-last-message` file; transient CLI output never enters the
graph.

```text
codex exec --ephemeral --ignore-user-config --ignore-rules \
  --sandbox read-only --skip-git-repo-check --color never \
  --model MODEL --output-last-message PRIVATE_TEMP_FILE \
  --cd PRIVATE_TEMP_DIR -
```

Optional process environment:

- `TA_CODEX_BIN` — alternate Codex executable;
- `TA_CODEX_MODEL` — explicit model id, avoiding bundled-model discovery;
- `TA_CODEX_TIMEOUT` — positive model-call timeout in seconds (default 840).

Registering the adapter does not start it:

```bash
ta harness register codex --adapter "$(command -v ta-harness-codex)"
ta harness doctor codex
ta harness run --harness codex
```

## Claude Code

`ta-harness-claude` requires an authenticated official `claude` executable.
`describe` reads `claude --version` and only the saved `model` field from Claude
Code's `settings.json`, unless `TA_CLAUDE_MODEL` pins a model or alias. Selecting
Claude Code's default removes that saved override, so the adapter then uses the
official `sonnet` alias. It passes the selection explicitly and records the exact
canonical serving model from the completed JSON result's `modelUsage` field. Claude Code may
report auxiliary model usage alongside the requested model; when that happens,
the adapter matches the configured exact name or Haiku/Sonnet/Opus family and
still records the matched entry's canonical model. Ambiguous unmatched results
fail rather than guessing.

Each continuation runs in a private empty temporary directory with safe mode,
an empty tool set, an empty strict MCP configuration, disabled slash commands
and Chrome integration, no session persistence or prompt suggestions, and a
replacement system prompt. The public TA envelope is supplied on stdin and the
adapter accepts only Claude Code's final JSON result. API failures are rejected
through the result's `is_error` field even when the CLI exits zero.

```text
claude --print --input-format text --output-format json --safe-mode \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' --tools "" \
  --disable-slash-commands --no-chrome --no-session-persistence \
  --permission-mode dontAsk --prompt-suggestions false \
  --system-prompt SYSTEM_PROMPT [--model MODEL]
```

Optional process environment:

- `TA_CLAUDE_BIN` — alternate Claude Code executable;
- `TA_CLAUDE_MODEL` — explicit model id or alias; exact graph attribution still
  comes from Claude Code's completed result;
- `TA_CLAUDE_TIMEOUT` — positive model-call timeout in seconds (default 840).

Claude authentication remains wherever the official CLI keeps it. Registering
the adapter does not start it:

```bash
ta harness register claude --adapter "$(command -v ta-harness-claude)"
ta harness doctor claude
ta harness run --harness claude
```

## OpenCode

`ta-harness-opencode` requires an authenticated official `opencode` executable.
Model selection has explicit precedence: `TA_OPENCODE_MODEL`, a fixed `model`
in OpenCode's resolved configuration, then the latest nonempty model selection
stored by an OpenCode session. The latter is read through OpenCode's own
read-only `db` command, not by opening its database directly. Provider and model
are always passed back to `run` explicitly; the selected variant is also passed
when present.

Each continuation supplies the public TA envelope on stdin and runs in an empty
temporary directory with external plugins and project configuration disabled.
`OPENCODE_PERMISSION={"*":"deny"}` denies every tool permission; thinking,
continuation, and auto-approval flags are never enabled, while an invocation-only
config override forces manual sharing even if the user's normal config uses
auto-share. The adapter
accepts only finalized `text` events from raw JSON output and rejects any tool
event or structured error.

OpenCode `run` persists a session even for a fresh non-interactive turn. After a
successful call, the adapter uses the official `export` command to verify the
exact `providerID`, `modelID`, and variant reported on the assistant message.
It then deletes that one adapter-created session through the official `session
delete` command before returning the response to TA. Thinking and tool traces
never enter the graph, and OpenCode remains the sole owner of authentication.

```text
opencode run --pure --format json --model PROVIDER/MODEL \
  [--variant VARIANT] --dir PRIVATE_TEMP_DIR
```

Optional process environment:

- `TA_OPENCODE_BIN` — alternate OpenCode executable;
- `TA_OPENCODE_MODEL` — explicit `provider/model` selection;
- `TA_OPENCODE_VARIANT` — explicit provider-specific variant;
- `TA_OPENCODE_TIMEOUT` — positive model-call timeout in seconds (default 840).

Registering the adapter does not activate it or restart the watcher:

```bash
ta harness register opencode --adapter "$(command -v ta-harness-opencode)"
ta harness doctor opencode
ta harness run --harness opencode
```

## Prime Agent

`ta-harness-prime-agent` requires an authenticated official `prime-agent`
executable. It reads only `defaultProvider`, `defaultModel`, and
`defaultThinkingLevel` from Prime Agent's user `settings.json`, unless the
corresponding TA environment overrides are present. The adapter never opens
`auth.json`. Provider, model, and thinking are passed explicitly on every call.

Each continuation uses Prime Agent's documented JSON event-stream mode in an
empty temporary directory. `--no-session` prevents transcript persistence;
all built-in and discovered tools, extensions, skills, prompt templates,
themes, and context files are disabled. `--offline` suppresses startup network
work such as update checks without disabling the selected model call, and
telemetry is disabled for the invocation. The adapter accepts only a completed
assistant message with a normal `stop` reason, rejects tool events and tool-call
content, and verifies the serving provider/model from that message before
returning public text to TA. Thinking blocks and event-stream metadata never
enter the graph.

```text
prime-agent --print --mode json --cwd PRIVATE_TEMP_DIR --offline \
  --provider PROVIDER --model MODEL --thinking LEVEL --no-session \
  --no-tools --no-builtin-tools --no-extensions --no-skills \
  --no-prompt-templates --no-themes --no-context-files \
  --system-prompt SYSTEM_PROMPT
```

Optional process environment:

- `TA_PRIME_AGENT_BIN` — alternate Prime Agent executable;
- `TA_PRIME_AGENT_PROVIDER` — explicit provider identifier;
- `TA_PRIME_AGENT_MODEL` — explicit model identifier;
- `TA_PRIME_AGENT_THINKING` — explicit Prime Agent thinking level;
- `TA_PRIME_AGENT_TIMEOUT` — positive model-call timeout in seconds (default 840).

Registering the adapter does not activate it or restart the watcher:

```bash
ta harness register prime-agent --adapter "$(command -v ta-harness-prime-agent)"
ta harness doctor prime-agent
ta harness run --harness prime-agent
```
