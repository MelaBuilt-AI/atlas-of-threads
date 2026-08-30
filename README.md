# Thought Archaeology

Inspectable AI thought-graphs: inhabit, fork, and keep the negative space.

Depth 1 compiles any chat-model answer into a thought-graph of claims, premises,
analogies, judgment calls, uncertainties, and rejected alternatives. The graph is
the **story** of the answer, stored as objects — not a circuit trace.

License: MIT.

## Install

Python 3.11+. Runtime dependency is `jsonschema` only.

```bash
git clone https://github.com/MelaBuilt-AI/thought-archaeology.git
cd thought-archaeology
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
```

```bash
ta init --title demo
ta compile --session <id> --mode posthoc \
  --transcript fixtures/transcripts/simple-freeform.jsonl \
  --from-graph fixtures/graphs/simple.gold.json
ta inhabit <node> --session <id>
ta serve
# open http://127.0.0.1:7462/ — Inhabit Space (stand at a node, not a dashboard)
```

## Origin playbook (first real graph)

From the repo root:

```bash
pip install -e ".[dev]"
ta init --title origin --origin example:synthetic-origin
ta compile --session <id> --mode posthoc --transcript fixtures/transcripts/origin-conversation.jsonl --from-graph fixtures/graphs/origin-conversation.gold.json --model-name grok-4.6-build
ta show <session> --format tree
```

`ta init` prints `session_id`. `ta compile` prints `graph_id`.

## Grok TUI playbook

This TUI cannot type into a child process's stdin. Never use `StdinProvider`
(or `--provider stdin`) from Grok TUI — it blocks on stdin the TUI cannot feed.

**How Grok supplies a graph:**

1. Write a **raw JSON object, no markdown fences**, to a file
   (`{ "nodes": [...], "edges": [...] }` short-emit).
2. Compile with `--from-graph PATH` (parse-only; no provider call).

```bash
ta compile --session SESSION_ID --mode posthoc \
  --transcript fixtures/transcripts/origin-conversation.jsonl \
  --from-graph /tmp/ta-graph.json \
  --model-name grok-4.6-build
```

`--from-graph` skips the provider. Parser tries `json.loads` of the whole file
first, then thought-graph fences as a fallback. Raw JSON is the intended TUI
path. Fences still parse so a sloppy dump is not a hard fail.

**Structured emit** (when Grok writes prose + a `thought-graph` fence in chat):
write that raw text to a file, then:

```bash
ta compile --session SESSION_ID --mode structured --input /tmp/ta-turn.txt
```

Do **not** pipe the TUI into `ta compile --provider stdin`.

Dump the compiler prompts with:

```bash
ta prompt structured
ta prompt posthoc
ta prompt fork
```

**Fork / inhabit / veto** (no network required for bookkeeping):

```bash
ta inhabit NODE --session SESSION_ID
ta fork NODE --session SESSION_ID --reason "accept chain except this cut"
ta fork NODE --session SESSION_ID --from-graph /tmp/ta-fork.json
ta veto NODE --session SESSION_ID --reason "this judgment call is the wrong cut"
```

`ta fork` without `--from-graph` or a provider writes a new graph with
`(fork pending regeneration)` as prose. `--from-graph` is the TUI path for a
regenerated emit (raw JSON or a `thought-graph` fence). G0 bytes never change.
The omit-set is the fork target plus causal descendants: outgoing `shapes` /
`supports`, incoming `depends_on` — never outgoing `depends_on`.

## CLI

