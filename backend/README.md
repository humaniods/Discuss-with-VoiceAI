# Discuss with VoiceAI — backend

A voice-first **Topic Companion**: name any topic, discuss it. It answers
your questions, simplifies or goes deeper on request, and plays devil's
advocate with short counter-questions to sharpen your thinking. No grading,
no score, no "understanding verdict" — open discussion, not a test.

Four jobs, on purpose kept minimal:

1. **Mint short-lived AssemblyAI tokens** for the browser (`GET /api/token`)
   — the raw `ASSEMBLYAI_API_KEY` never reaches the client. The browser then
   connects **directly** to `wss://agents.assemblyai.com/v1/ws` — this
   backend is not in that path at all.
2. **Live web search** (`POST /api/tools/web-search`) through Exa when the
   voice agent requests current information. The browser executes this as a
   client-side tool and sends the result back over its AssemblyAI WebSocket.
3. **Offline text-chat fallback** (`POST /api/mock_chat`), same persona,
   for demoing/building the discuss-and-debate behavior before you have an
   AssemblyAI key.
4. **Live text sentiment** (`POST /api/sentiment`) for finalized user turns.
   It calls AssemblyAI LLM Gateway from the server and returns one of
   `POSITIVE`, `NEUTRAL`, or `NEGATIVE`; it never blocks the voice reply.

There are no AssemblyAI-hosted HTTP callbacks into this backend. Instead,
the agent emits client-side tool calls over the existing WebSocket: the
browser reads its own clock for `get_current_datetime`, or calls this local
backend for Exa-powered `web_search`, then sends `tool.result` back. No
tunnel/public URL is needed in development.

## Endpoints

| Method | Path | Called by | Purpose |
|---|---|---|---|
| GET | `/health` | you | liveness + `mock_mode` flag |
| GET | `/api/token` | browser | mint a short-lived AssemblyAI browser token |
| POST | `/api/mock_chat` | browser (mock mode only) | text-chat fallback, same persona |
| POST | `/api/sentiment` | browser | classify one finalized transcript turn; fail open to a local fallback |
| POST | `/api/tools/web-search` | browser | retrieve current, dated Exa results for the voice agent |

## Quickstart (mock mode — no AssemblyAI account needed)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # MOCK_MODE=true by default
uvicorn main:app --reload --port 8010
```

Open `../app.html` (or `../Voice-Topic-Companion.html` → "Start
Chamber"), point "Backend URL" at `http://localhost:8010`, press **Start
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
   AGENT_VOICE_FOCUS=far-field
   AGENT_VOICE_FOCUS_THRESHOLD=0.8
   ```
   `far-field` is tuned for laptop and room microphones; use `near-field` for
   a headset. The threshold accepts `0.0`-`1.0`, with higher values applying
   more aggressive suppression.
2. Publish the agent (creates it the first run, updates it after):
   ```bash
   python publish_agent.py
   ```
   This writes `AGENT_ID` back into `.env` automatically.
3. Restart uvicorn, reload `app.html` — `GET /api/token` now mints a real
   token and the browser connects to the real Voice Agent over WebSocket,
   with a real mic, AssemblyAI Voice Focus noise cancellation, and real
   playback. The browser keeps acoustic echo cancellation on but its own
   noise suppression off, avoiding two denoisers processing the same speech.

## Files

| File | What |
|---|---|
| `main.py` | FastAPI app / routes |
| `config.py` | env-driven settings |
| `prompts.py` | the one system prompt driving both the real agent and the mock-chat fallback |
| `agent_config.py` | builds the stored agent, including mandatory clock and live-search client tools |
| `publish_agent.py` | CLI to create/update the agent on AssemblyAI |
| `llm_gateway.py` | thin client for `POST https://llm-gateway.assemblyai.com/v1/chat/completions` |
| `discuss.py` | mock-mode text-chat logic (LLM Gateway call + heuristic fallback) |
| `sentiment.py` | live text-sentiment classifier (AssemblyAI LLM Gateway + deterministic fallback) |
| `web_search.py` | Exa live-search adapter returning short, dated source snippets |
| `test_agent_config.py` | client-tool and mandatory dynamic-fact prompt tests |
| `test_sentiment.py` | sentiment classifier unit tests |
| `test_web_search.py` | live-search adapter contract/error tests with mocked HTTP |
| `legacy_teachback/` | the previous "teach it back and get graded" version's tools/schemas/store — kept for reference, not imported by anything |

## Sentiment analysis architecture

The linked [Speech Understanding Sentiment Analysis](https://www.assemblyai.com/docs/speech-understanding/sentiment-analysis)
feature is enabled on an asynchronous pre-recorded transcript by sending
`sentiment_analysis: true` to `POST /v2/transcript`. The [Voice Agent event contract](https://www.assemblyai.com/docs/voice-agents/voice-agent-api/events-reference)
has no equivalent config or sentiment event. Retranscribing every mic turn
would add seconds of latency, duplicate STT cost, and only support the
dedicated model's listed English variants.

For the live app, `transcript.user` final text is sent asynchronously to this
backend, which uses AssemblyAI LLM Gateway to classify English or Hinglish
wording. The result decorates the existing transcript item by `item_id`, so
it neither delays nor changes the companion's spoken answer. This is text
sentiment—not tone, pitch, hesitation, or multi-class emotion detection. See
AssemblyAI's [LLM Gateway sentiment guide](https://www.assemblyai.com/docs/guides/call-sentiment-analysis).

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
