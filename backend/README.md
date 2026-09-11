# Discuss with VoiceAI — backend

A voice-first **Topic Companion**: name any topic, discuss it. It answers
your questions, simplifies or goes deeper on request, and plays devil's
advocate with short counter-questions to sharpen your thinking. No grading,
no score, no "understanding verdict" — open discussion, not a test.

Two jobs, on purpose kept minimal:

1. **Mint short-lived AssemblyAI tokens** for the browser (`GET /api/token`)
   — the raw `ASSEMBLYAI_API_KEY` never reaches the client. The browser then
   connects **directly** to `wss://agents.assemblyai.com/v1/ws` — this
   backend is not in that path at all.
2. **Offline text-chat fallback** (`POST /api/mock_chat`), same persona,
   for demoing/building the discuss-and-debate behavior before you have an
   AssemblyAI key.

There are **no server-side tools** in this agent (unlike an earlier version
of this project — see `legacy_teachback/`) — the whole behavior lives in one
system prompt (`prompts.py`) that the agent's own LLM follows directly. That
means no tunnel/public URL is needed even in dev: AssemblyAI never calls back
into this backend.

## Endpoints

| Method | Path | Called by | Purpose |
|---|---|---|---|
| GET | `/health` | you | liveness + `mock_mode` flag |
| GET | `/api/token` | browser | mint a short-lived AssemblyAI browser token |
| POST | `/api/mock_chat` | browser (mock mode only) | text-chat fallback, same persona |

## Quickstart (mock mode — no AssemblyAI account needed)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # MOCK_MODE=true by default
uvicorn main:app --reload --port 8000
```

Open `../app.html` (or `../Voice-Topic-Companion.html` → "Start
Chamber"), point "Backend URL" at `http://localhost:8000`, press **Start
Discussion**. In mock mode there's no real voice yet — a text box appears
instead so you can try the discuss/debate flow end-to-end.

The mock-mode reply quality depends on whether a key is set:
- No `ASSEMBLYAI_API_KEY` at all → a small deterministic heuristic reply
  (`discuss.py`'s `_heuristic_reply`) — proves the plumbing, not smart.
- `ASSEMBLYAI_API_KEY` set but `MOCK_MODE=true` → real LLM Gateway replies
  over plain text, same persona, no voice yet.

## Going live with real AssemblyAI voice

1. Put your key in `.env`:
   ```
   ASSEMBLYAI_API_KEY=sk_...
   MOCK_MODE=false
   ```
2. Publish the agent (creates it the first run, updates it after):
   ```bash
   python publish_agent.py
   ```
   This writes `AGENT_ID` back into `.env` automatically.
3. Restart uvicorn, reload `app.html` — `GET /api/token` now mints a real
   token and the browser connects to the real Voice Agent over WebSocket,
   with a real mic and real playback.

## Files

| File | What |
|---|---|
| `main.py` | FastAPI app / routes |
| `config.py` | env-driven settings |
| `prompts.py` | the one system prompt driving both the real agent and the mock-chat fallback |
| `agent_config.py` | builds the `POST /v1/agents` body (name, system_prompt, voice) |
| `publish_agent.py` | CLI to create/update the agent on AssemblyAI |
| `llm_gateway.py` | thin client for `POST https://llm-gateway.assemblyai.com/v1/chat/completions` |
| `discuss.py` | mock-mode text-chat logic (LLM Gateway call + heuristic fallback) |
| `legacy_teachback/` | the previous "teach it back and get graded" version's tools/schemas/store — kept for reference, not imported by anything |

## A note on accuracy of the AssemblyAI wiring

`GET /v1/token`, `POST /v1/agents`, and the WebSocket event names used in
`app.html` were pulled from AssemblyAI's live docs while building this. The
mock-mode path is verified working end-to-end in this session; the real-voice
path (steps 1-3 above) has **not** been exercised against a real AssemblyAI
account here — verify against your dashboard / the latest
`docs/voice-agents/voice-agent-api/events-reference` before a live demo.

## Deploy

Backend → Render/Railway. `app.html` + the landing page → Vercel or any
static host (no server-side rendering needed).
