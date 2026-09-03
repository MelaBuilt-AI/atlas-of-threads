from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import thought_archaeology.adapters.grok as grok_module
from thought_archaeology.adapters.grok import GrokAdapterError
from thought_archaeology.store import Store

from tests.helpers import FIXTURES
from tests.test_cli import run

FAKE_GROK = Path(__file__).with_name("fake_grok_cli.py")


def _source(store_path: Path) -> tuple[str, str]:
    code, out, err = run(["init", "--title", "Grok adapter test"], store=store_path)
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


def test_grok_adapter_handshake_and_real_cli_shape(monkeypatch, tmp_path: Path):
    store_path = tmp_path / "data"
    session_id, graph_id = _source(store_path)
    store = Store(store_path)
    graph = store.load_graph(graph_id)
    config = tmp_path / "config" / "harnesses.json"
    capture = tmp_path / "grok-call.json"
    monkeypatch.setenv("TA_HARNESS_CONFIG", str(config))
    monkeypatch.setenv("TA_GROK_BIN", str(FAKE_GROK))
    monkeypatch.setenv("TA_TEST_GROK_CALL", str(capture))
    monkeypatch.setenv(
        "PYTHONPATH", str(Path(__file__).resolve().parent.parent / "src")
    )

    code, out, err = run(
        [
            "harness",
            "register",
            "grok",
            "--adapter",
            sys.executable,
            "--arg=-m",
            "--arg=thought_archaeology.adapters.grok",
            "--default",
        ],
        store=store_path,
    )
    assert code == 0, err
    code, out, err = run(["harness", "doctor", "grok"], store=store_path)
    assert code == 0, err
    diagnosis = json.loads(out)
    assert diagnosis["name"] == "grok"
    assert diagnosis["default_model"] == "grok-test"
    assert diagnosis["cli_version"].startswith("grok 0.0-test")

    code, out, err = run(
        [
            "continuation",
            "ready",
            graph.nodes[0].id,
            "--graph",
            graph.id,
            "--prompt",
            "Continue through Grok.",
        ],
        store=store_path,
    )
    assert code == 0, err
    request_id = out.strip()
    code, out, err = run(
        ["harness", "run", "--harness", "grok", "--request", request_id],
        store=store_path,
    )
    assert code == 0, err
    outcome = json.loads(out)
    response_graph = store.load_graph(outcome["graph_id"])
    assert response_graph.session_id == session_id
    assert response_graph.parent_graph_id == graph.id
    assert response_graph.model.name == "grok-test"

    call = json.loads(capture.read_text(encoding="utf-8"))
    argv = call["argv"]
    assert "--verbatim" in argv
    assert "--no-plan" in argv
    assert "--no-subagents" in argv
    assert "--disable-web-search" in argv
    assert argv[argv.index("--max-turns") + 1] == "10"
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--output-format") + 1] == "plain"
    assert argv[argv.index("--model") + 1] == "grok-test"
    prompt = call["prompt"]
    assert "Continue through Grok." in prompt
    assert "PUBLIC THOUGHT ARCHAEOLOGY CONTEXT" in prompt
    assert "hidden_reasoning" not in prompt
    assert "Do not inspect or modify local files" in prompt


def test_grok_empty_captured_stream_is_a_bounded_adapter_error(monkeypatch):
    monkeypatch.setattr(
        grok_module.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout=None, stderr=None
        ),
    )
    envelope = {
        "request": {},
        "graph": {},
        "standing": {},
        "session": {},
    }
    with pytest.raises(GrokAdapterError, match="returned no response"):
        grok_module._continue("grok", envelope, "grok-test")


def test_grok_model_output_is_read_as_utf8(monkeypatch):
    captured = {}

    def run(argv, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "rejected → retained", "")

    monkeypatch.setattr(grok_module.subprocess, "run", run)
    response = grok_module._continue(
        "grok",
        {"request": {}, "graph": {}, "standing": {}, "session": {}},
        "grok-test",
    )

    assert response == "rejected → retained"
    assert captured["encoding"] == "utf-8"
