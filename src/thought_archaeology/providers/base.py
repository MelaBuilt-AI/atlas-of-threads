from __future__ import annotations

from typing import Protocol


class ProviderError(Exception):
    """Provider could not complete."""


class Provider(Protocol):
    name: str

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Return the model text. Must not contact the network unless the
        concrete provider documents that it does (ShellProvider)."""
        ...
