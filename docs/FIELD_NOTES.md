# Human-authored Field Notes

Status: single-path eligibility and one-note revision slice implemented; live acceptance pending
Authorized by: user  
Date: 2026-09-01

## Purpose

One completed collaborator path creates the local movement:

```text
follow a path → inspect it
```

Field Notes completes it:

```text
follow a path → inspect it → decide what mattered
```

An inhabitant selects at least one exact thought-object from a completed
collaborator path and writes a durable conclusion, unresolved question, or
observation in their own words. Parallel Continuations can still provide a
richer multi-path comparison, but it is optional. One completed path or exact
comparison may own one Field Note. Its stable base artifact and every later revision are immutable;
editing appends to one linear history and never creates a second monument. It
does not modify its source graphs, invoke a provider, select a winner, or
synthesize an AI consensus graph.

This is the complete Phase 1 boundary. Portability, publication, remote
references, identity, and The Atlas shared layer remain later work.

## Product rules

- Every Field Note is explicitly `human` authored.
- One completed path or exact same-question Parallel Continuations comparison
  may own exactly one Field Note. After creation, eligibility disappears and
  every write surface becomes an edit surface for that note.
- The base note and each revision are write-once. Editing appends one revision
  to a linear chain; no earlier text or source selection is overwritten.
- The first composition flow requires one to twelve selected thoughts. A
  single-path note keeps every reference in that completed graph; a parallel
  note spans at least two completed graphs in the exact comparison.
- A selected thought is identified by exact session, graph, and node ULIDs plus
  the SHA-256 of the exact stored graph JSON bytes at commit time.
- Reference order preserves the comparison/path and selection order. It is not
  a ranking.
- Python authors validation, attribution, integrity status, and read payloads.
  JavaScript renders them and never infers semantic agreement or importance.
- Creating or reading a note performs no provider call, continuation request,
  graph compilation, turn append, graph mutation, or session-head update.
- Field Notes are human interpretation, not causal evidence. They do not appear
  in evidence strata and do not change evidence results.
- The local phase has no account system: the inhabitant controlling the private
  local store is its implicit original author. When networking exists, Atlas
  identity and instance signatures must restrict revision authorship to the
  original owner while other identities branch from or respond to an exact
  revision.

## Exact local thought reference

Phase 1 uses this deliberately local reference:

```json
{
  "session_id": "01...",
  "graph_id": "01...",
  "node_id": "01...",
  "graph_sha256": "64 lowercase hexadecimal characters"
}
```

The tuple `(session_id, graph_id, node_id)` identifies one local thought. The
digest is `SHA-256` over the exact bytes of
`sessions/{session_id}/graphs/{graph_id}.json` as stored when the note is
committed. It proves that later reads resolve the same immutable source bytes;
it is not a truth score or semantic fingerprint.

The browser and CLI supply only the three IDs. The store resolves the graph,
checks that it belongs to the session, checks that the node is in the graph,
and computes the digest itself. A client-supplied digest is never trusted.

No absolute path, store path, hostname, user handle, or presumed global
instance ID enters this reference. The future portability phase may wrap or
translate this local reference into a versioned portable envelope, but it must
not rewrite existing Field Notes.

## Canonical artifact

Each note is one JSON file with this shape:

```json
{
  "schema_version": "1.0.0",
  "id": "01...",
  "created_at": "2026-09-01T12:00:00Z",
  "author": "human",
  "kind": "conclusion",
  "text": "The disagreement that matters is ...",
  "references": [
    {
      "session_id": "01...",
      "graph_id": "01...",
      "node_id": "01...",
      "graph_sha256": "..."
    },
    {
      "session_id": "01...",
      "graph_id": "01...",
      "node_id": "01...",
      "graph_sha256": "..."
    }
  ]
}
```

Validation:

- `schema_version` is the existing `1.0.0` artifact schema version;
- `id`, session, graph, and node identities are ULIDs;
- `author` is exactly `human`;
- `kind` is exactly one of `conclusion`, `unresolved_question`, or
  `observation`;
- `text` is trimmed, non-empty, and at most 4,000 characters;
- `references` contains between 1 and 12 unique exact thoughts;
- every reference stays in one Threadwalk; single-path creation additionally
  keeps them in its one completed graph;
- every source exists and passes session, node, and digest checks at commit;
- no selected source graph or node is mutated.

The note does not duplicate source text, model names, harness labels, session
titles, or absolute locations. Those are server-authored read projections over
the referenced immutable artifacts. This keeps the canonical note small and
prevents copied display metadata from becoming a second source of truth.

## Stable note identity and append-only revisions

