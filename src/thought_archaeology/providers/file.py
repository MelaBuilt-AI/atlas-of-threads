from __future__ import annotations

from pathlib import Path

from thought_archaeology.providers.base import ProviderError


class FileProvider:
    name = "file"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        try:
            return self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProviderError(f"cannot read provider file {self.path}: {exc}") from exc
