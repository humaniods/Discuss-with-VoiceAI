import unittest
from unittest.mock import AsyncMock, patch

import main
import sentiment


class FallbackSentimentTests(unittest.TestCase):
    def test_positive_english(self):
        result = sentiment._fallback("This is amazing, thank you!")
        self.assertEqual(result.sentiment, "POSITIVE")

    def test_negative_hinglish(self):
        result = sentiment._fallback("Yeh bahut bekar hai, main pareshan hoon.")
        self.assertEqual(result.sentiment, "NEGATIVE")

    def test_negated_positive_word(self):
        result = sentiment._fallback("This is not good.")
        self.assertEqual(result.sentiment, "NEGATIVE")

    def test_factual_question_is_neutral(self):
        result = sentiment._fallback("How does a black hole form?")
        self.assertEqual(result.sentiment, "NEUTRAL")


class GatewaySentimentTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_gateway_result(self):
        gateway = AsyncMock(return_value="POSITIVE")
        with patch.object(sentiment.config, "MOCK_MODE", False), patch.object(sentiment, "chat_text", gateway):
            result = await sentiment.analyze("Thanks, that really helped.")

        self.assertEqual(result.sentiment, "POSITIVE")
        self.assertEqual(result.source, "assemblyai_llm_gateway")
        gateway.assert_awaited_once()
        self.assertEqual(gateway.await_args.kwargs["model"], sentiment.config.SENTIMENT_MODEL)

    async def test_invalid_gateway_label_falls_back(self):
        gateway = AsyncMock(return_value="MIXED")
        with patch.object(sentiment.config, "MOCK_MODE", False), patch.object(sentiment, "chat_text", gateway):
            result = await sentiment.analyze("This is a factual statement.")

        self.assertEqual(result.sentiment, "NEUTRAL")
        self.assertEqual(result.source, "local_fallback")

    async def test_mock_mode_never_calls_gateway(self):
        gateway = AsyncMock(side_effect=AssertionError("Gateway must not be called"))
        with patch.object(sentiment.config, "MOCK_MODE", True), patch.object(sentiment, "chat_text", gateway):
            result = await sentiment.analyze("Bahut badhiya!")

        self.assertEqual(result.sentiment, "POSITIVE")
        self.assertEqual(result.source, "local_fallback")
        gateway.assert_not_awaited()


class SentimentEndpointValidationTests(unittest.TestCase):
    def test_blank_text_is_rejected(self):
        with self.assertRaises(ValueError):
            main.SentimentIn(item_id="turn-1", text="   ", speaker="user")

    def test_unknown_speaker_is_rejected(self):
        with self.assertRaises(ValueError):
            main.SentimentIn(item_id="turn-1", text="Hello", speaker="system")


if __name__ == "__main__":
    unittest.main()
