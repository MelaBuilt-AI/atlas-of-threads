# Online release readiness

Updated September 19, 2026. This is the v0.4.0 candidate on `feature/online-atlas`;
public stable remains v0.3.1. No merge, tag or release is authorized.

## Implemented and checked

- Signed GitHub App deauthorization invalidates the exact numeric owner's
  sessions/devices/pairings and turns activity off. Old pending sign-ins cannot
  restore access. A fresh OAuth flow reconnects; duplicate deliveries stay inert.
- Browser-only moderator allowlist, private paged report queue, audited
  dismissals and separately confirmed exact-snapshot withdrawal. Other accounts,
  devices and anonymous requests cannot review reports.
- Activity starts off, explicitly opts in, renews only in visible online browser
  tabs and expires after 90 seconds. Off and account revocation stop renewal.
  Green activity dots differ from gold expeditions and violet accepted paths.
- Mobile navigation now uses one horizontally scrollable row, avoiding overlap
  with the inquiry panel. Readable inquiry view checked at 390 × 844 in Chrome;
  this is viewport testing, not physical-phone performance acceptance.
- Full Python suite: 441 passes. Online/UI suite: 48 passes. Synthetic browser
  report → dismiss → decision history, activity on/off and mobile reading pass.
- `npm run capacity`: 500 synthetic public Threadwalks across 25 owners, 100-row
  pagination without omissions/duplicates, 20 concurrent readers. Local measured
  page wall time 5–17 ms; concurrent maximum 96 ms. An empty final page follows
  an exact multiple of 100. These are Miniflare measurements, not hosted CPU.

The previously accepted two-account Capsule round trip, retries/restart,
witnessed launch/return and shared doorway entry/exact return remain accepted.
Do not resend or republish those accepted artifacts simply to resume.

## Hosted capacity and publication processing

The initial tests used owner-confirmed Workers Free. An isolated deployment of the actual Worker
with separate D1/R2 passed 503-publication pagination (six pages, no missing or
duplicate IDs) and 20 simultaneous 100-row reads. All temporary resources were
removed after each test; the existing preview's publications were preserved.

Three larger fixtures prepared by the real Python export path contained 30, 200
and 600 thoughts (185 KB, 1.63 MB and 5.72 MB). Initial uploads and exact retries
completed, but upload CPU exceeded the documented 10 ms Workers Free budget.
The first optimization streams stored publication parts on download, eliminates
redundant envelope serialization and reuses encoded graphs for checksums. The
same hosted workload still passed with exact inquiry/player downloads:

| Thoughts | Baseline upload CPU median | Updated upload CPU median |
| --- | ---: | ---: |
| 30 | 21.214 ms | 19.742 ms |
| 200 | 111.750 ms | 53.884 ms |
| 600 | 350.939 ms | 151.652 ms |

Each median uses only three isolated requests, including first publication and
two retries; these are bounded measurements, not sustained-load guarantees.
For the largest fixture, download CPU fell from 35.6–41.6 ms to a two-request
window with median 2.426 ms/p99 3.826 ms. Existing envelope snapshots retain the
compatibility path; this streaming result applies to newly stored split snapshots.

**Paid-plan follow-up (September 15):** the owner upgraded to Workers Paid
($5/month minimum). Cloudflare reports Standard usage for both the account and
existing preview Worker, with no custom CPU limit. Billing subscription details
are outside the existing token's permissions; the purchase is owner-confirmed.
Paid HTTP requests have a documented default CPU allowance of 30 seconds.
The free-tier staged-upload redesign is no longer a launch requirement.

A fresh isolated deployment of the same e96c92d runtime passed all three large
publications, two retries each and six byte-exact downloads. Using 600-thought
snapshots from two synthetic owners, Capsule source review/send/detail and
shared-doorway review/send/full returned-inquiry retrieval/owner acceptance all
passed. The returned inquiry and offer checksum were preserved. This bounded
functional check does not establish sustained load or every possible input.
All temporary credentials/resources were removed; the original eight preview
publications, 16 download hashes and accepted public doorway remain unchanged.
The earlier 503-publication pagination/concurrency result remains applicable;
that workload was not repeated solely for the account upgrade.

