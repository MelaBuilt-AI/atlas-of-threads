from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from thought_archaeology.harness import HarnessError, HarnessSpec
from thought_archaeology.store import Store

HARNESS_SERVICE_NAME = "thought-archaeology-harness.service"


def resolve_harness_service_path() -> Path:
    override = os.environ.get("TA_HARNESS_SERVICE")
    if override:
        return Path(override).expanduser().resolve()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    root = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return (root / "systemd" / "user" / HARNESS_SERVICE_NAME).resolve()


def _ta_command() -> tuple[str, ...]:
    installed = shutil.which("ta")
    if installed:
        return (str(Path(installed).absolute()),)
    sibling = Path(sys.executable).parent / "ta"
    if sibling.is_file() and os.access(sibling, os.X_OK):
        return (str(sibling.absolute()),)
    return (str(Path(sys.executable).absolute()), "-m", "thought_archaeology.cli")


def _unit_quote(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise HarnessError("service arguments cannot contain newlines")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_harness_service(
    store: Store,
    spec: HarnessSpec,
    *,
    interval: float = 2,
    timeout: float = 900,
    ta_command: tuple[str, ...] | None = None,
) -> str:
    if interval <= 0:
        raise HarnessError("watch interval must be greater than zero")
    if timeout <= 0:
        raise HarnessError("adapter timeout must be greater than zero")
    argv = [
        *(ta_command or _ta_command()),
        "--store",
        str(store.root),
        "harness",
        "watch",
        "--harness",
        spec.name,
        "--interval",
        f"{interval:g}",
        "--timeout",
        f"{timeout:g}",
    ]
    exec_start = " ".join(_unit_quote(item) for item in argv)
    return f"""[Unit]
Description=Thought Archaeology continuation harness ({spec.name})

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


def _systemctl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    executable = os.environ.get("TA_SYSTEMCTL") or shutil.which("systemctl")
    if not executable:
        raise HarnessError("systemctl is required for the background harness service")
    proc = subprocess.run(
        [executable, "--user", *args],
        capture_output=True,
        text=True,
        shell=False,
        check=False,
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or "no output"
        raise HarnessError(f"systemctl --user {' '.join(args)} failed: {detail}")
    return proc


def install_harness_service(
    store: Store,
    spec: HarnessSpec,
    *,
    interval: float = 2,
    timeout: float = 900,
    path: Path | None = None,
) -> Path:
    if not store.exists():
        raise HarnessError(f"store is not initialized: {store.root}")
    unit_path = path or resolve_harness_service_path()
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit = render_harness_service(store, spec, interval=interval, timeout=timeout)
    fd, temp_name = tempfile.mkstemp(prefix=".ta-harness-", dir=unit_path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(unit)
        os.chmod(temp, 0o600)
        os.replace(temp, unit_path)
        os.chmod(unit_path, 0o600)
    finally:
        if temp.exists():
            temp.unlink()
    _systemctl("daemon-reload")
    _systemctl("enable", "--now", HARNESS_SERVICE_NAME)
    return unit_path


def control_harness_service(action: str, *, path: Path | None = None) -> None:
    if action not in {"start", "stop", "restart"}:
        raise HarnessError(f"unsupported service action: {action}")
    unit_path = path or resolve_harness_service_path()
    if not unit_path.is_file():
        raise HarnessError("background harness service is not installed")
    _systemctl(action, HARNESS_SERVICE_NAME)


def harness_service_status(path: Path | None = None) -> dict[str, Any]:
    unit_path = path or resolve_harness_service_path()
    installed = unit_path.is_file()
    if not installed:
        return {
            "unit": HARNESS_SERVICE_NAME,
            "path": str(unit_path),
            "installed": False,
            "enabled": "not-installed",
            "active": "not-installed",
        }
    enabled = _systemctl("is-enabled", HARNESS_SERVICE_NAME, check=False)
    active = _systemctl("is-active", HARNESS_SERVICE_NAME, check=False)
    return {
        "unit": HARNESS_SERVICE_NAME,
        "path": str(unit_path),
        "installed": True,
        "enabled": enabled.stdout.strip() or "unknown",
        "active": active.stdout.strip() or "unknown",
    }


def remove_harness_service(path: Path | None = None) -> None:
    unit_path = path or resolve_harness_service_path()
    if not unit_path.is_file():
        raise HarnessError("background harness service is not installed")
    _systemctl("disable", "--now", HARNESS_SERVICE_NAME)
    unit_path.unlink()
    _systemctl("daemon-reload")
