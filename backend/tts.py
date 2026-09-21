"""Text-to-speech adapter for Hindi / Indian-accented English.

Originally spec'd against ElevenLabs (see docs/superpowers/specs/
2026-09-20-elevenlabs-tts-design.md), but the ElevenLabs account got its free
tier disabled ("detected_unusual_activity") and the user does not want a paid
plan. First swapped to gTTS (free, no key), but gTTS has one flat, slow voice
per language with no rate control. Switched to edge-tts (Microsoft Edge's
free "Read Aloud" TTS, no API key, no signup): real neural voices with a
native speaking-rate parameter, so latency-from-slow-speech is fixed at the
source instead of hacked around with playbackRate on the frontend.

One fixed female voice pair, matching the user's existing preference:
Devanagari text -> hi-IN-SwaraNeural, Latin-script text -> en-IN-NeerjaNeural
(Indian English accent). The system prompt (prompts.py) is written to use
feminine Hindi verb forms ("sakti", "rahi", ...) to match this voice's
gender.
"""

from __future__ import annotations

import re

import edge_tts

_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")

_HINDI_VOICE = "hi-IN-SwaraNeural"
_ENGLISH_VOICE = "en-IN-NeerjaNeural"
# Edge TTS's default pace reads slow for a live voice turn; +20% keeps it
# natural but brisk. Tune here if it still feels slow or gets too fast.
_RATE = "+20%"


class TtsError(RuntimeError):
    """Raised when edge-tts or the network cannot synthesize the text."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


async def synthesize(text: str) -> bytes:
    """Return raw MP3 bytes for ``text``, Hindi or Indian-English accented."""

    voice = _HINDI_VOICE if _DEVANAGARI_RE.search(text) else _ENGLISH_VOICE
    communicate = edge_tts.Communicate(text, voice, rate=_RATE)

    chunks: list[bytes] = []
    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
    except Exception as exc:  # network/service failures from edge-tts internals
        raise TtsError(f"edge-tts request failed: {exc}") from exc

    if not chunks:
        raise TtsError("edge-tts returned no audio")
    return b"".join(chunks)
