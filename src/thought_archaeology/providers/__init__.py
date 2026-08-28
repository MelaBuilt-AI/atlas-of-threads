from __future__ import annotations

import shlex
from pathlib import Path

from thought_archaeology.providers.base import Provider, ProviderError
from thought_archaeology.providers.file import FileProvider
from thought_archaeology.providers.none import NoneProvider
from thought_archaeology.providers.shell import ShellProvider
from thought_archaeology.providers.stdin import StdinProvider


def build_provider(
    name: str,
    *,
    provider_file: str | Path | None = None,
    provider_cmd: str | None = None,
) -> Provider:
    if name == "none":
        return NoneProvider()
    if name == "file":
        if not provider_file:
            raise ProviderError("--provider-file is required for provider 'file'")
        return FileProvider(provider_file)
    if name == "stdin":
        return StdinProvider()
    if name == "shell":
        argv = shlex.split(provider_cmd or "")
        return ShellProvider(argv)
    raise ProviderError(f"unknown provider {name!r}")


__all__ = [
    "Provider",
    "ProviderError",
    "NoneProvider",
    "FileProvider",
    "StdinProvider",
    "ShellProvider",
    "build_provider",
]
