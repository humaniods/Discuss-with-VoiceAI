"""
Central env-driven settings. Nothing here talks to the network -- it just
reads .env (via python-dotenv) and computes derived constants.
"""
import os
import re
from dotenv import load_dotenv

load_dotenv()


def _bool(v, default=False):
    if v is None or v == "":
        return default
    normalized = v.strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False
    raise ValueError("boolean settings must be one of: 1/0, true/false, yes/no, on/off")


def _choice(name, default, choices):
    value = os.getenv(name, default).strip().lower()
    if value not in choices:
        allowed = ", ".join(sorted(choices))
        raise ValueError(f"{name} must be one of: {allowed}")
    return value


def _nonempty(name, default):
    value = os.getenv(name, default).strip()
    if not value:
        raise ValueError(f"{name} cannot be empty")
    return value


def _optional(name, default=""):
    raw = os.getenv(name)
    return default if raw is None or not raw.strip() else raw.strip()


def _bounded_text(name, default, maximum):
    value = os.getenv(name, default).strip()
    if len(value) > maximum:
        raise ValueError(f"{name} must be at most {maximum} characters")
    return value


def _csv_list(name, default, maximum, item_maximum=None):
    raw = os.getenv(name, default)
    values = []
    seen = set()
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        if item_maximum is not None and len(value) > item_maximum:
            raise ValueError(
                f"each {name} entry must be at most {item_maximum} characters"
            )
        normalized = value.casefold()
        if normalized not in seen:
            seen.add(normalized)
            values.append(value)
    if len(values) > maximum:
        raise ValueError(f"{name} accepts at most {maximum} entries")
    return values


def _bounded_float(name, default, minimum=0.0, maximum=1.0):
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number between {minimum} and {maximum}") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "").strip()
ASSEMBLYAI_REGION = _choice("ASSEMBLYAI_REGION", "us", {"us", "eu"})

# Exa (https://exa.ai) live web search, backing the web_search client-side
# tool (see web_search.py, agent_config.py). Not an AssemblyAI product --
# AssemblyAI's Voice Agent API only provides tool-calling plumbing (client-
# side tools, HTTP tools), not a hosted search data source of its own.
EXA_API_KEY = os.getenv("EXA_API_KEY", "").strip()

# LLM Gateway expects the API model ID (for example `claude-opus-5`), not the
# catalog's provider/model display label (`anthropic/claude-opus-5`). Accounts
# still need explicit access to the selected model. AGENT_LLM_MODEL inherits
# this setting so an existing deployment can keep its currently enabled model.
LLM_GATEWAY_MODEL = _nonempty("LLM_GATEWAY_MODEL", "claude-opus-5")
AGENT_LLM_MODEL = _optional("AGENT_LLM_MODEL", LLM_GATEWAY_MODEL)
SENTIMENT_MODEL = _optional("SENTIMENT_MODEL", LLM_GATEWAY_MODEL)
AGENT_CUSTOM_LLM_ENABLED = _bool(
    os.getenv("AGENT_CUSTOM_LLM_ENABLED"), default=False
)

# These knobs are for direct Claude requests to /chat/completions. The stored
# Voice Agent `llm` schema has no cache-control field, so agent_config.py does
# not claim or attempt to enable caching for the managed voice loop.
LLM_GATEWAY_PROMPT_CACHE_ENABLED = _bool(
    os.getenv("LLM_GATEWAY_PROMPT_CACHE_ENABLED"), default=True
)
LLM_GATEWAY_PROMPT_CACHE_TTL = _choice(
    "LLM_GATEWAY_PROMPT_CACHE_TTL", "5m", {"5m", "1h"}
)

AGENT_ID = os.getenv("AGENT_ID", "").strip()
AGENT_VOICE_ID = _nonempty("AGENT_VOICE_ID", "alba")

# AssemblyAI Voice Focus performs the actual noise cancellation inside the
# managed Voice Agent pipeline. Far-field fits the laptop/room microphones
# this browser app normally uses; switch to near-field for a headset.
AGENT_VOICE_FOCUS = _choice(
    "AGENT_VOICE_FOCUS", "far-field", {"near-field", "far-field"}
)
AGENT_VOICE_FOCUS_THRESHOLD = _bounded_float(
    "AGENT_VOICE_FOCUS_THRESHOLD", 0.8
)

# Balanced is AssemblyAI's default speed/accuracy tradeoff. Keeping it explicit
# prevents a future service default from changing the application's behavior.
AGENT_TRANSCRIPTION_MODE = _choice(
    "AGENT_TRANSCRIPTION_MODE",
    "balanced",
    {"balanced", "min_latency", "max_accuracy"},
)
AGENT_TRANSCRIPTION_PROMPT = _bounded_text(
    "AGENT_TRANSCRIPTION_PROMPT",
    (
        "A voice-first discussion about any topic. The user may speak English, "
        "Hindi, or naturally code-switch in Hinglish. Expect names, technical "
        "terms, acronyms, and numbers from many subject areas."
    ),
    1750,
)

# Comma-separated transcription-bias terms. Voice Agent input accepts at most
# 100 terms; the underlying STT guidance recommends keeping each term <=50
# characters. Duplicates are removed without changing the first spelling.
AGENT_KEYTERMS = _csv_list(
    "AGENT_KEYTERMS",
    "AssemblyAI,VoiceAI,Claude,Voice Focus,Hinglish",
    maximum=100,
    item_maximum=50,
)

# Languages to steer STT detection toward. English and Hindi are the app's
# required pair; additional supported two-letter language codes are allowed.
AGENT_LANGUAGE_CODES = _csv_list(
    "AGENT_LANGUAGE_CODES", "en,hi", maximum=18
)
if not AGENT_LANGUAGE_CODES:
    raise ValueError("AGENT_LANGUAGE_CODES must contain at least one language code")
for _language_code in AGENT_LANGUAGE_CODES:
    if not re.fullmatch(r"[a-z]{2}", _language_code):
        raise ValueError(
            "AGENT_LANGUAGE_CODES entries must be lowercase two-letter language codes"
        )

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*").strip()

# Forced on when there is no key -- there is nothing to call otherwise.
MOCK_MODE = _bool(os.getenv("MOCK_MODE"), default=False) or not ASSEMBLYAI_API_KEY

AGENTS_HOST = (
    "https://agents.eu.assemblyai.com"
    if ASSEMBLYAI_REGION == "eu"
    else "https://agents.assemblyai.com"
)

LLM_GATEWAY_BASE_URL = (
    "https://llm-gateway.eu.assemblyai.com/v1"
    if ASSEMBLYAI_REGION == "eu"
    else "https://llm-gateway.assemblyai.com/v1"
)
LLM_GATEWAY_URL = f"{LLM_GATEWAY_BASE_URL}/chat/completions"


def direct_gateway_cache_control():
    """Return Claude's explicit cache-control value for direct Gateway calls."""
    if not LLM_GATEWAY_PROMPT_CACHE_ENABLED:
        return None
    return {"type": "ephemeral", "ttl": LLM_GATEWAY_PROMPT_CACHE_TTL}
