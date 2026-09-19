# Public repository readiness

This is the release checklist for the public Atlas of Threads source repository.
It records the decisions made before publication and the checks that should stay
part of future releases.

## Publication decisions

- Version 0.4.0 combines portable inquiries, private returned paths,
  reviewed Capsule exchange and the connected Atlas in one desktop release.
  Physical Linux/Windows exchange, Windows offline use, account lifecycle,
  desktop smoothness and live flight audio are accepted. Fresh versioned packages
  pass; the owner authorized unsigned publication on September 19, 2026. See [release review](DESKTOP_RELEASE_REVIEW.md).
- Original local Capsules keep their one-shot private dossier contract. Shared
  Capsule receipt, private continuation and public doorway acceptance are
  separate reviewed actions; see [Capsules](KNOWLEDGE_CAPSULES.md).
- The historical origin-conversation fixture was replaced with a synthetic
  reference example. Private source material is excluded from rewritten public
  history.
- Contributor instructions contain only repository-facing guidance; private
  collaboration memory remains outside the repository.
- Local machine paths, session identifiers, and the local-only author identity
  were removed from public history.
- The generated GLB assets and their provenance are documented in
  `THIRD_PARTY_NOTICES.md`.
- The previously exposed Cloudflare credential was rotated before publication.

## Verified release boundary

Version **0.3.1 — Bring Your Own Agent** gathers the Agent Bridge, local and
remote onboarding, Agent Spark, terrain/Reflect navigation, cinematic audio,
and bounded formatting repair. The owner accepted the completed build and
authorized its public release on September 8, 2026.

The 0.3.0 release passed its CI/package gates, but a final Arch startup check
found that the frozen updater could not locate the host CA bundle. Version
0.3.1 fixes that lookup for verified HTTPS release requests and respects explicit
trust settings; its release repeats the full CI and packaging gates.

Before the version bump, the exact final application source passed all 367
local tests, Python 3.11/3.12 CI, both platform package builds, and installed
Windows smoke checks. Release preparation repeats these gates at the versioned
source. GitHub Actions and the tagged release manifest are the authoritative
record of the final commit and published artifacts.

The package smoke suite covers MCP, SSH dispatch, discovery, all 33 effect and
13 music assets with HTTP range serving, guide entry points and formatting
repair. Live-client acceptance and platform-specific limits remain explicitly
recorded in [MCP compatibility](MCP_COMPATIBILITY.md); synthetic smokes do not
claim a fresh live response from every provider. Remote helper hosting requires
POSIX (including WSL); automatic LAN discovery and a native Windows remote
Hermes/OpenClaw host are not implied. The Windows Atlas client can use the
supported remote route.

Audio logic checks cover autoplay retry, separate controls, random entry and
local playlist resolution. Local file-picker interaction was not automated;
file import logic was tested independently. Browser autoplay remains subject
to the browser's user-interaction policy.

- The project is MIT-licensed and owned under `MelaBuilt-AI`.
- Runtime data, environments, caches, and package metadata are ignored. No live
  Personal Atlas data is tracked.
- Credential-pattern scans cover the current tree and rewritten Git history.
- The complete test suite, JavaScript syntax checks, package builds, installer
  smoke tests, and clean-environment installs are release gates.
- The HTTP application refuses non-loopback binds. Knowledge Capsule manifests,
  receipts, and exports remain inside the documented local boundary.
- Stable release metadata records the version and exact source commit, and
  published downloads carry SHA-256 checksums.
- The current/future capability boundary is documented in
  `docs/ATLAS_OF_THREADS.md`.

## Check for every release

1. Run the complete Python suite and JavaScript syntax checks.
2. Scan tracked files and all reachable history for credentials, private paths,
   real conversations, Personal Atlas data, and unexpected large files.
3. Confirm package, source, installer, tag, and release-manifest versions agree.
4. Verify GitHub Actions succeeds for Linux and Windows packaging.
5. From an anonymous client, clone the repository and verify README links,
   release assets, checksums, and the Linux and Windows download paths.
6. Reconfirm provenance and distribution rights for any new generated or
   third-party asset.

## Known limitations

- Windows installers are currently unsigned, so Windows may display a
  reputation warning.
- Python 3.11 and 3.12 are the supported source-install versions.
- `ta harness service` requires a systemd user session; other platforms use
  the foreground `ta harness watch` path.
- Mobile remains experimental; the accepted release scope is desktop Linux and
  Windows, including the optional connected Atlas. Rich co-walking and private
  clusters remain later work.

Passing this checklist does not replace an explicit owner decision for future
visibility or release changes.


## Connected Atlas v0.4.0

PR #5 delivers the verified v0.4.0 desktop release. The existing
hosted service is accepted for the desktop milestone: published immutable
inquiries, private exact-source work and returns, explicit shared doorways,
GitHub identity/pairing/revocation, Capsule flights, stars/following, report
review and opt-in expiring activity. Existing public snapshots and accepted
connections are preserved. Private excerpt acceptance never publishes a doorway.

The September 19 source adds accepted charge/blast audio, versioned hosted sound
loading and a no-send launch preview. Source/package/installer versions
are aligned to 0.4.0; final CI, package and publication receipts must identify the
exact versioned source. The owner authorized publishing v0.4.0 and updating the
stable download aliases on September 19, 2026. SignPath review is pending; this
release is unsigned.

Mobile support is experimental: iPhone Safari runtime/audio works, but panels
and keyboard controls need a dedicated touch-interface milestone. See
[release readiness](ONLINE_READINESS.md) for exact accepted evidence and limits.
