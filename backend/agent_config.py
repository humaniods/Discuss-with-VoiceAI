"""
Builds the JSON body for POST /v1/agents (AssemblyAI Voice Agent API).
Reference: docs/voice-agents/voice-agent-api/api-spec/create-agent,
docs/voice-agents/voice-agent-api/language-selection,
docs/voice-agents/voice-agent-api/noise-suppression,
docs/voice-agents/voice-agent-api/tools/client-side-tools, and
docs/voice-agents/voice-agent-api/connect-your-own-llm.

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

`input.voice_focus` is AssemblyAI's server-side noise cancellation. The
profile and strength are env-driven so laptop/room mics can use far-field
while headset deployments can switch to near-field. The browser deliberately
does not stack its own noise suppression on top (see app.html), which avoids
speech-damaging artifacts while retaining browser acoustic echo cancellation.

The flat client-side tools provide an Exa-backed web search and the user's
actual browser-local clock. AssemblyAI emits tool.call; the browser executes
the requested tool and returns tool.result -- see app.html and web_search.py.
We also leave `input.turn_detection` out so AssemblyAI's adaptive semantic
defaults remain in control rather than pinning raw silence windows.

The opt-in `llm` entry points the stored Voice Agent to AssemblyAI's LLM
Gateway and reuses the server-side AssemblyAI key. It is omitted unless both
the feature flag and key are configured, which lets an account without access
to the requested model keep using the managed model. Prompt-cache settings in
config.py are for later *direct* Gateway requests only: the stored Voice Agent
LLM schema exposes no cache-control field.
"""
import config
from prompts import SYSTEM_PROMPT


class AgentBody(dict):
    """Dict accepted by JSON encoders, with credentials redacted in logs."""

    def _redacted(self):
        redacted = dict(self)
        if "llm" in redacted:
            redacted["llm"] = [
                {**entry, "api_key": "***"} for entry in redacted["llm"]
            ]
        return redacted

    def __repr__(self):
        return repr(self._redacted())

    def __str__(self):
        return str(self._redacted())


def _web_search_tool() -> dict:
    return {
        "type": "function",
        "name": "web_search",
        "description": (
            "Search the live web for current external facts and return dated "
            "source snippets. You MUST use this before answering anything "
            "described as latest, current, today, recent, newest, or "
            "time-sensitive, including products, news, prices, scores, "
            "schedules, availability, and office-holders; never answer those "
            "from model memory."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A concise freshness-seeking query that preserves the "
                        "user's complete request and requested market, for "
                        "example 'latest Apple iPhone lineup official India "
                        "prices' or 'India cricket score today'."
                    ),
                }
            },
            "required": ["query"],
        },
        "execution_mode": "interactive",
        "timeout_seconds": 120,
    }


def _current_datetime_tool() -> dict:
    return {
        "type": "function",
        "name": "get_current_datetime",
        "description": (
            "Read the user's device clock and return its current local date, "
            "weekday, exact time, UTC offset, and IANA time zone. You MUST use "
            "this whenever the user asks for the current date, day, time, "
            "year, or what 'today'/'now' means; never guess from memory."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "execution_mode": "interactive",
        "timeout_seconds": 30,
    }


def _validate_agent_body(body: dict) -> None:
    input_config = body["input"]
    if input_config.get("transcription_mode") != "balanced":
        raise ValueError("Voice Agent transcription_mode must be balanced")
    if len(input_config.get("transcription_prompt", "")) > 1750:
        raise ValueError("Voice Agent transcription_prompt exceeds 1750 characters")
    if len(input_config.get("keyterms", [])) > 100:
        raise ValueError("Voice Agent keyterms exceeds 100 entries")
    if not {"en", "hi"}.issubset(input_config.get("language_codes", [])):
        raise ValueError("Voice Agent language_codes must include en and hi")
    if "turn_detection" in input_config:
        raise ValueError("Use adaptive turn detection; do not set raw silence overrides")

    tools = body.get("tools", [])
    tool_names = [tool.get("name") for tool in tools if isinstance(tool, dict)]
    expected_tools = {"get_current_datetime", "web_search"}
    if (
        len(tools) != len(expected_tools)
        or any(tool.get("type") != "function" for tool in tools)
        or len(set(tool_names)) != len(tool_names)
        or set(tool_names) != expected_tools
    ):
        raise ValueError(
            "Voice Agent must expose flat get_current_datetime and web_search tools"
        )

    llm = body.get("llm")
    if llm is not None:
        if len(llm) != 1:
            raise ValueError("Voice Agent API currently accepts one LLM entry")
        entry = llm[0]
        if not entry["base_url"].startswith("https://") or not entry[
            "base_url"
        ].endswith("/v1"):
            raise ValueError("Voice Agent LLM base_url must be a public HTTPS /v1 base")
        if not entry["model"] or not entry["api_key"]:
            raise ValueError("Voice Agent LLM model and api_key cannot be empty")


def build_agent_body() -> dict:
    body = AgentBody({
        "name": "Discuss with VoiceAI",
        "system_prompt": SYSTEM_PROMPT,
        "voice": {"voice_id": config.AGENT_VOICE_ID},
        "input": {
            "transcription_mode": config.AGENT_TRANSCRIPTION_MODE,
            "transcription_prompt": config.AGENT_TRANSCRIPTION_PROMPT,
            "keyterms": list(config.AGENT_KEYTERMS),
            "language_codes": list(config.AGENT_LANGUAGE_CODES),
            "voice_focus": config.AGENT_VOICE_FOCUS,
            "voice_focus_threshold": config.AGENT_VOICE_FOCUS_THRESHOLD,
            "format": {"encoding": "audio/pcm", "sample_rate": 24000},
        },
        "output": {
            "format": {"encoding": "audio/pcm", "sample_rate": 24000},
        },
        "tools": [_current_datetime_tool(), _web_search_tool()],
    })
    if config.AGENT_CUSTOM_LLM_ENABLED and config.ASSEMBLYAI_API_KEY:
        body["llm"] = [
            {
                "base_url": config.LLM_GATEWAY_BASE_URL,
                "model": config.AGENT_LLM_MODEL,
                "api_key": config.ASSEMBLYAI_API_KEY,
            }
        ]
    _validate_agent_body(body)
    return body
