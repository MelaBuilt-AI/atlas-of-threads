"""Run the browser's route model against observable navigation contracts."""
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("script", ["walk.test.cjs", "terrain.test.cjs"])
def test_experienced_route(script):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the browser route tests")
    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_name(script))],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
