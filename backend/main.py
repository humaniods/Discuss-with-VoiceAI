"""
Discuss with VoiceAI backend.

Minimal by design: the voice agent uses browser-executed client tools (see
agent_config.py), while the backend's jobs are:
  1. Mint short-lived AssemblyAI browser tokens (GET /api/token) so the raw
     API key never reaches the client. The browser then connects DIRECTLY to
     wss://agents.assemblyai.com/v1/ws -- this backend is not in that path.
  2. Serve a text-chat fallback (POST /api/mock_chat) with the same persona,
     so the app is fully demoable before an AssemblyAI key is wired in.
  3. Classify each finalized user transcript through AssemblyAI LLM Gateway
     (POST /api/sentiment) for non-blocking live text-sentiment badges.
  4. Run Exa live searches requested by the browser's web_search client tool
     (POST /api/tools/web-search), keeping both provider keys off the client.

Run:
    uvicorn main:app --reload --port 8010
"""
from typing import Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

import config
import discuss
import sentiment
import tts
import web_search

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


class SentimentIn(BaseModel):
    item_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=4000)
    speaker: Literal["user", "agent"] = "user"

    @field_validator("item_id", "text")
    @classmethod
    def reject_blank_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class SentimentOut(BaseModel):
    item_id: str
    sentiment: sentiment.SentimentLabel
    reason: str
    source: Literal["assemblyai_llm_gateway", "local_fallback"]


@app.post("/api/sentiment", response_model=SentimentOut)
async def analyze_sentiment(body: SentimentIn):
    result = await sentiment.analyze(body.text)
    return SentimentOut(item_id=body.item_id, **result.model_dump())


class WebSearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=240)
    language: Literal["auto", "en", "hi"] = "auto"

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("query must contain at least two characters")
        return value


class WebSearchOut(BaseModel):
    query: str
    scope: Literal["live_web_search"] = "live_web_search"
    results: list[web_search.WebSearchResult]


@app.post("/api/tools/web-search", response_model=WebSearchOut)
async def search_reference_web(body: WebSearchIn):
    """Client-side Voice Agent tool backed by Exa's live web search."""

    if not config.EXA_API_KEY:
        raise HTTPException(500, "EXA_API_KEY is not configured -- get a free key at https://exa.ai")
    try:
        results = await web_search.search_web(body.query, body.language)
    except web_search.WebSearchError as exc:
        raise HTTPException(502, str(exc)) from exc
    return WebSearchOut(query=body.query, results=results)


class TtsIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


@app.post("/api/tts")
async def synthesize_speech(body: TtsIn):
    """Hindi/Indian-accent voice synthesis via gTTS, replacing AssemblyAI's
    own reply.audio (see docs/superpowers/specs/2026-09-20-elevenlabs-tts-design.md
    for the original design; switched off ElevenLabs after its free tier got
    disabled -- see tts.py's module docstring)."""

    try:
        audio_bytes = await tts.synthesize(body.text)
    except tts.TtsError as exc:
        raise HTTPException(502, str(exc)) from exc
    return Response(content=audio_bytes, media_type="audio/mpeg")
