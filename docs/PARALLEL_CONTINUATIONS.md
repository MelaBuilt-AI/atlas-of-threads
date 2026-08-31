# Parallel Continuations

Status: accepted implementation specification  
Accepted by: user and Codex  
Date: 2026-08-31

Implementation status: Phase 1 was live-accepted by the user on 2026-08-31.
Phase 2 is implemented and deterministically verified by Codex; its required
two-collaborator then complete-set live acceptance remains pending.

## Purpose

Parallel Continuations lets an inhabitant inspect, and later deliberately
create, several AI continuations from one exact chamber and one exact question.
It preserves each response as its own attributed, immutable thought-graph. It
does not infer a winner, synthesize consensus, expose hidden reasoning, or turn
Thought Archaeology into a model leaderboard.

The feature is implemented and accepted in two separate phases:

1. **Read parallel paths.** Thread Compass groups and compares continuations
   that already share an exact source and prompt.
2. **Request parallel paths.** Pressing `P` at a terminal chamber opens a
   bounded Workspace composer that sends one exact question to two or more
   selected registered collaborators. The single background worker processes
   those requests sequentially.

Phase 1 must be complete, tested, and lived with before Phase 2 begins. The
comparison destination must exist before the batch machinery that populates it.

## Product decision

This is one feature family with two distinct actions:

- `T` reads lineage and parallel continuations.
- `P` deliberately creates parallel continuations.

The existing meanings remain intact:

- `E` explains why the currently inhabited thought took its recorded story
  path, then shows evidence beneath that one thought.
- `M` owns collaborator-related and cross-session state-changing operations.
- `L` owns controls, contextual cut/human-no editing, sound, and the visual
  legend.
- The terminal pane remains the immediate spatial end-of-path event.
- Direct story paths remain ahead, rejected roads remain left, and conversation
  or continuation doors remain right at graph origins and terminal chambers.

Parallel comparison is graph lineage, not evidence. Parallel requesting is an
explicit workspace operation from a specific terminal chamber, not a new kind
of graph relation.

## User-visible terminology

Use **Parallel continuations** and **same-question paths** in the interface.
Do not use “sibling comparison” as the primary visible label. The existing
thought graph already uses “rejected siblings,” and conflating rejected
thought-nodes with parallel response graphs would be confusing.

Internal code may use `parallel_group` or `sibling` where useful, but server
payload and interface copy should prefer the accepted user language.

## Exact grouping identity

Two completed continuations belong to the same comparison group only when all
of these stored values match exactly:

```text
session_id
+ source graph_id
+ source node_id
+ exact stored prompt
```

The prompt comparison is exact after the existing request-time outer whitespace
trim. Do not semantically normalize or cluster rephrasings into one group.

- A rephrased question is a separate group.
- An empty prompt is a separate “continued without a new question” group.
- Two requests from the same parent graph but different standing nodes are
  separate groups.
- Canceled or failed requests may be counted in batch progress, but only
  completed graphs appear as comparable paths.
- A group needs at least two completed graphs before the comparison action is
  offered.

This identity is derived from canonical `ContinuationRequest` and
`ContinuationCompletion` artifacts. It is not saved as graph metadata and does
not mutate any graph.

## Shared epistemic rules

Both phases obey these rules:

- Each response remains a separate immutable graph with its exact completion
  harness and exact returned model attribution.
- No majority vote, winner, aggregate confidence, or truth score is inferred.
- Self-reported node confidence is not compared or averaged across models.
- Response time is lifecycle metadata, not a quality ranking, and is absent
  from the primary comparison surface.
- The browser does not invent summaries, rationale, agreement, disagreement,
  or warning severity.
- Hidden reasoning and provider-internal traces remain excluded.
- Any later synthesis must be a separate, explicitly requested continuation
  with its own author/model attribution. Parallel Continuations never creates a
  synthetic summary graph automatically.
- Provider credentials remain provider-owned. Batch routing stores only the
  registered harness name, never credentials or provider SDK state.

---

# Phase 1 — Read parallel paths

## Scope

Phase 1 is a read-only projection over existing append-only requests,
completions, graphs, turns, and store log entries. It writes no canonical data
and invokes no model.

