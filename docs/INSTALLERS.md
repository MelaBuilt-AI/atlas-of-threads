# Atlas of Threads installers

Atlas is distributed as one self-contained local application. Provider agents,
authentication, subscriptions, and model selection remain outside Atlas.

## Linux

Install with:

```bash
curl -fsSL https://atlasofthreads.com/install.sh | sh
```

The hosted script is the reviewed `packaging/linux/install.sh`. It downloads a
matching binary plus its SHA-256 file, installs the binary under the user's XDG
data directory, starts the local application, and prints the clickable
`http://127.0.0.1:7462/` URL. A systemd user service is preferred; when the user
bus is unavailable, the application owns its collaborator worker while it is
open.

## Windows

[Download `AtlasOfThreadsSetup.exe`](https://downloads.atlasofthreads.com/releases/latest/AtlasOfThreadsSetup.exe).
It installs per-user without requiring Python, Git, or administrator access.
The completion action starts Atlas and opens the local browser automatically.
Uninstalling the application leaves the user's Personal Atlas and
provider-owned configuration intact.

The installer, application executable, Start menu entry, and optional desktop
shortcut use the Thread Compass `13-app-icon` identity. Onboarding detects
supported provider CLIs installed natively on Windows and distinguishes missing,
provider sign-in required, ready, and failed setup checks. For Codex, Claude
Code, and Grok Build it can open the provider's official native PowerShell
installer or visible account sign-in command; the user completes every flow in
that provider-owned terminal/browser and then chooses **Check again**. Atlas
never receives, proxies, logs, or stores those credentials and does not bundle
the provider executables. The provider alone decides account eligibility,
subscription access, and any API billing; Atlas neither selects nor changes that
billing route. It also checks the default WSL distribution as a
fallback; set `TA_WSL_DISTRO` before starting Atlas to select a different
distribution.

The official Codex standalone installer exposes a stable Windows command through
directory junctions. Atlas reads that provider-owned junction metadata and runs
the current physical standalone release, preserving Codex's package context while
avoiding Windows environments that reject traversal of the public junction.
Provider path probes are best-effort and cannot prevent Atlas itself from opening.

A vendor desktop app by itself does not qualify as a collaborator in this
release. Atlas requires the provider's supported non-interactive CLI contract,
so install and sign in to Codex CLI, Claude Code, or Grok Build either natively
or inside the selected WSL distribution. Desktop-app and WSL authentication may
be separate. Atlas does not inspect a desktop app's private files or automate
its UI.

## Windows download trust

The current public installer is unsigned, which can cause Microsoft Defender
SmartScreen or the browser to report an unknown or suspicious download. A
self-signed certificate would not improve public trust.

The supported remedies require an external publisher identity:

- Publish an MSIX through Microsoft Store, where Microsoft signs the package;
  this is the most reliable route to avoiding SmartScreen download warnings.
- For the existing direct-download EXE, obtain Microsoft Artifact Signing or a
  public OV code-signing certificate, then Authenticode-sign and timestamp both
  `AtlasOfThreads.exe` and the final `AtlasOfThreadsSetup.exe` on every release.

Signing displays a verified publisher and lets reputation carry across releases,
but a new signing identity can still receive early SmartScreen warnings while
publisher reputation develops. Microsoft documents the current behavior in
[SmartScreen reputation for Windows app developers](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).

## Releases

The `package` GitHub Actions workflow always produces private Linux and Windows
acceptance artifacts. A manual run can additionally publish a version to the
public `atlas-of-threads-downloads` Cloudflare R2 bucket when its explicit
`publish` input is enabled. Ordinary pushes never publish.

Each release is stored under an immutable versioned path and copied to
`releases/latest`. SHA-256 files are published beside both platform packages.
The packages remain unsigned until a publisher identity and signing service or
certificate are provisioned; code signing must happen before checksums and
publication.
