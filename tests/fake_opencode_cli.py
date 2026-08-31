#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


SESSION_ID = "ses_ta_opencode_test"


def _capture(update: dict[str, object]) -> None:
    path = os.environ.get("TA_TEST_OPENCODE_CALL")
    if not path:
        return
    target = Path(path)
    data = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
    data.update(update)
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _selection() -> tuple[str, str, str | None]:
    requested = os.environ.get("TA_TEST_OPENCODE_REPORTED_MODEL", "openai/opencode-test")
    provider, model = requested.split("/", 1)
    variant = os.environ.get("TA_TEST_OPENCODE_REPORTED_VARIANT", "high")
    return provider, model, variant or None


def main() -> int:
    args = sys.argv[1:]
    if args == ["--version"]:
        print("1.18.25")
        return 0
    if args == ["debug", "config", "--pure"]:
        config: dict[str, object] = {"plugin": []}
        model = os.environ.get("TA_TEST_OPENCODE_CONFIG_MODEL")
        if model:
            config["model"] = model
        print(json.dumps(config))
        return 0
    if len(args) >= 4 and args[:3] == ["db", "--format", "json"]:
        saved = os.environ.get("TA_TEST_OPENCODE_LATEST_MODEL")
        print(json.dumps([] if not saved else [{"model": saved}]))
        return 0
    if len(args) == 2 and args[0] == "export":
        provider, model, variant = _selection()
        print(
            json.dumps(
                {
                    "info": {
                        "id": args[1],
                        "model": {
                            "providerID": provider,
                            "id": model,
                            "variant": variant,
                        },
                    },
                    "messages": [
                        {
                            "info": {
                                "role": "assistant",
                                "providerID": provider,
                                "modelID": model,
                                "variant": variant,
                            },
                            "parts": [],
                        }
                    ],
                }
            )
        )
        return 0
    if len(args) == 3 and args[:2] == ["session", "delete"]:
        _capture({"deleted_session": args[2]})
        return 0
    if not args or args[0] != "run":
        print("unsupported fake OpenCode invocation", file=sys.stderr)
        return 2

    prompt = sys.stdin.read()
    _capture(
        {
            "argv": args,
            "prompt": prompt,
            "cwd": os.getcwd(),
            "permission": os.environ.get("OPENCODE_PERMISSION"),
            "config_content": os.environ.get("OPENCODE_CONFIG_CONTENT"),
            "disable_project_config": os.environ.get(
                "OPENCODE_DISABLE_PROJECT_CONFIG"
            ),
        }
    )
    if os.environ.get("TA_TEST_OPENCODE_ERROR"):
        print(
            json.dumps(
                {
                    "type": "error",
                    "sessionID": SESSION_ID,
                    "error": {
                        "name": "APIError",
                        "data": {"message": "Request timed out"},
                    },
                }
            )
        )
        return 1
    if os.environ.get("TA_TEST_OPENCODE_TIMEOUT"):
        print(json.dumps({"type": "step_start", "sessionID": SESSION_ID}), flush=True)
        time.sleep(10)
        return 0
    if os.environ.get("TA_TEST_OPENCODE_TOOL"):
        print(
            json.dumps(
                {
                    "type": "tool_use",
                    "sessionID": SESSION_ID,
                    "part": {"type": "tool", "tool": "read"},
                }
            )
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
                "type": "text",
                "sessionID": SESSION_ID,
                "part": {
                    "type": "text",
                    "text": response,
                    "time": {"end": 1},
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