The accepted 2026-08-31 study is the live fixture for this phase: one source
node, three exact prompts, and five completed continuations per prompt.

## Primary access

The comparison lives inside the existing centered **Thread Compass**.

1. The inhabitant presses `T` from any chamber in the current session.
2. The server groups exact same-question continuations.
3. A repeated question appears as one branch group in the lineage rather than
   as an undifferentiated run of visually similar entries.
4. Selecting the group opens its comparison reading inside the same Thread
   Compass panel.
5. Selecting an individual path enters that graph through its canonical entry
   chamber.
6. `B` continues to retrace the normal walk trail.
7. `Esc` from comparison returns to the Thread Compass lineage. A second `Esc`
   closes Thread Compass and returns to the chamber.

Do not add a new comparison key. `T` already means graph generations and is the
correct home for parallel children of one source.

## Thread Compass group presentation

For a group with five completed continuations, the lineage entry reads in this
shape:

```text
When evidence of serious AI harm is incomplete…
5 parallel continuations · Grok · Codex · Claude · OpenCode · Prime Agent
Compare 5 paths
```

Requirements:

- Preserve the exact question in accessible text; visual truncation may use an
  ellipsis.
- List completion harness display names, not guessed provider families.
- Keep the individual graph-generation entries available inside the group.
- Mark the inhabited graph and mutable session head separately, as Thread
  Compass already does.
- Do not group unrelated branches merely because they share a parent graph.
- Ordinary sessions with no repeated exact question render exactly as they do
  now.

## Comparison reading

The comparison replaces the Thread Compass lineage body temporarily; it does
not open another overlay over the Compass.

Header:

```text
Parallel continuations
Five answers from the same chamber. No vote or winner is inferred.
```

It shows:

- the exact source thought;
- the exact shared question, or “continued without a new question”;
- the number of completed, failed, canceled, and still-pending paths when the
  group came from a Phase 2 batch;
- one vertically stacked path reading per completed continuation.

Use a vertical list rather than one column per model. Five columns turn the
surface into a dashboard, do not fit narrow screens, and make longer thought
objects unreadable.

Each path reading uses this order:

```text
Grok · grok-4.6
Entry claim: …
Judgment: …
Uncertainty: … / none recorded
Roads not taken: 2
Structural notes: none
Enter this path
```

Detailed rules:

- Attribution is `completion.harness` plus `graph.model.name`.
- “Entry claim” is the existing server-selected graph entry node when that node
  is a claim. Otherwise label it “Entry thought”; do not promote another node by
  browser inference.
- Show every `judgment_call` in graph order. If there is none, say “none
  recorded.”
- Show every `uncertainty` in graph order. Absence is “none recorded,” not
  certainty.
- Show the number of `rejected_alternative` nodes in the compact reading. They
  may expand in place, but the first implementation need not show every rejected
  text by default.
- Show structural or policy notes quietly and exactly. A warning is not a
  failed answer.
- “Enter this path” uses the existing Thread Compass graph-entry navigation.
- Entering a path closes Thread Compass and inhabits the path normally. `E`
  then explains that path alone.

## Structural notes and warning provenance

The 2026-08-31 study found one valid graph with the non-fatal policy warning
`supports/depends_on/shapes cycle detected`. Phase 1 must not flatten that graph
into the same structural status as the fourteen warning-free graphs.

The server supplies, separately when available:

- `recorded_warnings`: warnings written on the matching `harness_continue`
  store-log event at compile time;
- `current_policy_warnings`: warnings produced by the current graph policy
  checker at read time.

The UI labels both as structural notes and does not invent severity. If no
matching compile event exists, recorded warnings may be empty while current
policy warnings remain available.

## Deterministic comparison only

The first comparison version aligns recorded fields; it does not summarize
their semantics.

The existing deterministic normalization/Jaccard utilities may later identify
textually recurring judgment calls, but only under their recorded threshold and
with wording such as “recurring text.” They must not label low-overlap answers
as substantive disagreement or high-overlap answers as truth or consensus.

The browser receives server-authored comparison data and only renders it.

## Chamber presence

