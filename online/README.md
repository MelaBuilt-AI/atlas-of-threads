# Online Atlas preview

A separate Cloudflare Worker serves reviewed, immutable inquiry publications and
a navigable shared world. This is part of draft PR #5, not a new desktop release.
The existing landing page, field guide and curated walk are separate deployments.

## Run and verify

```sh
npm ci
npm run build
npm test
node scripts/preview.mjs
```

The last command serves `http://127.0.0.1:7490/` with six **synthetic** inquiries
and an ephemeral local D1/R2 environment. It never opens a Personal Atlas store,
loads a collaborator registry, installs a service, or calls an agent. Its fixture
publishing credential is generated for that run and immediately revoked. There
is no test-login or administrator-bypass endpoint in the deployed Worker.

The build copies the existing `viz/dist` renderer, models, textures, album and
sound effects. These are Workers Static Assets; inquiry uploads live in R2.
Asset notices are retained. The world streams nearby relic models and initially
loads one terrain texture; the original Threadwalk player retains the full media
library. The shared score stays in the parent window through entry and return.
World camera position is a browser preference; Threadwalk placement is durable
and depends on its first publication’s server sequence, never browser storage or layout randomness.
Fine filaments are atmospheric scenery. Larger bundled roads join each visible
publication to the geographically nearest earlier publication, ordered by the
server's stable sequence (earliest sequence breaks distance ties). These roads
represent a shared world across publishers; accepted contribution links remain
a separate later increment.

## Visual direction — September 10

The owner's five Atlas references define the world: deep indigo space, interwoven
cyan/electric-blue/violet threads, occasional warm gold, orbital islands and
luminous knots. Following user feedback, the static background image is removed.
The background is now an animated neural lattice with 484 junctions and curved
connections. Foreground currents use branching dendrites, braided strands,
traveling luminous knots and bright pulse trails. A shared displacement field
makes joined branches undulate together. Scenery ribbons are batched into five
meshes; a bounded particle field carries the stars and traveling lights.

Nearby locales reveal the original textured islands, orbits and relic models;
distant locales become beacons. Reduced-motion preferences freeze ambient
geometry motion, pulses and orbital animation. Atmospheric connections are
scenery, not inferred relationships, live presence or accepted contribution links.
Actual publication placements and selection remain server-backed. Visual feel
and device performance still require user/browser acceptance.

## Converging roads and growing arrivals

Each road combines a broad cyan glow with 27 braided cyan/gold filaments that
spread near the two locales and converge into a prominent flowing route. A new
road forms from the earlier locale toward the arrival over 2.4 seconds. Existing
road meshes remain intact when later publications arrive. Select a Threadwalk node to center the camera smoothly and shine an overhead
spotlight onto its island. Overview road clicks do not move the camera. Use
**Follow path** in the selected locale’s panel to travel along the road’s curve
to the neighboring Threadwalk. Dragging or arrow movement cancels travel.

While the visible world is idle, the loaded publication pages refresh every 30
seconds. New arrivals gain roads without reloading the world. Withdrawn locales
are removed; surviving locales reconnect to their nearest remaining predecessor.
Placement and sequence come from the service; geographic road layout is a browser
projection with no graph/author/membership inference. Larger worlds retain the
explicit Load more boundary. Hidden tabs, Threadwalk visits and camera transitions
skip polling. Reduced-motion displays completed roads and makes travel immediate.

Future group/organization/private-cluster direction: distinct shared color for
each cluster, internal roads only, and a luminous enclosing boundary. Outside
public roads should route around that boundary and continue branching beyond or
to either side. This is saved future scope; cluster membership, private access,
barriers and obstacle routing are not implemented in this increment.

## Prepare and publish

In the updated Personal Atlas source app, open Portable inquiries, review an
export, and choose **Save online publication file**. This prepares a file locally;
it sends nothing. Alternatively:

```sh
PYTHONPATH=../src python -m thought_archaeology.online inquiry.json publication.json
```