The first artifact remains the stable Field Note identity and revision 1. An
edit writes a second artifact rather than changing it:

```json
{
  "schema_version": "1.0.0",
  "id": "01...REVISION",
  "note_id": "01...STABLE_NOTE",
  "previous_revision_id": "01...STABLE_NOTE_OR_PRIOR_REVISION",
  "created_at": "2026-09-01T13:00:00Z",
  "author": "human",
  "kind": "unresolved_question",
  "text": "The question that remains is ...",
  "references": [
    {
      "session_id": "01...",
      "graph_id": "01...",
      "node_id": "01...",
      "graph_sha256": "..."
    },
    {
      "session_id": "01...",
      "graph_id": "01...",
      "node_id": "01...",
      "graph_sha256": "..."
    }
  ]
}
```

`note_id` never changes. `previous_revision_id` is the base note ID for the
first edit and the immediately prior revision ID thereafter, producing one
inspectable linear chain. The same content and exact-source validation applies
to every revision. The ordinary read surface returns the latest revision while
also returning revision count, current revision ID, and history; an exact older
revision remains directly readable.

## Append-only store location

Field Notes can reference several graphs in one Threadwalk, so they live at
store scope rather than beneath one graph:

```text
field-notes/{note_id}.json
field-note-revisions/{note_id}/{revision_id}.json
```

`Store.write_field_note` validates all references and rejects an existing ID.
Eligibility-guarded creation uses a bounded store lock so concurrent requests
cannot create two notes for one completed path or comparison. `Store.write_field_note_revision`
requires the exact current predecessor and rejects an existing revision ID.
There is no overwrite or delete operation.

The ordinary store log records `field_note_create` or
`field_note_revision_create` with note/revision IDs, kind, exact referenced
IDs, path, and an empty warning list. It does not copy note text into the log.

## CLI surfaces

The CLI exposes the artifact independently of the browser:

```text
ta field-note create \
  --kind conclusion \
  --comparison REQUEST \
  --reference SESSION/GRAPH/NODE \
  --reference SESSION/GRAPH/NODE \
  --text "What mattered..."

ta field-note edit NOTE \
  --kind unresolved_question \
  --comparison REQUEST \
  --reference SESSION/GRAPH/NODE \
  --reference SESSION/GRAPH/NODE \
  --text "What matters now..."

ta field-note list [--graph GRAPH [--node NODE]] [--format table|json]
ta field-note show NOTE [--revision REVISION] [--format text|json]
```

`create` accepts either `--text TEXT` or `--input PATH` (including `-` for
stdin), never both. Human output shows kind, text, exact source attribution,
and whether every graph digest still matches. JSON returns the complete
server-authored read model.

`edit` accepts the same kind, comparison, reference, and text boundary as
creation but appends to the named note. `list` is chronological and may filter
by any exact graph/node referenced anywhere in the note's history. `show`
defaults to the current revision and `--revision` selects the stable base ID or
an exact revision ID. It resolves that revision's references into their exact
thought text, kind, status, model, harness when recorded, session title, and
entry target. Missing or mismatched source bytes are reported as an integrity
failure; raw artifacts remain readable and are never silently repaired.

## Server surfaces

```text
POST /api/field-notes
GET  /api/field-notes?graph=GRAPH&node=NODE
POST /api/field-notes/NOTE/revisions
GET  /api/field-notes/NOTE[?revision=REVISION]
```

The write body is:

```json
{
  "kind": "observation",
  "text": "...",
  "comparison_request_id": "01...",
  "references": [
    {"session_id": "01...", "graph_id": "01...", "node_id": "01..."},
    {"session_id": "01...", "graph_id": "01...", "node_id": "01..."}
  ]
}
```

`comparison_request_id` is an optional write-time guard, not part of the
canonical note or revision. Parallel creation supplies it. Single-path creation
instead supplies `source_graph_id` and `source_node_id`; the server verifies
that the source graph is a completed continuation and keeps every submitted
reference inside it. The store then validates exact references and computes
hashes.

Creation additionally rejects a completed path or comparison that already owns
a Field Note. Revision creation keeps a single-path note within its earning
graph or requires a parallel note to belong to the supplied comparison.

The detailed Parallel Continuations payload adds `selectable_thoughts` for
every path in canonical graph order and `field_notes` whose references touch at
least two graphs in that comparison. `GET /api/inhabit/...` adds compact
`field_notes` for the exact standing graph/node so rediscovery is
server-authored.

## Composition and chamber flow

Field Notes attach to one completed collaborator path or an exact Parallel
Continuations comparison. Python marks the terminal chamber eligible after the
completion receipt exists and the session has no pending work. JavaScript does
not infer eligibility.

