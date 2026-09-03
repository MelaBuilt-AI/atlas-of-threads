from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

import thought_archaeology.harness as harness_module
from thought_archaeology.continuation import (
    continuation_attempt,
    continuation_cancellation,
)
from thought_archaeology.harness import (
    HarnessError,
    HarnessRegistry,
    process_continuation,
)
from thought_archaeology.serve import (
    create_workspace_inquiry,
    thread_payload,
    workspace_payload,
)
from thought_archaeology.store import Store

from tests.helpers import FIXTURES
from tests.test_cli import run

FAKE_ADAPTER = Path(__file__).with_name("fake_harness_adapter.py")


def _compiled(store_path: Path) -> tuple[str, str]:
    code, out, err = run(["init", "--title", "harness source"], store=store_path)
    assert code == 0, err
    session_id = out.strip()
    code, out, err = run(
        [
            "compile",
            "--session",
            session_id,
            "--mode",
            "posthoc",
            "--transcript",
            str(FIXTURES / "transcripts" / "simple-freeform.jsonl"),
            "--from-graph",
            str(FIXTURES / "graphs" / "simple.gold.json"),
        ],
        store=store_path,
    )
    assert code == 0, err
    return session_id, out.strip()


def _register(monkeypatch, tmp_path: Path, store_path: Path) -> Path:
    config = tmp_path / "config" / "harnesses.json"
    monkeypatch.setenv("TA_HARNESS_CONFIG", str(config))
    code, out, err = run(
        [
            "harness",
            "register",
            "fake",
            "--adapter",
            sys.executable,
            f"--arg={FAKE_ADAPTER}",
            "--default",
        ],
        store=store_path,
    )
    assert code == 0, err
    assert out.strip() == "fake"
    return config


def test_harness_registry_is_user_owned_and_secret_free(monkeypatch, tmp_path: Path):
    store_path = tmp_path / "data"
    config = _register(monkeypatch, tmp_path, store_path)
    assert config.is_file()
    assert os.stat(config).st_mode & 0o777 == 0o600
    raw = json.loads(config.read_text(encoding="utf-8"))
    assert raw["default"] == "fake"
    assert raw["harnesses"]["fake"]["argv"] == [
        str(Path(sys.executable).absolute()),
        str(FAKE_ADAPTER),
    ]
    assert "credential" not in json.dumps(raw).lower()

    refreshed = HarnessRegistry(config).record_model(
        "fake", "fake-default", cli_version="fake-cli 1.0"
    )
    assert refreshed.model == "fake-default"
    assert refreshed.model_refreshed_at
    assert refreshed.cli_version == "fake-cli 1.0"

    code, out, err = run(["harness", "list", "--format", "json"], store=store_path)
    assert code == 0, err
    assert json.loads(out)[0]["default"] is True
    code, out, err = run(["harness", "doctor"], store=store_path)
    assert code == 0, err
    assert json.loads(out)["capabilities"] == ["continue"]
    code, out, err = run(["harness", "status", "--format", "json"], store=store_path)
    assert code == 0, err
    status = json.loads(out)
    assert status["registered"] == 1
    assert status["store_ready"] is False
    assert status["pending"] == 0

    code, out, err = run(["harness", "remove", "fake"], store=store_path)
    assert code == 0, err
    assert HarnessRegistry(config).specs() == ()
    assert HarnessRegistry(config).default_name() is None


def test_adapter_protocol_is_ascii_safe_over_an_explicit_utf8_pipe(
    monkeypatch, tmp_path: Path
):
    captured = {}
    spec = HarnessRegistry(tmp_path / "harnesses.json").register(
        "fake", sys.executable, make_default=True
    )

    def run(argv, **kwargs):
        captured.update(kwargs)
        return __import__("subprocess").CompletedProcess(
            argv,
            0,
            json.dumps(
                {
                    "protocol_version": "1",
                    "response": "retained → path",
                    "model_name": "fake",
                },
                ensure_ascii=True,
            ),
            "",
        )

    monkeypatch.setattr(harness_module.subprocess, "run", run)
    result = harness_module._adapter_call(
        spec, "continue", {"text": "rejected → retained"}, timeout=5
    )

    assert result["response"] == "retained → path"
    assert captured["encoding"] == "utf-8"
    assert "→" not in captured["input"]
    assert "\\u2192" in captured["input"]


