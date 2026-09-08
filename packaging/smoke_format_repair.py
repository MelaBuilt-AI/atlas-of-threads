"""Exercise packaged continuation format repair with a synthetic external adapter."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def smoke(command):
    with tempfile.TemporaryDirectory(prefix="atlas-format-repair-") as folder:
        root = Path(folder)
        store = root / "store"
        fixture = Path(__file__).resolve().parents[1] / "fixtures/transcripts/simple-structured.txt"
        answer = root / "answer.txt"
        answer.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
        adapter = root / "adapter.py"
        adapter.write_text('''import json, sys
from pathlib import Path
root = Path(__file__).parent
if sys.argv[-1] == "describe":
    print(json.dumps({"protocol_version": "1", "capabilities": ["continue"]}))
else:
    envelope = json.load(sys.stdin)
    counter = root / "calls.json"
    calls = json.loads(counter.read_text()) if counter.exists() else []
    calls.append(envelope["request"]["id"])
    counter.write_text(json.dumps(calls))
    if len(calls) == 1:
        response = "Synthetic answer missing its graph."
    else:
        assert len(calls) == 2
        assert "FORMAT REPAIR ONLY" in envelope["request"]["prompt"]
        assert "Synthetic answer missing its graph." in envelope["request"]["prompt"]
        response = (root / "answer.txt").read_text(encoding="utf-8")
    print(json.dumps({"protocol_version": "1", "response": response, "model_name": "synthetic"}))
''', encoding="utf-8")
        env = {**os.environ, "TA_HARNESS_CONFIG": str(root / "harnesses.json")}

        def run(*args):
            result = subprocess.run([*command, "--store", str(store), *args],
                                    env=env, capture_output=True, text=True, timeout=60)
            assert result.returncode == 0, result.stderr
            return result.stdout.strip()

        session = run("init", "--title", "Synthetic formatting smoke")
        graph_id = run("compile", "--session", session, "--mode", "structured", "--input", str(answer))
        graph = json.loads(run("show", graph_id, "--format", "json"))
        run("harness", "register", "synthetic", "--adapter", sys.executable,
            "--arg=" + str(adapter), "--default")
        request = run("continuation", "ready", graph["nodes"][0]["id"], "--graph", graph_id)
        outcome = json.loads(run("harness", "run", "--request", request))
        assert outcome["status"] == "completed", outcome
        assert json.loads((root / "calls.json").read_text()) == [request, request]
        assert len(list((store / "continuations/completions").glob("*.json"))) == 1
        assert len(list((store / "continuations/attempts").glob("*.json"))) == 1
        assert not list((store / "continuations/failures").glob("*.json"))
        events = [json.loads(line) for line in (store / "store.log.jsonl").read_text().splitlines()]
        assert sum(e["op"] == "harness_format_repair" for e in events) == 1
        print("PASS: packaged formatting repair calls the adapter twice and completes once; no model calls.")


if __name__ == "__main__":
    smoke(sys.argv[1:])
