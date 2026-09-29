"""
Vercel entrypoint: exposes backend/main.py's FastAPI app as a Python
serverless function. vercel.json rewrites /api/* and /health here; the
static pages (Voice-Topic-Companion.html, app.html) are served by Vercel
directly from the repo root, so frontend and backend share one origin.

backend/ modules import each other as top-level modules (`import config`),
so backend/ goes on sys.path before importing main.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from main import app  # noqa: E402,F401
