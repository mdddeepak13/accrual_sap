"""Vercel Functions entrypoint.

Vercel's Python runtime auto-detects an ASGI `app` variable in this file
and serves the FastAPI app directly — no uvicorn needed.

The package lives in ``src/accrual_pipeline/`` (src-layout) so we add it to
sys.path before importing. requirements.txt installs the third-party deps
but not the package itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from accrual_pipeline.main import app  # noqa: E402

__all__ = ["app"]
