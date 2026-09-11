"""
Text-chat fallback for when there's no AssemblyAI key yet (MOCK_MODE).
Same persona as the real voice agent (prompts.SYSTEM_PROMPT) -- lets you
build/demo the discuss-and-debate behaviour over plain HTTP before wiring
real voice. See main.py's POST /api/mock_chat and app.html's mock-mode chat
box.

`history` is the prior turns as [{role: "user"|"assistant", text: str}, ...]
(oldest first); `message` is the new user turn. Never raises -- on any LLM
failure it falls back to a small canned response so a broken key can't dead-
end the demo.
"""
import re

import config
from llm_gateway import chat_text, LLMGatewayError
from prompts import SYSTEM_PROMPT

_WORD_RE = re.compile(r"[a-zA-Z']+")

_COUNTERS = [
    "Here's a wrinkle worth considering: is that true in every case, or mostly under typical conditions?",
    "Let me push back for a second -- what's the strongest argument against what you just said?",
    "Counter-question: what would have to be true for the opposite to hold?",
]


def _topic_from_history(history: list[dict], message: str) -> str:
    first_user = next((h["text"] for h in history if h.get("role") == "user"), message)
    return first_user.strip()


def _heuristic_reply(history: list[dict], message: str) -> str:
    turn = len([h for h in history if h.get("role") == "user"])
    if turn == 0:
        topic = message.strip() or "this topic"
        return f"Got it -- let's talk about {topic}. What would you like to know, or should I just start unpacking it?"
    topic = _topic_from_history(history, message)
    counter = _COUNTERS[turn % len(_COUNTERS)]
    words = _WORD_RE.findall(message)
    gist = " ".join(words[:12]) or topic
    return (
        f"On \"{gist}\" -- that's a reasonable starting point for {topic}. "
        f"{counter}"
    )


async def reply(history: list[dict], message: str) -> str:
    if not config.MOCK_MODE:
        try:
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for h in history:
                role = "assistant" if h.get("role") == "assistant" else "user"
                messages.append({"role": role, "content": h.get("text", "")})
            messages.append({"role": "user", "content": message})
            return (await chat_text(messages)).strip()
        except LLMGatewayError:
            pass  # fall through to heuristic -- never dead-end the chat
    return _heuristic_reply(history, message)