```
ta init [--title T] [--origin S]
ta compile --session ID --mode structured|posthoc
  [--input PATH|-]
  [--transcript PATH]
  [--turn-id ID]
  [--from-graph PATH]
  [--hidden PATH]
  [--provider none|file|stdin|shell]
  [--provider-file PATH]
  [--provider-cmd CMD]
  [--model-name NAME]
ta show ID [--format json|tree|ids] [--node NODE]
ta validate PATH|ID
ta log SESSION
ta prompt structured|posthoc|fork
ta inhabit NODE [--graph G] [--session S]
ta fork NODE --session ID [--graph G] [--reason TEXT]
  [--from-graph PATH] [--provider none|file|stdin|shell]
  [--provider-file PATH] [--provider-cmd CMD] [--model-name NAME]
ta veto NODE --session ID [--graph G] --reason TEXT
ta continuation ready NODE --graph G [--prompt TEXT]
ta continuation pending [--format table|json]
ta continuation cancel REQUEST
ta continuation complete REQUEST --graph G --harness NAME

ta harness configure
ta harness register NAME --adapter PATH [--arg VALUE ...] [--default]
ta harness use NAME
ta harness list [--format table|json]
ta harness status [--format table|json]
ta harness doctor [NAME] [--timeout SECONDS]
ta harness remove NAME
ta harness run [--harness NAME] [--request ID] [--timeout SECONDS]
ta harness watch [--harness NAME] [--interval SECONDS] [--timeout SECONDS]
ta harness service install [--harness NAME] [--interval SECONDS] [--timeout SECONDS]
ta harness service status [--format table|json]
ta harness service start|stop|restart|remove
ta sensor attach NODE [--graph G] [--session S]
ta sensor attach --from-attribution PATH
ta sensor import-circuit-tracer NODE --graph G --from-graph PATH \
  --source-uri URI --producer-revision REV
ta sensor record-intervention NODE --graph G --from-result PATH \
  [--neuronpedia-request PATH --manifest PATH] \
  --source-uri URI --parent-evidence ID
ta sensor import-activation NODE --graph G --request PATH \
  --from-response PATH --graph-position N --target TEXT
ta sensor synthesize-recurrence --neural-evidence ID \
  --neural-evidence ID --neural-evidence ID
ta provenance checkpoint --graph G --node N --measurements PATH \
  --checkpoint-map PATH --model-card PATH --model-card-uri URI \
  --training-docs PATH --training-docs-uri URI --corpus NAME
ta fingerprint [--session ID ...] [--min-sessions N] [--out PATH]
ta canvas GRAPH [--out PATH] [--fingerprint PATH]
ta export-wiki GRAPH --out PATH [--fingerprint PATH]
ta probe plan --graph G --kind drop_premise|invert_constraint|resample|steer_later --node N
ta probe diff GRAPH_A GRAPH_B [--spec PATH]
ta probe run --spec PATH --provider-cmd CMD
ta serve [--port 7462] [--bind 127.0.0.1]
```

Global flags: `--store PATH`, `--strict`, `--quiet`.

Store path, first hit wins: `--store` → env `TA_STORE` → `./data` if that
directory already exists → `$XDG_DATA_HOME/thought-archaeology` or
`~/.local/share/thought-archaeology` (created on `ta init`).

Exit codes: `0` ok, `1` validation / `--strict` policy failure, `2` usage,
`3` I/O, `4` not-implemented (unsupported probe kinds and Depth 3).

`ta serve` is a localhost server (default `127.0.0.1:7462`). It serves
Inhabit Space: you stand at a thought-node. Walking a chamber fetches
`/api/inhabit/{node}` — the same omit-set as `ta inhabit`. Fork (`f`) and
veto (`v`) POST to Python; the browser does not compute the omit-set.
Left/right selection is a true-north clock around the inhabited chamber: Left
moves counterclockwise and Right clockwise through every visible path, including
story and fork paths at north. Up remains a direct north-path shortcut; Enter
walks the selected path, or the north path when no selection is active.
The surrounding neural canopy is procedural: dim connections carry visible
pulses while the graph itself remains the authored story, not a circuit claim.
A continuation request connects the standing relic to one random visible neuron
with sparking green lightning. Completion retains that neuron and returns a blue
beam to the new doorway until entry, alongside the doorway's blue selection
spotlight. Browser-local memory keeps that one visual circuit stable across
a refresh; the graph store remains canonical. These beams are lifecycle
atmosphere, not hidden model activity. No Node runtime; `viz/dist` is committed.

When a completed continuation arrives, only its new doorway is inserted and
raised; the standing relic and existing paths keep their mesh and animation
state. At a terminal chamber, opening cut (`f`) or human no (`v`) stacks that
input above the end-of-path pane rather than behind it.

Cut and human no do not train or modify Grok, Codex, or another closed model.
The browser cut writes a child graph with the selected node and its bounded
dependents omitted, leaving the original graph intact and adding a fork doorway.
Human no preserves the graph and adds a human veto node and edge. A later model
continuation can receive that edited public graph as context and respond
differently, but that is a behavioral/context intervention—not a weight edit or
vendor preference-training signal. Provider-backed fork regeneration is an
explicit CLI operation; the browser gesture itself invokes no model.

