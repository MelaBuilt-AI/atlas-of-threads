from __future__ import annotations

import sys


class StdinProvider:
    name = "stdin"

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        if system:
            sys.stdout.write(system.rstrip() + "\n\n")
        sys.stdout.write(prompt)
        if prompt and not prompt.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()
        return sys.stdin.read()
