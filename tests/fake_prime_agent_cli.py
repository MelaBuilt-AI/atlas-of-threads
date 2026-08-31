#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _capture(data: dict[str, object]) -> None:
    path = os.environ.get("TA_TEST_PRIME_AGENT_CALL")
    if path:
        Path(path).write_text(json.dumps(data), encoding="utf-8")


def _value(args: list[str], flag: str) -> str:
    return args[args.index(flag) + 1]


def main() -> int:
    args = sys.argv[1:]
    if args == ["--version"]:
        print("0.8.1", file=sys.stderr)
        return 0

    prompt = sys.stdin.read()
    requested_provider = _value(args, "--provider")
    requested_model = _value(args, "--model")
    provider = os.environ.get(
        "TA_TEST_PRIME_AGENT_REPORTED_PROVIDER", requested_provider
    )
    model = os.environ.get("TA_TEST_PRIME_AGENT_REPORTED_MODEL", requested_model)
    _capture(
        {
            "argv": args,
            "prompt": prompt,
            "cwd": os.getcwd(),
            "skip_version_check": os.environ.get("PI_SKIP_VERSION_CHECK"),
            "telemetry": os.environ.get("PRIME_AGENT_TELEMETRY"),
        }
    )
    print(
        json.dumps(
            {
                "type": "session",
                "version": 3,
                "id": "ta-prime-agent-test",
                "timestamp": "2026-08-31T00:00:00Z",
                "cwd": os.getcwd(),
            }
        )
    )
    print(json.dumps({"type": "agent_start"}))
    print(json.dumps({"type": "turn_start"}))
    if os.environ.get("TA_TEST_PRIME_AGENT_TOOL"):
        print(
            json.dumps(
                {
                    "type": "tool_execution_start",
                    "toolCallId": "tool-1",
                    "toolName": "ipython",
                    "args": {},
                }
            )
        )
    response = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "transcripts"
        / "simple-structured.txt"
    ).read_text(encoding="utf-8")
    message = {
        "role": "assistant",
        "content": [{"type": "text", "text": response}],
        "api": "openai-codex-responses",
        "provider": provider,
        "model": model,
        "stopReason": os.environ.get("TA_TEST_PRIME_AGENT_STOP_REASON", "stop"),
        "timestamp": 0,
    }
    if os.environ.get("TA_TEST_PRIME_AGENT_ERROR"):
        message["errorMessage"] = "Request timed out"
    print(json.dumps({"type": "message_end", "message": message}))
    print(json.dumps({"type": "turn_end", "message": message, "toolResults": []}))
    print(json.dumps({"type": "agent_end", "messages": [message]}))
    return int(os.environ.get("TA_TEST_PRIME_AGENT_EXIT", "0"))


if __name__ == "__main__":
    raise SystemExit(main())