The chamber's sound field uses twelve original, sample-free cinematic OGG assets
made specifically for Thought Archaeology; it contains no stock effects or
recognizable notification sounds. The neural atmosphere wakes on the first
keyboard or pointer interaction (browser autoplay policy) and remains continuous.
Distinct assets cover object cycling, forward/back traversal, red origin return,
blue path activation and entry, camera movement, AI-working pressure, green-beam
activation/crackle, and blue completion lightning. The three continuous layers
crossfade through one conservative master compressor instead of stopping or
stacking abruptly. Evidence/relic inspection, cut/veto inscription, and
cancellation retain their small procedural gestures because this first cinematic
pack does not include replacements for them. `s` toggles mute; the top-bar
control exposes persistent browser-local volume and pack loading state.

A future open-weight training slice may explicitly export reviewed cuts and
human vetoes as versioned training examples, paired with accepted alternatives
where needed, then record the base model, dataset, recipe, and resulting local
checkpoint. This must remain a deliberate export/train operation: chamber
gestures never silently update weights. A veto is a negative preference signal;
a cut is a structural counterfactual and does not by itself assert a preferred
replacement or universal error.

`ta canvas` / `ta export-wiki` write a lossy Markdown projection (`type: overview`,
Obsidian wikilinks). Hidden reasoning stays JSON-only. Dual archaeology appears
only with `--fingerprint PATH`. Neither command writes `wiki/index.md` or
`wiki/log.md`. Re-import is `ta compile --from-graph` of JSON, not parse→store.

`ta fingerprint` is offline dual archaeology: normalize + Jaccard 0.8
clustering of model judgment calls and human vetoes. Default `min_sessions=2`.
A single session is all `emerging`. No ML. Writes
`data/fingerprints/{id}.json` (write-once). `--out PATH` copies the JSON;
`--out -` prints it. Inhabit Space uses the latest fingerprint as **climate**
(fog and light at the standing node), not a cluster chart.

`ta probe plan` writes a `ProbeSpec` JSON next to the graph (sibling
`probes/` directory) and exits 0. `ta probe diff` matches nodes by id, then
by kind + Jaccard ≥ 0.8, and writes a `GraphDiff`. If `--spec` is a
`drop_premise` whose target vanished while the conclusion stayed, stderr
prints `story falsified under intervention; not a weight-level proof`.
`ta probe run` executes `drop_premise` through the shell provider. It omits the
premise and its causal descendants through the existing fork path, calls the
provider once, stores the regenerated child graph, writes a `GraphDiff`, and
appends behavioral evidence for each tested conclusion. Pass
`--parent-evidence ID` to continue a validated same-session evidence chain.
The command prints graph, diff, then evidence ids. Other probe kinds still
exit 4. `edit_context` is also functional: plan it with an ancestral `--turn`
and one exact `--old`/`--new` span, then run it through the same provider.
It regenerates the conversation from scratch and tests the named thought.

`ta sensor attach NODE` remains the no-provider Depth-3 stub and exits 4.
Collapsed attributions (≤12 supernodes bound to a thought-node) can be
displayed from JSON with `--from-attribution`. Supplying matching `NODE` and
`--graph` stores a provenance-bearing measured attribution and automatically
adds an inconclusive `activation_correlation` evidence binding.
`ta sensor import-circuit-tracer` reads plain or gzip-compressed official
circuit-tracer graph JSON, preserves and hashes the exact source bytes, and collapses its raw
nodes by recorded structural type. It deliberately does not invent semantic
feature labels. Uncollapsed displays are refused; feature ids stay JSON-only.

`ta sensor record-intervention` is the causal gate. Its parent must be the
matching node's `activation_correlation`; its attribution, model, prompt,
target, and edited `(layer, feature, position)` must all match. The raw result
must contain a baseline observation, an intervened observation, the exact
activation value written, the runner revision and device, plus a preregistered
direction and minimum absolute change. The command preserves the raw bytes,
recomputes the delta and verdict itself, then appends `neural_intervention`
evidence. A claimed verdict inside the input is ignored. This establishes only
a local causal effect under the recorded intervention conditions.
For Neuronpedia graph steering, `--neuronpedia-request` and `--manifest`
add a stricter path: the manifest must bind the exact request SHA-256 before
the run; the importer derives the baseline/intervened target-token outcome
from the untouched API response and preserves all three byte streams.