1. At an eligible completed path ending, a floating **Field Note Eligible** prompt says
   **press W to write** and emits a restrained ethereal procedural cue after
   browser sound has awakened.
2. `W` opens the completed path's Field Note composer inside Thread Compass and
   preselects the standing thought. For a Parallel comparison, `T` → comparison
   → **Write Field Note** remains an equivalent entrance.
3. The supplied `field-notes-writing-loop` plays only while the composer is
   active.
4. Each available path reveals its public thought-objects in recorded graph order.
5. Select 1–12 exact thoughts. A parallel note must represent at least two paths.
   Every selection shows harness/model attribution, kind, status, and exact text.
6. Choose conclusion, unresolved question, or observation.
7. Write up to 4,000 characters and review the selected references in their
   preserved order. `Enter` commits when valid; `Shift+Enter` inserts a line.
8. The immutable base note is written once. The composer closes back to the same
   chamber and its writing loop stops.
9. An 18-second `field-notes-monument-construction-loop` accompanies the
   hologram monument while it materializes. Completion swaps to the permanent
   model and plays `field-notes-monument-complete`.
10. A small amber/blue neuron halo circles the monument until its first entry.
    First-entry state is browser-local atmosphere, not canonical note state.
11. Entering plays `field-notes-scribe-entry`, dissipates the first-entry halo,
    and inhabits the note without turning it into a graph node.
12. Once authored, the floating eligibility message and `W` invitation vanish.
    Thread Compass presents **Edit Field Note** instead.
13. Editing begins from the latest kind, text, and exact selections. Saving
    appends a revision, returns to the same note reader, and does not replay the
    monument construction/completion ceremony because the monument already
    exists.

Existing notes appear above the comparison path readings under **Human Field
Notes**. A note card visibly distinguishes its kind and human authorship.
Opening it shows the current note text followed by each exact referenced thought
and an **Enter this thought** action. Its revision history opens every older
text and its corresponding exact selections without changing the current note.

Thread Compass also nests one stable note card beneath its Parallel
Continuations group. Revisions remain inside that card rather than becoming
siblings or graph generations. They are connective human inscriptions, not
children, votes, or merged paths.

When standing at a referenced chamber, the server-authored bottom plate says
`N human Field Notes · inspect in Thread Compass`. Opening `T` places those notes
in a **Field Notes from this chamber** section. The same immutable note is also
projected as a permanent Field Notes Monument in the chamber's left-side human
inscription alcove. A note selected from several chambers is not duplicated in
storage; each monument is a doorway to the one store-scoped artifact.
If an edit changes the selections, the monument remains discoverable at every
chamber referenced by any revision so old archaeological doorways never vanish.
Every doorway opens the stable note's current revision; its history exposes the
older chamber selections. A newly referenced chamber receives the same permanent
monument on entry, not a second stored object.

Left placement is deliberate spatial grammar: story consequences remain ahead,
rejected roads and human interpretation remain leftward but separate, AI
arrivals remain rightward, and returns remain behind. Field Note monuments are
placed beyond existing rejected-road rows so they do not displace story
geometry. Their amber ring and notebook/pen form distinguish them from ghosted
negative-space relics.

Inside a monument, the current note kind and exact human text occupy the
ordinary main reading plate and identify its revision count. `B`, down, or
Escape returns to the source chamber. `E` opens **Field Note source selections**
for the current revision in recorded order with exact attribution, text, IDs,
and integrity. This reuses the archaeological descent surface as an
inspection gesture while explicitly saying that human selection context is not
causal evidence and creates no `EvidenceBinding`.

While a Field Note textarea owns focus, ordinary chamber shortcuts do not fire.
`Esc` first leaves the composer without writing. Submitting disables the commit
control until the request succeeds or fails, preventing accidental duplicate
notes from one gesture.

## Read-model wording

Use these visible labels:

- `Human Field Note`
- `conclusion`
- `unresolved question`
- `observation`
- `Exact referenced thought`
- `Enter this thought`
- `Source integrity verified`

Do not use `annotation`, `consensus`, `summary`, `winner`, `agreement score`,
or `confidence` as substitutes. A Field Note records what mattered to one
inhabitant; it does not settle what should matter to everyone.

## Tests

### Artifact and store

- schema accepts all three kinds and one to twelve exact references, and rejects
  unknown kinds, empty/oversized text, malformed hashes, duplicate references,
  zero references, and more than twelve references;
- creation computes exact stored graph-byte SHA-256 values;
- wrong session/graph/node combinations are rejected;
- writing the same note ID twice is rejected;
- a second note for the same completed path or comparison is rejected, including
  under the store lock, and eligibility disappears after the first;
