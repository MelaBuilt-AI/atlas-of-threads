# Online Atlas milestone

Status: draft implementation, including the accepted portable inquiry work.
There will be one larger online release; portable inquiries are not scheduled
for a separate release. Public v0.3.1 remains the current release.

## The release experience

An inhabitant connects deliberately, reviews and publishes one inquiry, and
sees it in a navigable shared Atlas. Another visitor selects its neuron, reads
its attribution, enters its Threadwalk, and returns to the same overworld
position. They can bring the inquiry into their Personal Atlas, continue an
exact chamber privately with their own collaborator, and offer that new path
back. The source inhabitant reviews and accepts the arrival before it becomes
a doorway. The world gains a path grounded in that explicit exchange.

The overworld uses an isometric camera, arrow movement, panning and zoom, with
published Threadwalks represented as neurons along sprawling paths. Placement
is stable; relationships come from explicit accepted contributions, not inferred
similarity. Selecting a neuron exposes its title, author and entry action.
Browser visitors can read without installing Atlas or configuring an agent;
mobile visitors have a readable view alongside the immersive experience.

## Work in this PR

- [x] Reviewed portable exports, isolated imports and private recipient guides.
  Two-PC transfer and manual browser import are accepted.
- [x] Private exact-source continuation and reviewable offer-back files.
  Local synthetic worker and browser flow pass; real-agent/two-PC acceptance
  for returned paths remains in the final gate below.
- [ ] Inert incoming offers, explicit acceptance/decline, exact-source doors,
  duplicate-delivery safety, and entry/return without changing source heads.
- [ ] Separate hosted service for reviewed snapshots and durable deliveries;
  reconnect/offline delivery and a disconnect/block action.
- [ ] GitHub App owner authentication, stable numeric GitHub owner IDs, distinct
  registered instance identities, local keys and revocation.
- [ ] Explicit publication review, bounded visibility, withdrawal/tombstones,
  ownership checks, request limits and basic moderation/reporting.
- [ ] Shared isometric overworld, stable placements, meaningful paths, inquiry
  selection, Threadwalk entry and exact overworld return.
- [ ] Public read-only web player and readable mobile view; local import and
  private guide/continuation handoff.
- [ ] Opt-in coarse activity lights with expiry and a clear off state. Activity
  and newly accepted paths have different visual meanings.
- [ ] Physical two-PC end-to-end acceptance, local offline behavior, final
  Linux/Windows packages and installer checks, then owner release acceptance.

Build these as working increments in this draft PR. An unchecked item is not
implemented merely because a design or mockup exists. Do not merge or release
the portable part early to satisfy an intermediate checkpoint.

## Current working increment

The local A → B → A kernel now supports context review before a collaborator
call, a separate private continuation session, reviewed return-path JSON export,
inert receive, explicit accept/decline and duplicate reuse. Accepted paths have
an entry link at the exact source chamber and a return-to-source link inside
the received Threadwalk. Private continuations also link back to their imported
source. These links establish working entry/return; native 3D arrival doors and
unread traversal behavior remain unfinished.

See [returned paths](RETURNED_PATHS.md) for the local contract and verification.
The next increment adds `online/`: a Cloudflare Worker, D1 publication/owner
records, R2 snapshots, a shared isometric world with the existing terrain/relics,
public reading/download, and entry into the same Python-authored Threadwalk
renderer with exact world-camera return. A continuous parent-owned album crosses
the transition. Personal Atlas can prepare online publication files locally.

GitHub App OAuth and device-revocation endpoints are implemented, but real App
setup and live sign-in remain pending. Authenticated publication/withdrawal and
mocked OAuth pass runtime tests; this is not full network or lived-use acceptance.
Durable offered returns, accepted world links, native arrival doors, device pairing,
block/report management and activity are still to build. See
[online service](../online/README.md) for setup, tested boundaries and deployment.

## Implementation boundaries

Keep the existing Store, schemas, continuation worker and renderer authoritative.
Portable bundles are the transport boundary. New paths are locally owned
canonical graphs with explicit external-source receipts; received paths remain
separate imported inquiries. Neither an offer nor its acceptance rewrites the
source graph, attribution, history or session head.

Prove the two-store return loop before adding transport. Use a small HTTPS
service with durable storage, not peer-to-peer machinery. Keep the local server
loopback-only. Reuse the existing renderer/media and hosting where practical;
inquiry data must not require a bespoke website/media build for each publication.
The service implementation and deployment contract will be committed here;
existing public site links remain stable.

Local use stays account-free. Official-network contribution uses the accepted
GitHub App bootstrap, verified by the service, with owner and instance identities
kept distinct. Self-reported portable names are never presented as verified
accounts. Account access and local model credentials remain separate.

Publishing, offering a path, accepting it, and invoking an agent are distinct
human actions. Remote content is inert untrusted data. Show the selected context
before a local call. No browsing/import action automatically invokes an agent,
publishes local content, or exposes a local store to the internet.

## End-to-end release gate

On two physical PCs with isolated stores, publish one reviewed synthetic inquiry,
find it in the shared overworld, enter/read/return, import it locally, ask a local
collaborator a private question from an exact chamber, offer the resulting path,
receive it after reconnect, review/accept it, enter its doorway and return.
Verify attribution and hashes, unchanged source graphs/heads, duplicate delivery,
decline/block/withdrawal behavior and local use during service unavailability.
User lived-use acceptance must include the world navigation and a useful exchange.

Live co-walking, rich real-time presence, feeds/ranking, automatic semantic
clustering, federation, communities and monetization are later work. Field Notes
and Capsule portability remain separately designed extensions; the first online
release does not implicitly publish them.
