# Portable inquiries — first slice

Status: development on top of v0.3.1; not in the released installer yet.

Open **Portable inquiries** in your Atlas window or Workspace. Choose one
Threadwalk, enter a sharing name and description, and review the export. Expand
each answer and the exact file inspection before saving `.atlas-inquiry.json`.
Atlas prepares a file; it does not upload or send it anywhere.

The recipient opens **Portable inquiries**, chooses that file, reviews it, and
selects **Import and visit**. The imported library keeps it available for later
visits. The existing renderer provides terrain, sound, music, Reflect, Thread
Compass and the thought map. Continuations retain source-return doors.
**Return to my Atlas** leaves the shared visit.

With a guide assigned in the recipient's own Workspace, **G** opens private
discussion about the exact selected thought. Import and navigation never call
a model. The guide uses the recipient's provider with its ordinary permissions
and billing. Discussion stays outside the snapshot and is not returned to the
publisher.

## What travels

- All graph generations in the selected session: prose, thought objects,
  relationships, model labels, fork reasons and continuation questions.
- Original session/graph/node identities and closed ancestry/source references.
- Evidence bindings with HTTP(S) references and no embedded URL credentials.
  Review/import does not fetch those URLs or local files.
- Publisher-supplied sharing name, description and a local origin identity.
- Separate checksums for each original graph file and its shared projection,
  plus a content-derived snapshot identity.

Hidden reasoning, private graph metadata, sensor/probe references, unattached
turns, agent discussions/memory, settings, credentials, local evidence files,
Field Notes and Knowledge Capsules are excluded. Text in an answer, thought,
fork reason, question or web URL may itself be private; review it before sharing.
This is not an automatic secret detector.

Sharing names and original-source checksums are publisher claims, not signatures
or verified identities. A changed snapshot gets a new identity. First-slice
limits are 8 MiB and 256 graphs. Cross-session ancestry is rejected rather than
silently exporting another private inquiry.

## Storage and authority

Existing graph schemas and Store remain canonical. The bundle is a versioned
transport envelope (`atlas-inquiry`, version 1), not a second graph format.
Import validates schemas, hashes and references before materialization. A
temporary Store is validated and atomically renamed into place. An identical
reimport reuses the snapshot.

```
<store>/portable-origin.json
<store>/imported-inquiries/<snapshot-id>/inquiry.json
<store>/imported-inquiries/<snapshot-id>/data/...
<store>/inquiry-discussions/<snapshot-id>/guide-discussions/...
```

Normal sessions and heads stay untouched even when identities collide. Imported
reads use a scoped local API and the normal renderer. That API rejects graph
writes; only private guide discussion and its clear action are enabled. Browser
route/stand memory is scoped to the snapshot. Guide context and receipts carry
the snapshot, origin, attribution and both graph checksums.

## CLI

```
ta inquiry export --session SESSION_ID --author "Sharing name" --output walk.atlas-inquiry.json
ta inquiry inspect walk.atlas-inquiry.json
ta inquiry import walk.atlas-inquiry.json
ta inquiry list
```

Use the existing `--store PATH` option to select an initialized store. Export
refuses to overwrite a file. Inspect is read-only. Review the exported JSON
before sharing it.

## Acceptance and later work

`tests/test_portable.py` uses synthetic publisher/recipient stores to exercise
projection, exact sources, colliding identities, duplicate import, damaged
hashes/references/fields, atomic failure, CLI, scoped HTTP reads, mutation
rejection and private guide discussion.

Physical Windows acceptance uses the existing packaging-test PC and separate
test stores. The release update and candidate test require the OS to permit
execution through its normal approval process. Never replace real inquiry data.

Private continuation and local offer-back/acceptance are now a development
increment described in [returned paths](RETURNED_PATHS.md). Portable inquiries
will ship in the [combined online milestone](ONLINE_ATLAS.md), not separately.
Upload hosting, verified authors and the shared isometric overworld remain in
that milestone; live co-walking is later work.
