# ElevenLabs Hindi/Indian-Accent Voice Output — Design

## Problem

AssemblyAI's Voice Agent API's built-in TTS (`reply.audio` WebSocket events,
played by `app.html`'s `playAgentAudio`) currently supports only 6 output
languages: English, Italian, Spanish, German, Portuguese, French — **no
Hindi** — and only American/British English accents, no Indian-English
accent. Verified against AssemblyAI's own docs (`voice-agents/voice-agent-api`
voices reference) 2026-09-19.

Result: the agent's STT correctly transcribes Hindi speech (STT supports 32
languages including `hi`), and the LLM can compose a Hindi reply, but the
spoken audio the user hears is always English, in an American accent — never
Hindi, never Indian-accented.

This is a platform limitation, not a bug in this codebase. No config change
within AssemblyAI's Voice Agent API can produce Hindi or Indian-accented
audio today.

## Decision

Keep AssemblyAI for everything except the spoken audio: mic capture, STT,
turn detection, barge-in, and the LLM/agent brain via the managed Voice
Agent stay exactly as they are. Replace only the **audio synthesis** step
with ElevenLabs, which supports Hindi (via `eleven_multilingual_v2` /
`eleven_flash_v2_5`) and has user-selected multilingual (Hindi+English)
voices from the ElevenLabs Voice Library.

Hackathon-rules check (2026-09-20, official lablab.ai Hackathon Rule Book +
event page): no rule restricts combining additional third-party APIs with
the sponsor technology. The event page states "every participant builds on
AssemblyAI" (core tech requirement, satisfied — AssemblyAI still drives STT,
turn-taking, and the agent brain); judging criteria are Presentation,
Business value, Application of technology, and Originality, with no
exclusivity clause. Submission write-up should disclose this explicitly:
AssemblyAI is the core pipeline; ElevenLabs patches a specific, named gap
(no Hindi TTS) as a value-add, not a replacement.

## Architecture

```
Browser (app.html)                    Backend (FastAPI)              External
─────────────────                     ──────────────────             ────────
mic → AssemblyAI WS (unchanged)
  ← transcript.agent (final text) ──────────────────────────────────────────
  │
  ├─ POST /api/tts {text} ──────────→ tts.synthesize(text)  ────→  ElevenLabs
  │                                    (server-side API key)       REST API
  │  ←── audio/mpeg bytes ───────────  returns raw MP3 bytes  ←────────┘
  │
  └─ decodeAudioData → existing playback queue (activePlaybackSources/
     playHead) → speaker. Same queue AssemblyAI audio used, so barge-in
     (flushAgentAudio on input.speech.started / reply.done interrupted)
     works unchanged for ElevenLabs audio too.

  ← reply.audio (AssemblyAI's own synthesized audio) ── received, ignored.
    AssemblyAI still generates it server-side (wasted bandwidth, zero risk
    of touching the already-verified-working pipeline); the browser simply
    stops calling playAgentAudio(msg.data) for it.
```

### Backend

- `config.py`: add `ELEVENLABS_API_KEY` (required, non-empty when used;
  already set in `backend/.env`), `ELEVENLABS_VOICE_ID` (default
  `MmQVkVZnQ0dUbfWzcW6f` — the user's chosen female multilingual
  Hindi+English Voice Library voice; the male alternative
  `7qBNUtXRGP0jPi0H4r8k` is swappable via `.env`, no code change), and
  `ELEVENLABS_MODEL_ID` (default `eleven_flash_v2_5` — chosen for lowest
  latency, since this design already adds a full-reply-then-network round
  trip; supports Hindi like multilingual_v2 but faster).