- editing preserves the base bytes, appends a mode-`0600` revision with the
  exact current predecessor, and rejects overwrite or a branched predecessor;
- latest and exact historical reads return the correct text and selections;
- source graph bytes, turns, session heads, continuation artifacts, and the
  pending inbox are unchanged by note creation;
- list/filter/show are deterministic and report source integrity.

### CLI and server

- CLI create/edit/list/show table and JSON paths preserve stable note,
  revision, exact IDs, and text;
- server creation accepts only references from the guarded completed path or comparison;
- GET detail and exact chamber filtering return server-authored attribution;
- hidden reasoning never enters a Field Note payload;
- creating and reading notes invoke no harness/provider function.

### Inhabit Space

- a completed path exposes all selectable public nodes in graph order;
- selection requires 1–12 thoughts; a parallel note requires two distinct paths;
- kind and multiline text remain stable while focused;
- commit produces one note and returns to the same comparison/chamber context;
- after commit, the eligibility prompt is absent and the comparison exposes
  edit rather than a second creation action;
- edit is prefilled from current content, saves one revision, exposes history,
  and does not reconstruct the stable monument;
- existing notes reopen from the comparison and every referenced chamber;
- terminal completed paths receive server-authored eligibility and `W`
  preselects the standing thought;
- writing, construction, completion, and entry sounds follow their exact
  lifecycle without stacking after exit;
- hologram construction swaps to the permanent monument after 18 seconds;
- exact referenced chambers show the left-side monument and Thread Compass
  nests notes under their comparison group;
- the first-entry neuron halo is browser-local and dissipates only for the
  entered note;
- monument entry puts note text on the main plate and `E` shows exact source
  selections without presenting them as evidence;
- `Esc` returns a single-path composer to its chamber and retraces a parallel
  composer → comparison → lineage → chamber;
- the layout remains usable at wide and 375 px widths.

### Regression

- all existing graph, evidence, continuation, harness, Thread Compass, browser
  syntax, and static-asset tests remain green;
- strict store/session validation includes Field Notes without changing Graph
  schema `1.0.0` or existing immutable artifacts.

## Live acceptance gate

Before Public Local Preview work begins:

1. Stand at a real parallel-path ending and confirm the floating eligibility
   prompt and ethereal cue appear once.
2. Press `W`, confirm the standing thought is preselected, select a second
   path, and verify the writing loop stops when the composer closes.
3. Commit the one Field Note with `Enter`; observe the complete 18-second
   hologram/construction-loop transition, completion cue, permanent monument,
   and first-entry neuron halo.
4. Enter the monument, confirm the scribe-entry cue and halo dissipation, read
   the note on the main plate, and use `E` to inspect every source selection.
5. Confirm its kind, human authorship, exact text, referenced graph/node IDs,
   and graph hashes.
6. Confirm every referenced source graph has the same SHA-256 bytes as before.
7. Close and reopen Inhabit Space and recover the note without restoring the
   first-entry halo in that browser.
8. Open it from the original comparison and from every referenced chamber.
9. Enter every referenced thought from the note and retrace normally.
10. Confirm the eligibility invitation is now absent and the exact comparison
    offers **Edit Field Note**, not a second note.
11. Edit its kind, text, or selections; confirm the monument does not reconstruct,
    the stable note ID remains, and both revisions and their exact selections
    remain inspectable.
12. Create or inspect each visible kind: conclusion, unresolved question, and
    observation.
13. Confirm no continuation request, provider call, compiled graph, turn, or
    session-head change occurred.
14. Run the complete local suite and GitHub Python 3.11/3.12 workflow.
15. Obtain explicit user live acceptance.

## Explicit deferrals

Phase 1 does not add:

- single-thought or single-graph notes;
- deletion, drafts, reactions, tags, search, or automatic suggestions;
- agent-authored or agent-proposed note text;
- semantic clustering, agreement detection, voting, ranking, synthesis, or
  confidence aggregation;
- new graph node/edge kinds or mutation of graph schema `1.0.0`;
- evidence bindings derived from Field Notes;
- portable reference envelopes, bundles, imports, or migrations;
- runtime instance identity, signatures, handles, accounts, permissions,
  publication, remote references, networking, presence, or The Atlas
  service (the accepted GitHub-gated identity bootstrap is preserved in the
  shared-world specification for that later slice);
- generalized annotation geometry, note-to-note links, remote monuments,
  monument publication, or a social feed.

After live acceptance, development stops at this gate and moves to the separate
Public Local Preview readiness phase. Portability begins only after independent
lived use produces a grounded portability question and the user explicitly
authorizes it.
