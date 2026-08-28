from __future__ import annotations

import subprocess

from thought_archaeology.providers.base import ProviderError


class ShellProvider:
    name = "shell"

    def __init__(self, argv: list[str]):
        if not argv:
            raise ProviderError("--provider-cmd is required for provider 'shell'")
        self.argv = list(argv)

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        payload = (system + "\n\n" + prompt) if system else prompt
        try:
            proc = subprocess.run(
                self.argv,
                input=payload,
                capture_output=True,
                text=True,
                shell=False,
                check=False,
            )
        except OSError as exc:
            raise ProviderError(f"shell provider failed: {exc}") from exc
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise ProviderError(
                f"shell provider exited {proc.returncode}: {err or 'no output'}"
            )
        return proc.stdout
