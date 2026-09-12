# Online release readiness

Updated September 12, 2026. This is the unreleased `feature/online-atlas` work;
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
- Full Python suite: 441 passes. Online/UI suite: 44 passes. Synthetic browser
  report → dismiss → decision history, activity on/off and mobile reading pass.
- `npm run capacity`: 500 synthetic public Threadwalks across 25 owners, 100-row
  pagination without omissions/duplicates, 20 concurrent readers. Local measured
  page wall time 5–17 ms; concurrent maximum 96 ms. An empty final page follows
  an exact multiple of 100. These are Miniflare measurements, not hosted CPU.

The previously accepted two-account Capsule round trip, retries/restart,
witnessed launch/return and shared doorway entry/exact return remain accepted.
Do not resend or republish those accepted artifacts simply to resume.

## Live account check

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

## Remaining human and deployment checks

- Physical Linux/Windows full exchange, including reconnect and offline reading:
  use isolated synthetic stores, exact reviewed source chambers, real private
  agent continuation, explicit return receipt/acceptance and source return.
  Preserve the two existing test stores and actual private Atlas stores.
- Listen to navigation and departure/return effects with music, mute and volume
  controls. Verify the effects feel useful; automated audio tests cannot do this.
- Check touch/mobile on a physical device and representative GPU/frame behavior.
- Measure hosted Worker CPU for representative larger publications and concurrent
  service use against the actual account allowance. The local read benchmark
  does not establish this. Keep paid-plan changes separate.
- Build final Linux/Windows packages from the reviewed branch, verify checksums,
  installed CLI/startup, MCP/SSH/discovery/guides and updater behavior. Existing
  user dev binaries are not automatically claimed to match later source.
- Present the final tested revision and remaining limits for owner release review.

Rich co-walking, private clusters and unrelated features remain later work.
