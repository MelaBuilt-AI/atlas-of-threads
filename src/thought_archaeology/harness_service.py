from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from thought_archaeology.harness import HarnessError, HarnessRegistry, HarnessSpec
from thought_archaeology.store import Store

HARNESS_SERVICE_NAME = "thought-archaeology-harness.service"
_PORTABLE_LOCK = threading.Lock()
_PORTABLE_PROCESS: subprocess.Popen[bytes] | None = None
_PORTABLE_STORE: Path | None = None
_PORTABLE_HARNESS: str | None = None


def resolve_harness_service_path() -> Path:
    override = os.environ.get("TA_HARNESS_SERVICE")
    if override:
        return Path(override).expanduser().resolve()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    root = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return (root / "systemd" / "user" / HARNESS_SERVICE_NAME).resolve()


def _ta_command() -> tuple[str, ...]:
    if getattr(sys, "frozen", False):
        return (str(Path(sys.executable).absolute()),)
    installed = shutil.which("ta")
    if installed:
        return (str(Path(installed).absolute()),)
    sibling = Path(sys.executable).parent / "ta"
    if sibling.is_file() and os.access(sibling, os.X_OK):
        return (str(sibling.absolute()),)
    return (str(Path(sys.executable).absolute()), "-m", "thought_archaeology.cli")


def _worker_backend() -> str:
    override = os.environ.get("TA_WORKER_BACKEND")
    if override:
        if override not in {"systemd", "application"}:
            raise HarnessError("TA_WORKER_BACKEND must be systemd or application")
        return override
    return "systemd" if sys.platform.startswith("linux") else "application"


def _portable_status() -> dict[str, Any]:
    with _PORTABLE_LOCK:
        process = _PORTABLE_PROCESS
        active = process is not None and process.poll() is None
        return {
            "backend": "application",
            "installed": active,
            "enabled": "while-atlas-is-open" if active else "not-running",
            "active": "active" if active else "inactive",
            "store": str(_PORTABLE_STORE) if _PORTABLE_STORE else None,
            "harness": _PORTABLE_HARNESS,
        }


def _stop_portable_worker() -> None:
    global _PORTABLE_PROCESS, _PORTABLE_STORE, _PORTABLE_HARNESS
    with _PORTABLE_LOCK:
        process = _PORTABLE_PROCESS
        _PORTABLE_PROCESS = None
        _PORTABLE_STORE = None
        _PORTABLE_HARNESS = None
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _start_portable_worker(
    store: Store,
    spec: HarnessSpec,
    *,
    interval: float,
    timeout: float,
) -> None:
    global _PORTABLE_PROCESS, _PORTABLE_STORE, _PORTABLE_HARNESS
    with _PORTABLE_LOCK:
        current = _PORTABLE_PROCESS
        if (
            current is not None
            and current.poll() is None
            and _PORTABLE_STORE == store.root
            and _PORTABLE_HARNESS == spec.name
        ):
            return
    _stop_portable_worker()
    argv = [
        *_ta_command(),
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
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except OSError as exc:
        raise HarnessError(f"cannot start the Atlas collaborator worker: {exc}") from exc
    with _PORTABLE_LOCK:
        _PORTABLE_PROCESS = process
        _PORTABLE_STORE = store.root
        _PORTABLE_HARNESS = spec.name


def application_worker_status(path: Path | None = None) -> dict[str, Any]:
    """Status for the worker backend used by the packaged local application."""
    if _worker_backend() == "application":
        return _portable_status()
    status = harness_service_status(path)
    return {"backend": "systemd", **status}


def ensure_application_worker(
    store: Store,
    spec: HarnessSpec,
    *,
    interval: float = 2,
    timeout: float = 900,
    path: Path | None = None,
) -> dict[str, Any]:
    """Start or switch the one worker owned by the local Atlas application."""
    if _worker_backend() == "application":
        _start_portable_worker(store, spec, interval=interval, timeout=timeout)
        return _portable_status()
    unit_path = path or resolve_harness_service_path()
    installed = unit_path.is_file()
    install_harness_service(
        store,
        spec,
        interval=interval,
        timeout=timeout,
        path=unit_path,
    )
    if installed:
        control_harness_service("restart", path=unit_path)
    return application_worker_status(unit_path)


def resume_application_worker(store: Store) -> None:
    """Resume the app-owned worker after relaunch on non-systemd platforms."""
    if _worker_backend() != "application" or not store.exists():
        return
    registry = HarnessRegistry()
    if registry.default_name() is None:
        return
    ensure_application_worker(store, registry.get())


def stop_application_worker() -> None:
    if _worker_backend() == "application":
        _stop_portable_worker()


def _unit_quote(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise HarnessError("service arguments cannot contain newlines")
    return (
        '"'
        + value.replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"')
        + '"'
    )


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
    path_environment = _unit_quote(f"PATH={os.environ.get('PATH', os.defpath)}")
    return f"""[Unit]
Description=Thought Archaeology continuation harness ({spec.name})

[Service]
Type=simple
Environment={path_environment}
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


def harness_service_options(path: Path | None = None) -> dict[str, float]:
    """Read the watcher timing from the installed unit before switching adapters."""
    unit_path = path or resolve_harness_service_path()
    if not unit_path.is_file():
        return {"interval": 2.0, "timeout": 900.0}
    exec_line = next(
        (
            line.removeprefix("ExecStart=")
            for line in unit_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("ExecStart=")
        ),
        "",
    )
    argv = shlex.split(exec_line)

    def value(flag: str, default: float) -> float:
        if flag not in argv or argv.index(flag) + 1 >= len(argv):
            return default
        try:
            return float(argv[argv.index(flag) + 1])
        except ValueError as exc:
            raise HarnessError(f"installed service has invalid {flag} value") from exc

    return {
        "interval": value("--interval", 2.0),
        "timeout": value("--timeout", 900.0),
    }


def remove_harness_service(path: Path | None = None) -> None:
    unit_path = path or resolve_harness_service_path()
    if not unit_path.is_file():
        raise HarnessError("background harness service is not installed")
    _systemctl("disable", "--now", HARNESS_SERVICE_NAME)
    unit_path.unlink()
    _systemctl("daemon-reload")
