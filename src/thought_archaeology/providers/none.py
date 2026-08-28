from __future__ import annotations

from thought_archaeology.providers.base import ProviderError


class NoneProvider:
    name = "none"

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        raise ProviderError(
            "provider 'none' cannot complete; use --from-graph or --input"
        )
