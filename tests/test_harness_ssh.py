"""Synthetic transport/session tests; no LAN host or provider credentials."""
import json
import shlex
import subprocess
import sys
import socket
import threading
from pathlib import Path

import pytest

from thought_archaeology.adapters import remote_host, ssh
from thought_archaeology.harness import HarnessError, HarnessRegistry, HarnessSpec


def test_session_only_registration_round_trip(tmp_path):
    registry = HarnessRegistry(tmp_path / "harnesses.json")
    spec = registry.register("remote", sys.executable, collaborator_id="synthetic-agent",
                             agent_name="Test Agent", session_only=True)
    assert registry.get() == spec
    assert spec.memory_mode == "resumable_session"
    assert spec.memory_root is None and spec.memory_files == ()
    assert spec.session_state
    with pytest.raises(HarnessError):
        HarnessSpec.from_dict("remote", {**spec.to_dict(), "session_only": False})
    with pytest.raises(HarnessError):
        HarnessSpec.from_dict("remote", {**spec.to_dict(), "memory_root": "/unapproved"})
    with pytest.raises(HarnessError):
        registry.register("missing", sys.executable, session_only=True)


def test_ssh_keeps_prompt_off_remote_shell(monkeypatch):
    seen = {}
    def run(argv, **kwargs):
        seen.update(argv=argv, **kwargs)
        return subprocess.CompletedProcess(argv, 0, '{"protocol_version":"1"}', "")
    monkeypatch.setattr(subprocess, "run", run)
    config = {"ssh_argv": ["ssh", "-i", "/key path/key"], "host": "user@example.invalid",
              "remote_command": ["python3", "/agent path/helper.py", "--config", "/settings.json"]}
    request = {"prompt": "Never execute $(touch /tmp/bad) `whoami` ' \"\nΩ"}
    ssh.call(config, request, 10)
    assert json.loads(seen["input"]) == request
    assert shlex.split(seen["argv"][-1]) == config["remote_command"]
    assert request["prompt"] not in " ".join(seen["argv"])
    assert "StrictHostKeyChecking=yes" in seen["argv"]
    assert "BatchMode=yes" in seen["argv"]
    assert not seen.get("shell")


def test_ssh_does_not_expose_provider_stderr(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k:
                        subprocess.CompletedProcess(a, 1, "", "private-native-context"))
    with pytest.raises(ValueError) as exc:
        ssh.call({"ssh_argv": ["ssh"], "host": "test", "remote_command": ["helper"]}, {}, 10)
    assert "private-native-context" not in str(exc.value)


@pytest.mark.skipif(sys.platform == "win32", reason="remote helper requires POSIX file locks")
def test_remote_receipt_replays_without_second_model_call(monkeypatch, tmp_path):
    calls = []
    def native(config, request, state, path):
        calls.append(request)
        state["session_id"] = "synthetic-session"
        remote_host.save(path, state)
        return "Synthetic response", "test/model"
    monkeypatch.setattr(remote_host, "hermes", native)
    config = {"provider": "hermes", "state_dir": str(tmp_path)}
    request = {"operation": "continue", "request_id": "synthetic-1", "prompt": "hello"}
    first = remote_host.handle(config, request)
    assert remote_host.handle(config, request) == first
    assert len(calls) == 1
    with pytest.raises(ValueError, match="different content"):
        remote_host.handle(config, {**request, "prompt": "changed"})
    assert len(calls) == 1


@pytest.mark.skipif(sys.platform == "win32", reason="remote helper requires POSIX file locks")
def test_interrupted_remote_call_is_not_automatically_resubmitted(monkeypatch, tmp_path):
    calls = []
    def interrupted(*args):
        calls.append(True)
        raise subprocess.TimeoutExpired("native-cli", 10)
    monkeypatch.setattr(remote_host, "hermes", interrupted)
    config = {"provider": "hermes", "state_dir": str(tmp_path)}
    request = {"operation": "discuss", "request_id": "synthetic-2", "prompt": "hello"}
    with pytest.raises(subprocess.TimeoutExpired):
        remote_host.handle(config, request)
    with pytest.raises(ValueError, match="unresolved"):
        remote_host.handle(config, request)
    assert len(calls) == 1


def test_openclaw_dedicated_session_is_restricted_before_model_call(monkeypatch, tmp_path):
    calls = []
    def rpc(config, method, params, **kwargs):
        calls.append((method, params))
        if method == "sessions.create":
            assert "message" not in params and "task" not in params
            return {"key": params["key"], "sessionId": "native-test"}
        if method == "sessions.patch":
            return {"entry": {"inheritedToolDeny": params["inheritedToolDeny"]}}
        return {"result": {"payloads": [{"text": "hello"}], "meta": {"agentMeta": {
            "sessionId": "native-test", "provider": "test", "model": "actual-model"}}}}
    monkeypatch.setattr(remote_host, "rpc", rpc)
    state = {}
    request = {"request_id": "synthetic-request", "prompt": "hello"}
    config = {"display_name": "Test Agent", "model": "test/requested-model"}
    result = remote_host.openclaw(config, request, state, tmp_path / "session.json")
    assert result == ("hello", "test/actual-model")
    assert [c[0] for c in calls] == ["sessions.create", "sessions.patch", "agent"]
    assert calls[1][1]["inheritedToolDeny"] == ["*"]
    assert calls[2][1]["deliver"] is False
    assert calls[2][1]["sessionId"] == "native-test"
    assert "expectedExistingSessionId" not in calls[2][1]
    calls.clear()
    remote_host.openclaw(config, request, state, tmp_path / "session.json")
    assert [c[0] for c in calls] == ["sessions.patch", "agent"]


def test_openclaw_missing_tool_restriction_stops_before_model(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(remote_host, "rpc", lambda c, m, p: calls.append(m) or {})
    with pytest.raises(ValueError, match="tool restriction"):
        remote_host.openclaw({"model": "test/model"}, {}, {"key": "test", "session_id": "test"}, tmp_path / "state.json")
    assert calls == ["sessions.patch"]


def test_remote_prompt_only_includes_public_context():
    envelope = {"protocol_version": "1", "operation": "discuss", "request": {"prompt": "test"},
                "graph": {}, "standing": {}, "unrelated_private_field": "DO_NOT_FORWARD"}
    assert "ordinary prose" in ssh.prompt(envelope)
    assert "DO_NOT_FORWARD" not in ssh.prompt(envelope)
    with pytest.raises(ValueError, match="hidden reasoning"):
        ssh.prompt({**envelope, "graph": {"hidden_reasoning": "DO_NOT_FORWARD"}})


@pytest.mark.skipif(sys.platform == "win32", reason="remote Unix socket transport")
def test_stdio_socket_preserves_utf8_and_half_close(tmp_path):
    # The subprocess closes stdin before the server replies, as MCP smoke does.
    from thought_archaeology.adapters import stdio_socket
    path = str(tmp_path / "mcp.sock")
    payload = '{"question":"synthetic Ω – lamp"}\n'.encode()
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(path)
        listener.listen(1)
        received = []
        def server():
            with listener.accept()[0] as connection:
                parts = []
                while data := connection.recv(4096):
                    parts.append(data)
                received.append(b"".join(parts))
                connection.sendall(payload)
        thread = threading.Thread(target=server, daemon=True)
        thread.start()
        result = subprocess.run([sys.executable, str(Path(stdio_socket.__file__)), path],
                                input=payload, capture_output=True, timeout=10)
        thread.join(timeout=2)
    assert result.returncode == 0, result.stderr
    assert result.stdout == payload
    assert received == [payload]
