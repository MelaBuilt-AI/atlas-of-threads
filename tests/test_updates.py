from __future__ import annotations

import hashlib
import io
import json
import shutil
from pathlib import Path

import pytest

from thought_archaeology import updates


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_installed_application_offers_only_a_newer_tagged_release(monkeypatch):
    monkeypatch.setattr(updates.sys, "frozen", True, raising=False)
    monkeypatch.setattr(updates.sys, "platform", "win32")
    monkeypatch.setattr(updates, "__version__", "1.2.3")

    def opener(request, *, timeout):
        assert request.full_url == updates.MANIFEST_URL
        assert timeout == 5
        return Response(
            json.dumps(
                {
                    "version": "v1.3.0",
                    "published_at": "2026-09-02T12:00:00Z",
                }
            ).encode("utf-8")
        )

    assert updates.update_status(opener=opener) == {
        "current_version": "v1.2.3",
        "latest_version": "v1.3.0",
        "available": True,
        "supported": True,
        "platform": "windows",
        "published_at": "2026-09-02T12:00:00Z",
    }


@pytest.mark.parametrize("version", ["main", "v1.2", "v1.2.3-rc1", "1.2.3"])
def test_non_release_versions_are_not_accepted(monkeypatch, version):
    monkeypatch.setattr(updates.sys, "frozen", True, raising=False)
    monkeypatch.setattr(updates.sys, "platform", "linux")

    def opener(_request, *, timeout):
        assert timeout == 5
        return Response(json.dumps({"version": version}).encode("utf-8"))

    assert updates.update_status(opener=opener)["available"] is False


def test_release_download_uses_immutable_version_and_verifies_checksum(monkeypatch):
    monkeypatch.setattr(updates.sys, "frozen", True, raising=False)
    monkeypatch.setattr(updates.sys, "platform", "linux")
    artifact = b"verified atlas package"
    digest = hashlib.sha256(artifact).hexdigest()
    requested = []

    def opener(request, *, timeout):
        requested.append((request.full_url, timeout))
        if request.full_url.endswith(".sha256"):
            return Response(f"{digest}  atlas-of-threads-linux-x86_64\n".encode("ascii"))
        return Response(artifact)

    prepared = updates.prepare_update("v1.3.0", opener=opener)
    try:
        assert prepared.artifact.read_bytes() == artifact
        assert requested == [
            (
                f"{updates.DOWNLOAD_ROOT}/v1.3.0/atlas-of-threads-linux-x86_64",
                30,
            ),
            (
                f"{updates.DOWNLOAD_ROOT}/v1.3.0/atlas-of-threads-linux-x86_64.sha256",
                30,
            ),
        ]
    finally:
        shutil.rmtree(prepared.artifact.parent)


def test_linux_activation_atomically_replaces_the_running_package(monkeypatch, tmp_path: Path):
    installed = tmp_path / "atlas-of-threads"
    installed.write_bytes(b"old")
    downloaded = tmp_path / "download" / "atlas-of-threads-linux-x86_64"
    downloaded.parent.mkdir()
    downloaded.write_bytes(b"new")
    monkeypatch.setattr(updates.sys, "executable", str(installed))

    result = updates.activate_update(
        updates.PreparedUpdate("v1.3.0", "linux", downloaded)
    )

    assert result == "installed"
    assert installed.read_bytes() == b"new"
    assert installed.stat().st_mode & 0o111
    assert not downloaded.parent.exists()
