# Atlas of Threads installers

Atlas is distributed as one self-contained local application. Provider agents,
authentication, subscriptions, and model selection remain outside Atlas.

## Linux

The intended public command is:

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

`AtlasOfThreadsSetup.exe` installs per-user without requiring Python, Git, or
administrator access. The completion action starts Atlas and opens the local
browser automatically. Uninstalling the application leaves the user's Personal
Atlas and provider-owned configuration intact.

## Private build

The `package` GitHub Actions workflow produces unsigned Linux and Windows
artifacts for private clean-machine acceptance. It uploads workflow artifacts
only; it does not create a release, publish a package, change repository
visibility, or update the website/domain.

Code signing, a hosted Linux install endpoint, and public release assets remain
publication actions and require separate approval.
