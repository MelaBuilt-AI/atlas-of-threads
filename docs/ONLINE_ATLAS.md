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
similarity. Geographic roads additionally connect each public Threadwalk to its
nearest earlier neighbor across publishers. They are shared-world travel routes;
accepted contribution relationships remain a separate layer. Selecting a neuron exposes its title, author and entry action.
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
- [x] Stars associated with verified accounts, a Starred collection, optional
  in-app following, and stable Threadwalk identity across published editions.
- [x] Offline Capsule preparation, exact excerpts, private keeping/file export,
  inert receipt, private continuation and contextual return preparation.
- [ ] Shared local/online Capsule intents (invitation, offering, return), reviewed
  contents/destination, discoverable requests and accepted return connections.
- [ ] Actual online Capsule launch/return events, overworld launcher history,
  witnessed flights and distance-aware sound without taking over the camera.
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
source. Native 3D arrival/source-return doors and browser-local visited cues now
reuse these exact accepted artifacts. Published shared doorways are described below.

See [returned paths](RETURNED_PATHS.md) for the local contract and verification.
The next increment adds `online/`: a Cloudflare Worker, D1 publication/owner
records, R2 snapshots, a shared isometric world with the existing terrain/relics,
public reading/download, and entry into the same Python-authored Threadwalk
renderer with exact world-camera return. A continuous parent-owned album crosses
the transition. The September 10 visual update follows the owner’s supplied
Atlas artwork with luminous blue/violet/gold currents, orbital islands and an
animated neural background; original relics and terrain appear on approach.
The static reference backdrop was removed following user feedback. Branches,
braided currents and traveling light knots now animate within the 3D field. Personal Atlas can prepare online publication files locally.

GitHub App OAuth and device-revocation endpoints are implemented. Real App
registration and owner sign-in are now verified on the hosted preview, including
the numeric GitHub identity and signed-in browser state. Authenticated
publication/withdrawal and mocked OAuth pass runtime tests; this is not full
network or lived-use acceptance.
The September 10 continuation implements node centering/spotlights and inert road
clicks while retaining menu path travel. Stable ongoing Threadwalks now have
reviewed, immutable editions; stars, Starred and optional in-app following persist
across editions/devices. Personal Atlas pairs through an expiring single-use code,
keeps its device credential private, and supports explicit check/disconnect and
an explained offline forget option. The account panel revokes devices or all
Atlas sessions/devices/pending codes. No pairing uploads an inquiry.

Connected excerpt Capsule delivery/reconnect, exact-source decisions and blocks
are implemented. Published full-return transport, explicitly accepted public links
and native doors/visited cues now work. GitHub-side deauthorization, report management
and activity remain. See
[online service](../online/README.md) for setup, tested boundaries and deployment.

## September 10 implementation checkpoint

The first three dependency steps are implemented and verified in the draft:
selection/spotlight behavior, stable editions with Personal Atlas pairing, and
stars with optional in-app edition updates. Account-wide Atlas revocation is
implemented; external GitHub App deauthorization remains pending. No desktop
package or combined release is claimed. See `online/README.md` for API/lifecycle
rules and the verification boundary.

Offline shared Capsule preparation and exchange are now implemented, including
reviewed private continuation and contextual return preparation. Legacy artifacts
retain their meaning. See [Capsules](KNOWLEDGE_CAPSULES.md) for the format, controls
and verification limits. Connected delivery and private acceptance now follow below.

Connected invitations, exact-source return delivery, explicit receipts/decisions,
withdrawal and blocks are implemented and tested. Witnessed launch/return events,
ports/history, beacons, distance-aware audio and audience-filtered following now
track committed deliveries. Shared/native doors and visited cues now connect
explicitly reviewed published full returns. Resume with deauthorization,
moderation/activity and physical two-PC/release gates. Private excerpt acceptance
is not consent to publish a shared connection; see [returned paths](RETURNED_PATHS.md).

## Accepted Capsule direction — September 10

