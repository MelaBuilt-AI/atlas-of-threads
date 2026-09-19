# Knowledge Capsules

Status: offline preparation and connected delivery/receipt/return decisions are
implemented in the development branch, including witnessed expeditions and history.
Local slice authorized: 2026-09-01
Shared local/online direction accepted: 2026-09-10

## Accepted plan: Capsules carry inquiries between places

Capsules become deliberate invitations, offerings and returns. An online launcher
serves as a Threadwalk's outbound port and a visible history of its expeditions.
Each Capsule has one reviewed payload and one launch; an online port can serve
successive Capsules. Invitations and returns are the first end-to-end priority.
Offline preparation and connected delivery/acceptance are implemented below.
Witnessed launch behavior is implemented as described below.

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

Live witnessing is implemented within the combined online milestone. Private cluster
destinations follow the separately deferred group/organization access design.

## Implemented offline preparation and exchange — September 10

Personal Atlas's **Capsules** button opens preparation and a local library.
Choose invitation or offering, supply a sharing name and message, optionally add
human interpretation, then choose a local Threadwalk and individual thoughts.
Public web evidence attached to those thoughts is separately selected. Full answer
prose and the source question are optional, separately reviewed additions; a full
answer can contain otherwise unselected thoughts. Message-only Capsules are valid.
No earned legacy launcher is required. Return intent is available from a received
Capsule or an exact chamber in an imported portable inquiry.

Review shows every included excerpt and expandable exact JSON. Freezing requires
explicit review, re-resolves the draft against canonical sources and rejects a
changed payload. Choose private keeping or local export. Export produces canonical
`.atlas-capsule.json` and readable `.md` files with independent download links.
Repeated exports reuse the same bytes and receipt; they never consume a legacy
launcher or claim an online launch. Connecting a device does not upload them.
Browser preparation and file receipt carry the original JSON text back to Python,
preserving numeric representations and checksums through review, freeze and import.

The version-1 `atlas-capsule` envelope identifies canonical content by SHA-256.
Its content includes origin, optional home Threadwalk, intent, attribution,
message, interpretation, contextual return reference and explicit graph excerpts.
Excerpts carry selected public thought fields, selected web evidence and exact
source/shared graph hashes. Full graphs, ancestry, private guide conversations,
private graph metadata, sensor/probe references and local evidence files are not
implicitly carried. Source hashes identify versions; recipients cannot reconstruct
an omitted full graph from excerpts. Sharing names are self-reported and hashes
do not prove authorship. Included prose still needs human privacy review.

Files are bounded to 256 KiB and validated before receipt. Inspecting a file is
read-only; explicit receipt stores an inert copy without importing graphs, invoking
an agent or accepting a contribution. A return must match a locally prepared
Capsule or the exact local source of its referenced portable inquiry. Repeated
receipt reuses the same artifact. Offline receipt alone does not create accepted links; connected return decisions
are described below. The older returned-path offer format retains its consent flow.

From a received Capsule, choose a private question and which excerpts to give
**your configured collaborator**. Review the exact context and current collaborator
before creating a separate canonical private Threadwalk through the ordinary
continuation worker. The Capsule's message and interpretation are included in this
review; context is limited to 64 KiB. Receipt alone never starts work. The library
links to these private workspaces and can prepare a return from their selected
thoughts, anchored to the original incoming Capsule. Working offline means no Atlas
service is required; the configured collaborator may still require its provider's
network connection.

Store records live under `capsules/prepared`, `capsules/received` and
`capsules/exports`; exported files live under `exports/capsules/<id>/`.
`capsule-source.json` in the new private session records its incoming context.
These are transport artifacts and provenance receipts, not another graph store.
Original local Capsule manifests, dossiers and launch receipts remain unchanged
and readable through the library and their original chambers.

Verification: synthetic A → B → A exchange through the ordinary worker, exact
selection and privacy projection, stale/tampered review rejection, malformed-file
rejection without writes, interrupted-export retry, exact-source return checking,
local HTTP review/origin gates and byte-preserved legacy launch artifacts pass.
Browser preparation, freeze/export and private workspace entry pass. The browser
file-picker action was denied by browser permission review; receipt is covered by
API tests, but manual file-picker and physical two-PC acceptance remain open.

## Connected delivery and source-owner decisions — September 10

Pair Personal Atlas, open a frozen Capsule and choose **Choose online destination**.
Directed delivery names a GitHub login that has joined this Atlas; review resolves
and displays the stable account ID separately from the Capsule's sharing name.
Open invitations/offerings require your matching published home Threadwalk and
are readable by signed-in Atlas visitors. A directed Capsule can have no published
launch location. Returns are directed to the original source owner.

