"""The worker and the MCP server load only jobs or tools. Their models must still map."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("loader", ["load_jobs", "load_tools"])
def test_loader_maps_every_model_in_a_new_process(loader):
    code = (
        f"from modules.manifest import {loader}; {loader}()\n"
        "from sqlalchemy.orm import configure_mappers\n"
        "configure_mappers()\n"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]
