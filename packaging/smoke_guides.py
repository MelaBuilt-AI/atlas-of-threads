"""Synthetic packaged guide protocol checks; never invoke a provider model."""
import json
import os
import subprocess
import sys


def smoke(command):
    for name in ("codex", "claude", "grok", "prime-agent"):
        prefix = name.upper().replace("-", "_")
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("TA_HARNESS_")}
        # Python provides a harmless --version response in place of a native CLI.
        # The malformed envelope must be rejected before any model invocation.
        env.update({f"TA_{prefix}_BIN": sys.executable,
                    f"TA_{prefix}_MODEL": "synthetic-model",
                    "TA_PRIME_AGENT_PROVIDER": "synthetic-provider"})
        result = subprocess.run([*command, "adapter", name, "describe"],
                                env=env, capture_output=True, timeout=30)
        assert result.returncode == 0, result.stderr
        description = json.loads(result.stdout)
        assert {"continue", "discuss"} <= set(description["capabilities"])
        envelope = {"protocol_version": "1", "operation": "discuss", "request": {},
                    "graph": {"hidden_reasoning": "synthetic private sentinel"},
                    "standing": {}}
        result = subprocess.run([*command, "adapter", name, "discuss"],
                                input=json.dumps(envelope).encode(), env=env,
                                capture_output=True, timeout=30)
        assert result.returncode != 0
        assert b"must not contain hidden_reasoning" in result.stderr, result.stderr
        assert not result.stdout
    print("PASS: four packaged guide capabilities and private-context rejection; no model calls.")


if __name__ == "__main__":
    smoke(sys.argv[1:])
