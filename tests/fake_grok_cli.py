#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    if args == ["--version"]:
        print("grok 0.0-test (fake) [test]")
        return 0
    if args == ["models"]:
        print("Default model: grok-test")
        print("Available models:\n  * grok-test (default)")
        return 0
    if "--prompt-file" not in args:
        print("missing --prompt-file", file=sys.stderr)
        return 2
    prompt_path = Path(args[args.index("--prompt-file") + 1])
    prompt = prompt_path.read_text(encoding="utf-8")
    capture = os.environ.get("TA_TEST_GROK_CALL")
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
    print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
