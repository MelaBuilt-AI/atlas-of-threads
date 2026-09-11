# Private continuations and returned paths

Development increment in the [combined online milestone](ONLINE_ATLAS.md).
The local two-store loop and published shared/native doorways are implemented in
the draft. This is not a combined milestone release.

## Use it

While visiting an imported inquiry, choose **Continue privately**, write a
question, and review the exact answer/thought/source context and currently
selected collaborator. Confirming creates a separate local Threadwalk and queues
the ordinary local worker. The imported inquiry and existing session heads stay
unchanged. Use the local Workspace to choose a different collaborator first.

The Atlas menu folds up against the top edge in both local and imported views.
Use the glowing neuron/arrow to expand it. A private continuation's
**Return to Source: publisher name** link lives there and returns to its exact
imported source thought. The imported view then offers **Return to my Atlas**.
The menu remembers whether it is expanded for this browser tab.

In your own Atlas, **Returned paths** lists private continuations. Once a response
has completed, enter a sharing name, review every graph and exact JSON, and save
an `.atlas-return.json` offer. Sharing is a separate action; saving does not send
the file anywhere. Private guide conversations and source-context metadata are
not included. As with portable inquiries, review graph prose for private text.

The original source inhabitant chooses the offer file, inspects its contents,
and receives it into a pending inbox. **Review path** reopens the saved contents;
accepting imports the offered snapshot and exposes an entry link at the exact
source chamber. Declining leaves it inert. Accepted paths offer **Return to Source:
publisher name** in the Atlas menu. Repeated receipt/acceptance reuses the same offer and snapshot. A
decision is final for that exact offer in this initial increment.

## Contract

- Ordinary Store sessions/graphs/turns and continuation requests/completions own
  the private continuation. The initial human question graph carries the exact
  selected public answer, thought and source references in `metadata.external_inquiry`.
  Existing adapters treat that graph context as quoted data, not instructions.
- Context is limited to 64 KiB; the question uses the existing 400-character
  limit. Larger source context is rejected for review rather than silently cut.
- A local `sessions/<id>/external-source.json` receipt pins the seed graph,
  source and question. It is not added to the portable inquiry format.
- A version-1 `atlas-return-path` envelope contains a content hash, source
  reference, question and ordinary portable inquiry bundle. Its entire serialized
  size is bounded to 8 MiB. Returned graph bundles retain the portable validator.
- Sources identify origin, inquiry snapshot, session, graph and node, and both
  original graph-file and shared-projection hashes. Receipt checks the target's
  local origin, exact immutable source bytes and selected node before writing.
- Offers live under `return-paths/offers/`; decisions under `return-paths/decisions/`.
  Atomic files and the existing local continuation lock serialize mutations.
  Acceptance materializes a separate imported inquiry before publishing its
  decision. No receive/accept action queues an agent request.
- Portable sharing names and offers are publisher assertions, not signatures.
  Matching source hashes prove which source is named, not verified authorship
  or that the offered reasoning follows from it. Online doorway transport additionally
  checks the existing verified account ownership of both publications.

Local HTTP actions use `/api/return-paths/{preview,begin,export,inspect,receive,decide}`
and the existing same-origin JSON checks. Read APIs list private paths/offers,
retrieve saved offers for review and expose source links/accepted arrivals at an
exact chamber. These are local APIs; the existing server remains loopback-only.

## Verification and remaining work

Synthetic tests exercise the actual continuation worker, exact prompt context,
unchanged source graphs/heads/imports, sanitized export, malformed/misaddressed
offers with zero writes, duplicate receipt/acceptance, decline, and HTTP use.
Browser checks cover context review, local worker completion, saved-offer review,
explicit acceptance, entry and exact-source return. The test adapter is synthetic;
these checks do not claim a new real provider response or physical Windows
returned-path acceptance. The earlier portable two-PC acceptance is separate.

