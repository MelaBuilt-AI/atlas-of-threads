from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from thought_archaeology import __version__


DOWNLOAD_ROOT = "https://downloads.atlasofthreads.com/releases"
MANIFEST_URL = f"{DOWNLOAD_ROOT}/latest/release.json"
_VERSION = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


class UpdateError(Exception):
    """A release could not be checked, verified, or activated."""


@dataclass(frozen=True)
class PreparedUpdate:
    version: str
    platform: str
    artifact: Path


def _version_tuple(version: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(version)
    if match is None:
        raise UpdateError("release version must use vMAJOR.MINOR.PATCH")
    return tuple(int(part) for part in match.groups())


def _platform_name() -> str | None:
    if sys.platform == "win32":
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return None


def update_status(*, opener=None) -> dict:
    """Read the public manifest written only by a published GitHub Release."""
    platform = _platform_name()
    status = {
        "current_version": f"v{__version__}",
        "latest_version": None,
        "available": False,
        "supported": bool(getattr(sys, "frozen", False) and platform),
        "platform": platform,
        "published_at": None,
    }
    if not status["supported"]:
        return status
    open_url = opener or urlopen
    manifest_url = os.environ.get("TA_UPDATE_MANIFEST_URL", MANIFEST_URL)
    try:
        request = Request(
            manifest_url,
            headers={"User-Agent": f"AtlasOfThreads/{__version__}"},
        )
        with open_url(request, timeout=5) as response:
            raw = response.read(64_001)
        if len(raw) > 64_000:
            raise UpdateError("release manifest is too large")
        manifest = json.loads(raw.decode("utf-8"))
        if not isinstance(manifest, dict):
            raise UpdateError("release manifest must be an object")
        latest = str(manifest.get("version") or "")
        latest_tuple = _version_tuple(latest)
        current_tuple = _version_tuple(status["current_version"])
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, UpdateError):
        return status
    status.update(
        latest_version=latest,
        available=latest_tuple > current_tuple,
        published_at=manifest.get("published_at"),
    )
    return status


def _download(url: str, destination: Path, *, opener=None) -> None:
    open_url = opener or urlopen
    request = Request(url, headers={"User-Agent": f"AtlasOfThreads/{__version__}"})
    try:
        with open_url(request, timeout=30) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
    except OSError as exc:
        raise UpdateError("could not download the release") from exc


def prepare_update(version: str, *, opener=None) -> PreparedUpdate:
    """Download one immutable release asset and verify its published SHA-256."""
    _version_tuple(version)
    platform = _platform_name()
    if not getattr(sys, "frozen", False) or platform is None:
        raise UpdateError("updates are available from an installed Atlas application")
    artifact_name = (
        "AtlasOfThreadsSetup.exe"
        if platform == "windows"
        else "atlas-of-threads-linux-x86_64"
    )
    release_root = f"{DOWNLOAD_ROOT}/{version}"
    update_dir = Path(tempfile.mkdtemp(prefix="atlas-of-threads-update-"))
    artifact = update_dir / artifact_name
    checksum = update_dir / f"{artifact_name}.sha256"
    try:
        _download(f"{release_root}/{artifact_name}", artifact, opener=opener)
        _download(f"{release_root}/{artifact_name}.sha256", checksum, opener=opener)
        checksum_parts = checksum.read_text(encoding="ascii").split()
        if not checksum_parts:
            raise UpdateError("release checksum is empty")
        expected = checksum_parts[0].lower()
        if not _SHA256.fullmatch(expected):
            raise UpdateError("release checksum is invalid")
        with artifact.open("rb") as package:
            actual = hashlib.file_digest(package, "sha256").hexdigest()
        if actual != expected:
            raise UpdateError("release checksum did not match")
    except Exception:
        shutil.rmtree(update_dir, ignore_errors=True)
        raise
    return PreparedUpdate(version=version, platform=platform, artifact=artifact)


def activate_update(update: PreparedUpdate) -> str:
    """Activate a verified update; the caller then shuts down the old server."""
    if update.platform == "windows":
        try:
            subprocess.Popen([str(update.artifact)], shell=False)
        except OSError as exc:
            raise UpdateError("could not open the verified Windows installer") from exc
        return "installer_opened"

    executable = Path(sys.executable).resolve()
    replacement = executable.with_name(f".{executable.name}.update")
    try:
        shutil.copyfile(update.artifact, replacement)
        replacement.chmod(0o755)
        os.replace(replacement, executable)
    except OSError as exc:
        replacement.unlink(missing_ok=True)
        raise UpdateError("could not replace the installed Linux application") from exc
    shutil.rmtree(update.artifact.parent, ignore_errors=True)
    return "installed"


def restart_linux_application() -> None:
    """Restart the installed service, or relaunch a non-systemd package instance."""
    if _platform_name() != "linux":
        return
    if os.environ.get("TA_WORKER_BACKEND") == "systemd" and shutil.which("systemctl"):
        subprocess.Popen(
            ["systemctl", "--user", "restart", "atlas-of-threads.service"],
            shell=False,
        )
        return
    subprocess.Popen(
        [sys.executable, *sys.argv[1:]],
        shell=False,
        env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"},
    )
