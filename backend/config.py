"""
Central env-driven settings. Nothing here talks to the network -- it just
reads .env (via python-dotenv) and computes derived constants.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _bool(v, default=False):
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "").strip()
ASSEMBLYAI_REGION = os.getenv("ASSEMBLYAI_REGION", "us").strip().lower()
LLM_GATEWAY_MODEL = os.getenv("LLM_GATEWAY_MODEL", "qwen3.5-4b-32k-fast").strip()

AGENT_ID = os.getenv("AGENT_ID", "").strip()
AGENT_VOICE_ID = os.getenv("AGENT_VOICE_ID", "alba").strip()

# Languages to steer STT detection toward (see agent_config.py's comment on
# why this matters -- unset, detection can drift, e.g. transcribing English
# speech as phonetic Hindi script). Comma-separated ISO codes in .env.
AGENT_LANGUAGE_CODES = [
    c.strip() for c in os.getenv("AGENT_LANGUAGE_CODES", "en,hi").split(",") if c.strip()
]

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*").strip()

# Forced on when there is no key -- there is nothing to call otherwise.
MOCK_MODE = _bool(os.getenv("MOCK_MODE"), default=False) or not ASSEMBLYAI_API_KEY

AGENTS_HOST = "https://agents.assemblyai.com"

LLM_GATEWAY_URL = (
    "https://llm-gateway.eu.assemblyai.com/v1/chat/completions"
    if ASSEMBLYAI_REGION == "eu"
    else "https://llm-gateway.assemblyai.com/v1/chat/completions"
)
