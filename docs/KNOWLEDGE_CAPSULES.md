# Knowledge Capsules

Status: approved local implementation slice
Authorized by: user
Date: 2026-09-01

## Purpose

A Knowledge Capsule carries one completed, human-interpreted inquiry milestone
out of Thought Archaeology as a private Markdown dossier:

```text
ask together → inspect separately → decide what mattered → carry it forward
```

It is a readable projection over immutable local artifacts. It is not a truth
certificate, consensus result, hidden-reasoning export, lossless backup, import
bundle, publication action, or network message.

## Eligibility

Python offers one Capsule at the exact source chamber of a Parallel
Continuations comparison only when:

- the exact-source/exact-prompt comparison has at least two completed paths;
- its one stable Field Note exists;
- the current Field Note revision and every selected source verify;
- every continuation request in the owning session is completed, failed, or
  canceled; and
- no Capsule manifest already names that comparison and stable Field Note.

No word, node, time, model, confidence, popularity, agreement, or semantic
quality score participates. Browser-local unread or entered state is not
canonical eligibility.

## Frozen manifest

Pressing `K` appends one mode-`0600` `KnowledgeCapsuleManifest` under:

```text
knowledge-capsules/{capsule_id}.json
```

The manifest pins the human author, owning session and title, current session head,
qualifying comparison source, stable Field Note and exact current revision,
creation time, rendering version, privacy warning, omissions, and an ordered
inventory of every included immutable artifact with its exact SHA-256.

The snapshot includes all artifacts already present in the owning session:
turn records, public graphs, continuation requests and their attempt/completion/
failure/cancellation receipts, Parallel Continuation batches, Field Notes and
revisions touching that session, graph diffs, probes, evidence bindings,
attributions, neural interventions, and bounded training-provenance records.
Mutable `session.json`, the store log, canvases, fingerprints, raw sensor
sources, credentials, browser atmosphere, and unrelated sessions are not
included artifacts. The manifest embeds the exact session/head values observed
at construction instead of treating later `session.json` mutations as Capsule
corruption.

A turn hash covers the exact UTF-8 JSONL record including its newline. Every
other artifact hash covers the exact stored file bytes. Construction is
write-once and guarded so the same Field Note/comparison milestone cannot
create a second launcher.

## Launch

Launching renders only the IDs frozen in the manifest. It writes:

```text
exports/knowledge-capsules/{capsule_id}/knowledge-capsule.md
```

with mode `0600`, then appends one mode-`0600` launch receipt under:

```text
knowledge-capsule-launches/{capsule_id}.json
```

The receipt pins one launch ID and time, the store-relative Markdown path, and
its SHA-256. If rendering or writing fails, no receipt is written and launch
remains retryable. If the Markdown was written but receipt creation was
interrupted, a retry accepts only the exact deterministic bytes and completes
the receipt. An existing receipt rejects relaunch.

The Markdown order is deterministic:

1. identity, scope, privacy warning, and non-claims;
2. chronological human and assistant turns;
3. public graph generations, attribution, nodes, and typed edges;
4. continuation, comparison, failure, cancellation, cut, and veto history;
5. Field Notes with full included revision history and exact selections;
6. evidence/provenance summaries and artifact references;
7. exact ID/SHA-256 integrity appendix;
8. explicit omissions.

`hidden_reasoning` is never rendered even when an exact graph-byte hash covers
a legacy canonical graph containing that field.

## Read surfaces

The CLI exposes:

```text
ta capsule construct --comparison REQUEST
ta capsule launch CAPSULE
ta capsule list [--session SESSION] [--format table|json]
ta capsule show CAPSULE [--format text|json]
```

The localhost server exposes:

```text
POST /api/knowledge-capsules
POST /api/knowledge-capsules/CAPSULE/launch
GET  /api/knowledge-capsules[?session=SESSION]
GET  /api/knowledge-capsules/CAPSULE
```

Python authors eligibility, lifecycle state, pinned scope, paths, integrity,
and read wording. JavaScript does not infer achievement or export scope.

## Chamber lifecycle

- At the qualifying source chamber, **Knowledge Capsule Earned · Press K to
  construct** appears and its supplied cue plays once per browser memory.
- `K` freezes the manifest. The supplied hologram and construction loop run for
  18 seconds on the first raised rear-right outbound terrace that clears every
  planned chamber object. During construction, the Field Note invitation and
  other floating actions are suppressed; layered energy rings and particles
  make the build state visible.
- Completion swaps to the ready launcher, plays the completion cue, crossfades
  into the ready hum, emits a bounded flash/shockwave/smoke cloud, starts a
  larger bright orange neuron orbit, and exposes only **Press Enter to Launch
  Capsule**. Enter performs the same server-success-gated one-shot launch.
- Successful launch plays the supplied launch cue and a bounded flash while the
  charged Capsule fires a pulsing exhaust, points its crown along the live
  flight-path tangent, rises with a bright core and broad smoke trail, then
  curves toward one visible canopy neuron. It does not tumble or travel
  sideways. The target is local atmosphere, not evidence or a recipient. Once
  launch succeeds, ordinary chamber invitations may return.
- The launcher becomes the permanent post-launch model and remains selectable.
  Its reading shows identity, pinned scope, launch time, integrity, and local
  Markdown path. It never becomes a graph generation.
- Reload after manifest creation restores the ready launcher without replaying
  construction. Reload after the receipt restores the spent launcher without
  replaying the flight.

Thread Compass nests the Capsule beneath its stable Field Note and shows the
pinned Field Note revision and session head. One canonical launcher exists only
at the comparison source chamber; referenced Field Note chambers do not receive
duplicates.

## Explicit deferrals

This slice adds no upload, publication, recipients, remote execution, portable
round-trip bundle, import, signing, GitHub or Atlas identity, connection
request, public discovery, presence, or Master Atlas service. A local launch is
private and inert. Public Local Preview work starts only after the user performs
and accepts the first real one-shot Capsule ceremony.