The online page accepts this file only after sign-in and another explicit review.
The original portable inquiry remains embedded byte-for-byte as canonical JSON.
Python prepares the existing chamber and compass views from a temporary imported
copy. No live user store is accessed during preparation. The Worker compiles its
schema validator from the same repository schemas, verifies snapshot/graph hashes,
closed references and bounded projections, and treats every display field as
untrusted publisher text. Prepared display prose is part of the reviewed artifact;
the service does not independently rerun Python interpretation or verify claims.
Sharing names are publisher-supplied. The separate account identity is verified
through GitHub's user endpoint using the GitHub App code exchange.

Public downloads return an ordinary portable inquiry for import into Personal
Atlas. Online browsing never invokes a collaborator or exposes a local server.
Publication requests require a session or a registered device bearer token, an
explicit review flag, and at most 8 MiB including the display projection. Duplicate
owner/snapshot pairs reuse one publication. Withdrawal removes its R2 object and
keeps a tombstone; it cannot recall copies already downloaded. The preview limits
each owner to 20 total publications, including all editions and withdrawn snapshots.

## Ongoing Threadwalks, editions and saved interest

An ongoing Threadwalk groups one verified owner’s publications by the portable
origin and session identity. Its stable ID is its first publication ID. Migration
`0002` joins existing editions without changing any snapshot IDs, R2 bytes or
source graphs. Each new edition explicitly names the latest predecessor after
review; concurrent competing editions accept one successor and reject stale
reviews. Duplicate delivery of an already published snapshot still reuses it.

The world shows the latest edition at the original location, with the original
map sequence and geographic roads. Updating an edition refreshes its selection
without moving the visitor’s camera or replaying an arrival. The **Published
editions** panel reads or downloads earlier exact snapshots. Withdrawing the
latest edition hides the locale; it does not resurrect an older edition. Older
unwithdrawn editions remain available by exact link, and a revised publication
can restore the ongoing locale. Stars survive withdrawal and restoration.

**Star** saves appreciation in **Inquiries → Starred**. **Follow updates** is a
separate, optional choice. Both are stored per account and ongoing Threadwalk,
so they survive browser/device changes and published editions. A restrained star
appears by the map title; followed unseen changes add a `new` cue. **Updates**
shows new deliberate publications since following began. **Mark seen** records
the displayed update sequence, leaving later events unread. No public ranking,
stargazer list, GitHub repository star, email or push notification is created.
Capsule invitation and accepted-return updates will be added with those features.

## GitHub owner setup

Register a GitHub App with no repository or account permissions and no webhooks.
Use the deployed preview origin plus `/auth/callback` as its callback. Public user
identity is enough; this app does not need repository contents or write access.
Set `GITHUB_CLIENT_ID` in ignored `wrangler.local.json` and provision
`GITHUB_CLIENT_SECRET` as a Worker secret. Never put either secret in source,
command arguments, build output or logs. Sign-in fails closed while unconfigured.

OAuth uses PKCE and a one-use state tied to an HttpOnly browser cookie. The Worker
fetches the numeric GitHub user ID; login names are display values. GitHub access
and refresh tokens are not retained. Atlas sessions expire after seven days and
logout deletes the current session. The device API creates independent random
bearer credentials, stores only their SHA-256 hashes and supports revocation.
Personal Atlas now has **Connect to the Atlas** in its toolbar and Workspace.
Open the online account panel and create a code for a named computer, then paste
it into Personal Atlas. Codes expire after ten minutes, work once, and replace
that account’s preceding pending code. Creation requires a current browser
session. Exchange atomically issues a device credential and consumes the code;
only hashes remain in D1. Up to ten active devices are allowed.

Personal Atlas stores the device credential in `online-connection.json` with
owner-only permissions where supported. Local status reads do not contact the
network; **Check connection** verifies access explicitly. The credential never
enters browser responses, portable bundles, graph projections or agent calls.
The client uses verified HTTPS, the existing packaged Linux CA fallback, and
refuses redirects. Pairing itself sends no inquiry or Capsule.

**Disconnect this Personal Atlas** revokes its device before removing the local
credential. If offline, it retains the credential so disconnection can be retried;
**Forget local connection** is a separately explained local-only option. The
online account panel can revoke individual devices or **Disconnect all sessions
and devices**, including pending codes. A device may revoke only itself and may
not create other devices. Account revocation preserves publications and stars.