Phase 1 adds no new permanent geometry, ring color, relic, beam, sound, drawer,
or keyboard shortcut.

The only permitted chamber addition is an optional descriptive bottom-plate
sentence when at least one comparison group exists in the current session:

```text
3 same-question groups · inspect in Thread Compass
```

This hint is not required for the first implementation. Add it only if live use
shows that the Thread Compass grouping is insufficiently discoverable. Do not
add it to the persistent top line or terminal action pane.

## Phase 1 read model

Python authors the complete read model. JavaScript must not discover or group
parallel paths independently.

Recommended CLI:

```text
ta continuation compare NODE --graph GRAPH [--request REQUEST] \
  [--format table|json]
```

- Without `--request`, list comparison-eligible exact-prompt groups anchored to
  the source graph/node.
- With a completed request ID, return the group containing that request.
- A request that is not completed or does not belong to the supplied source is
  an error.
- Human table output remains compact; JSON is the complete server/UI contract.

Recommended server shape:

- Extend `GET /api/thread/SESSION_ID` with server-authored
  `parallel_groups` summaries.
- Add `GET /api/parallel/REQUEST_ID` for the detailed comparison containing the
  request's exact group.
- Use a representative completed request ID as the read-only group locator. Do
  not create a persisted comparison ID in Phase 1.

Each detailed path contains at least:

```text
request_id
completion_id
graph_id
harness
model
created_at
entry_node
judgment_calls[]
uncertainties[]
rejected_alternatives[]
node_count
edge_count
recorded_warnings[]
current_policy_warnings[]
```

## Phase 1 acceptance criteria

- The 15 live study graphs render as three groups of five.
- The groups use the exact source graph/node and exact prompt identity.
- A rephrased prompt remains separate.
- A source with only one matching completion shows no comparison action.
- Exact harness and model attribution appears for every path.
- Claude Q1 exposes its reciprocal `shapes`/`depends_on` structural note.
- Missing uncertainty reads “none recorded.”
- No winner, vote, confidence aggregate, speed ranking, or synthesized consensus
  appears.
- Entering any path uses existing graph-entry behavior and `B` retraces it.
- `Esc` returns comparison → lineage → chamber in that order.
- The comparison remains readable at narrow and wide viewport sizes.
- Opening and using it changes no graph, request, completion, session head, or
  source checksum.
- Existing single-generation Thread Compass behavior remains unchanged.
- Browser tests verify accessible labels, focus restoration, and keyboard
  behavior; server tests verify grouping and payload authorship.

Phase 1 receives a live user acceptance before Phase 2 begins.

---

# Phase 2 — Request parallel paths

## Scope

Phase 2 adds an explicit batch authoring operation. It sends one exact question
from one exact terminal chamber to two or more selected registered
collaborators. Each selected collaborator produces its own ordinary continuation
request, attempt, graph or terminal failure, and completion receipt.

The batch is launched as one user action but executes one adapter at a time.
There is never more than one active model invocation for a store.

## Access and composer

`P` is the accepted keyboard accelerator and is currently unassigned.

- `P` is available only when the standing chamber is terminal and no ordinary
  or parallel continuation is already pending.
- Pressing `P` opens the existing Workspace drawer directly at a contextual
  **Parallel Continuation Request** section. It does not create another drawer
  or centered overlay.
- The same section is pointer-accessible from Workspace when the current chamber
  is eligible.
- Pressing `P` at a non-terminal chamber does not open the composer; the bottom
  plate may briefly say “Parallel requests begin at a path ending.”
- `P` does nothing while another modal surface or text composer owns keyboard
  focus, except that Workspace may focus its already-open parallel section.
- Add `P — parallel request at a path ending` to the existing Legend controls.

The composer shows:

- a concise excerpt of the exact source thought;
- registered collaborators with checkboxes;
- the active/default collaborator preselected;
- the cached non-secret model display snapshot when present, explicitly not
  presented as authoritative completion attribution;
- one prompt input with the existing 400-character limit;
- a count-aware submit button;
- a short provider-quota consequence line.

Accepted copy shape:

