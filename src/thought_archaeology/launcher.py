from __future__ import annotations

import os
import sys
from pathlib import Path
from collections.abc import Callable

from thought_archaeology import cli
from thought_archaeology.store import fallback_store_path


def _adapter(name: str) -> Callable[[list[str] | None], int]:
    if name == "claude":
        from thought_archaeology.adapters.claude import main
    elif name == "codex":
        from thought_archaeology.adapters.codex import main
    elif name == "grok":
        from thought_archaeology.adapters.grok import main
    elif name == "opencode":
        from thought_archaeology.adapters.opencode import main
    elif name == "prime-agent":
        from thought_archaeology.adapters.prime_agent import main
    elif name == "ssh":
        from thought_archaeology.adapters.ssh import main
    else:
        raise ValueError(f"unknown packaged collaborator {name!r}")
    return main


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["adapter"]:
        if len(args) < 3:
            print(
                "usage: atlas-of-threads adapter "
                "claude|codex|grok|opencode|prime-agent|ssh [options] describe|continue|discuss",
                file=sys.stderr,
            )
            return 2
        try:
            adapter = _adapter(args[1])
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
        try:
            return adapter(args[2:])
        except Exception as exc:
            if sys.stderr is not None:
                print(
                    f"{args[1]} adapter failed unexpectedly "
                    f"({type(exc).__name__})",
                    file=sys.stderr,
                )
            return 1
    console_bridge = Path(sys.executable).name.lower() == "atlasofthreadsmcp.exe"
    app_args = args or (["--help"] if console_bridge else ["launch"])
    if (
        getattr(sys, "frozen", False)
        and "launch" in app_args
        and "--store" not in app_args
        and "TA_STORE" not in os.environ
    ):
        os.environ["TA_STORE"] = str(fallback_store_path())
    return cli.main(app_args)


if __name__ == "__main__":
    raise SystemExit(main())