The displayed frozen payload goes to the service for validation when **Review
destination with the online Atlas** is chosen. That review does not persist a
launch. **Send reviewed Capsule** commits one delivery per sender/Capsule hash,
with immutable contents and audience. A retry recovers its original ID; changing
audience requires preparing a new Capsule. Pairing and checking an inbox never
upload existing Capsules or reinterpret historical local launches.

**Online deliveries** in Personal Atlas and **Capsules** in the shared-world
browser expose Inbox, Sent, and Open invitations & offerings. Checks are deliberate,
paginated and account-scoped. The server retains deliveries while the recipient
is offline. Reading is inert. Explicit receipt saves the local Capsule before
acknowledging it, so an interrupted acknowledgement is retryable. Account-side
receipt from the web browser is separate from downloading/importing a local file.
The source sender sees directed receipt and decision status.

The service checks returned Capsule identity/origin against the original accessible
delivery. A return to an imported inquiry must match the exact online publication,
source/shared graph hashes and selected thought. Review shows the original source
alongside the return. Explicit source-owner **Accept contribution** or **Decline
contribution** records an immutable private decision; duplicate decisions reuse it
and conflicting decisions fail. Local acceptance additionally requires the matching
original Capsule or source graph in this Personal Atlas. Another paired computer
without that source can still review the return in the online browser.

Acceptance does not publish private returned excerpts, import graphs, invoke an
agent, or create a world/native doorway. Existing private continuation and
selected return preparation reuse the offline work loop. The separate full
[returned-path flow](RETURNED_PATHS.md) now provides reviewed shared/native doors
for published inquiries. A delivery sequence/time is a committed record,
not a claim that anybody witnessed an animation.

Senders can withdraw service access; downloaded copies and private local receipts
remain. Tombstones and private service records are retained for retry/history.
Either account can block further exchanges and hide that account's incoming/open
Capsules; unblocking restores visibility. Blocking does not recall prior copies or
delete decisions. The preview caps each sender at 200 total Capsule deliveries,
including withdrawals; this is not a measured production capacity guarantee.

Migration `0003` adds D1 delivery and receipt records. Raw canonical Capsule JSON
preserves Python numeric hashes in transit and is validated against the same
schema plus selected-evidence constraints. Local delivery receipts live under
`capsules/online/<service-account-hash>/`; credentials remain solely in the pairing
file. Saved receipts and received Capsules are readable offline. No cursor marks
unread deliveries as received merely because they appeared in a list.

Verification: 24 online runtime/road tests and 433 Python tests pass. Chrome's real
local Worker → two isolated Personal Atlases loop passed review/send, inert receipt,
contextual return preparation/send, exact-source receipt and acceptance. The browser
return was a synthetic human-authored message; no real collaborator was called.
Physical two-PC exchange, GitHub App deauthorization, listening/load and
installer/release acceptance remain open.

## Witnessed expeditions — September 10

Migration `0004` records each committed delivery and explicit accepted return once,
in the same transaction as its underlying action. Historical deliveries are not
backfilled as new launches. The same events appear under followed Threadwalks,
with the delivery's existing audience and block checks applied on every read.
Directed events and decisions are visible only to sender and recipient; open
invitations/offerings are visible to signed-in visitors. Anonymous visitors see no
Capsule event metadata. Acceptance remains private disclosure-wise.

Personal Atlas can choose an optional published destination owned by a directed
recipient. Returns recover the original source port. A published home supplies the
launch location; unpublished sources never invent one. Ports expose readable,
paginated expedition history, pending/open beacons and accepted-return markers.
Clicking a launcher or its history control opens review without moving the camera.

Current observers can witness charge, crown-first curved flight and fading trails
using the existing supplied Capsule/launcher models. Returns travel toward their
actual source; open invitations ascend without inventing a recipient. Initial
connection, reload, hidden tabs, failed requests and gaps over eight seconds reset
the live watermark, leaving durable history without replaying it as present motion.
Flights are bounded to eight and ten seconds each. Reduced motion suppresses
flights; muted/hidden audio stays silent, with distance/zoom attenuation and stereo
placement through the existing sound controls. Offscreen arrivals remain history.

Verification: **29 online tests and 433 Python tests pass**. Real local D1 tests
cover audience/block filtering, directed target ownership, atomic/idempotent launch
and acceptance events, following and migration preservation. Observer/THREE tests
cover reconnection, stale responses, camera preservation, curved flight orientation,
reduced motion and resource cleanup. Chrome showed synthetic launch and return
flights between two actual ports, launcher history, source review and acceptance.
Listening, full hosted two-account exchange and physical two-PC acceptance remain
open; no real user Capsule or collaborator was used.

## Existing local implementation

The remainder documents the currently shipped private local Capsule contract.
It remains authoritative for old artifacts. The separate excerpt format above
does not migrate or reinterpret their earned, one-shot lifecycle.

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
