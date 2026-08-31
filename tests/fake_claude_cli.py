#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    if args == ["--version"]:
        print("2.1.251 (Claude Code test)")
        return 0
    if "--print" not in args or "--output-format" not in args:
        print("unsupported fake Claude invocation", file=sys.stderr)
        return 2
    prompt = sys.stdin.read()
    capture = os.environ.get("TA_TEST_CLAUDE_CALL")
    if capture:
        Path(capture).write_text(
            json.dumps(
                {
                    "argv": args,
                    "prompt": prompt,
                    "cwd": os.getcwd(),
                    "skip_prompt_history": os.environ.get(
                        "CLAUDE_CODE_SKIP_PROMPT_HISTORY"
                    ),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    if os.environ.get("TA_TEST_CLAUDE_ERROR"):
        print(
            json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": True,
                    "result": "Request timed out",
                    "modelUsage": {},
                }
            )
        )
        return 0
    response = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "transcripts"
        / "simple-structured.txt"
    ).read_text(encoding="utf-8")
    print(
        json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": response,
                "modelUsage": {
                    "claude-test-alias": {"canonicalModel": "claude-test-exact"}
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