Revising decisions, private full-graph online offers without publication, physical
two-PC and final release acceptance remain open. The published doorway flow below
adds no graph schema or portable format version.


## Shared and native doorways — September 10

In Personal Atlas, **Returned paths → Review offer back → Review online doorway**
starts from the existing complete return offer. Pair the Atlas first. Choose the
original exact published source (including its account if multiple publishers
shared the same snapshot). Review and explicitly publish the returned inquiry,
then separately review and send the doorway proposal. Publishing exposes the full
returned inquiry to everyone immediately; it does not depend on acceptance of the
connection. This first online doorway flow uses public snapshots. Private full-graph
offers remain available through the existing offline return-file flow.

The contributor reviews the exact public source/target chamber projection. The
source owner sees the proposal in **Doorways → My proposals and decisions** in the
shared Atlas, or **Check online returned doorways** in Personal Atlas. Reading is
inert. Public acceptance requires a separate checkbox after reviewing the source,
complete returned inquiry and endpoint projection. Declining publishes no link.
Accepting an excerpt Capsule is a different, private decision and never creates
this public doorway automatically.

The service checks the original inquiry/origin/session, exact source/shared graph
hashes and selected node, contributor ownership of the returned snapshot, and the
full canonical `atlas-return-path` content hash. D1 migration `0005` stores bounded
routing/consent records, with at most 200 offers per contributor including withdrawn
ones. Full graphs remain ordinary immutable R2 publication artifacts. Download
reconstructs the exact canonical offer from the pinned snapshot and source; Python
validates it before any local receipt. No second graph store is introduced.

Only participants can read pending proposals. Public accepted projections contain
the two published endpoints and acceptance time, excluding the offer's separate question field and transport identifiers. Prose
already included in either public inquiry remains public. Either participant can withdraw the proposal
or link; either-direction blocks and withdrawal of either exact publication hide
it on subsequent service reads. Decisions are final for that offer and retries
reuse its identity. New published editions never silently move the pinned chamber
endpoints. Already viewed links, downloaded files and local imports cannot be recalled.

Native online receipt first saves the full offer pending. Local acceptance imports
an independent read-only snapshot through the existing portable importer and
creates the native door. **Accept and share doorway** materializes locally before
recording the public decision; if the network fails, the private acceptance remains
usable and the public action can be retried. Accepting privately from the ordinary
local inbox makes no online consent request. Another computer without the exact
original local source can review/accept online, but must acquire that source before
using local exact-source acceptance.

Accepted native arrivals use the existing 3D arrival relic at the exact source
chamber, including chambers that are not graph thresholds. The returned inquiry
provides the source-return relic. Entry preserves the exact target; return opens
the exact source directly, even when it matches the browser's remembered chamber.
Browser-local unvisited/visited state changes only after entering the accepted
target chamber, never on listing, receipt or acceptance. Native and shared visit
state are separate; clearing browser storage resets this presentation cue.

The shared world draws violet contribution arcs separately from geographic roads.
Its Doorways panel enters either exact published chamber. The hosted player uses
the same native relics and source-return behavior; leaving the player restores the
world camera. The parent keeps ownership of continuous audio, while direct player
links initialize their own sound interface. The map refreshes shared links with its
ordinary 30-second refresh. Doorway updates are not an additional external notification.

Verification: **436 Python tests, 33 online tests and 7 audio tests pass**. Real local
D1/R2 checks cover canonical full-return download, source/owner validation, deliberate
public consent, duplicate/concurrent sends, immutable decisions, blocks and withdrawal.
Native tests cover exact source/target, inert receipt, unchanged source graphs and
network-failure retry. Chrome passed contributor review/publication/send, source-owner
acceptance, native receipt/import, 3D entry/return, persistent visited cues, shared
player entry/return and the distinct contribution arc. These were synthetic stores
and a test collaborator, not physical two-PC or new real-provider acceptance.
