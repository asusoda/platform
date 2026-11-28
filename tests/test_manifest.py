"""The worker and the MCP server load only jobs or tools. Their models must still map."""

import os
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


# Each process starts its own way. Each one must load every job and the events.deliver handler, because on the
# inline queue a job runs in the process that queued it.
STARTS = {
    "bot": "import bot_main\nbot_main.main()\n",
    "mcp": "import mcp_main, uvicorn\nuvicorn.run = lambda *args, **kwargs: None\nmcp_main.main()\n",
    "api": "import main\n",
}


@pytest.mark.parametrize("process", sorted(STARTS))
def test_each_process_registers_every_job_and_the_event_handler(process, tmp_path):
    code = STARTS[process] + (
        "from core import jobs, webhooks\n"
        "from modules import manifest\n"
        "from modules.alerts import delivery\n"
        "assert 'events.deliver' in jobs.JOBS, sorted(jobs.JOBS)\n"
        "assert delivery.send_event in webhooks._handlers, webhooks._handlers\n"
        "print('registered', len(jobs.JOBS))\n"
    )
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'start.db'}",
        "JOBS_BACKEND": "inline",
        "JOBS_SCHEDULER": "false",
        "BOT_TOKEN": "",
        "RUN_BOT_IN_API": "false",
        "PYTHONPATH": str(ROOT),
    }
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=180
    )
    assert result.returncode == 0, result.stderr[-3000:]
    assert "registered" in result.stdout
