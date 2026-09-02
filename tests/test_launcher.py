from __future__ import annotations

import os
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


def test_frozen_application_uses_itself_for_packaged_bridges(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/opt/AtlasOfThreads")
    assert _packaged_harness_command("ta-harness-prime-agent") == (
        str(Path("/opt/AtlasOfThreads").absolute()),
        ("adapter", "prime-agent"),
    )


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
