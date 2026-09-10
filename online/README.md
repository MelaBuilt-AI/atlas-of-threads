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
World camera position is a browser preference; publication placement is durable
and depends on the server sequence, never browser storage or layout randomness.
Filaments in the landscape are scenery, not inferred relationships or proof of
contributions. Accepted contribution links remain a later world increment.

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
each owner to 20 total publications, including withdrawn snapshots.

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
A complete in-app device pairing/disconnection flow is not yet implemented.

GitHub deauthorization webhooks and prompt remote session revocation remain an
online release gate; current sessions have their documented seven-day expiry.

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
These do not constitute real GitHub login, browser navigation/audio acceptance,
physical two-PC exchange, performance/load testing or release acceptance.

Still required in PR #5: live GitHub connection, device pairing, durable offered
returns and reconnect, accepted doorway links in the shared world, block/report
management, opt-in activity, complete browser/two-PC checks, and final installers.
The report endpoint stores authenticated reports; no active moderation service or
response-time promise is implied. See `../docs/ONLINE_ATLAS.md` for the full gate.
