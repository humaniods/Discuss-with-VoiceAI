"""Live web-search adapter for the voice agent, backed by Exa
(https://exa.ai/docs/reference/search).

This replaces an earlier Wikipedia-only version: Wikipedia's intro-paragraph
extracts cannot answer time-sensitive questions (current prices, a just-
announced product, this week's news) since encyclopedia articles lag real
events and rarely state retail prices at all. Exa indexes the live web, so
"latest iPhone price" resolves to this week's announcement instead of
whatever generation Wikipedia's intro paragraph was last edited to describe.
"""

from __future__ import annotations

from typing import Literal

import httpx
from typing_extensions import TypedDict

import config

SearchLanguage = Literal["en", "hi", "auto"]

_EXA_SEARCH_URL = "https://api.exa.ai/search"
_DEFAULT_LIMIT = 3
_MAX_LIMIT = 5
_MAX_SNIPPET_CHARS = 400
# "fast" skips Exa's LLM-generated summary (~4s) in favor of extractive
# highlights (~0.5s). A live voice turn cannot afford a multi-second tool
# call, so latency is weighted over the more polished "summary" mode.
_SEARCH_TYPE = "fast"
_EXCLUDED_DOMAINS = ["wikipedia.org"]


class WebSearchResult(TypedDict):
    title: str
    snippet: str
    url: str
    source: str
    published_date: str | None


class WebSearchError(RuntimeError):
    """Raised when Exa or the network cannot fulfill a valid lookup."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _compact(text: object) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    if len(compact) <= _MAX_SNIPPET_CHARS:
        return compact

    prefix = compact[: _MAX_SNIPPET_CHARS - 1]
    if " " in prefix:
        prefix = prefix.rsplit(" ", 1)[0]
    return prefix.rstrip() + "…"


def _source_name(url: str) -> str:
    host = url.split("//", 1)[-1].split("/", 1)[0].lower()
    host = host[4:] if host.startswith("www.") else host
    return host or "Web"


def _published_date(value: object) -> str | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    return value[:10]


def _parse_results(data: object) -> list[WebSearchResult]:
    if not isinstance(data, dict):
        raise WebSearchError("Exa returned an invalid response")

    error = data.get("error")
    if isinstance(error, str) and error:
        raise WebSearchError(f"Exa API error: {error}")

    raw_results = data.get("results")
    if raw_results is None:
        return []
    if not isinstance(raw_results, list):
        raise WebSearchError("Exa returned an invalid response")

    results: list[WebSearchResult] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        url = item.get("url")
        if not isinstance(title, str) or not title.strip():
            continue
        if not isinstance(url, str) or not url.startswith("https://"):
            continue

        highlights = item.get("highlights")
        highlight = highlights[0] if isinstance(highlights, list) and highlights else None
        results.append(
            {
                "title": title.strip(),
                "snippet": _compact(highlight),
                "url": url,
                "source": _source_name(url),
                "published_date": _published_date(item.get("publishedDate")),
            }
        )
    return results


async def search_web(
    query: str,
    language: SearchLanguage = "auto",
    *,
    limit: int = _DEFAULT_LIMIT,
    client: httpx.AsyncClient | None = None,
    api_key: str | None = None,
) -> list[WebSearchResult]:
    """Return a few live web results with short highlighted snippets.

    ``query`` and ``language`` are expected to be validated by the caller.
    ``language`` is accepted for API compatibility with the client-side tool
    contract but does not change which index is searched -- Exa searches the
    live web directly rather than routing to a per-language encyclopedia
    mirror the way the previous Wikipedia adapter did.
    ``client`` and ``api_key`` are dependency-injection seams for connection
    reuse and deterministic tests; they default to a fresh client and
    ``config.EXA_API_KEY``.
    """

    if language not in ("en", "hi", "auto"):
        raise ValueError("language must be 'en', 'hi', or 'auto'")
    if not 1 <= limit <= _MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {_MAX_LIMIT}")

    resolved_api_key = api_key if api_key is not None else config.EXA_API_KEY
    if not resolved_api_key:
        raise WebSearchError("EXA_API_KEY is not configured")

    body = {
        "query": query,
        "numResults": limit,
        "type": _SEARCH_TYPE,
        # Keep encyclopedia results out of current-fact answers. We avoid a
        # forced live-crawl here because it can exceed a voice turn's latency
        # budget; Exa's live index + dated results provide the freshness signal.
        "excludeDomains": _EXCLUDED_DOMAINS,
        "contents": {"highlights": True},
    }
    headers = {"x-api-key": resolved_api_key, "content-type": "application/json"}

    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=httpx.Timeout(8.0))

    try:
        response = await active_client.post(_EXA_SEARCH_URL, json=body, headers=headers)
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as exc:
            raise WebSearchError(
                "Exa returned invalid JSON", status_code=response.status_code
            ) from exc
        return _parse_results(data)
    except httpx.HTTPStatusError as exc:
        raise WebSearchError(
            "Exa request failed", status_code=exc.response.status_code
        ) from exc
    except httpx.RequestError as exc:
        raise WebSearchError("Exa is temporarily unavailable") from exc
    finally:
        if owns_client:
            await active_client.aclose()
