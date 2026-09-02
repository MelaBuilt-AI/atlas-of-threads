from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from thought_archaeology import cli
from thought_archaeology import harness as harness_module
from thought_archaeology import store as store_module
from thought_archaeology.harness import HarnessRegistry
from thought_archaeology.harness_service import (
    application_worker_status,
    ensure_application_worker,
    stop_application_worker,
)
from thought_archaeology.launcher import main as launcher_main
from thought_archaeology.adapters import provider_command as provider_command_module
from thought_archaeology.adapters.provider_command import (
    WSLCommand,
    command_argv,
    command_path,
    discover_provider_command,
    discover_provider_commands,
)
from thought_archaeology.serve import _packaged_harness_command
from thought_archaeology.store import Store


def test_launcher_defaults_to_the_local_application(monkeypatch):
    seen = []
    monkeypatch.setattr(cli, "main", lambda argv: seen.append(argv) or 0)
    assert launcher_main([]) == 0
    assert seen == [["launch"]]


def test_frozen_launcher_uses_the_private_application_store(monkeypatch, tmp_path: Path):
    seen = []
    monkeypatch.setattr(cli, "main", lambda argv: seen.append(argv) or 0)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        "thought_archaeology.launcher.fallback_store_path",
        lambda: tmp_path / "personal-atlas",
    )
    monkeypatch.delenv("TA_STORE", raising=False)
    assert launcher_main([]) == 0
    assert seen == [["launch"]]
    assert os.environ["TA_STORE"] == str(tmp_path / "personal-atlas")


