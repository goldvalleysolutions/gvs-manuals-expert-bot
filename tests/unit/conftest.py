"""Unit tests import this repo's bot/ code on top of core from source.

Core comes from GVS_CORE_DIR (a gvs-core-bot checkout at the e2e CORE_SHA) or the
checkout the e2e suite clones into .e2e/core. No network, no LLM keys.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = Path(os.environ.get("GVS_CORE_DIR") or REPO / ".e2e" / "core").resolve()
if not (CORE / "core" / "app.py").is_file():
    pytest.exit(f"no core checkout at {CORE} (set GVS_CORE_DIR)", returncode=2)
sys.path.insert(0, str(CORE))
