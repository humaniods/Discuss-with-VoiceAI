"""
Thin client for the AssemblyAI LLM Gateway
(https://www.assemblyai.com/docs/llm-gateway/quickstart).

POST {LLM_GATEWAY_URL}
headers: {"authorization": <ASSEMBLYAI_API_KEY>}
body:    {"model", "messages", "max_tokens", "response_format": {"type": "json_object"}}

We ask for response_format=json_object and additionally force the model's
hand with an explicit "return ONLY JSON" instruction, then parse + validate
with pydantic. If parsing/validation fails we retry once with the parse error
appended to the conversation so the model can self-correct.
"""
import json
import httpx

import config


class LLMGatewayError(RuntimeError):
    pass


async def chat_text(messages: list[dict], *, max_tokens: int = 300) -> str:
    """Plain conversational completion (no JSON mode) -- used by discuss.py's
    mock-text fallback so the offline demo path has the same persona as the
    real voice agent, just without a real AssemblyAI call."""
    if config.MOCK_MODE:
        raise LLMGatewayError("chat_text called while MOCK_MODE is on -- caller should use the heuristic path instead")

    headers = {
        "authorization": config.ASSEMBLYAI_API_KEY,
        "content-type": "application/json",
    }
    body = {
        "model": config.LLM_GATEWAY_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(config.LLM_GATEWAY_URL, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (httpx.HTTPStatusError, httpx.TransportError, KeyError, IndexError) as e:
            raise LLMGatewayError(f"LLM Gateway call failed: {e}")


async def chat_json(system: str, user: str, *, max_tokens: int = 900) -> dict:
    if config.MOCK_MODE:
        raise LLMGatewayError("chat_json called while MOCK_MODE is on -- caller should use the heuristic path instead")

    headers = {
        "authorization": config.ASSEMBLYAI_API_KEY,
        "content-type": "application/json",
    }
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    async with httpx.AsyncClient(timeout=20.0) as client:
        last_err = None
        raw_content = ""
        for attempt in range(2):
            body = {
                "model": config.LLM_GATEWAY_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            }
            try:
                resp = await client.post(config.LLM_GATEWAY_URL, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
                raw_content = data["choices"][0]["message"]["content"]
                return json.loads(raw_content)
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                last_err = e
                break  # network/auth errors won't be fixed by asking the model again
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                last_err = e
                # give the model one chance to fix its own malformed JSON
                messages.append({"role": "assistant", "content": raw_content})
                messages.append({
                    "role": "user",
                    "content": f"That was not valid JSON ({e}). Reply again with ONLY a single valid JSON object, no markdown fences, no commentary.",
                })
                continue

        raise LLMGatewayError(f"LLM Gateway call failed after retries: {last_err}")
