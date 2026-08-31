#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    if args == ["--version"]:
        print("codex-cli 0.0-test")
        return 0
    if args == ["debug", "models", "--bundled"]:
        print(json.dumps({
            "models": [
                {"slug": "codex-fallback", "priority": 2, "visibility": "list"},
                {"slug": "codex-test", "priority": 1, "visibility": "list"},
            ]
        }))
        return 0
    if not args or args[0] != "exec" or "--output-last-message" not in args:
        print("unsupported fake Codex invocation", file=sys.stderr)
        return 2
    prompt = sys.stdin.read()
    output_path = Path(args[args.index("--output-last-message") + 1])
    capture = os.environ.get("TA_TEST_CODEX_CALL")
    if capture:
        Path(capture).write_text(
            json.dumps({"argv": args, "prompt": prompt}, indent=2) + "\n",
            encoding="utf-8",
        )
    response = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "transcripts"
        / "simple-structured.txt"
    ).read_text(encoding="utf-8")
    output_path.write_text(response, encoding="utf-8")
    print('{"type":"turn.completed"}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
