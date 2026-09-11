"""
Discuss with VoiceAI backend.

Minimal by design: this agent has no server-side tools (see agent_config.py),
so the backend's only jobs are:
  1. Mint short-lived AssemblyAI browser tokens (GET /api/token) so the raw
     API key never reaches the client. The browser then connects DIRECTLY to
     wss://agents.assemblyai.com/v1/ws -- this backend is not in that path.
  2. Serve a text-chat fallback (POST /api/mock_chat) with the same persona,
     so the app is fully demoable before an AssemblyAI key is wired in.

Run:
    uvicorn main:app --reload --port 8000
"""
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
import discuss

app = FastAPI(title="Discuss with VoiceAI backend")


class TokenOut(BaseModel):
    token: str
    agent_id: Optional[str] = None
    mock: bool = False
    expires_in_seconds: int = 300

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN] if config.FRONTEND_ORIGIN != "*" else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "mock_mode": config.MOCK_MODE, "agent_id": config.AGENT_ID or None}


@app.get("/api/token", response_model=TokenOut)
async def get_token():
    if config.MOCK_MODE:
        return TokenOut(token="mock-token", agent_id=config.AGENT_ID or "mock-agent", mock=True)

    if not config.AGENT_ID:
        raise HTTPException(500, "AGENT_ID is not set -- run `python publish_agent.py` first")

    url = f"{config.AGENTS_HOST}/v1/token"
    headers = {"Authorization": f"Bearer {config.ASSEMBLYAI_API_KEY}"}
    params = {"expires_in_seconds": 300, "max_session_duration_seconds": 3600}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers, params=params)
    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, f"AssemblyAI token mint failed: {resp.text}")

    token = resp.json()["token"]
    return TokenOut(token=token, agent_id=config.AGENT_ID, mock=False)


class ChatTurn(BaseModel):
    role: str  # "user" | "assistant"
    text: str


class MockChatIn(BaseModel):
    history: list[ChatTurn] = []
    message: str


@app.post("/api/mock_chat")
async def mock_chat(body: MockChatIn):
    reply_text = await discuss.reply([t.model_dump() for t in body.history], body.message)
    return {"reply": reply_text}