- `tts.py` (new, mirrors `web_search.py`'s shape): one function
  `synthesize(text: str) -> bytes` that POSTs to
  `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}` with the server
  key in the `xi-api-key` header, `model_id`, and `text`; returns the raw
  MP3 response body. Raises a typed `TtsError` on HTTP failure, bad status,
  or missing key — mirrors `WebSearchError`'s pattern so `main.py` can
  translate it into a clean HTTP error the same way.
- `main.py`: `POST /api/tts` accepting `{text: str}` (validated non-empty,
  bounded length — reuse the same kind of `field_validator` bound already
  used elsewhere, e.g. cap at 2000 chars, generous for a 2-4 sentence spoken
  turn per the system prompt's own style rule). Returns
  `Response(content=audio_bytes, media_type="audio/mpeg")`. On `TtsError`,
  return an HTTP error; the frontend treats that as "no audio for this
  turn" and does not crash the session.

### Frontend (`app.html`)

- On the `transcript.agent` case (final agent text, not `.delta`): after the
  existing `addLine`/state-classification logic, call a new
  `speakAgentReply(text)` that:
  - Aborts any previous in-flight TTS fetch (`AbortController`) — a new
    reply always supersedes a pending one.
  - `fetch(`${apiBase()}/api/tts`, {method:'POST', body: JSON.stringify({text}), signal})`
  - On success: `arrayBuffer()` → `audioCtx.decodeAudioData()` → build an
    `AudioBufferSourceNode`, connect to `companionAnalyser || audioCtx.destination`
    (same routing `playAgentAudio` uses, so the COMPANION waveform still
    reacts), add to the existing `activePlaybackSources` set, schedule at
    `playHead` exactly like `playAgentAudio` does.
  - On failure/abort: log a console warning, do nothing else — the reply
    text is already visible in the transcript regardless of audio.
- `reply.audio` case: remove the `playAgentAudio(msg.data)` call (becomes a
  no-op comment). `playAgentAudio`/`flushAgentAudio`/`activePlaybackSources`
  stay as shared playback infrastructure used by the new path.
- Abort the in-flight TTS fetch wherever `flushAgentAudio()` is already
  called (barge-in, interrupted reply, session end) so audio doesn't start
  playing after the user has already interrupted or ended the session.

## Trade-offs (explicit, accepted)

- **Latency**: audio now starts only after the full reply text is finalized
  (not streamed word-by-word like AssemblyAI's own TTS was) plus one
  ElevenLabs network round-trip. Expect a real pause (roughly 1-3s) before
  the agent starts speaking, versus near-instant streaming today. Mitigated
  partially by choosing `eleven_flash_v2_5` (fastest ElevenLabs model).
  True streaming TTS (chunking on `transcript.agent.delta`, ElevenLabs'
  streaming endpoint) would remove this but is materially more complex
  (chunk-boundary text handling, many concurrent in-flight requests to
  cancel correctly on interrupt) — explicitly out of scope for this pass.
- **Bandwidth waste**: AssemblyAI still synthesizes and sends `reply.audio`
  frames that are now discarded unplayed. Accepted to avoid touching the
  agent's `output` config (no republish risk) for a hackathon timeline.
- **Voice selection**: one multilingual (Hindi+English) ElevenLabs voice
  used for both languages, per the user's existing Voice Library pick, not
  a cloned voice — no consent/sample-collection step needed.

## Testing

- `backend/test_tts.py` (new, mirrors `test_web_search.py`): mocked HTTP
  tests for `tts.synthesize` — success returns bytes, HTTP error / missing
  key raise `TtsError`, `main.py`'s `/api/tts` endpoint returns
  `audio/mpeg` on success and a clean error status on `TtsError`.
- Manual: `run`/browser-automation smoke test of the real live-voice flow
  (already scripted once this session — extend it to also assert an
  `/api/tts` network call fires and the response is `audio/mpeg`, since a
  headless browser cannot judge audio quality by ear).

## Out of scope (explicitly, YAGNI)

- Voice cloning (user confirmed the two voice IDs are ready Voice Library
  voices, not clone material).
- Streaming/chunked TTS for lower latency.
- Removing/disabling AssemblyAI's own `output` TTS config.
- Any change to STT, turn detection, or the agent's LLM/system prompt.
