from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class WSLCommand:
    launcher: str
    executable: str
    distro: str | None = None


ProviderCommand = str | WSLCommand


class ProviderCommandError(Exception):
    """Provider discovery or Windows/WSL path translation failure."""


def _safe_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _safe_which(name: str) -> str | None:
    try:
        return shutil.which(name)
    except OSError:
        return None


def _windows_junction_target(path: Path) -> Path | None:
    """Read a junction target without traversing the reparse point."""
    try:
        target = path.readlink()
    except (OSError, ValueError):
        return None
    raw = str(target)
    for prefix, replacement in (
        ("\\\\?\\UNC\\", "\\\\"),
        ("\\??\\UNC\\", "\\\\"),
        ("\\\\?\\", ""),
        ("\\??\\", ""),
    ):
        if raw.startswith(prefix):
            raw = replacement + raw[len(prefix) :]
            break
    target = Path(raw)
    if not target.is_absolute():
        return None
    return target


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return -1


def _physical_codex_command() -> str | None:
    """Bypass the official Windows launch junction when it is guarded."""
    root = (
        Path(os.environ["CODEX_HOME"])
        if os.environ.get("CODEX_HOME")
        else Path.home() / ".codex"
    ) / "packages" / "standalone"
    releases = []
    current = _windows_junction_target(root / "current")
    if current is not None:
        releases.append(current)
    try:
        cached = list((root / "releases").iterdir())
    except OSError:
        cached = []
    releases.extend(
        release
        for release in sorted(
            cached, key=lambda path: (_safe_mtime(path), path.name), reverse=True
        )
        if release not in releases
    )
    for release in releases:
        for candidate in (release / "bin" / "codex.exe", release / "codex.exe"):
            if _safe_is_file(candidate):
                return str(candidate.absolute())
    return None


def _known_windows_paths(name: str) -> tuple[Path, ...]:
    user = Path.home()
    app_data = os.environ.get("APPDATA")
    local_app_data = os.environ.get("LOCALAPPDATA")
    candidates = [
        user / ".local" / "bin" / f"{name}.exe",
        user / ".local" / "bin" / name,
    ]
    if app_data:
        candidates.extend(
            [Path(app_data) / "npm" / f"{name}.cmd", Path(app_data) / "npm" / name]
        )
    if name == "codex" and local_app_data:
        root = Path(local_app_data) / "Programs" / "OpenAI" / "Codex" / "bin"
        candidates.extend([root / "codex.exe", root / "codex.cmd", root / "codex"])
    if name == "grok":
        root = Path(os.environ.get("GROK_HOME") or user / ".grok") / "bin"
        candidates.extend([root / "grok.exe", root / "grok.cmd", root / "grok"])
    return tuple(candidates)


def _native_command(name: str, override: str | None) -> str | None:
    if override:
        candidate = _safe_which(override) or override
        path = Path(candidate).expanduser()
        return str(path.absolute()) if _safe_is_file(path) else None
    if sys.platform == "win32" and name == "codex":
        physical = _physical_codex_command()
        if physical:
            return physical
    found = _safe_which(name)
    if found:
        return str(Path(found).absolute())
    if name == "grok":
        root = Path(os.environ.get("GROK_HOME") or Path.home() / ".grok") / "bin"
        for candidate in (root / "grok", root / "grok.exe", root / "grok.cmd"):
            if _safe_is_file(candidate):
                return str(candidate.absolute())
    if sys.platform == "win32":
        for candidate in _known_windows_paths(name):
            if _safe_is_file(candidate):
                return str(candidate.absolute())
    return None


def _wsl_launcher() -> str | None:
    found = _safe_which("wsl.exe") or _safe_which("wsl")
    if found:
        return str(Path(found).absolute())
    system_root = os.environ.get("SystemRoot")
    if system_root:
        candidate = Path(system_root) / "System32" / "wsl.exe"
        if _safe_is_file(candidate):
            return str(candidate)
    return None


def _wsl_base(command: WSLCommand) -> list[str]:
    argv = [command.launcher]
    if command.distro:
        argv.extend(["--distribution", command.distro])
    return argv


def discover_provider_commands(
    requests: Iterable[tuple[str, str | None]],
    *,
    wsl_names: set[str] | None = None,
) -> dict[str, ProviderCommand | None]:
    """Find native CLIs first, then fixed-name CLIs in the selected/default WSL2 distro."""
    requested = list(requests)
    result: dict[str, ProviderCommand | None] = {}
    for name, override in requested:
        try:
            result[name] = _native_command(name, override)
        except OSError:
            result[name] = None
    unresolved = [
        name
        for name, override in requested
        if result[name] is None
        and not override
        and (wsl_names is None or name in wsl_names)
    ]
    if sys.platform != "win32" or not unresolved:
        return result
    launcher = _wsl_launcher()
    if launcher is None:
        return result
    distro = os.environ.get("TA_WSL_DISTRO") or None
    probe = WSLCommand(launcher=launcher, executable="sh", distro=distro)
    script = (
        'for command do path=$(command -v -- "$command" 2>/dev/null || true); '
        'printf "%s\\t%s\\n" "$command" "$path"; done'
    )
    argv = _wsl_base(probe) + ["--exec", "sh", "-lc", script, "sh", *unresolved]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            shell=False,
            timeout=10,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return result
    if proc.returncode != 0:
        return result
    for line in proc.stdout.splitlines():
        name, separator, executable = line.partition("\t")
        if separator and name in result and executable.strip():
            result[name] = WSLCommand(
                launcher=launcher,
                executable=executable.strip(),
                distro=distro,
            )
    return result


def discover_provider_command(
    name: str, override: str | None = None
) -> ProviderCommand | None:
    return discover_provider_commands([(name, override)])[name]


def command_argv(
    command: ProviderCommand,
    *args: str,
    cwd: str | Path | None = None,
) -> list[str]:
    if isinstance(command, str):
        return [command, *args]
    argv = _wsl_base(command)
    if cwd is not None:
        argv.extend(["--cd", command_path(command, cwd)])
    return argv + ["--exec", command.executable, *args]


def command_path(command: ProviderCommand, path: str | Path) -> str:
    if isinstance(command, str):
        return str(path)
    argv = _wsl_base(command) + [
        "--exec",
        "wslpath",
        "-a",
        str(Path(path).absolute()),
    ]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            shell=False,
            timeout=10,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProviderCommandError(
            f"cannot translate a Windows path for WSL: {exc}"
        ) from exc
    translated = (proc.stdout or "").strip()
    if proc.returncode != 0 or not translated:
        detail = (proc.stderr or proc.stdout or "").strip() or "no output"
        raise ProviderCommandError(f"WSL path translation failed: {detail}")
    return translated


def command_location(command: ProviderCommand | None) -> str | None:
    if command is None:
        return None
    if isinstance(command, WSLCommand):
        return f"WSL ({command.distro})" if command.distro else "WSL"
    return "Windows" if sys.platform == "win32" else "native"


def read_wsl_config(
    command: ProviderCommand,
    environment_name: str,
    default_directory: str,
    filename: str,
) -> str | None:
    if not isinstance(command, WSLCommand):
        return None
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    for value in (environment_name, default_directory, filename):
        if not value or any(character not in allowed for character in value):
            raise ProviderCommandError("invalid WSL configuration path component")
    script = (
        f'root="${{{environment_name}:-$HOME/{default_directory}}}"; '
        f'test -f "$root/{filename}" && cat "$root/{filename}"'
    )
    argv = _wsl_base(command) + ["--exec", "sh", "-lc", script]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            shell=False,
            timeout=10,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 and proc.stdout else None
