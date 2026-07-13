"""Vercel serverless entrypoint for the NextBest FastAPI backend.

Vercel's Python runtime serves the module-level ``app`` ASGI application, so
every ``/api/*`` request (routed here by ``vercel.json``) is handled by the
same FastAPI app used locally.
"""

import os
import sys

# The function bundle runs with this file as the entrypoint; add the repo root
# to sys.path so the ``backend`` package resolves.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.main import app  # noqa: E402

__all__ = ["app"]