The user adopted Capsules as invitations, offerings and returns that carry an
inquiry beyond its home Threadwalk. Invitations and returns are the first
end-to-end focus. Launchers are visible outbound ports and expedition histories;
actual online launches and returns should be witnessed on the overworld with
animation and distant sound. Personal Atlas adopts the same intent, content
review and destination model while retaining complete offline use. Existing
private artifacts keep their meaning. See [Capsule plan](KNOWLEDGE_CAPSULES.md).
The implemented expedition boundary and checks are recorded in the Capsule document.

Implemented map interactions: selecting a Threadwalk centers the camera and shines
a spotlight down on it. Overview-road clicks do not move the camera. Follow path
buttons in the Threadwalk menu retain their existing travel behavior.

## Accepted stars and following — September 10

Users can star a Threadwalk to express appreciation and find it again in their
Starred collection, with a separate optional Follow updates control. Stars attach
to the ongoing Threadwalk across published editions; exact published snapshots
remain preserved. Meaningful updates include new published editions, Capsule
invitations and accepted returns, with a restrained new-since-last-visit cue.

Stars live in Atlas under its existing verified GitHub owner identity. They do
not star a GitHub repository and do not require additional GitHub Starring
permissions. Start with the collection and optional in-app updates. Public counts
were discussed as a possible interest signal; public stargazer lists, ranking and
external notification behavior are not specified. Map placement remains stable.

## Next-session implementation order

The user requested saving this plan and beginning the work in the next session.
No runtime feature in this section is delivered merely by documenting it.

1. Apply node-click centering/spotlight, remove overview-road camera actions,
   and retain Follow path menu travel.
2. Establish stable ongoing Threadwalk identity across immutable editions and
   complete account/device pairing needed by publishing and local-online exchange.
3. Add stars, Starred collection and optional in-app following.
4. Build the shared Capsule intent/content/destination flow in Personal Atlas,
   retaining offline file exchange and compatibility with existing artifacts.
5. Connect invitations and reviewed returns to durable online delivery/reconnect,
   explicit acceptance, source references, withdrawal/blocking and revocation.
6. Add real shared Capsule launch/return events, miniature launcher ports,
   witnessed animation/distant audio and expedition history; wire followed updates.
7. Complete native arrival doors/unread behavior, accepted world links, opt-in
   activity, moderation and the physical two-PC/package/release acceptance gates.

The cluster direction below remains in the staged roadmap. Implement actual
membership/visibility boundaries before presenting private cluster enclosures or
routing public roads around them. Rich live co-walking remains later work.

## Roads and future clusters

The September 10 road increment turns converging trace bundles into prominent
flowing paths between Threadwalks. New arrivals connect to the nearest earlier
publication and grow their road outward from that neighbor. Visitors can follow
a road with the camera; periodic refreshes reveal new publications and remove
withdrawn ones without a page reload.

The user's future group/organization/private-cluster direction is recorded:
each cluster has a distinct color, connects internally, and is enclosed by a
glowing boundary. Public roads route around the outside and continue branching
beyond it or to either side. Membership/private access and cluster obstacle
routing remain future work; this increment implements public geographic roads.

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

Live co-walking, rich real-time presence, algorithmic feeds/ranking, automatic
semantic clustering, federation, communities and monetization are later work.
The accepted Capsule and stars/following scope above extends the earlier roadmap;
existing private Field Notes and Capsules are never implicitly published.

## Connected Capsule checkpoint

The next delivery increment supports reviewed directed/open Capsules, explicit
inert receipt, reconnect/retry, exact-source accept/decline, withdrawal and account
blocks in Personal Atlas and the shared browser. Service and local tests plus a
synthetic two-store browser loop pass; see [Capsules](KNOWLEDGE_CAPSULES.md).
Decisions are private: accepting excerpts does not expose them as public content
or import a full returned Threadwalk. The separate full-return flow now provides
public contribution links and shared/native doors between exact published snapshots,
with explicit contributor and source-owner consent. Private full-graph network offers
without publication are outside this increment. Draft PR #5 still retains the
remaining combined release checklist.
