"""
Vercel entrypoint: exposes backend/main.py's FastAPI app as a Python
serverless function. Vercel treats a FastAPI project as a backend framework
and routes every request to this app, so the app also serves the two static
pages (landing + live app) -- frontend and backend share one origin.

backend/ modules import each other as top-level modules (`import config`),
so backend/ goes on sys.path before importing main.
"""
import os
import sys

from fastapi.responses import FileResponse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from main import app  # noqa: E402


@app.get("/", include_in_schema=False)
@app.get("/Voice-Topic-Companion.html", include_in_schema=False)
async def landing_page():
    return FileResponse(os.path.join(ROOT, "Voice-Topic-Companion.html"))


@app.get("/app.html", include_in_schema=False)
async def live_app_page():
    return FileResponse(os.path.join(ROOT, "app.html"))