```text
Parallel Continuation Request
Ask the same question from this chamber through several collaborators.

[x] Prime Agent · openai-codex/gpt-5.6-sol (thinking: high)
[x] Grok · grok-4.6
[ ] Claude · sonnet

Question: …

Send one question to 2 collaborators
Creates 2 append-only continuations and may use provider quota.
```

Require at least two selected collaborators. Do not hard-code the current set of
five as a product maximum: the number of requests and beams equals however many
registered collaborators the inhabitant explicitly selects. Phase 2
deliberately supports one prompt per batch. Do not add multiple questions, a
prompt matrix, model ranking options, temperature controls, or automatic
synthesis.

Submitting a batch does not change the globally active/default collaborator,
rewrite the installed service choice, refresh provider metadata, or relabel
history.

## Why execution is sequential

“Send” creates the whole logical batch immediately, but the single watcher
invokes adapters sequentially in the manifest's recorded order.

Do not spawn registered provider CLIs concurrently in Phase 2. True concurrent
execution would introduce provider session-cleanup collisions, local resource
spikes, rate-limit bursts, harder failure attribution, and multi-worker claiming
that protocol v1 intentionally excludes.

Sequential execution is still a valid same-question comparison because every
request records the same immutable source graph/node and exact prompt. A child
completion may advance the mutable session head, but it never becomes the next
batch member's parent.

The execution order is deterministic and recorded. Put the active/default
collaborator first, followed by the selected collaborators in registry display
order. The user need not manually reorder them in Phase 2.

## Durable batch and routing model

Phase 2 must not implement routing only in browser memory. The store gains one
append-only `ParallelContinuationBatch` sidecar and backward-compatible optional
routing fields on new `ContinuationRequest` records.

Recommended batch shape:

```json
{
  "schema_version": "1.0.0",
  "id": "ULID",
  "session_id": "ULID",
  "graph_id": "ULID",
  "node_id": "ULID",
  "created_at": "RFC3339 UTC",
  "prompt": "one exact trimmed question",
  "source": "workspace",
  "jobs": [
    {"request_id": "ULID", "harness": "prime-agent", "position": 0},
    {"request_id": "ULID", "harness": "grok", "position": 1}
  ]
}
```

New batch-created continuation requests add optional fields:

```json
{
  "requested_harness": "prime-agent",
  "parallel_batch_id": "ULID"
}
```

Existing request files without these fields remain valid and retain their
current default-harness behavior. The names are provider-neutral registry names,
not provider credentials or SDK identifiers.

Batch creation validates before writing:

- source session, graph, and node exist and agree;
- the standing node is terminal under the current server-authored traversal;
- the inbox is empty;
- the prompt is nonempty and at most 400 characters;
- at least two unique selected harnesses are registered;
- every job references the same source and prompt;
- no selected harness changes the active/default registry entry.

Batch creation and worker dequeue use one bounded store-inbox lock so the worker
cannot observe a partially authored batch. This is process coordination, not a
canonical lease or mutable claim record. Canonical artifacts remain append-only.

## Single watcher routing

Keep the one-watcher-per-store invariant.

The installed watcher continues to use its configured harness as the default
for ordinary unassigned requests. When the oldest request has
`requested_harness`, the same watcher resolves that registered `HarnessSpec` and
uses it for that request only.

Requirements:

- Exactly one adapter subprocess may be active for the store.
- The attempt's harness must equal `requested_harness`.
- The completion's harness must equal the attempt and requested harness.
- The adapter still re-reads its provider-owned model selection at invocation.
- Exact returned model attribution remains authoritative.
- After the targeted request, the watcher has not changed the registry default
  or its ordinary fallback harness.
- `ta harness run --request ID` honors and verifies a request's targeted harness
  rather than allowing a mismatched explicit harness.
- An ordinary unassigned request continues through the existing active/default
  harness path unchanged.

Do not install one service per collaborator and do not temporarily rewrite and
restart the service between batch members.

## One attempt and terminal failures

Each batch job gets at most one `ContinuationAttempt`. Automatic retries are
forbidden for parallel batches because retries would make cell counts and
comparisons ambiguous.

