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
ta sensor attach NODE [--graph G] [--session S]
ta sensor attach --from-attribution PATH
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
No Node runtime; `viz/dist` is committed.

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
prints both ids. Other probe kinds still exit 4.

`ta sensor attach NODE` is a Depth-3 stub: it binds nothing, prints that
open weights or a vendor interpretability API are required, and exits 4.
Collapsed attributions (≤12 supernodes bound to a thought-node) can be
displayed from JSON with `--from-attribution`. Uncollapsed dumps are
refused. `raw_feature_count` is an integer; the CLI never prints raw
feature id lists. No vendor client ships in v1.

Policy warnings (stderr, exit 0 unless `--strict`): zero `rejected_alternative`
nodes, more than 40 nodes, no `claim`, `supports`/`depends_on`/`shapes` cycles.

## Tests

```bash
pytest -q
```
