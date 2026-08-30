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

## Worker behavior

- `ta harness run` processes the oldest pending request, or a named `--request`.
- `ta harness watch` stays in the foreground and polls the same durable inbox.
- `ta harness service install` is the explicit systemd-Linux opt-in that binds
  the selected harness and resolved store to one persistent user service,
  enables it, and starts it. Clone/open/register operations remain inert.
- `ta harness service status|start|stop|restart|remove` inspects and controls
  that unit. The foreground watcher remains the portable fallback.
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
| Codex | planned after Grok's real terminal-to-doorway acceptance |
| Claude Code | planned |
| OpenCode | planned |
| Prime Agent | planned |

These names are planned adapter targets, not provider dependencies of the TA
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