Add an append-only `ContinuationFailure` terminal receipt rather than
mislabeling an adapter failure as a user cancellation. It contains:

```text
schema_version
id
request_id
created_at
harness
reason_code
public_summary
```

`public_summary` is bounded, sanitized, and excludes raw provider output,
credentials, prompts beyond the already stored request, or hidden reasoning.
Useful reason codes include `adapter_error`, `timeout`, `interrupted`,
`invalid_response`, and `unavailable_harness`.

For batch requests:

- an adapter exception or timeout appends one failure receipt;
- the worker continues to the next batch job;
- a request with an existing attempt but no completion/cancellation/failure
  after worker restart becomes `interrupted` rather than being invoked again;
- pending enumeration treats completion, cancellation, or failure as terminal;
- the batch may finish `4 returned · 1 failed`;
- failures are inspectable in Thread Compass but produce no graph doorway.

Ordinary non-batch request retry behavior remains unchanged unless separately
designed and accepted later.

## Cancellation

During a batch, the terminal pane offers `cancel remaining` rather than one
ambiguous global cancel.

- Unattempted jobs receive ordinary append-only cancellation receipts.
- If a model invocation is active, cancellation closes its request; the existing
  post-invocation pending checks discard any later response before graph write.
- Completed and failed jobs remain immutable.
- Canceling the remaining jobs does not delete the batch or completed paths.

## Green request presentation

Submitting a valid batch immediately creates one green request circuit per
selected collaborator, each assigned to a distinct retained canopy neuron.

- The number of green beams equals the number of selected jobs that have not
  completed, failed, or been canceled.
- Queued beams are quieter/steadier.
- The one currently responding beam uses the stronger existing electrical
  activity.
- Use the existing green request color and meaning. Add no new queued color.
- Use one shared working sound bed regardless of batch size; never stack one
  continuous loop per request.
- Browser-local visual memory stores the request-to-neuron mapping, while the
  canonical batch/request/attempt state remains server-authored.

The terminal pane reports factual progress:

```text
Parallel request · 1 responding · 4 queued
Claude is responding from this chamber.
```

It must not imply that queued providers are thinking or that simultaneous model
execution is occurring.

## Blue completion presentation

Every successful collaborator produces one blue completion circuit and one
authored doorway. This is non-negotiable: each model produced a real graph.

- Only the completed job's green beam turns blue.
- Its own doorway rises incrementally using existing arrival geometry,
  attribution, sound, and source anchoring.
- Other unfinished jobs remain green.
- A completion may emit the existing bounded arrival splash, but continuous
  sounds do not multiply.
- Batch arrivals do not repeatedly steal focus or clear a user's selected path.
  The user is never teleported.
- Each unentered blue circuit remains anchored to the source chamber under the
  existing completion-until-entry meaning.
- Entering one doorway clears only that path's blue circuit.
- Other arrivals stay at the source and do not follow the inhabitant into the
  selected child graph.
- Browser refresh reconstructs the batch circuits and progress from durable
  state plus bounded request-to-neuron visual memory.

Progress copy advances without synthesizing an answer:

```text
3 of 5 paths returned · 1 responding · 1 queued
```

When terminal:

```text
5 parallel paths returned · press T to compare
```

or:

```text
4 paths returned · 1 failed · press T to compare
```

There is no single blue summary graph. There is also no completion state that
exists only in Thread Compass while hiding successful graph arrivals from the
chamber.

## Thread Compass during and after a batch

The exact-question group appears as soon as two completions exist and updates
incrementally. Before that, Thread Compass may show factual batch progress
without offering a completed-path comparison.

The group presents completed, failed, canceled, responding, and queued counts.
Only completed jobs have “Enter this path.” Failed paths show harness and public
failure summary. Canceled paths show that they were not completed. The group
does not rank completion order or speed.

## Phase 2 API surface

Recommended endpoints:

- `POST /api/parallel` — validate and append one batch plus routed requests;
- `POST /api/parallel/BATCH_ID/cancel` — cancel all still-pending jobs;
- the existing inhabit payload gains a server-authored `parallel_continuation`
  progress object only when the standing chamber anchors a live or completed
  batch;