def test_harness_run_completes_request_and_advances_session(
    monkeypatch, tmp_path: Path
):
    store_path = tmp_path / "data"
    session_id, source_graph_id = _compiled(store_path)
    store = Store(store_path)
    source_graph = store.load_graph(source_graph_id)
    node = source_graph.nodes[0]
    _register(monkeypatch, tmp_path, store_path)
    capture = tmp_path / "envelope.json"
    monkeypatch.setenv("TA_TEST_HARNESS_ENVELOPE", str(capture))

    code, out, err = run(
        [
            "continuation",
            "ready",
            node.id,
            "--graph",
            source_graph.id,
            "--prompt",
            "Continue from this exact chamber.",
        ],
        store=store_path,
    )
    assert code == 0, err
    request_id = out.strip()
    code, out, err = run(
        ["harness", "run", "--request", request_id], store=store_path
    )
    assert code == 0, err
    outcome = json.loads(out)
    assert outcome["status"] == "completed"
    assert outcome["harness"] == "fake"
    assert outcome["request_id"] == request_id
    attempts = list(store.iter_continuation_attempts())
    assert len(attempts) == 1
    assert attempts[0].request_id == request_id
    assert attempts[0].harness == "fake"
    assert list(store.iter_continuation_requests(pending=True)) == []
    completions = list(store.iter_continuation_completions())
    assert len(completions) == 1
    assert completions[0].graph_id == outcome["graph_id"]

    response_graph = store.load_graph(outcome["graph_id"])
    assert response_graph.parent_graph_id == source_graph.id
    assert response_graph.session_id == session_id
    assert response_graph.model.provider == "shell"
    assert response_graph.model.name == "fake-model"
    assert store.load_session(session_id).head_graph_id == response_graph.id
    turns = list(store.iter_turns(session_id))
    assert [turn.role for turn in turns[-2:]] == ["user", "assistant"]
    assert turns[-2].prose == "Continue from this exact chamber."
    assert turns[-2].parent_turn_id == source_graph.turn_id
    assert turns[-1].parent_turn_id == turns[-2].id
    assert turns[-1].graph_id == response_graph.id
    assert store.validate_session(session_id) == []

    envelope = json.loads(capture.read_text(encoding="utf-8"))
    assert envelope["protocol_version"] == "1"
    assert envelope["request"]["id"] == request_id
    assert envelope["graph"]["id"] == source_graph.id
    assert "hidden_reasoning" not in envelope["graph"]
    assert envelope["standing"]["node"]["id"] == node.id
    assert envelope["response_contract"]["model_name"]

    code, out, err = run(["harness", "run"], store=store_path)
    assert code == 0, err
    assert json.loads(out) == {"status": "idle"}


def test_harness_discards_response_canceled_during_model_call(
    monkeypatch, tmp_path: Path
):
    store_path = tmp_path / "data"
    _session_id, graph_id = _compiled(store_path)
    store = Store(store_path)
    graph = store.load_graph(graph_id)
    node = graph.nodes[0]
    code, out, err = run(
        ["continuation", "ready", node.id, "--graph", graph.id],
        store=store_path,
    )
    assert code == 0, err
    request_id = out.strip()
    response = (FIXTURES / "transcripts" / "simple-structured.txt").read_text(
        encoding="utf-8"
    )

    def cancel_then_answer(spec, operation, payload, *, timeout):
        assert operation == "continue"
        store.write_continuation_cancellation(
            continuation_cancellation(request_id, source="inhabit_space")
        )
        return {
            "protocol_version": "1",
            "response": response,
            "model_name": "too-late",
        }

    monkeypatch.setattr(harness_module, "_adapter_call", cancel_then_answer)
    before_graphs = [item.id for item in store.iter_graphs()]
    spec = HarnessRegistry(tmp_path / "unused.json").register(
        "fake", sys.executable, args=(str(FAKE_ADAPTER),), make_default=True
    )
    with pytest.raises(HarnessError, match="response was discarded"):
        harness_module.process_continuation(store, spec, request_id=request_id)
    assert [item.id for item in store.iter_graphs()] == before_graphs
    assert list(store.iter_continuation_requests(pending=True)) == []


