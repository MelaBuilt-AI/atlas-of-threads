# Code signing policy

Atlas of Threads is maintained by [MelaBuilt AI](https://github.com/MelaBuilt-AI).

## Current status

Windows releases are currently unsigned. We are applying to the
[SignPath Foundation](https://signpath.org/) free open-source signing program.
An application is not approval, and no current installer should be described as
SignPath-signed or Microsoft-approved.

If accepted, the signing credit will be: Free code signing provided by
[SignPath.io](https://signpath.io/), certificate by
[SignPath Foundation](https://signpath.org/). Foundation-backed signatures identify
SignPath Foundation as the certificate publisher.

## Responsibility and approval

- Maintainer, committer and reviewer: Aaron Vozzolo, through MelaBuilt AI.
- Release-signing approver: Aaron Vozzolo. Automated tools and AI collaborators
  do not authorize a signing request or release.
- Proposed external changes require maintainer review before release.
- Any SignPath-backed release must be explicitly approved by the maintainer.
  Signing and repository access must use multi-factor authentication as required
  by the Foundation. Signing access has not yet been provisioned.

## Build and signing scope

The public repository contains the source and GitHub Actions packaging workflow.
Windows builds use PyInstaller for `AtlasOfThreads.exe` and
`AtlasOfThreadsMCP.exe`, then Inno Setup for `AtlasOfThreadsSetup.exe`.

The intended signed release signs the two application executables before
packaging, then signs the installer before generating checksums. Product names
and versions must match the release. Published checksums must describe the final
signed bytes. Upstream components retain their own attribution and licensing;
provider CLIs are installed separately by the user.

SignPath integration, certificate selection and signature checks remain pending
program acceptance and configuration. We will not mark an unsigned artifact as
signed, use a self-signed certificate as public trust, or promise that a signature
immediately removes every Windows reputation warning.

## Privacy and removal

See the [privacy information](PRIVACY.md) for local storage, update checks,
optional provider calls and the optional Connected Atlas. Windows includes an
uninstaller; uninstalling the program does not deliberately erase a user's
separately stored Personal Atlas inquiries.