GitHub-side App deauthorization webhooks remain a release gate; revoking the
GitHub App itself does not yet promptly invalidate Atlas sessions. Atlas’s own
account-wide and per-device revocation is implemented. Browser sessions otherwise
expire after seven days. Webhooks remain disabled for the preview App.

## Deploy to your Cloudflare account

This service lives in the Atlas application PR and deploys to the user's own
Cloudflare account, as requested; it does not replace the existing Sites mirror
or request a new Sites project.

```sh
python scripts/deploy.py --account-id YOUR_ACCOUNT --token-file /secure/token-file
python scripts/seed_preview.py --token-file /secure/token-file
```

The first command creates/reuses only `atlas-online-preview` D1 and R2 resources,
applies numbered migrations and deploys the built Worker plus Static Assets to
its workers.dev preview URL. It records resource IDs in ignored
`wrangler.local.json`. The second command publishes only the six committed
synthetic fixtures under an explicitly synthetic owner, then revokes its
one-time device credential. Do not repurpose it for user data.

The deployment helper neither activates a subscription nor changes existing DNS,
domain routes or paid plans. D1/R2 activation must already be available. Wrangler
debug logs go to a temporary symlink to the null device, and captured output is
redacted before display. Preserve deployed migrations; add a new numbered file
for schema changes. Preview limits are not a production capacity guarantee:
measure Worker CPU for larger publications against the account's free allowance.

## Current acceptance boundary

Tested: local canonical projection/privacy, Worker runtime with real local D1/R2,
publication/read/download/deduplication, rejection before writes, ownership,
withdrawal/tombstones, instance revocation, and mocked GitHub state/PKCE exchange.
Live GitHub App registration and owner sign-in also passed on September 9, 2026:
the public preview displayed the signed-in owner and D1 retained the verified
numeric GitHub owner identity. The app requests no repository/account permissions,
uses an exact callback URL and has webhooks disabled. These checks do not establish
browser world-navigation/audio acceptance, physical two-PC exchange,
performance/load testing or release acceptance.

September 10 continuation: 18 online runtime/road tests and 409 Python tests pass.
Additional cases cover migration, stable editions, competing publications,
account-scoped stars/follows, bounded seen receipts, one-use/expired pairing,
concurrent revocation, private local credential handling and offline forgetting.
Chrome checks on isolated synthetic accounts cover selection, edition reading,
stars, optional following, a real new-edition update and marking it seen. Actual
Worker → local HTTP pairing, saved readback, browser check and disconnect passed.
The existing Windows-discovery tests now isolate their synthetic home directories.

Still required in PR #5: GitHub-side deauthorization, report management,
opt-in activity, complete browser/two-PC checks, and final installers.
The report endpoint stores authenticated reports; no active moderation service or
response-time promise is implied. See `../docs/ONLINE_ATLAS.md` for the full gate.

## Connected Capsule increment

Migration `0003` stores bounded, frozen Capsule deliveries and separate per-account
receipt/decision records in D1. Personal Atlas explicitly reviews payload/audience,
then commits one delivery per sender/Capsule hash. Directed recipients are resolved
from an existing account's GitHub login; public offerings/invitations require the
sender's matching published home Threadwalk. Canonical Capsule JSON travels as a
string, preserving Python numbers and checksums. The same schema is compiled by
the build, and the Worker checks exact selected evidence and return sources.

`GET /api/capsules?view=inbox|sent|public&after=SEQUENCE` is authenticated and returns
up to 50 summaries plus a next cursor. It never acknowledges a delivery. Exact
`GET /api/capsules/ID` reads the payload/source review. `POST /api/capsules/review`
validates without storage; `/send` requires the returned review and explicit
consent. `/ID/receive`, `/ID/decide`, and `/ID/withdraw` remain separate reviewed
actions. `/api/blocks` reads/sets account blocks. No authentication bypass exists.
The browser's **Capsules** panel provides reading, receipt, download, source review,
accept/decline, sent history, withdrawal and blocks; preparation/sending uses the
connected Personal Atlas. Credentials never enter its browser responses.

