# Human-authored Field Notes

Status: implementation authorized; live acceptance pending  
Authorized by: user  
Date: 2026-09-01

## Purpose

Parallel Continuations created the local movement:

```text
ask together → inspect separately
```

Field Notes completes it:

```text
ask together → inspect separately → decide what mattered
```

An inhabitant selects exact thought-objects from at least two paths in one
Parallel Continuations comparison and writes a durable conclusion, unresolved
question, or observation in their own words. The note is a new immutable human
artifact. It does not modify its source graphs, invoke a provider, select a
winner, or synthesize an AI consensus graph.

This is the complete Phase 1 boundary. Portability, publication, remote
references, identity, and the Master Atlas remain later work.

## Product rules

- Every Field Note is explicitly `human` authored.
- Notes and their references are append-only.
- The first composition flow requires at least two selected thoughts from at
  least two distinct graphs in one exact same-question comparison.
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
- `references` contains between 2 and 12 unique exact thoughts;
- at least two distinct `graph_id` values are present;
- every source exists and passes session, node, and digest checks at commit;
- no selected source graph or node is mutated.

The note does not duplicate source text, model names, harness labels, session
titles, or absolute locations. Those are server-authored read projections over
the referenced immutable artifacts. This keeps the canonical note small and
prevents copied display metadata from becoming a second source of truth.

## Append-only store location

Field Notes span sessions, so they live at store scope rather than beneath one
session:

```text
field-notes/{note_id}.json
```

`Store.write_field_note` validates all references and rejects an existing ID.
There is no update or delete operation in Phase 1. Corrections are new notes;
later correspondence may relate them without rewriting either artifact.

The ordinary store log records one `field_note_create` event with note ID,
kind, exact referenced IDs, path, and an empty warning list. It does not copy
the note text into the log.

## CLI surfaces

The CLI exposes the artifact independently of the browser:

```text
ta field-note create \
  --kind conclusion \
  --comparison REQUEST \
  --reference SESSION/GRAPH/NODE \
  --reference SESSION/GRAPH/NODE \
  --text "What mattered..."

ta field-note list [--graph GRAPH [--node NODE]] [--format table|json]
ta field-note show NOTE [--format text|json]
```

`create` accepts either `--text TEXT` or `--input PATH` (including `-` for
stdin), never both. Human output shows kind, text, exact source attribution,
and whether every graph digest still matches. JSON returns the complete
server-authored read model.

`list` is chronological and may filter by exact graph/node. `show` resolves
every reference into its current exact thought text, kind, status, model,
harness when recorded, session title, and entry target. Missing or mismatched
source bytes are reported as an integrity failure; the raw note remains
readable and is never silently repaired.

## Server surfaces

```text
POST /api/field-notes
GET  /api/field-notes?graph=GRAPH&node=NODE
GET  /api/field-notes/NOTE
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

`comparison_request_id` is a write-time guard, not part of the canonical note.
The server loads that exact eligible comparison and requires every submitted
graph to be one of its completed paths. This prevents the first UI from
quietly becoming a generalized cross-store annotation endpoint. It then lets
the store validate the exact thought references and compute hashes.

The detailed Parallel Continuations payload adds `selectable_thoughts` for
every path in canonical graph order and `field_notes` whose references touch at
least two graphs in that comparison. `GET /api/inhabit/...` adds compact
`field_notes` for the exact standing graph/node so rediscovery is
server-authored.

## Thread Compass flow

Field Notes use the existing Thread Compass rather than a new global key,
drawer, chamber relic, or evidence surface.

1. Open `T` and enter an eligible Parallel Continuations comparison.
2. Choose **Write Field Note**.
3. Each path reveals its public thought-objects in recorded graph order.
4. Select 2–12 exact thoughts across at least two paths. Every selection shows
   harness/model attribution, kind, status, and exact text.
5. Choose conclusion, unresolved question, or observation.
6. Write up to 4,000 characters in a multiline field.
7. Review the selected references in their preserved order.
8. Choose **Commit Field Note** once.
9. The immutable note opens inside Thread Compass; the chamber behind it is not
   replaced.
10. `Esc` returns to the comparison, then lineage, then the chamber.

Existing notes appear above the comparison path readings under **Human Field
Notes**. A note card visibly distinguishes its kind and human authorship.
Opening it shows the note text followed by each exact referenced thought and an
**Enter this thought** action.

When standing at a referenced chamber, the server-authored bottom plate says
`N human Field Notes · inspect in Thread Compass`. Opening `T` places those notes
in a **Field Notes from this chamber** section. This is the Phase 1 rediscovery
path; there is no new keyboard shortcut or permanent 3D object.

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

- schema accepts all three kinds and rejects unknown kinds, empty/oversized
  text, malformed hashes, duplicate references, fewer than two references,
  more than twelve references, and fewer than two distinct graphs;
- creation computes exact stored graph-byte SHA-256 values;
- wrong session/graph/node combinations are rejected;
- writing the same note ID twice is rejected;
- source graph bytes, turns, session heads, continuation artifacts, and the
  pending inbox are unchanged by note creation;
- list/filter/show are deterministic and report source integrity.

### CLI and server

- CLI create/list/show table and JSON paths preserve exact IDs and text;
- server creation accepts only references from the guarded comparison;
- GET detail and exact chamber filtering return server-authored attribution;
- hidden reasoning never enters a Field Note payload;
- creating and reading notes invoke no harness/provider function.

### Inhabit Space

- comparison exposes all selectable public nodes in graph order;
- selection requires 2–12 thoughts and two distinct paths;
- kind and multiline text remain stable while focused;
- commit produces one note and returns to the same comparison/chamber context;
- existing notes reopen from the comparison and every referenced chamber;
- `Esc` retraces composer → comparison → lineage → chamber;
- the layout remains usable at wide and 375 px widths.

### Regression

- all existing graph, evidence, continuation, harness, Thread Compass, browser
  syntax, and static-asset tests remain green;
- strict store/session validation includes Field Notes without changing Graph
  schema `1.0.0` or existing immutable artifacts.

## Live acceptance gate

Before Public Local Preview work begins:

1. Create one Field Note from a real multi-path comparison.
2. Confirm its kind, human authorship, exact text, referenced graph/node IDs,
   and graph hashes.
3. Confirm every referenced source graph has the same SHA-256 bytes as before.
4. Close and reopen Inhabit Space and recover the note.
5. Open it from the original comparison and from every referenced chamber.
6. Enter every referenced thought from the note and retrace normally.
7. Create or inspect each visible kind: conclusion, unresolved question, and
   observation.
8. Confirm no continuation request, provider call, compiled graph, turn, or
   session-head change occurred.
9. Run the complete local suite and GitHub Python 3.11/3.12 workflow.
10. Obtain explicit user live acceptance.

## Explicit deferrals

Phase 1 does not add:

- single-thought or single-graph notes;
- editing, deletion, drafts, reactions, tags, search, or automatic suggestions;
- agent-authored or agent-proposed note text;
- semantic clustering, agreement detection, voting, ranking, synthesis, or
  confidence aggregation;
- new graph node/edge kinds or mutation of graph schema `1.0.0`;
- evidence bindings derived from Field Notes;
- portable reference envelopes, bundles, imports, or migrations;
- instance identity, signatures, handles, accounts, permissions, publication,
  remote references, networking, presence, or a Master Atlas service;
- new chamber geometry, sound, beam, ring, global shortcut, or social feed.

After live acceptance, development stops at this gate and moves to the separate
Public Local Preview readiness phase. Portability begins only after independent
lived use produces a grounded portability question and the user explicitly
authorizes it.