- Thread Compass and `GET /api/parallel/REQUEST_ID` reuse the Phase 1 read model.

The POST body contains only:

```json
{
  "graph_id": "ULID",
  "node_id": "ULID",
  "prompt": "exact question",
  "harnesses": ["prime-agent", "grok"]
}
```

The server derives session identity, request IDs, batch ID, timestamps, ordering,
and source. JavaScript does not author canonical IDs or infer terminal state.

## Phase 2 acceptance criteria

- `P` is documented, keyboard-accessible, and available only at an eligible
  terminal chamber with an empty inbox.
- `P` opens Workspace at the parallel composer; no new drawer or overlay is
  added.
- The active/default collaborator is preselected and remains unchanged after
  submission and completion.
- The form accepts one prompt and at least two unique registered collaborators;
  it does not hard-code five as the maximum.
- Submit copy states the exact request count and provider-quota consequence.
- One immutable batch and the expected routed requests are written with the
  same source graph/node and exact prompt.
- A single worker invokes selected harnesses in recorded order with maximum
  concurrency one.
- Each job produces at most one attempt.
- Each success produces one correctly attributed direct sibling graph,
  completion, blue beam, and doorway.
- All successful graphs parent the original source even as session head changes.
- One adapter failure writes a sanitized terminal failure, receives no retry,
  and does not prevent later jobs from running.
- Cancel remaining closes only unfinished jobs and preserves finished paths.
- The number and state of green/blue beams matches durable job state.
- Only the active job is described as responding.
- Batch completions never repeatedly steal focus or teleport the inhabitant.
- One working sound bed is used; completion sounds remain bounded.
- Thread Compass incrementally groups completed paths and exposes failure state.
- Browser refresh restores correct progress without graph mutation.
- Existing `Q`, Ask from here, ordinary watcher, Workspace activation, model
  Refresh, Thread Compass, evidence descent, and Historical behavior continue to
  pass unchanged.
- Exact model attribution, provider credential isolation, append-only history,
  source immutability, and repository privacy remain intact.

Phase 2 receives live acceptance with at least two real collaborators before a
five-collaborator batch is attempted.

---

# Explicit non-goals

Neither phase adds:

- a model leaderboard;
- automatic consensus or majority voting;
- an automatically authored summary graph;
- concurrent provider execution;
- multiple questions per batch;
- arbitrary prompt matrices or eval datasets;
- temperature, seed, or provider-specific generation controls;
- a new ring color, comparison relic, or permanent chamber object;
- a new comparison drawer;
- model selection changes or provider credential management;
- hidden chain-of-thought, reasoning traces, or internal provider events;
- automatic retries for batch jobs;
- cross-session semantic grouping;
- training or preference feedback.

## Rollout and verification order

### Phase 1

1. Implement deterministic grouping and comparison read model in Python.
2. Add CLI JSON/human output and focused store/read tests.
3. Add Thread Compass grouping and comparison reading.
4. Verify keyboard, focus, responsive layout, exact attribution, structural
   notes, and zero mutation against deterministic fixtures.
5. Restart the live server and review the existing 15-graph study.
6. Obtain user acceptance before beginning Phase 2.

### Phase 2

1. Add schemas/models/store support for immutable batch, routed request, and
   terminal failure artifacts.
2. Extend the one watcher into a sequential provider-neutral router while
   preserving ordinary default-harness behavior.
3. Add server endpoints and factual batch progress payload.
4. Add Workspace composer and `P` accelerator.
5. Generalize the singleton continuation circuit into request-keyed batch
   circuits without changing single-request visuals.
6. Verify deterministic fake-adapter success, failure, interruption,
   cancellation, restoration, and maximum-concurrency-one behavior.
7. Live-accept a two-collaborator batch.
8. Only after that passes, live-accept the complete registered-collaborator
   batch and its Thread Compass comparison.

## Design guardrail

Parallel Continuations is valuable because it lets the inhabitant hold source
and question constant while preserving several attributed paths and their
negative space. If implementation begins to optimize model throughput, rank
providers, hide individual graphs behind a summary, or crowd the chamber with a
new navigation vocabulary, stop and return to this boundary.
