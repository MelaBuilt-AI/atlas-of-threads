from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

import thought_archaeology.harness as harness_module
from thought_archaeology.continuation import continuation_cancellation
from thought_archaeology.harness import HarnessError, HarnessRegistry
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
