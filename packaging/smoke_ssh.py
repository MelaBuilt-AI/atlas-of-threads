"""Exercise the frozen SSH adapter with synthetic transport, never real credentials."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def smoke(command):
    with tempfile.TemporaryDirectory(prefix="atlas-ssh-smoke-") as folder:
        root = Path(folder)
        host = root / "fake_host.py"
        host.write_text(
            "import json,sys\n"
            "r=json.load(sys.stdin)\n"
            "d={'protocol_version':'1','name':'synthetic','capabilities':['continue','discuss','resumable_session'],"
            "'default_model':'synthetic/model','cli_version':'synthetic-1'}\n"
            "if r['operation']!='describe':d={'protocol_version':'1','response':r['prompt'],"
            "'model_name':'synthetic/model','remote_session_id':'synthetic-session'}\n"
            "print(json.dumps(d,ensure_ascii=True))\n", encoding="utf-8")
        config = root / "connection.json"
        config.write_text(json.dumps({"ssh_argv": [sys.executable, str(host)],
            "host": "synthetic.invalid", "remote_command": ["synthetic-helper"]}), encoding="utf-8")
        base = [*command, "adapter", "ssh", "--config", str(config)]
        def call(operation, envelope=None):
            p = subprocess.run([*base, operation], capture_output=True, timeout=30,
                               input=json.dumps(envelope).encode() if envelope else None)
            assert p.returncode == 0, p.stderr.decode(errors="replace")
            return json.loads(p.stdout)
        assert call("describe")["default_model"] == "synthetic/model"
        for operation in ("continue", "discuss"):
            result = call(operation, {"protocol_version": "1", "operation": operation,
                "request": {"id": "synthetic-request", "prompt": "Café 植物 $(literal)"},
                "graph": {}, "standing": {}})
            assert "Café 植物 $(literal)" in result["response"]
            assert result["remote_session_id"] == "synthetic-session"
    print("PASS: packaged SSH describe, contribution and guide dispatch with UTF-8 synthetic transport.")


if __name__ == "__main__":
    smoke(sys.argv[1:])
