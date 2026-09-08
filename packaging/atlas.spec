# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path


root = Path(SPECPATH).parent
binary_name = "AtlasOfThreads" if sys.platform == "win32" else "atlas-of-threads"

a = Analysis(
    [str(root / "src" / "thought_archaeology" / "launcher.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[
        (str(root / "src" / "thought_archaeology" / "adapters" / "host_probe.py"), "agent-host"),
        (str(root / "src" / "thought_archaeology" / "adapters" / "remote_host.py"), "agent-host"),
        (str(root / "viz" / "dist"), "viz/dist"),
        (str(root / "src" / "thought_archaeology" / "prompts"), "thought_archaeology/prompts"),
        (str(root / "src" / "thought_archaeology" / "schemas"), "thought_archaeology/schemas"),
    ],
    hiddenimports=[
        "thought_archaeology.adapters.claude",
        "thought_archaeology.adapters.codex",
        "thought_archaeology.adapters.grok",
        "thought_archaeology.adapters.opencode",
        "thought_archaeology.adapters.prime_agent",
        "thought_archaeology.adapters.ssh",
        "thought_archaeology.adapters.local",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=binary_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=sys.platform != "win32",
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=str(root / "packaging" / "windows" / "atlas-of-threads.ico")
    if sys.platform == "win32"
    else None,
    codesign_identity=None,
    entitlements_file=None,
)

# Keep the desktop launcher windowed; MCP clients need real stdin/stdout pipes.
if sys.platform == "win32":
    # The console bridge serves MCP and adapter protocols, without the desktop UI.
    mcp_datas = [item for item in a.datas if not item[0].replace("\\", "/").startswith("viz/dist/")]
    mcp_exe = EXE(
        pyz, a.scripts, a.binaries, mcp_datas, [],
        name="AtlasOfThreadsMCP", console=True,
        debug=False, strip=False, upx=True,
        icon=str(root / "packaging" / "windows" / "atlas-of-threads.ico"),
    )
