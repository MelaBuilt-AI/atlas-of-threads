from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    operation = sys.argv[-1]
    if operation == "describe":
        print(
            json.dumps(
                {
                    "protocol_version": "1",
                    "name": "fake-harness",
                    "capabilities": ["continue"],
                    "cli_version": "fake-cli 1.0",
                    "default_model": "fake-default",
                }
            )
        )
        return 0
    if operation != "continue":
        print(f"unknown operation: {operation}", file=sys.stderr)
        return 2
    envelope = json.load(sys.stdin)
    capture = os.environ.get("TA_TEST_HARNESS_ENVELOPE")
    if capture:
        Path(capture).write_text(
            json.dumps(envelope, indent=2) + "\n", encoding="utf-8"
        )
    response = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "transcripts"
        / "simple-structured.txt"
    ).read_text(encoding="utf-8")
    print(
        json.dumps(
            {
                "protocol_version": "1",
                "response": response,
                "model_name": "fake-model",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
