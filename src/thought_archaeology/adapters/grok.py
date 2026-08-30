from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from thought_archaeology.harness import HARNESS_PROTOCOL_VERSION
from thought_archaeology.schema import read_prompt

DEFAULT_MODEL_TIMEOUT = 840.0


class GrokAdapterError(Exception):
    """Installed Grok CLI discovery or invocation failure."""


def _grok_bin() -> str:
    configured = os.environ.get("TA_GROK_BIN")
    executable = shutil.which(configured) if configured else None
    if executable is None and configured is None:
        grok_home = Path(os.environ.get("GROK_HOME") or Path.home() / ".grok")
        canonical = grok_home / "bin" / "grok"
        if canonical.is_file() and os.access(canonical, os.X_OK):
            executable = str(canonical)
    if executable is None and configured is None:
        executable = shutil.which("grok")
    if executable is None:
        raise GrokAdapterError(
            "Grok CLI not found; install it or set TA_GROK_BIN to its executable"
        )
    return str(Path(executable).resolve())


def _run_metadata(argv: list[str], *, timeout: float = 30) -> tuple[str, str]:
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            shell=False,
            timeout=timeout,
            check=False,
            env={**os.environ, "NO_COLOR": "1"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GrokAdapterError(f"cannot inspect Grok CLI: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or "no output"
        raise GrokAdapterError(
            f"Grok CLI metadata command exited {proc.returncode}: {detail}"
        )
    return proc.stdout.strip(), proc.stderr.strip()


def _version(executable: str) -> str:
    stdout, _stderr = _run_metadata([executable, "--version"])
    if not stdout:
        raise GrokAdapterError("Grok CLI returned no version")
    return stdout.splitlines()[-1].strip()


def _default_model(executable: str) -> str:
    configured = os.environ.get("TA_GROK_MODEL")
    if configured:
        return configured.strip()
    stdout, _stderr = _run_metadata([executable, "models"])
    match = re.search(r"^Default model:\s*(\S+)\s*$", stdout, re.MULTILINE)
    if not match:
        raise GrokAdapterError(
            "Grok CLI did not report a default model; set TA_GROK_MODEL explicitly"
        )
    return match.group(1)


def _validate_envelope(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise GrokAdapterError("continue expects one JSON object on stdin")
    if raw.get("protocol_version") != HARNESS_PROTOCOL_VERSION:
        raise GrokAdapterError("unsupported Thought Archaeology harness protocol")
    if raw.get("operation") != "continue":
        raise GrokAdapterError("adapter input operation must be 'continue'")
    request = raw.get("request")
    graph = raw.get("graph")
    standing = raw.get("standing")
    if not isinstance(request, dict) or not isinstance(graph, dict) or not isinstance(
        standing, dict
    ):
        raise GrokAdapterError("adapter input is missing request, graph, or standing")
    if "hidden_reasoning" in graph:
        raise GrokAdapterError("adapter input must not contain hidden_reasoning")
    return raw


def _prompt(envelope: dict[str, Any]) -> str:
    request = envelope["request"]
    optional_prompt = str(request.get("prompt") or "").strip()
    task = (
        "Answer the inhabitant's exact continuation prompt from this chamber."
        if optional_prompt
        else "Continue the thought from this terminal chamber with the next useful idea."
    )
    public_context = {
        "request": request,
        "session": envelope.get("session"),
        "graph": envelope["graph"],
        "standing": envelope["standing"],
    }
    return (
        "You are the Grok adapter for Thought Archaeology.\n"
        f"{task}\n"
        "Treat the supplied graph as the authored story of the prior answer, not hidden "
        "chain-of-thought or a neural trace. Do not inspect or modify local files, call "
        "tools, browse, or delegate. Use only the supplied public context.\n\n"
        f"{read_prompt('structured')}\n\n"
        "PUBLIC THOUGHT ARCHAEOLOGY CONTEXT (JSON):\n"
        + json.dumps(public_context, ensure_ascii=False, indent=2)
    )


def _model_timeout() -> float:
    raw = os.environ.get("TA_GROK_TIMEOUT")
    if raw is None:
        return DEFAULT_MODEL_TIMEOUT
    try:
        timeout = float(raw)
    except ValueError as exc:
        raise GrokAdapterError("TA_GROK_TIMEOUT must be a number") from exc
    if timeout <= 0:
        raise GrokAdapterError("TA_GROK_TIMEOUT must be greater than zero")
    return timeout


def _continue(executable: str, envelope: dict[str, Any], model: str) -> str:
    prompt = _prompt(envelope)
    with tempfile.TemporaryDirectory(prefix="ta-grok-") as temp_dir:
        prompt_path = Path(temp_dir) / "prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        os.chmod(prompt_path, 0o600)
        argv = [
            executable,
            "--verbatim",
            "--no-plan",
            "--no-subagents",
            "--disable-web-search",
            "--max-turns",
            "10",
            "--tools",
            "",
            "--output-format",
            "plain",
            "--model",
            model,
            "--prompt-file",
            str(prompt_path),
        ]
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                shell=False,
                timeout=_model_timeout(),
                check=False,
                env={**os.environ, "NO_COLOR": "1"},
            )
        except subprocess.TimeoutExpired as exc:
            raise GrokAdapterError(
                f"Grok model call timed out after {_model_timeout():g}s"
            ) from exc
        except OSError as exc:
            raise GrokAdapterError(f"cannot run Grok model call: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or "no output"
        raise GrokAdapterError(
            f"Grok model call exited {proc.returncode}: {detail}"
        )
    response = proc.stdout.strip()
    if not response:
        detail = proc.stderr.strip()
        raise GrokAdapterError(
            "Grok model call returned no response"
            + (f": {detail}" if detail else "")
        )
    return response


def _emit(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) != 1 or args[0] not in {"describe", "continue"}:
            raise GrokAdapterError("usage: ta-harness-grok describe|continue")
        executable = _grok_bin()
        version = _version(executable)
        model = _default_model(executable)
        if args[0] == "describe":
            _emit(
                {
                    "protocol_version": HARNESS_PROTOCOL_VERSION,
                    "name": "grok",
                    "capabilities": ["continue"],
                    "cli_version": version,
                    "default_model": model,
                }
            )
            return 0
        envelope = _validate_envelope(json.load(sys.stdin))
        response = _continue(executable, envelope, model)
        _emit(
            {
                "protocol_version": HARNESS_PROTOCOL_VERSION,
                "response": response,
                "model_name": model,
            }
        )
        return 0
    except (GrokAdapterError, json.JSONDecodeError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
