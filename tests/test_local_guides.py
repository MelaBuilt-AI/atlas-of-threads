"""Synthetic native CLI contracts for all four local guide adapters."""
import importlib
import io
import json
import sys
from pathlib import Path

import pytest

from thought_archaeology import agent_spark as spark
from thought_archaeology.harness import HarnessRegistry, describe_harness
from thought_archaeology.store import Store
from tests.test_agent_spark import canonical, wait
from tests.test_serve import _compile_simple


@pytest.mark.parametrize("name", ["claude", "codex", "grok", "prime_agent"])
def test_local_guide_discussion_history_and_cli_contract(name, tmp_path, monkeypatch):
    prefix = name.upper()
    monkeypatch.setenv("TA_TEST_CLAUDE_MISE", "1")
    capture = tmp_path / "call.json"
    monkeypatch.setenv("TA_HARNESS_CONFIG", str(tmp_path / "config/harnesses.json"))
    monkeypatch.setenv(f"TA_{prefix}_BIN", str(Path(__file__).with_name(f"fake_{name}_cli.py")))
    monkeypatch.setenv(f"TA_TEST_{prefix}_CALL", str(capture))
    monkeypatch.setenv(f"TA_{prefix}_MODEL", "synthetic-model")
    monkeypatch.setenv("TA_PRIME_AGENT_PROVIDER", "synthetic-provider")
    monkeypatch.setenv("TA_TEST_GUIDE_RESPONSE", "My assessment: test the synthetic claim — café.")
    monkeypatch.delenv("TA_HARNESS_AGENT_NAME", raising=False)
    monkeypatch.delenv("TA_HARNESS_MEMORY_ROOT", raising=False)
    registry = HarnessRegistry()
    spec = registry.register(name, sys.executable, args=("-m", f"thought_archaeology.adapters.{name}"))
    assert "discuss" in describe_harness(spec)["capabilities"]
    _, graph_id = _compile_simple(tmp_path / "store")
    store = Store(tmp_path / "store")
    graph = store.load_graph(graph_id)
    before = canonical(store)
    spark.assign_roles(store, {"harness": name, "collaborator": False, "guide": True})
    body = {"prompt": "Assess this claim — café.", "request_id": "first",
            "graph_id": graph_id, "node_id": graph.nodes[0].id}
    spark.begin_discussion(store, body)
    first = wait(store)["turns"][0]
    assert first["status"] == "completed"
    assert first["response"] == "My assessment: test the synthetic claim — café."
    assert first["source"]["node_id"] == graph.nodes[0].id
    # Reloading the store supplies this guide's saved visible turns to its next call.
    spark.begin_discussion(Store(store.root), {**body, "request_id": "second", "prompt": "What did you suggest?"})
    assert wait(store)["turns"][-1]["status"] == "completed"
    call = json.loads(capture.read_text())
    prompt = call["prompt"]
    context = json.loads(prompt.split("PUBLIC THOUGHT ARCHAEOLOGY CONTEXT (JSON):\n")[1])
    assert context["discussion"][0]["response"] == first["response"]
    assert context["graph"]["id"] == graph_id
    assert "hidden_reasoning" not in context["graph"]
    assert "prompt" not in context["request"]
    assert "ordinary prose" in prompt
    assert "exactly one fenced" not in prompt
    assert "What did you suggest?" in prompt
    argv = call["argv"]
    if name == "codex":
        assert "--ephemeral" in argv and "--ignore-user-config" in argv
        assert argv[argv.index("--sandbox") + 1] == "read-only"
    elif name == "prime_agent":
        assert all(flag in argv for flag in ("--no-session", "--no-tools", "--no-context-files"))
    else:
        assert argv[argv.index("--tools") + 1] == ""
        if name == "claude":
            assert "--strict-mcp-config" in argv and "--no-session-persistence" in argv
        else:
            assert "--no-subagents" in argv and "--disable-web-search" in argv
    assert registry.collaborator_names() == ()
    assert canonical(store) == before
    # CLI operation and envelope must agree; invalid input must not invoke the model.
    module = importlib.import_module(f"thought_archaeology.adapters.{name}")
    envelope = {"protocol_version": "1", "operation": "continue", "request": {}, "graph": {}, "standing": {}}
    capture.unlink()
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(envelope)))
    assert module.main(["discuss"]) == 1
    assert not capture.exists()
    envelope["operation"] = "discuss"
    envelope["graph"]["hidden_reasoning"] = "private synthetic sentinel"
    with pytest.raises(Exception, match="hidden_reasoning"):
        module._validate_envelope(envelope)
