"""Post-session AssemblyAI analytics for completed Voice Agent calls.

The Voice Agent recording is a stereo OGG/Opus artifact (user on channel 1,
agent on channel 2).  This module submits that artifact to the pre-recorded
API and deliberately returns a small, sanitized view of the result: free-text
fields produced by secondary analytics are never returned because they may
contain PII even when transcript redaction is enabled.
"""

from __future__ import annotations

import asyncio
import math
import re
from collections import Counter
from typing import Any

import httpx

import config


_SESSION_ID_RE = re.compile(r"\Asess_[A-Za-z0-9]{8,128}\Z")
_SAFE_CODE_RE = re.compile(r"\A[a-z]{2,3}(?:_[a-z]{2})?\Z")
_SAFE_LABEL_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_&>./+ -]{0,159}\Z")

_SPEECH_MODELS = ["universal-3-5-pro", "universal-2"]
_TERMINAL_FAILURE_STATUSES = {"cancelled", "canceled", "error", "failed"}

# Direct identifiers only.  Broad semantic policies such as occupation,
# religion, or generic dates are intentionally excluded so useful discussion
# context is not needlessly removed.
_PII_POLICIES = [
    "account_number",
    "banking_information",
    "credit_card_cvv",
    "credit_card_expiration",
    "credit_card_number",
    "date_of_birth",
    "drivers_license",
    "email_address",
    "healthcare_number",
    "ip_address",
    "location",
    "number_sequence",
    "passport_number",
    "password",
    "person_name",
    "phone_number",
    "us_social_security_number",
    "username",
    "vehicle_id",
]

# PII text redaction's documented language set.  If automatic language
# detection ever resolves outside this set, transcript text is withheld rather
# than risk returning an unredacted transcript.
_PII_SUPPORTED_LANGUAGES = {
    "af",
    "ar",
    "be",
    "bg",
    "ca",
    "cs",
    "da",
    "de",
    "el",
    "en",
    "en_au",
    "en_uk",
    "en_us",
    "es",
    "et",
    "fa",
    "fi",
    "fr",
    "he",
    "hi",
    "hr",
    "hu",
    "id",
    "is",
    "it",
    "ja",
    "ka",
    "km",
    "ko",
    "lb",
    "lt",
    "lv",
    "ms",
    "my",
    "nl",
    "no",
    "pl",
    "pt",
    "ro",
    "ru",
    "sk",
    "sl",
    "sv",
    "sw",
    "ta",
    "tl",
    "tr",
    "uk",
    "vi",
    "zh",
}

_PROFANITY_SUPPORTED_LANGUAGES = {
    "de",
    "en",
    "en_au",
    "en_uk",
    "en_us",
    "es",
    "fr",
    "hi",
    "it",
    "ja",
    "nl",
    "pt",
}


