# Discuss with VoiceAI

A voice-first **Topic Companion**: name any topic, Discuss with VoiceAI discusses
it with you — answers questions, simplifies or goes deeper on request, and
plays devil's advocate with short counter-questions to sharpen your
thinking. No grading, no score. Built for the AssemblyAI Voice Agent
Hackathon.

> Original plan doc: [ExamPilot_Voice_Hackathon_MVP.md](ExamPilot_Voice_Hackathon_MVP.md)
> — note the actual build below **intentionally diverges** from it: the plan
> describes a teach-back/grading "Understanding Map" product; the app was
> repivoted mid-build to an open discuss-and-debate companion (no verdict).
> The retired teach-back code has been removed (still in git history if
> ever needed).

## Structure

```
Voice-Topic-Companion.html   Landing / hero page (animated visual mockup of
                              the product -- topic-orbit visualization,
                              You/Companion cards, sample transcript. "Start
                              Discussion" links to the real app below)
app.html                      The real working app: Start -> live voice
                              discussion, styled to match the landing page's
                              orbit visualization (real topic, real state,
                              real transcript, real audio-reactive waveform)
backend/                      FastAPI backend (see backend/README.md)
```

`app.html`'s Screen 2 (live discussion) recreates the landing page's visual
language in plain HTML/CSS/JS, wired to real data: the topic circle shows the
actual topic named, the COMPANION/YOU cards show real state
(listening/explaining/challenging, driven by the live transcript) with a
waveform that reacts to real mic/playback audio via Web Audio
`AnalyserNode`s, and a counter-question gets the same amber callout style as
the mockup. Finalized user turns also receive asynchronous text-sentiment
badges (`Positive`, `Neutral`, or `Negative`) without delaying the voice
reply. It's a from-scratch recreation, not an extraction from the
landing page's bundle (that file is a minified React artifact with no
readable source) -- so it matches the intent and color language, not
necessarily every pixel.

## Run it

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8010
```

```bash
# from the repo root, in another terminal
python3 -m http.server 8020
```

Open `http://localhost:8020/Voice-Topic-Companion.html`, click **Start
Discussion**, confirm the Backend URL field (under "Advanced") says
`http://localhost:8010`, press **Start Discussion** again on that screen.

- `.env` ships with `MOCK_MODE=true` — a text-chat box appears instead of the
  mic, running the same discuss/debate persona. Verified working end-to-end.
- To go live with real AssemblyAI voice, see "Going live" in
  `backend/README.md`.

## Status

| Item | Status |
|---|---|
| Any topic, open discussion (no fixed packs) | ✅ |
| Answer / simplify / go-deeper / counter-question / debate the other side | ✅ — all in `backend/prompts.py`'s system prompt |
| No grading / no verdict screen | ✅ — removed by design |
| Temp browser token (key never sent to client) | ✅ |
| Text-chat fallback for offline dev/demo | ✅ verified end-to-end (heuristic + real LLM Gateway path) |
| Real voice via AssemblyAI Voice Agent API (token, agent, WS events) | ✅ verified live -- token mint, WebSocket connect, `session.ready`, mic capture all confirmed working with a real account |
| Noise cancellation | ✅ AssemblyAI Voice Focus on the stored agent (far-field laptop profile by default); browser echo cancellation stays on while duplicate browser denoising stays off |
| Live sentiment analysis | ✅ finalized user turns classified as POSITIVE / NEUTRAL / NEGATIVE through AssemblyAI LLM Gateway; per-turn badge + latest-session indicator |
| STT language steering + Hinglish-for-Hindi TTS workaround | ✅ (`AGENT_LANGUAGE_CODES` in `.env`, see `backend/prompts.py`) |
| Landing page ↔ app visual consistency | ✅ `app.html`'s live screen recreates the landing page's orbit/state-card/waveform design, wired to real data |
| Semantic turn detection / barge-in | Delegated to AssemblyAI's Voice Agent defaults (not tuned) |
| Deployment | Not deployed; Render/Railway + Vercel, backend is deploy-ready |

The live sentiment label is based on transcript wording, not acoustic voice
emotion. AssemblyAI's dedicated [Speech Understanding Sentiment Analysis](https://www.assemblyai.com/docs/speech-understanding/sentiment-analysis)
feature requires a pre-recorded `/v2/transcript` job; the live Voice Agent
WebSocket does not emit that result, so this app uses AssemblyAI's documented
[LLM Gateway sentiment pattern](https://www.assemblyai.com/docs/guides/call-sentiment-analysis)
on each finalized turn instead.
