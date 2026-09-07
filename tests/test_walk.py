"""Run the browser's route model against observable navigation contracts."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_experienced_route():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the browser route tests")
    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_name("walk.test.cjs"))],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