See [Cloudflare limits](https://developers.cloudflare.com/workers/platform/limits/)
and the [storage compatibility notes](../online/README.md#publication-processing-and-storage--september-15).

## Live account check

Live activation, revocation, browser/device reconnection and inert duplicate
delivery were accepted September 13. Pending-code rejection retains automated
coverage only. The procedure below is preserved for future deliberate retesting;
do not repeat revocation merely to resume.

The existing App uses `/api/github/webhook`, JSON and SSL verification. Its
existing webhook secret is provisioned as `GITHUB_WEBHOOK_SECRET`. Activate
**Active** in the existing App settings after account verification; do not create
another App or broaden permissions. The preview operator MelaBuilt-AI is the
configured moderator by verified numeric ID; no ID is hardcoded in source.

With the user ready, use only the PCDG-AI test authorization:

1. Verify the browser identity and paired source-owner Personal Atlas on 7488.
   MelaBuilt-AI's Personal Atlas is 7487; browser login and device pairing differ.
2. From PCDG-AI's GitHub authorized-app settings revoke **Atlas of Threads Preview**.
3. Verify a successful `github_app_authorization` delivery in the App webhook
   history, then verify PCDG-AI's old Atlas browser session and device fail access.
   Its pending pairing code should fail; public snapshots/stars remain intact,
   MelaBuilt-AI stays connected, and local offline inquiry reading still works.
4. Sign in anew as PCDG-AI and issue a new pairing code. Reconnect 7488 and verify
   its received/accepted history. Redeliver the same webhook event only as an
   explicitly coordinated retry check; the new connection must remain valid.

Actual GitHub activation, delivery and live revocation are acceptance gates;
mocked OAuth and signed synthetic requests do not close them.

## Physical offline acceptance and current packages

Physical Linux/Windows exchange and restart passed September 13. On September
17 the owner disabled Windows Ethernet, reloaded the local page, returned to the
last chamber, navigated objects, read saved output and opened the Spark guide
UI. Reconnected reload also worked. Subsequent checks preserved the exact saved
response, Capsule library, session heads and accepted return, with the existing
owner connection verified online. This closes offline reading/navigation on the
installed dd852b0 candidate; no offline model response was tested.

[Package workflow 35236456383](https://github.com/MelaBuilt-AI/atlas-of-threads/actions/runs/35236456383)
built candidate 1906410. Linux packaged MCP/SSH/discovery/guides/format-repair and
startup checks passed. Windows standalone checks, installer build and installed
MCP/SSH/discovery/guides checks passed. The downloaded Linux package also passed
checksum verification, isolated CLI/HTTP startup, six source-asset comparisons,
public stable update-status lookup and clean exit. Thirteen focused updater tests
passed. The installed dd852b0 candidate has identical desktop source, assets and
packaging to 1906410; intervening runtime changes are confined to the online Worker.
No user installation was replaced. Publication is disabled for this workflow run.

## Audio acceptance follow-up

The September 17 physical Windows listening check found overlapping music between
Personal/connected tabs and silent effects in both surfaces and hosted Threadwalks.
Earlier UI-only and synthetic-player passes did not establish audible effects.
The audio repair makes music/effects follow the active tab, preserves explicit
music pause and position, fixes effects volume input being overwritten during
activation, retries suspended/interrupted audio on gestures and adds Test effects
with actual engine readiness.

**Owner acceptance, September 17:** on the updated physical Windows candidate
(a3d95d1), music stays within the active Personal/connected Atlas tab and no longer
overlaps. Music and effects work in both, and the connected Atlas score continues
from the overworld into a Threadwalk and back. The owner described this as flawless.
This closes the reported audio failures on these tested paths. The same revision
has 441 Python and 60 online/audio passes, green CI and Linux/Windows packages;
the updated Windows installation preserves all 20 saved JSON files and its pairing.

The Linux Personal Atlas Dev installation now also runs the verified a3d95d1
package. Its prior installation and store were backed up; all 42 saved JSON files,
sessions, Capsule library, online receipts and return paths were preserved. Eight
served desktop assets match source and its existing online pairing verifies.
This is installation/runtime verification, not a new physical Linux listening test.

## Desktop release scope

On September 17 the owner accepted a desktop-first release scope. The target is
Linux and Windows Personal Atlas plus the connected Atlas in desktop browsers.
The owner also verified runtime and audio on iPhone Safari, but text panels
obscure the scene and keyboard controls are not usable there. Mobile support is
experimental; the connected Atlas displays a small desktop recommendation on
narrow screens and touch devices.

A later mobile milestone in the same codebase will provide touch equivalents for
essential actions, collapsible reading panels, portrait/landscape layouts and
physical-device usability/performance acceptance. These mobile changes do not
block this desktop release. The iPhone observation is not mobile usability signoff.

## Remaining human and deployment checks

**Desktop smoothness accepted, September 19:** the owner reports smooth Atlas
navigation and transitions into Threadwalks and back with no stuttering on a 2022
laptop with integrated CPU graphics and a 2022 Windows desktop with a GeForce
GTX 1650. This closes the representative desktop observation on those machines;
no measured frame-rate or broader GPU compatibility claim follows.

**Live flight audio accepted, September 19:** after accepting the direct preview,
the owner heard and accepted the updated charging buildup and liftoff blast on a
fresh Windows overworld flight. The flying sound retains its accepted level.
The final source adds dedicated charge/blast accents, versioned hosted audio
loading and a no-send launch preview. Earlier missing-cue observations remain
historical; stale cached code was suspected but not proven as the Windows cause.
Build/61 online-audio tests, two focused Python serving/audio checks and fresh
browser preview/renderer signal checks pass. Do not replay accepted deliveries.

## Remaining release work

Present the final tested revision for the owner's combined desktop release
decision. Candidate metadata is aligned to 0.4.0, and fresh Linux/Windows packages
from `44e14e7` pass their executable and installer checks. Full source checks,
anonymous clone/link review and isolated Linux version/assets/updater checks pass;
see [desktop release review](DESKTOP_RELEASE_REVIEW.md) for exact receipts.
Existing user test installations still identify as v0.3.1. Merge, stable release
publication and public download updates await the owner's explicit decision.

Rich co-walking, private clusters and unrelated features remain later work.

See the [desktop release review](DESKTOP_RELEASE_REVIEW.md) for evidence, scope
and remaining limits. This preview deployment is not a stable release.