Offline recipients find durable deliveries on their next explicit check. Lost
send responses reuse the single launch; received content is stored before the
local acknowledgement, and acknowledgements/decisions are retryable. Accepted
returns record a private relationship to their exact Capsule or published inquiry
source; they do not publicly expose the return or create world/native doors.
Shared doors use the separate full-return/publication consent flow below.
Withdrawal stops subsequent service access but keeps private records/tombstones;
prior downloaded copies cannot be recalled. Blocks apply in both directions to
new exchanges and incoming/open visibility. Sender quota: 200 total deliveries,
including withdrawn records. D1 rows retain the bounded payload and review; no
second graph store or new R2 bucket is introduced.

24 online tests and 433 Python tests pass. Synthetic browser A → B → A through a
real local Worker and two isolated Python HTTP servers passed receipt and explicit
acceptance with unchanged graphs/heads and no agent call. This is not physical
Windows/two-PC, production load, or combined release acceptance. See
[Capsules](../docs/KNOWLEDGE_CAPSULES.md) for offline compatibility and remaining work.

## Witnessed expeditions

Migration `0004` adds atomic launch/acceptance events, preserves existing edition
update sequences and does not replay or backfill historical deliveries.
`GET /api/expeditions?ports=THREADWALK_IDS&after=CURSOR` returns current port summaries
and authorized events; omitting `after` establishes a watermark only. Requests
accept up to 100 ports and return up to 100 events. Anonymous reads return no
Capsule metadata. `GET /api/expeditions/history?threadwalk=ID&before=SEQUENCE` pages
50 authorized records. Block/audience checks also apply to Capsule following.

Personal Atlas can review a directed recipient's published target port; returns
recover their original source. The map renders existing launcher/Capsule relics,
beacons, history and bounded live flights while preserving camera control. The
observer polls every 2.5 seconds, resets across hidden/offline/slow gaps and never
replays history on arrival. Audio respects existing controls and distance/zoom;
reduced motion suppresses flights. Accepting a return creates no public doorway.

29 online tests and 433 Python tests pass. Synthetic Chrome/real-local-Worker
checks cover directed and return flight, launcher history and explicit acceptance.
Full hosted two-account exchange, listening/load and the existing release gates
remain open. See [Capsules](../docs/KNOWLEDGE_CAPSULES.md) for the complete boundary.


## Shared returned doorways

Migration `0005` adds participant-private doorway proposals and explicit source-owner
public decisions between two exact published inquiry snapshots. The contributor must
publish the complete returned inquiry first and separately consent to the connection.
`/api/doorways/review` checks the canonical return hash, exact source chamber and both
publication owners without writes; `/send` requires that frozen review. Full return
JSON is reconstructed from the pinned R2 publication on `/api/doorways/ID`, preserving
canonical numeric hashes. Graphs are not copied to D1.

`GET /api/doorways?after=SEQUENCE` pages 50 participant records;
`GET /api/doorways/sources?inquiry=HASH` finds exact public source choices.
`POST /api/doorways/ID/decide` requires the exact review and explicit public consent
for acceptance. Either participant may `POST /api/doorways/ID/withdraw`.
`GET /api/doorways/public?publication=ID&after=SEQUENCE` optionally filters an exact
publication and pages 100 public accepted projections, hiding either publication's
withdrawal and either-direction blocks. Pending proposals never enter that feed.
No listing marks a path received or visited. Quota: 200 offers per contributor.

Personal Atlas integrates reviewed publication, proposal/send, full receipt and local
import/acceptance through its paired device. The shared browser provides public and
participant collections, review/accept/decline, exact download and withdrawal. Shared
and native players render accepted chamber doors and source returns with separate
browser-local visit cues. Violet map arcs remain distinct from geographic roads.
See [returned paths](../docs/RETURNED_PATHS.md) for the public-snapshot prerequisite,
network-retry behavior, offline guarantees and acceptance limits.

436 Python, 33 online and 7 audio tests pass, with synthetic browser checks for the
contributor/source-owner flow and native/shared 3D entry-return. Full hosted two-account,
physical two-PC, listening/capacity and combined release acceptance remain open.