def test_windows_application_paths_use_roaming_and_local_app_data(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setattr(store_module.sys, "platform", "win32")
    monkeypatch.setattr(harness_module.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("TA_HARNESS_CONFIG", raising=False)
    assert store_module.fallback_store_path() == (
        tmp_path / "local" / "MelaBuilt AI" / "Atlas of Threads" / "Personal Atlas"
    )
    assert harness_module.resolve_harness_config_path() == (
        tmp_path / "roaming" / "MelaBuilt AI" / "Atlas of Threads" / "harnesses.json"
    )


def test_launcher_dispatches_the_packaged_adapter(monkeypatch):
    seen = []

    def adapter(argv=None):
        seen.append(argv)
        return 0

    monkeypatch.setattr("thought_archaeology.launcher._adapter", lambda name: adapter)
    assert launcher_main(["adapter", "prime-agent", "describe"]) == 0
    assert seen == [["describe"]]


def test_launcher_bounds_unexpected_adapter_errors(monkeypatch, capsys):
    def adapter(_args):
        raise AttributeError("private provider detail")

    monkeypatch.setattr("thought_archaeology.launcher._adapter", lambda _name: adapter)
    assert launcher_main(["adapter", "grok", "continue"]) == 1
    error = capsys.readouterr().err
    assert error == "grok adapter failed unexpectedly (AttributeError)\n"
    assert "private provider detail" not in error


def test_frozen_application_uses_itself_for_packaged_bridges(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/opt/AtlasOfThreads")
    assert _packaged_harness_command("ta-harness-prime-agent") == (
        str(Path("/opt/AtlasOfThreads").absolute()),
        ("adapter", "prime-agent"),
    )


def test_windows_discovers_the_official_native_codex_install(monkeypatch, tmp_path: Path):
    local_app_data = tmp_path / "local"
    codex = local_app_data / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe"
    codex.parent.mkdir(parents=True)
    codex.write_bytes(b"test")
    monkeypatch.setattr(provider_command_module.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "missing-codex-home"))
    monkeypatch.setattr(provider_command_module.shutil, "which", lambda _name: None)

    assert discover_provider_command("codex") == str(codex.absolute())


def test_windows_codex_uses_the_physical_standalone_release(monkeypatch, tmp_path: Path):
    codex_home = tmp_path / ".codex"
    standalone = codex_home / "packages" / "standalone"
    release = standalone / "releases" / "v1-x86_64-pc-windows-msvc"
    codex = release / "bin" / "codex.exe"
    codex.parent.mkdir(parents=True)
    codex.write_bytes(b"test")
    standalone.joinpath("current").symlink_to(release, target_is_directory=True)
    monkeypatch.setattr(provider_command_module.sys, "platform", "win32")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr(provider_command_module.shutil, "which", lambda _name: None)

    assert discover_provider_command("codex") == str(codex.absolute())


def test_windows_codex_falls_back_to_the_newest_physical_release(
    monkeypatch, tmp_path: Path
):
    codex_home = tmp_path / ".codex"
    release = (
        codex_home
        / "packages"
        / "standalone"
        / "releases"
        / "v2-x86_64-pc-windows-msvc"
    )
    codex = release / "bin" / "codex.exe"
    codex.parent.mkdir(parents=True)
    codex.write_bytes(b"test")
    monkeypatch.setattr(provider_command_module.sys, "platform", "win32")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr(provider_command_module.shutil, "which", lambda _name: None)

    assert discover_provider_command("codex") == str(codex.absolute())


def test_windows_untrusted_provider_path_does_not_break_discovery(
    monkeypatch, tmp_path: Path
):
    local_app_data = tmp_path / "local"
    guarded = local_app_data / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe"
    original_is_file = Path.is_file

    def guarded_is_file(path: Path) -> bool:
        if path == guarded:
            raise OSError(448, "untrusted mount point", str(path))
        return original_is_file(path)

    monkeypatch.setattr(provider_command_module.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "missing-codex-home"))
    monkeypatch.setattr(provider_command_module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(Path, "is_file", guarded_is_file)

    assert discover_provider_commands([("codex", None)], wsl_names=set()) == {
        "codex": None
    }


def test_one_provider_discovery_error_does_not_hide_another(monkeypatch):
    def discover(name: str, _override: str | None) -> str | None:
        if name == "codex":
            raise OSError(448, "untrusted mount point")
        return f"/provider/{name}"

    monkeypatch.setattr(provider_command_module, "_native_command", discover)

    assert discover_provider_commands(
        [("codex", None), ("claude", None)], wsl_names=set()
    ) == {"codex": None, "claude": "/provider/claude"}


def test_windows_discovers_and_invokes_provider_clis_in_wsl(monkeypatch):
    wsl = Path("C:/Windows/System32/wsl.exe")
    monkeypatch.setattr(provider_command_module.sys, "platform", "win32")
    monkeypatch.setenv("GROK_HOME", "/provider-not-installed")
    monkeypatch.setenv("CODEX_HOME", "/provider-not-installed")
    monkeypatch.setattr(provider_command_module, "_known_windows_paths", lambda _name: ())
    monkeypatch.setattr(
        provider_command_module.shutil,
        "which",
        lambda name: str(wsl) if name in {"wsl.exe", "wsl"} else None,
    )

    def fake_run(argv, **_kwargs):
        assert argv[-3:] == ["codex", "claude", "grok"]
        return subprocess.CompletedProcess(
            argv,
            0,
            "codex\t/home/test/.local/bin/codex\n"
            "claude\t/home/test/.local/bin/claude\n"
            "grok\t\n",
            "",
        )

    monkeypatch.setattr(provider_command_module.subprocess, "run", fake_run)
    commands = discover_provider_commands(
        [("codex", None), ("claude", None), ("grok", None)]
    )

    codex = commands["codex"]
    assert codex == WSLCommand(str(wsl.absolute()), "/home/test/.local/bin/codex")
    assert command_argv(codex, "--version") == [
        str(wsl.absolute()),
        "--exec",
        "/home/test/.local/bin/codex",
        "--version",
    ]
    assert isinstance(commands["claude"], WSLCommand)
    assert commands["grok"] is None


def test_wsl_command_translates_paths_and_selects_a_distribution(monkeypatch):
    command = WSLCommand("C:/Windows/System32/wsl.exe", "/usr/bin/codex", "Ubuntu")

    def fake_run(argv, **_kwargs):
        assert argv == [
            "C:/Windows/System32/wsl.exe",
            "--distribution",
            "Ubuntu",
            "--exec",
            "wslpath",
            "-a",
            str(Path("C:/Temp/Atlas").absolute()),
        ]
        return subprocess.CompletedProcess(argv, 0, "/mnt/c/Temp/Atlas\n", "")

    monkeypatch.setattr(provider_command_module.subprocess, "run", fake_run)

    assert command_path(command, "C:/Temp/Atlas") == "/mnt/c/Temp/Atlas"
    assert command_argv(command, "--version", cwd="C:/Temp/Atlas") == [
        "C:/Windows/System32/wsl.exe",
        "--distribution",
        "Ubuntu",
        "--cd",
        "/mnt/c/Temp/Atlas",
        "--exec",
        "/usr/bin/codex",
        "--version",
    ]


def test_application_worker_supervises_the_portable_fallback(monkeypatch, tmp_path: Path):
    store = Store(tmp_path / "data")
    store.initialize()
    config = tmp_path / "harnesses.json"
    fake_adapter = Path(__file__).with_name("fake_harness_adapter.py")
    monkeypatch.setenv("TA_WORKER_BACKEND", "application")
    monkeypatch.setenv("TA_HARNESS_CONFIG", str(config))
    spec = HarnessRegistry().register(
        "fake",
        sys.executable,
        args=(str(fake_adapter),),
        make_default=True,
    )
    try:
        before = application_worker_status()
        assert before["active"] == "inactive"
        active = ensure_application_worker(store, spec, interval=0.05, timeout=5)
        assert active["backend"] == "application"
        assert active["active"] == "active"
        assert active["harness"] == "fake"
        assert active["store"] == str(store.root)
    finally:
        stop_application_worker()
    assert application_worker_status()["active"] == "inactive"
