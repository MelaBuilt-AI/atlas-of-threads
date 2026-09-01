# Public repository readiness

This is the release checklist for the public Atlas of Threads source repository.
It records the decisions made before publication and the checks that should stay
part of future releases.

## Publication decisions

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
- Accounts, networking, and the shared Atlas are future work. The current
  release is a local-first Personal Atlas.

Passing this checklist does not replace an explicit owner decision for future
visibility or release changes.
