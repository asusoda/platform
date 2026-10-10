"""Test setup shared by every test.

The app reads its database location, signing keys and .env from the working directory at
import time, so the tests run from a fresh temporary directory with their own SQLite file.
"""

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_HOME = Path(tempfile.mkdtemp(prefix="platform-tests-"))
atexit.register(shutil.rmtree, TEST_HOME, ignore_errors=True)

sys.path.insert(0, str(REPO_ROOT))
os.chdir(TEST_HOME)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_HOME / 'data' / 'user.db'}"
os.environ.setdefault("IS_PROD", "false")
