import json
import unittest

import httpx

import postcall


SESSION_ID = "sess_abcdef12345678"


def completed_session():
    return {
        "id": SESSION_ID,
        "status": "completed",
        "artifacts": [
            {
                "type": "audio",
                "url": "https://artifacts.test/fresh-recording.ogg?signature=fresh",
                "content_type": "audio/ogg",
            },
            {
                "type": "timeline",
                "url": "https://artifacts.test/timeline.json?signature=fresh",
            },
        ],
    }


def completed_transcript(language="en"):
    return {
        "id": "tr_123",
        "status": "completed",
        "speech_model": "universal-3-5-pro",
        "language_code": language,
        "language_confidence": 0.97,
        "audio_channels": 2,
        "audio_duration": 42.5,
        "redact_pii": True,
        "filter_profanity": True,
        "text": "My name is [PERSON_NAME]. The agent replied safely.",
        "utterances": [
            {
                "speaker": "1A",
                "text": "My name is [PERSON_NAME].",
                "start": 10,
                "end": 1200,
                "confidence": 0.96,
                "speaker_confidence": 0.93,
                "words": [{"text": "Sanyam"}],
            },
            {
                "speaker": "2A",
                "text": "The agent replied safely.",
                "start": 1300,
                "end": 2600,
                "confidence": 0.98,
            },
        ],
        "entities": [
            {
                "entity_type": "email_address",
                "text": "secret@example.com",
                "start": 100,
                "end": 500,
            }
        ],
        "iab_categories_result": {
            "status": "success",
            "summary": {"Technology&Computing>ArtificialIntelligence": 0.91},
            "results": [
                {
                    "text": "Raw topic excerpt containing Sanyam",
                    "timestamp": {"start": 0, "end": 2600},
                    "labels": [
                        {
                            "label": "Technology&Computing>ArtificialIntelligence",
                            "relevance": 0.91,
                        }
                    ],
                }
            ],
        },
        "sentiment_analysis_results": [
            {
                "text": "Raw sentiment text with secret@example.com",
                "sentiment": "POSITIVE",
                "confidence": 0.88,
                "speaker": "1A",
                "start": 10,
                "end": 1200,
            }
        ],
        "content_safety_labels": {
            "status": "success",
            "summary": {"profanity": 0.71},
            "severity_score_summary": {
                "profanity": {"low": 0.8, "medium": 0.2, "high": 0.0}
            },
            "results": [
                {
                    "text": "Raw moderation excerpt containing Sanyam",
                    "timestamp": {"start": 10, "end": 900},
                    "labels": [
                        {"label": "profanity", "confidence": 0.71, "severity": 0.2}
                    ],
                }
            ],
        },
        "speech_understanding": {
            "request": {
                "speaker_identification": {
                    "speakers": [{"role": "User", "private": "Sanyam"}]
                }
            },
            "response": {
                "speaker_identification": {
                    "status": "success",
                    "mapping": {"1A": "User", "2A": "AI Companion"},
                }
            },
        },
        "unredacted_text": "Sanyam can be reached at secret@example.com",
        "unredacted_words": [{"text": "Sanyam"}],
        "unredacted_utterances": [{"text": "secret@example.com"}],
    }