def test_harness_failure_closes_ordinary_request_and_next_request_runs(
    monkeypatch, tmp_path: Path
):
    store_path = tmp_path / "data"
    _session_id, graph_id = _compiled(store_path)
    store = Store(store_path)
    graph = store.load_graph(graph_id)
    node = graph.nodes[0]
    spec = HarnessRegistry(tmp_path / "harnesses.json").register(
        "fake", sys.executable, args=(str(FAKE_ADAPTER),), make_default=True
    )

    code, out, err = run(
        ["continuation", "ready", node.id, "--graph", graph.id],
        store=store_path,
    )
    assert code == 0, err
    failed_request_id = out.strip()

    def fail_adapter(*_args, **_kwargs):
        raise HarnessError("provider leaked-secret rejected an unknown argument")

    monkeypatch.setattr(harness_module, "_adapter_call", fail_adapter)
    outcome = process_continuation(store, spec, request_id=failed_request_id)
    assert outcome["status"] == "failed"
    assert outcome["reason_code"] == "adapter_error"
    assert list(store.iter_continuation_requests(pending=True)) == []
    failure = list(store.iter_continuation_failures())[-1]
    assert failure.request_id == failed_request_id
    assert failure.public_summary == (
        "The installed collaborator CLI rejected the request options. "
        "Update it, then retry."
    )
    assert "leaked-secret" not in failure.public_summary

    code, out, err = run(
        ["continuation", "ready", node.id, "--graph", graph.id],
        store=store_path,
    )
    assert code == 0, err
    retry_request_id = out.strip()
    response = (FIXTURES / "transcripts" / "simple-structured.txt").read_text(
        encoding="utf-8"
    )
    monkeypatch.setattr(
        harness_module,
        "_adapter_call",
        lambda *_args, **_kwargs: {
            "protocol_version": "1",
            "response": response,
            "model_name": "fake-model",
        },
    )
    retry = process_continuation(store, spec, request_id=retry_request_id)
    assert retry["status"] == "completed"


def test_harness_restart_closes_an_attempted_ordinary_request(
    monkeypatch, tmp_path: Path
):
    store_path = tmp_path / "data"
    _session_id, graph_id = _compiled(store_path)
    store = Store(store_path)
    graph = store.load_graph(graph_id)
    spec = HarnessRegistry(tmp_path / "harnesses.json").register(
        "fake", sys.executable, args=(str(FAKE_ADAPTER),), make_default=True
    )
    code, out, err = run(
        ["continuation", "ready", graph.nodes[0].id, "--graph", graph.id],
        store=store_path,
    )
    assert code == 0, err
    request_id = out.strip()
    store.write_continuation_attempt(continuation_attempt(request_id, "fake"))
    monkeypatch.setattr(
        harness_module,
        "_adapter_call",
        lambda *_args, **_kwargs: pytest.fail("attempted request was invoked twice"),
    )

    outcome = process_continuation(store, spec, request_id=request_id)

    assert outcome["status"] == "failed"
    assert outcome["reason_code"] == "interrupted"
    assert list(store.iter_continuation_requests(pending=True)) == []


def test_ready_without_prompt_does_not_invent_a_user_turn(
    monkeypatch, tmp_path: Path
):
    store_path = tmp_path / "data"
    session_id, graph_id = _compiled(store_path)
    store = Store(store_path)
    graph = store.load_graph(graph_id)
    before = list(store.iter_turns(session_id))
    _register(monkeypatch, tmp_path, store_path)
    code, out, err = run(
        ["continuation", "ready", graph.nodes[0].id, "--graph", graph.id],
        store=store_path,
    )
    assert code == 0, err
    code, out, err = run(
        ["harness", "run", "--request", out.strip()], store=store_path
    )
    assert code == 0, err
    outcome = json.loads(out)
    after = list(store.iter_turns(session_id))
    assert len(after) == len(before) + 1
    assert after[-1].role == "assistant"
    assert after[-1].parent_turn_id == graph.turn_id
    assert after[-1].graph_id == outcome["graph_id"]