`ta sensor import-activation` binds a naturally observed feature value to its
own thought and preserves the exact Neuronpedia request/response. It records
the model/layer/feature/position identity but assigns no semantic meaning.
`ta sensor synthesize-recurrence` requires at least three distinct prompts,
the exact same model/layer/feature, a measured activation parent in every
context, and a neural intervention child in every context. It keeps supporting,
contradicting, and inconclusive counts. Only unanimous support or unanimous
contradiction receives that aggregate verdict; mixed outcomes stay
inconclusive. The resulting claim is recurrence of a local mechanism under the
tested conditions, not a universal concept label.

`ta provenance checkpoint` records a bounded target-token trajectory across
exact model checkpoints. It preserves the model card, training documentation,
measurement rows, and checkpoint-to-commit/weight-hash map by SHA-256, then
computes the rank and probability change itself. This is
`checkpoint_emergence`: evidence that behavior changed over training. The
schema explicitly records that exact training-record membership was not
tested, example influence was not measured, and weights were not attributed.
It must never be relabeled `training_influence` from this evidence alone.

## Evidence layers

Thought objects remain the human-readable coordinate system. Append-only
`EvidenceBinding` sidecars state what kind of evidence connects a node to a
concrete artifact: story report, context provenance, behavioral intervention,
activation correlation, neural intervention, recurring circuit, checkpoint
emergence, or bounded training influence. Each binding says whether the artifact supports,
contradicts, or is inconclusive; it never treats prose as neural ground truth.

The long-term design and scientific limits live in
`~/Documents/Wiki/futurelayers.md` on the origin machine.

`ta inhabit NODE --graph GRAPH` reads bindings beneath the standing node and
resolves their parent chain across earlier graphs and nodes. The
Inhabit Space receives the same typed bindings and a server-authored evidence
sentence. Press `e` in the chamber to descend through the server-authored strata,
including lineage and concrete artifact references; browser code displays those
lines but does not infer causality.
When none are attached, the CLI says that absence is not evidence.

The same descent keeps story and evidence visibly separate. Its **why this
path** section reads only relations already recorded in the graph—supporting
premises, shaping judgments, analogies, qualifications, descendants, and
rejected roads. It does not invent reasons or relabel story structure as causal
evidence.

While Inhabit Space remains open, it polls the local store for finalized graph
heads. A later `ta compile` rises as an optional teal doorway beside the current
chamber without a manual page refresh; the user is never teleported. If the
inhabitant is composing or inspecting a relic/evidence pane, the arrival waits
until that interaction clears before the chamber relays out. A selected path
preview does not hold a completed response indefinitely; completion clears the
preview and raises the new doorway.
Direct story relations are walked one edge at a time in front, rejected roads
remain to the left, and conversational
doors appear to the right only at graph origins and path endings. Entering a
doorway marks it seen but keeps a quieter reciprocal return route in bounded
browser memory. Companion doors name the harness and model when their completion
receipt provides them, so a `Grok · grok-4.6` continuation is distinguishable
from the graph it continued. Reloading while standing in an older graph recovers
the newer head as a doorway rather than silently treating it as already known.
After entry, graph-level attribution remains visible on every chamber while the
individual objects keep their semantic kind. Poll enrichment matches the exact
doorway stand, so a reciprocal route to another node in the same graph cannot
trigger repeated chamber respawns. Companion doors stay anchored to the graph
where they arrived instead of following the inhabitant globally. A continuation
graph carries one canonical red return doorway to the exact source chamber. Its
distinct relic, ring, selection light, and label all mean only “Return to
conversation origin.” A terminal chamber explicitly offers
return to the graph origin or a continuation request. This is a turn-level
companion for completed answers, not token-level hidden-thought streaming.

## Harness-neutral continuation

“Ready for continuation” is an append-only handoff, not an embedded model
client. At a terminal chamber, the ready button immediately writes and visibly
activates the handoff; clicking it again cancels the pending handoff. “Ask from
here” toggles an inline prompt beneath the terminal actions, keeping the action
visibly selected until it is submitted or toggled off. Submitting changes the
terminal pane to an animated `AI working…` state. That state remains until a
harness completes the request and the new path appears automatically, or the
user cancels the request. Inhabit Space writes a
`ContinuationRequest` containing only its request/session/graph/node ids,
timestamp, source, and prompt. Requests live under
`data/continuations/requests/`; completion receipts live under
`data/continuations/completions/`; cancellation receipts live under
`data/continuations/cancellations/`. Graphs and requests remain immutable.

Any AI harness can use the filesystem, CLI JSON, or localhost API:

