import json
import unittest

import httpx

import web_search


class WebSearchTests(unittest.IsolatedAsyncioTestCase):
    async def _search_with(self, handler, query="black hole", language="en", api_key="test-key", **kwargs):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await web_search.search_web(
                query,
                language,
                client=client,
                api_key=api_key,
                **kwargs,
            )

    async def test_returns_compact_results_with_source_and_date(self):
        seen_request = None

        def handler(request):
            nonlocal seen_request
            seen_request = request
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "Black hole",
                            "url": "https://en.wikipedia.org/wiki/Black_hole",
                            "publishedDate": "2026-09-01T00:00:00.000Z",
                            "highlights": ["A  black hole\n is a compact object."],
                        }
                    ]
                },
            )

        results = await self._search_with(handler)

        self.assertEqual(
            results[0],
            {
                "title": "Black hole",
                "snippet": "A black hole is a compact object.",
                "url": "https://en.wikipedia.org/wiki/Black_hole",
                "source": "en.wikipedia.org",
                "published_date": "2026-09-01",
            },
        )
        self.assertEqual(seen_request.headers["x-api-key"], "test-key")
        sent = json.loads(seen_request.content)
        self.assertEqual(sent["query"], "black hole")
        self.assertEqual(sent["numResults"], 3)
        self.assertEqual(sent["type"], "fast")
        self.assertEqual(sent["excludeDomains"], ["wikipedia.org"])
        self.assertEqual(sent["contents"], {"highlights": True})

    async def test_missing_highlight_yields_empty_snippet(self):
        def handler(_request):
            return httpx.Response(
                200,
                json={"results": [{"title": "No highlight", "url": "https://example.com/a"}]},
            )

        results = await self._search_with(handler)

        self.assertEqual(results[0]["snippet"], "")
        self.assertIsNone(results[0]["published_date"])
        self.assertEqual(results[0]["source"], "example.com")

    async def test_skips_results_missing_title_or_url(self):
        def handler(_request):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"title": "", "url": "https://example.com/a"},
                        {"title": "No URL"},
                        {"title": "http only", "url": "http://example.com/a"},
                        {"title": "Good", "url": "https://example.com/b", "highlights": ["fine"]},
                    ]
                },
            )

        results = await self._search_with(handler)

        self.assertEqual([r["title"] for r in results], ["Good"])

    async def test_empty_results_field_is_empty_list(self):
        def handler(_request):
            return httpx.Response(200, json={"results": []})

        results = await self._search_with(handler)

        self.assertEqual(results, [])

    async def test_snippet_is_bounded_for_voice_tool_payloads(self):
        long_highlight = ("encyclopedic detail " * 40).strip()

        def handler(_request):
            return httpx.Response(
                200,
                json={"results": [{"title": "Topic", "url": "https://example.com/a", "highlights": [long_highlight]}]},
            )

        results = await self._search_with(handler)

        self.assertLessEqual(len(results[0]["snippet"]), 400)
        self.assertTrue(results[0]["snippet"].endswith("…"))

    async def test_http_failure_raises_typed_error(self):
        def handler(_request):
            return httpx.Response(503, json={"error": "unavailable"})

        with self.assertRaises(web_search.WebSearchError) as caught:
            await self._search_with(handler)

        self.assertEqual(caught.exception.status_code, 503)

    async def test_transport_failure_raises_typed_error(self):
        def handler(request):
            raise httpx.ConnectError("offline", request=request)

        with self.assertRaises(web_search.WebSearchError) as caught:
            await self._search_with(handler)

        self.assertIsNone(caught.exception.status_code)

    async def test_invalid_json_raises_typed_error(self):
        def handler(_request):
            return httpx.Response(200, content=b"not-json")

        with self.assertRaises(web_search.WebSearchError) as caught:
            await self._search_with(handler)

        self.assertEqual(caught.exception.status_code, 200)

    async def test_exa_error_payload_raises_typed_error(self):
        def handler(_request):
            return httpx.Response(200, json={"error": "invalid query"})

        with self.assertRaisesRegex(web_search.WebSearchError, "invalid query"):
            await self._search_with(handler)

    async def test_rejects_unsupported_language_without_a_request(self):
        def handler(_request):
            self.fail("No HTTP request should be attempted")

        with self.assertRaises(ValueError):
            await self._search_with(handler, language="fr")

    async def test_rejects_excessive_limit_without_a_request(self):
        def handler(_request):
            self.fail("No HTTP request should be attempted")

        with self.assertRaises(ValueError):
            await self._search_with(handler, limit=6)

    async def test_missing_api_key_raises_typed_error_without_a_request(self):
        def handler(_request):
            self.fail("No HTTP request should be attempted")

        with self.assertRaises(web_search.WebSearchError):
            await self._search_with(handler, api_key="")


if __name__ == "__main__":
    unittest.main()