class PostCallTests(unittest.IsolatedAsyncioTestCase):
    async def _run(self, handler, **kwargs):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await postcall.analyze_voice_session(
                SESSION_ID,
                client=client,
                api_key="test-api-key",
                agents_base_url="https://agents.test",
                transcript_base_url="https://api.test",
                poll_interval_seconds=0,
                session_timeout_seconds=1,
                transcript_timeout_seconds=1,
                **kwargs,
            )

    async def test_combined_payload_and_sanitized_result(self):
        session_calls = 0
        submitted_payload = None

        def handler(request):
            nonlocal session_calls, submitted_payload
            self.assertEqual(request.headers["authorization"], "test-api-key")
            if request.url.path == f"/v1/sessions/{SESSION_ID}":
                session_calls += 1
                if session_calls == 1:
                    return httpx.Response(200, json={"status": "active", "artifacts": []})
                return httpx.Response(200, json=completed_session())
            if request.method == "POST" and request.url.path == "/v2/transcript":
                submitted_payload = json.loads(request.content)
                return httpx.Response(200, json={"id": "tr_123", "status": "queued"})
            if request.method == "GET" and request.url.path == "/v2/transcript/tr_123":
                return httpx.Response(200, json=completed_transcript())
            self.fail(f"Unexpected request: {request.method} {request.url}")

        result = await self._run(handler)

        self.assertEqual(session_calls, 2)
        self.assertEqual(
            submitted_payload["audio_url"],
            "https://artifacts.test/fresh-recording.ogg?signature=fresh",
        )
        self.assertEqual(
            submitted_payload["speech_models"],
            ["universal-3-5-pro", "universal-2"],
        )
        self.assertTrue(submitted_payload["language_detection"])
        self.assertTrue(submitted_payload["multichannel"])
        self.assertTrue(submitted_payload["speaker_labels"])
        self.assertEqual(
            submitted_payload["speaker_options"],
            {
                "min_speakers_expected": 1,
                "max_speakers_expected": 1,
                "include_speaker_confidence": True,
            },
        )
        self.assertTrue(submitted_payload["filter_profanity"])
        self.assertTrue(submitted_payload["redact_pii"])
        self.assertEqual(submitted_payload["redact_pii_sub"], "entity_name")
        self.assertFalse(submitted_payload["redact_pii_return_unredacted"])
        self.assertTrue(submitted_payload["entity_detection"])
        self.assertTrue(submitted_payload["iab_categories"])
        self.assertTrue(submitted_payload["content_safety"])
        self.assertTrue(submitted_payload["sentiment_analysis"])
        self.assertTrue(submitted_payload["disfluencies"])
        speaker_identification = submitted_payload["speech_understanding"]["request"][
            "speaker_identification"
        ]
        self.assertEqual(speaker_identification["speaker_type"], "role")
        self.assertEqual(
            [speaker["role"] for speaker in speaker_identification["speakers"]],
            ["User", "AI Companion"],
        )

        self.assertEqual(result["transcript"]["utterances"][0]["role"], "user")
        self.assertEqual(result["transcript"]["utterances"][0]["channel"], 1)
        self.assertEqual(result["transcript"]["utterances"][1]["role"], "agent")
        self.assertEqual(result["entities"]["items"][0]["type"], "email_address")
        self.assertEqual(result["sentiment"]["counts"], {"POSITIVE": 1})
        self.assertEqual(result["topics"]["status"], "success")
        self.assertEqual(result["moderation"]["status"], "success")
        self.assertEqual(result["features"]["speaker_identification"], "success")
        self.assertFalse(result["guardrails"]["pii"]["unredacted_fields_included"])

        serialized = json.dumps(result)
        self.assertNotIn("secret@example.com", serialized)
        self.assertNotIn("Raw topic excerpt", serialized)
        self.assertNotIn("Raw sentiment text", serialized)
        self.assertNotIn("Raw moderation excerpt", serialized)
        self.assertNotIn('"Sanyam"', serialized)
        self.assertNotIn("fresh-recording", serialized)
        self.assertNotIn("unredacted", serialized.lower().replace("unredacted_fields_included", ""))

    async def test_hindi_keeps_redacted_transcript_and_marks_unsupported_models(self):
        transcript = completed_transcript(language="hi")
        transcript.pop("iab_categories_result")
        transcript.pop("sentiment_analysis_results")
        transcript.pop("content_safety_labels")

        def handler(request):
            if request.url.path == f"/v1/sessions/{SESSION_ID}":
                return httpx.Response(200, json=completed_session())
            if request.method == "POST":
                return httpx.Response(200, json={"id": "tr_123", "status": "queued"})
            return httpx.Response(200, json=transcript)

        result = await self._run(handler)

        self.assertFalse(result["transcript"]["text_withheld"])
        self.assertEqual(result["guardrails"]["pii"]["status"], "success")
        self.assertEqual(result["guardrails"]["profanity"]["status"], "success")
        self.assertEqual(result["features"]["topic_detection"], "unavailable")
        self.assertEqual(result["features"]["content_moderation"], "unavailable")
        self.assertEqual(result["features"]["sentiment_analysis"], "unavailable")

    async def test_rejects_invalid_session_id_before_network_access(self):
        def handler(_request):
            self.fail("No request should be made for an invalid session ID")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(postcall.PostCallValidationError) as caught:
                await postcall.analyze_voice_session(
                    "../../etc/passwd",
                    client=client,
                    api_key="test-api-key",
                )

        self.assertEqual(caught.exception.stage, "validation")

    async def test_transcript_error_raises_typed_error_without_remote_details(self):
        def handler(request):
            if request.url.path == f"/v1/sessions/{SESSION_ID}":
                return httpx.Response(200, json=completed_session())
            if request.method == "POST":
                return httpx.Response(200, json={"id": "tr_123", "status": "queued"})
            return httpx.Response(
                200,
                json={"id": "tr_123", "status": "error", "error": "Sanyam secret"},
            )

        with self.assertRaises(postcall.PostCallRemoteError) as caught:
            await self._run(handler)

        self.assertEqual(caught.exception.stage, "transcript")
        self.assertNotIn("Sanyam", str(caught.exception))

    async def test_transcript_timeout_is_typed(self):
        def handler(request):
            if request.url.path == f"/v1/sessions/{SESSION_ID}":
                return httpx.Response(200, json=completed_session())
            if request.method == "POST":
                return httpx.Response(200, json={"id": "tr_123", "status": "queued"})
            return httpx.Response(200, json={"id": "tr_123", "status": "processing"})

        with self.assertRaises(postcall.PostCallTimeoutError) as caught:
            await self._run(handler, transcript_timeout_seconds=0)

        self.assertEqual(caught.exception.stage, "transcript")


if __name__ == "__main__":
    unittest.main()