```bash
# poll the neutral inbox
ta continuation pending --format json

# load the referenced public thought/story context
ta show GRAPH_ID --format json

# withdraw before a harness completes it; this appends a cancellation receipt
ta continuation cancel REQUEST_ID

# generate through any model/provider, compile the finalized answer normally,
# then acknowledge which graph answered the request
ta continuation complete REQUEST_ID --graph NEW_GRAPH_ID --harness my-runner
```

The equivalent local endpoints are `GET /api/continuations`,
`POST /api/continuation`, and `POST /api/continuation/cancel`.

The reference worker makes that neutral boundary usable without placing a
vendor client in the core. Register one executable adapter, verify its protocol
handshake, then run it once or keep it watching:

```bash
ta harness register my-ai --adapter /absolute/path/to/my-ta-adapter --default
ta harness doctor
ta harness status
ta harness run       # process the oldest pending request once
ta harness watch     # foreground worker; Ctrl+C stops it
ta harness service install  # opt in to a persistent user service
ta harness service status
```

`ta harness configure` is the interactive form. The registry lives at
`$TA_HARNESS_CONFIG`, or otherwise
`$XDG_CONFIG_HOME/thought-archaeology/harnesses.json` (falling back to
`~/.config/thought-archaeology/harnesses.json`). It stores only an absolute
executable argv and registration metadata with mode `0600`; never put API keys
in adapter arguments. Credentials and model settings stay in the adapter's
normal environment, keychain, or own configuration. TA invokes argv directly
with `shell=False`, and merely opening Inhabit Space never starts an adapter.

Adapters implement protocol version `1` over JSON stdin/stdout. `describe`
advertises the `continue` capability. `continue` receives the immutable request,
session, public graph, and server-authored standing view; `hidden_reasoning` is
removed. It returns a model name plus final prose containing one fenced
`thought-graph` block. The worker validates and compiles that response, appends
any exact user prompt as a turn, links the response to the source graph, writes
the existing completion receipt, and advances the session head. If the request
is canceled while the model is responding, the result is discarded before any
graph is written.

Run one watcher per store in this first implementation. The initial staged
adapter targets are Grok, Codex, Claude Code, OpenCode, and Prime Agent; they
will be installed and exercised locally one at a time against the same
contract. See [`docs/HARNESS_ADAPTERS.md`](docs/HARNESS_ADAPTERS.md).

On systemd Linux, `ta harness service install` writes one user-owned
`thought-archaeology-harness.service` bound to the resolved store and selected
harness, then explicitly enables and starts it. The service restarts only after
a worker failure; cloning the repository, opening Inhabit Space, and merely
registering an adapter never install or start it. `service stop|start|restart`
controls the installed watcher, while `service remove` disables it and removes
the unit. The foreground `ta harness watch` command remains the portable
fallback.

When a worker takes a queued request, TA appends a `ContinuationAttempt` before
calling the adapter. Inhabit Space retains the accepted `AI working…` state and
adds the harness name while that request is being handled. Completion and
cancellation remain the only states that close the immutable request.

The first thin adapter ships as `ta-harness-grok`. It uses the already
authenticated official Grok CLI in headless single-turn mode, disables plan
mode, subagents, web search, and the tool allowlist, and requests the existing
structured-emission format. After installing TA and Grok:

```bash
ta harness register grok --adapter "$(command -v ta-harness-grok)" --default
ta harness doctor grok
ta harness run --harness grok
```

`TA_GROK_BIN` may point to a non-default Grok executable,
`TA_GROK_MODEL` may pin a model instead of using `grok models`, and
`TA_GROK_TIMEOUT` changes the model-call timeout in seconds. These variables
are adapter settings, not graph data; credentials remain in Grok's own login.

Thought Archaeology owns the durable boundary and graph compilation; the
harness owns credentials, model invocation, and provider-specific prompt
assembly. No vendor SDK or callback URL is required by the core.

Restart `ta serve` after updating project code. Static HTML/JavaScript reload on
refresh, but an existing Python process cannot emit newly added read fields; the
descent names this mismatch when `why this path` data is unavailable.

`ta evidence context --graph G --node N --turn T` attaches verified context
provenance only when `T` is in the graph turn's parent lineage. The binding
stores the turn id and canonical SHA-256 and remains `inconclusive`: preceding
an answer is not proof of causing it.

Policy warnings (stderr, exit 0 unless `--strict`): zero `rejected_alternative`
nodes, more than 40 nodes, no `claim`, `supports`/`depends_on`/`shapes` cycles.

## Tests

```bash
pytest -q
```