class PostCallError(RuntimeError):
    """Base class for safe-to-surface post-call failures."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.status_code = status_code


class PostCallValidationError(PostCallError):
    """Raised before network access when caller input is invalid."""


class PostCallConfigurationError(PostCallError):
    """Raised when required server-side configuration is missing."""


class PostCallAPIError(PostCallError):
    """Raised for transport, HTTP, or malformed-response failures."""


class PostCallRemoteError(PostCallError):
    """Raised when AssemblyAI reports a terminal failed job/session."""


class PostCallTimeoutError(PostCallError):
    """Raised when a session artifact or transcript exceeds its wait budget."""


def _regional_transcript_base_url() -> str:
    region = str(getattr(config, "ASSEMBLYAI_REGION", "us") or "us").lower()
    if region == "eu":
        return "https://api.eu.assemblyai.com"
    if region == "us":
        return "https://api.assemblyai.com"
    raise PostCallConfigurationError(
        "ASSEMBLYAI_REGION must be 'us' or 'eu'",
        stage="configuration",
    )


def _base_url(value: str, *, setting: str) -> str:
    value = value.strip().rstrip("/")
    if not value.startswith("https://"):
        raise PostCallConfigurationError(
            f"{setting} must be an HTTPS URL",
            stage="configuration",
        )
    return value


def _validate_session_id(session_id: object) -> str:
    if not isinstance(session_id, str):
        raise PostCallValidationError(
            "session_id must be a Voice Agent session ID",
            stage="validation",
        )
    session_id = session_id.strip()
    if not _SESSION_ID_RE.fullmatch(session_id):
        raise PostCallValidationError(
            "session_id must match 'sess_' followed by letters or digits",
            stage="validation",
        )
    return session_id


def _validate_wait_options(
    poll_interval_seconds: float,
    session_timeout_seconds: float,
    transcript_timeout_seconds: float,
) -> None:
    values = {
        "poll_interval_seconds": poll_interval_seconds,
        "session_timeout_seconds": session_timeout_seconds,
        "transcript_timeout_seconds": transcript_timeout_seconds,
    }
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PostCallValidationError(
                f"{name} must be a finite non-negative number",
                stage="validation",
            )
        if not math.isfinite(float(value)) or value < 0:
            raise PostCallValidationError(
                f"{name} must be a finite non-negative number",
                stage="validation",
            )


async def _request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    stage: str,
    headers: dict[str, str],
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        response = await client.request(method, url, headers=headers, json=json)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise PostCallAPIError(
            f"AssemblyAI {stage} request failed with HTTP {exc.response.status_code}",
            stage=stage,
            status_code=exc.response.status_code,
        ) from exc
    except httpx.RequestError as exc:
        raise PostCallAPIError(
            f"AssemblyAI {stage} service is temporarily unavailable",
            stage=stage,
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise PostCallAPIError(
            f"AssemblyAI {stage} returned invalid JSON",
            stage=stage,
            status_code=response.status_code,
        ) from exc
    if not isinstance(data, dict):
        raise PostCallAPIError(
            f"AssemblyAI {stage} returned an invalid response",
            stage=stage,
            status_code=response.status_code,
        )
    return data


def _audio_artifact_url(session: dict[str, Any]) -> str | None:
    artifacts = session.get("artifacts")
    if not isinstance(artifacts, list):
        return None
    for artifact in artifacts:
        if not isinstance(artifact, dict) or artifact.get("type") != "audio":
            continue
        url = artifact.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise PostCallAPIError(
                "Voice Agent session returned an invalid audio artifact",
                stage="session",
            )
        return url
    return None


async def _wait_for_audio_artifact(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    poll_interval_seconds: float,
    timeout_seconds: float,
) -> str:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds

    while True:
        session = await _request_json(
            client,
            "GET",
            url,
            stage="session",
            headers=headers,
        )
        status_value = session.get("status")
        if not isinstance(status_value, str):
            raise PostCallAPIError(
                "Voice Agent session response is missing its status",
                stage="session",
            )
        status = status_value.lower()
        if status in _TERMINAL_FAILURE_STATUSES:
            raise PostCallRemoteError(
                "Voice Agent session did not complete successfully",
                stage="session",
            )
        if status == "completed":
            artifact_url = _audio_artifact_url(session)
            if artifact_url:
                return artifact_url

        if loop.time() >= deadline:
            raise PostCallTimeoutError(
                "Timed out waiting for the Voice Agent recording",
                stage="session",
            )
        await asyncio.sleep(min(poll_interval_seconds, max(0.0, deadline - loop.time())))


def _build_transcript_payload(audio_url: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "audio_url": audio_url,
        "speech_models": list(_SPEECH_MODELS),
        "language_detection": True,
        "multichannel": True,
        "speaker_labels": True,
        # Voice Agent recordings contain one known source per channel.  These
        # limits are applied per channel when multichannel diarization is on.
        "speaker_options": {
            "min_speakers_expected": 1,
            "max_speakers_expected": 1,
            "include_speaker_confidence": True,
        },
        "filter_profanity": True,
        "redact_pii": True,
        "redact_pii_policies": list(_PII_POLICIES),
        "redact_pii_sub": "entity_name",
        # Make the privacy boundary explicit, even though false is the API
        # default.  No unredacted transcript is needed by this application.
        "redact_pii_return_unredacted": False,
        "entity_detection": True,
        "iab_categories": True,
        "content_safety": True,
        "content_safety_confidence": 50,
        "sentiment_analysis": True,
        # Universal-3.5 Pro (first entry in _SPEECH_MODELS) now documents
        # disfluencies support alongside Universal-2, so filler words no
        # longer need to be withheld for this multilingual request.
        "disfluencies": True,
        "speech_understanding": {
            "request": {
                "speaker_identification": {
                    "speaker_type": "role",
                    "speakers": [
                        {
                            "role": "User",
                            "description": "Human caller on the left audio channel",
                        },
                        {
                            "role": "AI Companion",
                            "description": "AI voice agent on the right audio channel",
                        },
                    ],
                }
            }
        },
    }
    return payload


async def _submit_transcript(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    audio_url: str,
) -> str:
    response = await _request_json(
        client,
        "POST",
        url,
        stage="transcript_submit",
        headers={**headers, "content-type": "application/json"},
        json=_build_transcript_payload(audio_url),
    )
    if str(response.get("status") or "").lower() == "error":
        raise PostCallRemoteError(
            "AssemblyAI rejected the post-call transcription job",
            stage="transcript_submit",
        )
    transcript_id = response.get("id")
    if not isinstance(transcript_id, str) or not transcript_id.strip():
        raise PostCallAPIError(
            "AssemblyAI transcript response is missing its ID",
            stage="transcript_submit",
        )
    return transcript_id.strip()


async def _wait_for_transcript(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    poll_interval_seconds: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds

    while True:
        transcript = await _request_json(
            client,
            "GET",
            url,
            stage="transcript",
            headers=headers,
        )
        status_value = transcript.get("status")
        if not isinstance(status_value, str):
            raise PostCallAPIError(
                "AssemblyAI transcript response is missing its status",
                stage="transcript",
            )
        status = status_value.lower()
        if status == "completed":
            return transcript
        if status in _TERMINAL_FAILURE_STATUSES:
            raise PostCallRemoteError(
                "Post-call transcription did not complete successfully",
                stage="transcript",
            )
        if loop.time() >= deadline:
            raise PostCallTimeoutError(
                "Timed out waiting for post-call transcription",
                stage="transcript",
            )
        await asyncio.sleep(min(poll_interval_seconds, max(0.0, deadline - loop.time())))


def _safe_number(value: object) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)):
        return None
    return value


def _safe_integer(value: object) -> int | None:
    number = _safe_number(value)
    if number is None:
        return None
    return int(number)


def _safe_label(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    if not _SAFE_LABEL_RE.fullmatch(value):
        return None
    return value


def _language_code(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    return value if _SAFE_CODE_RE.fullmatch(value) else None


def _model_status(container: object) -> str:
    if isinstance(container, list):
        return "success"
    if not isinstance(container, dict):
        return "unavailable"
    status = str(container.get("status") or "success").lower()
    return "success" if status in {"completed", "success"} else "unavailable"


def _timestamp(item: dict[str, Any]) -> dict[str, int | None]:
    source = item.get("timestamp")
    if not isinstance(source, dict):
        source = item
    return {
        "start": _safe_integer(source.get("start")),
        "end": _safe_integer(source.get("end")),
    }


def _canonical_speaker(value: object) -> tuple[str, int | None]:
    label = str(value or "").strip()
    lowered = label.lower()
    if lowered in {"user", "human", "caller", "customer"}:
        return "user", 1
    if any(word in lowered for word in ("agent", "assistant", "companion")):
        return "agent", 2

    channel_match = re.match(r"^(\d+)", label)
    if channel_match:
        channel = int(channel_match.group(1))
        if channel == 1:
            return "user", channel
        if channel == 2:
            return "agent", channel
        return "unknown", channel
    return "unknown", None


def _sanitize_utterances(raw: object, *, include_text: bool) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    sanitized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role, channel = _canonical_speaker(item.get("speaker"))
        utterance: dict[str, Any] = {
            "role": role,
            "channel": channel,
            "start": _safe_integer(item.get("start")),
            "end": _safe_integer(item.get("end")),
            "confidence": _safe_number(item.get("confidence")),
        }
        speaker_confidence = _safe_number(item.get("speaker_confidence"))
        if speaker_confidence is not None:
            utterance["speaker_confidence"] = speaker_confidence
        text = item.get("text")
        utterance["text"] = text.strip() if include_text and isinstance(text, str) else None
        sanitized.append(utterance)
    return sanitized


def _sanitize_entities(raw: dict[str, Any]) -> dict[str, Any]:
    source = raw.get("entities")
    if not isinstance(source, list):
        return {"status": "unavailable", "count": 0, "by_type": {}, "items": []}

    items: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for entity in source:
        if not isinstance(entity, dict):
            continue
        entity_type = _safe_label(entity.get("entity_type"))
        if not entity_type:
            continue
        counts[entity_type] += 1
        # Never return entities[i].text: entity detection commonly extracts the
        # exact PII that transcript redaction is intended to hide.
        items.append({"type": entity_type, **_timestamp(entity)})
    return {
        "status": "success",
        "count": len(items),
        "by_type": dict(sorted(counts.items())),
        "items": items,
    }


def _numeric_mapping(raw: object) -> dict[str, int | float]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, int | float] = {}
    for key, value in raw.items():
        safe_key = _safe_label(key)
        safe_value = _safe_number(value)
        if safe_key and safe_value is not None:
            result[safe_key] = safe_value
    return result


def _sanitize_topics(raw: dict[str, Any]) -> dict[str, Any]:
    source = raw.get("iab_categories_result")
    if not isinstance(source, dict):
        return {"status": "unavailable", "summary": {}, "segments": []}

    segments: list[dict[str, Any]] = []
    results = source.get("results")
    if isinstance(results, list):
        for result in results:
            if not isinstance(result, dict):
                continue
            labels: list[dict[str, Any]] = []
            for label in result.get("labels", []):
                if not isinstance(label, dict):
                    continue
                name = _safe_label(label.get("label"))
                relevance = _safe_number(label.get("relevance"))
                if name and relevance is not None:
                    labels.append({"label": name, "relevance": relevance})
            if labels:
                segments.append({**_timestamp(result), "labels": labels})
    return {
        "status": _model_status(source),
        "summary": _numeric_mapping(source.get("summary")),
        # The source segment's free-text field is intentionally omitted.
        "segments": segments,
    }


def _sanitize_sentiment(raw: dict[str, Any]) -> dict[str, Any]:
    source = raw.get("sentiment_analysis_results")
    if not isinstance(source, list):
        return {"status": "unavailable", "counts": {}, "segments": []}

    counts: Counter[str] = Counter()
    segments: list[dict[str, Any]] = []
    for result in source:
        if not isinstance(result, dict):
            continue
        label = str(result.get("sentiment") or "").upper()
        if label not in {"POSITIVE", "NEUTRAL", "NEGATIVE"}:
            continue
        role, channel = _canonical_speaker(result.get("speaker"))
        counts[label] += 1
        segments.append(
            {
                "sentiment": label,
                "confidence": _safe_number(result.get("confidence")),
                "role": role,
                "channel": channel,
                **_timestamp(result),
            }
        )
    return {
        "status": "success",
        "counts": dict(sorted(counts.items())),
        # The source sentence text is intentionally omitted.
        "segments": segments,
    }


def _sanitize_severity_summary(raw: object) -> dict[str, dict[str, int | float]]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, int | float]] = {}
    for key, levels in raw.items():
        safe_key = _safe_label(key)
        if not safe_key or not isinstance(levels, dict):
            continue
        safe_levels = {
            level: value
            for level in ("low", "medium", "high")
            if (value := _safe_number(levels.get(level))) is not None
        }
        if safe_levels:
            result[safe_key] = safe_levels
    return result


def _sanitize_moderation(raw: dict[str, Any]) -> dict[str, Any]:
    source = raw.get("content_safety_labels")
    if not isinstance(source, dict):
        return {
            "status": "unavailable",
            "summary": {},
            "severity_summary": {},
            "segments": [],
        }

    segments: list[dict[str, Any]] = []
    results = source.get("results")
    if isinstance(results, list):
        for result in results:
            if not isinstance(result, dict):
                continue
            labels: list[dict[str, Any]] = []
            for label in result.get("labels", []):
                if not isinstance(label, dict):
                    continue
                name = _safe_label(label.get("label"))
                if not name:
                    continue
                labels.append(
                    {
                        "label": name,
                        "confidence": _safe_number(label.get("confidence")),
                        "severity": _safe_number(label.get("severity")),
                    }
                )
            if labels:
                segments.append({**_timestamp(result), "labels": labels})
    return {
        "status": _model_status(source),
        "summary": _numeric_mapping(source.get("summary")),
        "severity_summary": _sanitize_severity_summary(
            source.get("severity_score_summary")
        ),
        # The source segment's free-text field is intentionally omitted.
        "segments": segments,
    }


def _speaker_identification_status(raw: dict[str, Any]) -> str:
    speech_understanding = raw.get("speech_understanding")
    if not isinstance(speech_understanding, dict):
        return "unavailable"
    response = speech_understanding.get("response")
    if not isinstance(response, dict):
        return "unavailable"
    return _model_status(response.get("speaker_identification"))


def _sanitize_result(
    raw: dict[str, Any],
    *,
    session_id: str,
    transcript_id: str,
) -> dict[str, Any]:
    language = _language_code(raw.get("language_code"))
    pii_available = language in _PII_SUPPORTED_LANGUAGES
    profanity_available = language in _PROFANITY_SUPPORTED_LANGUAGES

    raw_text = raw.get("text")
    transcript_text = (
        raw_text.strip() if pii_available and isinstance(raw_text, str) else None
    )
    utterances = _sanitize_utterances(
        raw.get("utterances"),
        include_text=pii_available,
    )
    entities = _sanitize_entities(raw)
    topics = _sanitize_topics(raw)
    sentiment = _sanitize_sentiment(raw)
    moderation = _sanitize_moderation(raw)
    speaker_identification = _speaker_identification_status(raw)

    diarization_status = (
        "success" if isinstance(raw.get("utterances"), list) else "unavailable"
    )
    return {
        "session_id": session_id,
        "transcript_id": transcript_id,
        "status": "completed",
        "language": {
            "code": language,
            "confidence": _safe_number(raw.get("language_confidence")),
        },
        "model": _safe_label(raw.get("speech_model")),
        "audio": {
            "channels": _safe_integer(raw.get("audio_channels")),
            "duration_seconds": _safe_number(raw.get("audio_duration")),
        },
        "transcript": {
            "text": transcript_text,
            "text_withheld": not pii_available,
            # Word arrays are intentionally omitted to keep the response small.
            "utterances": utterances,
        },
        "features": {
            "multichannel": "success",
            "speaker_diarization": diarization_status,
            "speaker_identification": speaker_identification,
            "entity_detection": entities["status"],
            "topic_detection": topics["status"],
            "content_moderation": moderation["status"],
            "sentiment_analysis": sentiment["status"],
            # Filler words surface inline in transcript/utterance text, so
            # they share text's PII-language gate rather than a field of
            # their own.
            "filler_words": "success" if pii_available else "unavailable",
        },
        "guardrails": {
            "pii": {
                "status": "success" if pii_available else "unavailable",
                "substitution": "entity_name",
                "policies": list(_PII_POLICIES),
                "unredacted_fields_included": False,
            },
            "profanity": {
                "status": "success" if profanity_available else "unavailable",
                "filtering_active": profanity_available,
            },
        },
        "entities": entities,
        "topics": topics,
        "sentiment": sentiment,
        "moderation": moderation,
    }


async def analyze_voice_session(
    session_id: str,
    *,
    client: httpx.AsyncClient | None = None,
    api_key: str | None = None,
    agents_base_url: str | None = None,
    transcript_base_url: str | None = None,
    poll_interval_seconds: float = 1.0,
    session_timeout_seconds: float = 60.0,
    transcript_timeout_seconds: float = 300.0,
) -> dict[str, Any]:
    """Analyze one completed Voice Agent session and return sanitized results.

    ``client`` and URL overrides are dependency-injection seams for connection
    reuse and deterministic tests.  They should not be exposed to browser input.
    """

    validated_session_id = _validate_session_id(session_id)
    _validate_wait_options(
        poll_interval_seconds,
        session_timeout_seconds,
        transcript_timeout_seconds,
    )

    resolved_api_key = (
        api_key if api_key is not None else getattr(config, "ASSEMBLYAI_API_KEY", "")
    )
    if not isinstance(resolved_api_key, str) or not resolved_api_key.strip():
        raise PostCallConfigurationError(
            "ASSEMBLYAI_API_KEY is not configured",
            stage="configuration",
        )

    agents_base = _base_url(
        agents_base_url
        or str(getattr(config, "AGENTS_HOST", "https://agents.assemblyai.com")),
        setting="agents_base_url",
    )
    transcript_base = _base_url(
        transcript_base_url or _regional_transcript_base_url(),
        setting="transcript_base_url",
    )
    headers = {"authorization": resolved_api_key.strip()}

    owns_client = client is None
    active_client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(15.0, connect=5.0),
        follow_redirects=True,
    )
    try:
        artifact_url = await _wait_for_audio_artifact(
            active_client,
            f"{agents_base}/v1/sessions/{validated_session_id}",
            headers=headers,
            poll_interval_seconds=float(poll_interval_seconds),
            timeout_seconds=float(session_timeout_seconds),
        )
        # Submit immediately while the freshly fetched pre-signed URL is valid.
        transcript_id = await _submit_transcript(
            active_client,
            f"{transcript_base}/v2/transcript",
            headers=headers,
            audio_url=artifact_url,
        )
        raw = await _wait_for_transcript(
            active_client,
            f"{transcript_base}/v2/transcript/{transcript_id}",
            headers=headers,
            poll_interval_seconds=float(poll_interval_seconds),
            timeout_seconds=float(transcript_timeout_seconds),
        )
        return _sanitize_result(
            raw,
            session_id=validated_session_id,
            transcript_id=transcript_id,
        )
    finally:
        if owns_client:
            await active_client.aclose()


__all__ = [
    "PostCallAPIError",
    "PostCallConfigurationError",
    "PostCallError",
    "PostCallRemoteError",
    "PostCallTimeoutError",
    "PostCallValidationError",
    "analyze_voice_session",
]
