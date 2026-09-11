"""
Builds the JSON body for POST /v1/agents (AssemblyAI Voice Agent API).
Reference: docs/voice-agents/voice-agent-api/api-spec/create-agent,
docs/voice-agents/voice-agent-api/language-selection.

This agent has no tools -- it's a pure conversational Topic Companion
(discuss / explain / debate any single topic). All the behaviour lives in
the system prompt (prompts.py), which the agent's own LLM follows directly;
there's nothing our backend needs to compute mid-call.

Without `input.language_codes`, STT runs fully automatic multilingual
detection, which can drift -- e.g. English speech getting transcribed as
phonetic Hindi script instead of English. Pinning the language(s) you
actually expect steers detection away from that drift (per the docs: "A
Spanish support line set to ['es'] won't drift into look-alike
transcriptions of another language"). We pin a short list from
AGENT_LANGUAGE_CODES (config.py) instead of a single language, so it still
picks between the languages you actually speak rather than only one.

`input.format.sample_rate` is set explicitly to 24000 to match exactly what
app.html's mic capture sends -- AssemblyAI defaults to 24kHz too when this is
omitted, but a browser client sending the wrong rate doesn't error, it just
plays back sped up/slowed down to the STT engine, so pinning both sides
removes the ambiguity rather than relying on two defaults staying in sync.

Note: AssemblyAI currently has no dedicated Hindi TTS voice (per
docs/voice-agents/voice-agent-api/supported-languages -- it's "on the
roadmap"). See prompts.py for how the system prompt works around that for
spoken Hindi replies in the meantime.
"""
import config
from prompts import SYSTEM_PROMPT


def build_agent_body() -> dict:
    return {
        "name": "Discuss with VoiceAI",
        "system_prompt": SYSTEM_PROMPT,
        "voice": {"voice_id": config.AGENT_VOICE_ID},
        "input": {
            "language_codes": config.AGENT_LANGUAGE_CODES,
            "format": {"encoding": "audio/pcm", "sample_rate": 24000},
        },
        "output": {
            "format": {"encoding": "audio/pcm", "sample_rate": 24000},
        },
    }
