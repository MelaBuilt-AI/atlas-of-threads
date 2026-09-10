# Knowledge Capsules

Status: existing local implementation, with an accepted shared Capsule plan
Local slice authorized: 2026-09-01
Shared local/online direction accepted: 2026-09-10

## Accepted plan: Capsules carry inquiries between places

Capsules become deliberate invitations, offerings and returns. An online launcher
serves as a Threadwalk's outbound port and a visible history of its expeditions.
Each Capsule has one reviewed payload and one launch; an online port can serve
successive Capsules. Invitations and returns are the first end-to-end priority.
This section is an accepted plan, not implemented behavior.

### Intent, contents and destination

The preparation flow separates three decisions:

1. **Intent**: Invite perspectives (a question, challenge or request for evidence),
   Share a finding (an explanation, method, discovery or useful failed approach),
   or Return a contribution (a response anchored to an incoming Capsule/inquiry).
2. **Contents**: select the exact question, thoughts, evidence and interpretation
   to carry; review the complete payload before it is frozen for launch.
3. **Destination**: keep it privately in Personal Atlas, export a Capsule file,
   or send through the connected online Atlas as an open invitation or a directed
   delivery. Online destinations are offered only when connected and authorized.

Return intent is contextual: it requires an incoming Capsule/inquiry and its
source reference, including one received offline by file. An unrelated inquiry
cannot invent a return relationship. Audience and destination are explicit;
intent alone never publishes content or invokes an agent.

### Personal Atlas and the online Atlas align

Personal Atlas adopts the same intent-bearing Capsule and preparation flow.
Local-only users can prepare, keep, export, receive and work with Capsules offline,
including exchanging files with another person or deliberately giving their own
agent the selected context. Connecting later enables online delivery of reviewed
Capsules; it does not automatically upload existing local Capsules or launches.
The readable Markdown remains a useful view alongside the structured portable
contents rather than being the Capsule's only purpose.

The new flow should build on existing portable inquiries, canonical artifacts
and returned-path references. Existing manifests, one-shot launch receipts and
private exports retain their original meaning and remain readable. Do not
silently reinterpret old launches as online publications. The old earning rule
is not automatically a prerequisite for a new online invitation: deliberate
preparation and review supply its purpose. Exact eligibility/lifecycle migration
is implementation work, not an invented score or popularity requirement.

### Witnessed launch, response and return

A real committed online launch produces one shared event. Current observers see
its charge, flight and fading trail at the source Threadwalk, with distance/zoom
attenuating effects and sound; muted and reduced-motion preferences apply. The
viewer keeps control of their camera. Late arrivals see Capsule state and history
rather than old launches replayed as present activity. Local-only ceremonies do
not appear as online events.

Open invitations remain discoverable at their source; directed deliveries await
the recipient's attention. Another inhabitant can take up a question privately
and offer an attributed return. The source author reviews and accepts it before
it becomes an accepted connection. Return flights can be witnessed too. Those
meaningful contribution connections remain distinct from geographic map roads.
Launcher history exposes sent, open, returned and accepted expeditions.

Live witnessing, destinations, the shared Capsule format and local alignment are
planned work within the combined online milestone. Private cluster destinations
follow the separately deferred group/organization access design.

## Existing local implementation

The remainder documents the currently shipped private local Capsule contract.
It remains authoritative for old artifacts until an explicit implementation and
compatibility update delivers the shared plan above.

## Purpose

A Knowledge Capsule carries one completed, human-interpreted inquiry milestone
out of Thought Archaeology as a private Markdown dossier:

```text
follow a path → decide what mattered → carry it forward
```

It is a readable projection over immutable local artifacts. It is not a truth
certificate, consensus result, hidden-reasoning export, lossless backup, import
bundle, publication action, or network message.

## Eligibility

Python offers one Capsule after either one completed collaborator path or a
richer Parallel Continuations comparison when:

- at least one collaborator path has completed;
- its stable human Field Note exists and selects at least one exact thought;
- the current Field Note revision and every selected source verify;
- every continuation request in the owning session is completed, failed, or
  canceled; and
- no Capsule manifest already names that stable Field Note; and
- no unspent launcher is already stored anywhere in the Personal Atlas.

Parallel Continuations remains an optional richer earning route. It is never a
subscription requirement.

## Construct now or store

The earned notice offers two choices:

- `K · Construct here` freezes the Capsule immediately at the current chamber.
- `J · Store launcher` appends one private, immutable record under
  `knowledge-capsule-launchers/{launcher_id}.json` without freezing or exporting
  anything.

Only one unspent launcher may be stored at a time. It persists across reloads,
belongs only to the Threadwalk where it was earned, and suppresses further
Capsule earning until used. Within that Threadwalk, `K · Deploy here` constructs
the Capsule at whichever chamber the inhabitant chooses. Another Threadwalk
cannot use it. A failed construction leaves it stored and retryable; it becomes
spent only when a manifest successfully names its launcher ID.

No word, node, time, model, confidence, popularity, agreement, or semantic
quality score participates. Browser-local unread or entered state is not
canonical eligibility.

## Frozen manifest

Pressing `K` appends one mode-`0600` `KnowledgeCapsuleManifest` under:

```text
knowledge-capsules/{capsule_id}.json
```

The manifest pins the human author, owning session and title, current session head,
deployment chamber, earning chamber, optional qualifying comparison, stable
Field Note and exact current revision,
creation time, rendering version, privacy warning, omissions, and an ordered
inventory of every included immutable artifact with its exact SHA-256.

The snapshot includes all artifacts already present in the owning session:
turn records, public graphs, continuation requests and their attempt/completion/
failure/cancellation receipts, Parallel Continuation batches, Field Notes,
stored launcher records, and
revisions touching that session, graph diffs, probes, evidence bindings,
attributions, neural interventions, and bounded training-provenance records.
Mutable `session.json`, the store log, canvases, fingerprints, raw sensor
sources, credentials, browser atmosphere, and unrelated sessions are not
included artifacts. The manifest embeds the exact session/head values observed
at construction instead of treating later `session.json` mutations as Capsule
corruption.

A turn hash covers the exact UTF-8 JSONL record including its newline. Every
other artifact hash covers the exact stored file bytes. Construction is
write-once and guarded so the same Field Note milestone cannot
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
POST /api/knowledge-capsule-launcher/store
POST /api/knowledge-capsules/CAPSULE/launch
GET  /api/knowledge-capsules[?session=SESSION]
GET  /api/knowledge-capsules/CAPSULE
```

Python authors eligibility, lifecycle state, pinned scope, paths, integrity,
and read wording. JavaScript does not infer achievement or export scope.

## Chamber lifecycle

- At the qualifying chamber, **Knowledge Capsule Earned** offers `K · Construct
  here` and `J · Store launcher` and its supplied cue plays once per browser
  memory.
- A stored launcher appears throughout its earning Threadwalk as **Stored
  Launcher ×1 · K · Deploy here**. It is not offered in any other Threadwalk.
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

Thread Compass nests a constructed Capsule beneath its stable Field Note and
shows the pinned Field Note revision and session head. The manifest separately
pins the earning and deployment chambers.

## Explicit deferrals

This slice adds no upload, publication, recipients, remote execution, portable
round-trip bundle, import, signing, GitHub or Atlas identity, connection
request, public discovery, presence, or The Atlas shared service. A local launch is
private and inert. Public Local Preview work starts only after the user performs
and accepts the first real one-shot Capsule ceremony.