def test_workspace_new_inquiry_reuses_harness_without_duplicate_user_turn(
    monkeypatch, tmp_path: Path
):
    store_path = tmp_path / "data"
    _register(monkeypatch, tmp_path, store_path)
    unit = tmp_path / "thought-archaeology-harness.service"
    unit.write_text("[Service]\nExecStart=/bin/true\n", encoding="utf-8")
    systemctl = tmp_path / "systemctl"
    systemctl.write_text(
        "#!/bin/sh\n"
        'if [ "$2" = "is-enabled" ]; then echo enabled; fi\n'
        'if [ "$2" = "is-active" ]; then echo active; fi\n',
        encoding="utf-8",
    )
    systemctl.chmod(0o700)
    monkeypatch.setenv("TA_HARNESS_SERVICE", str(unit))
    monkeypatch.setenv("TA_SYSTEMCTL", str(systemctl))

    store = Store(store_path)
    opening = "How should a synthetic mind preserve disagreement?"
    created = create_workspace_inquiry(store, opening)
    assert store.exists()
    unit_text = unit.read_text(encoding="utf-8")
    assert f'"--store" "{store.root}"' in unit_text
    assert '"--harness" "fake"' in unit_text
    request = store.load_continuation_request(created["request"]["id"])
    seed = store.load_graph(created["graph_id"])
    assert request.source == "workspace"
    assert request.prompt == opening
    assert seed.parent_graph_id is None
    assert [(node.kind, node.agent, node.text) for node in seed.nodes] == [
        ("uncertainty", "human", opening)
    ]
    assert thread_payload(store, created["session_id"])["entries"][0]["label"] == (
        "opening inquiry"
    )

    outcome = process_continuation(
        store, HarnessRegistry().get(), request_id=request.id
    )
    assert outcome is not None
    response = store.load_graph(outcome["graph_id"])
    assert response.parent_graph_id == seed.id
    turns = list(store.iter_turns(created["session_id"]))
    assert [turn.role for turn in turns] == ["user", "assistant"]
    assert [turn.prose for turn in turns].count(opening) == 1

    workspace = workspace_payload(store)
    assert workspace["active_harness"] == "fake"
    assert workspace["pending"] == []
    assert workspace["history"][0]["id"] == created["session_id"]
    assert workspace["history"][0]["graph_count"] == 2
    assert workspace["history"][0]["harness"] == "fake"
    assert workspace["history"][0]["author_label"] == "Fake · fake-model"


def test_harness_service_is_explicit_and_bound_to_store(
    monkeypatch, tmp_path: Path
):
    store_path = tmp_path / "data with space"
    _compiled(store_path)
    _register(monkeypatch, tmp_path, store_path)
    unit = tmp_path / "config" / "systemd" / "user" / "thought-archaeology-harness.service"
    calls = tmp_path / "systemctl.log"
    systemctl = tmp_path / "systemctl"
    systemctl.write_text(
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" >> "$TA_TEST_SYSTEMCTL_LOG"\n'
        'if [ "$2" = "is-enabled" ]; then echo enabled; fi\n'
        'if [ "$2" = "is-active" ]; then echo active; fi\n',
        encoding="utf-8",
    )
    systemctl.chmod(0o700)
    monkeypatch.setenv("TA_HARNESS_SERVICE", str(unit))
    monkeypatch.setenv("TA_SYSTEMCTL", str(systemctl))
    monkeypatch.setenv("TA_TEST_SYSTEMCTL_LOG", str(calls))

    code, out, err = run(
        ["harness", "service", "install", "--harness", "fake"],
        store=store_path,
    )
    assert code == 0, err
    assert out.strip() == str(unit)
    text = unit.read_text(encoding="utf-8")
    assert "ExecStart=" in text
    assert f'"{store_path}"' in text
    assert '"--harness" "fake"' in text
    assert "Restart=on-failure" in text
    assert 'Environment="PATH=' in text
    assert "credential" not in text.lower()
    assert calls.read_text(encoding="utf-8").splitlines()[:2] == [
        "--user daemon-reload",
        "--user enable --now thought-archaeology-harness.service",
    ]

    code, out, err = run(
        ["harness", "service", "status", "--format", "json"],
        store=store_path,
    )
    assert code == 0, err
    status = json.loads(out)
    assert status["installed"] is True
    assert status["enabled"] == "enabled"
    assert status["active"] == "active"
