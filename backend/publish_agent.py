"""
CLI: publish (or update) the Discuss with VoiceAI agent on AssemblyAI.

    python publish_agent.py

Creates the agent (POST /v1/agents) the first time, and updates it in place
(PUT /v1/agents/{id}) on every run after that (reads AGENT_ID from .env).
Prints the agent_id and writes it back into .env so `main.py` can hand it to
the browser via GET /api/token.

The stored agent exposes browser-executed client tools. AssemblyAI emits a
tool.call over the existing browser WebSocket and the browser returns the
tool.result, so AssemblyAI never calls this local backend directly and no
tunnel/public URL is required in development.
"""
import sys
import httpx

import config
from agent_config import build_agent_body

ENV_PATH = ".env"


def _update_env_file(key: str, value: str) -> None:
    lines = []
    found = False
    try:
        with open(ENV_PATH) as f:
            lines = f.readlines()
    except FileNotFoundError:
        pass
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}\n")
    with open(ENV_PATH, "w") as f:
        f.writelines(lines)


def main() -> None:
    if not config.ASSEMBLYAI_API_KEY:
        print("ERROR: ASSEMBLYAI_API_KEY is not set (check backend/.env).", file=sys.stderr)
        sys.exit(1)

    body = build_agent_body()
    headers = {"Authorization": f"Bearer {config.ASSEMBLYAI_API_KEY}", "content-type": "application/json"}

    with httpx.Client(timeout=20.0) as client:
        if config.AGENT_ID:
            url = f"{config.AGENTS_HOST}/v1/agents/{config.AGENT_ID}"
            resp = client.put(url, headers=headers, json=body)
        else:
            url = f"{config.AGENTS_HOST}/v1/agents"
            resp = client.post(url, headers=headers, json=body)

    if resp.status_code >= 400:
        print(f"ERROR {resp.status_code} from {url}:\n{resp.text}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    agent_id = data.get("id") or data.get("agent_id") or config.AGENT_ID
    if not agent_id:
        print(f"Published, but couldn't find an id in the response:\n{data}", file=sys.stderr)
        sys.exit(1)

    _update_env_file("AGENT_ID", agent_id)
    print(f"Agent published. AGENT_ID={agent_id} (saved to backend/.env)")


if __name__ == "__main__":
    main()
