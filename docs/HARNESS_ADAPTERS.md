# Harness adapter protocol

Thought Archaeology does not select or authenticate an AI provider. A user
registers a local executable adapter, and the foreground TA worker passes
versioned JSON to it without a shell.

## Registration

```bash
ta harness register NAME --adapter /absolute/path/to/ADAPTER --default
ta harness doctor NAME
ta harness watch --harness NAME
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
- `ta harness status` reports configuration, store availability, and pending
  count; it does not claim that a detached worker is alive.
- Run one watcher per store in protocol version `1`. Multi-worker claiming and
  leasing are deliberately not implied by the append-only completion model.
- A request remains pending when no adapter is configured or no worker is
  running. Manual `ta continuation pending|complete` remains valid.

## Initial staged adapters

The first adapter set is intentionally staged so each real locally installed
harness can be tested against the same protocol before the next is added:

1. Grok
2. Codex
3. Claude Code
4. OpenCode
5. Prime Agent

These names are planned adapter targets, not provider dependencies of the TA
package. Each adapter owns its authentication, invocation flags, output
normalization, and model identifier. The TA core must not acquire their SDKs,
credentials, or vendor-specific schemas.
