from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from survey_insight.embeddings import _post_embeddings, embed_texts_with_provider


class EmbeddingsProviderTests(unittest.TestCase):
    def test_network_disable_flag_blocks_real_http_transport(self) -> None:
        with patch.dict(os.environ, {"SURVEY_INSIGHT_DISABLE_NETWORK": "1"}), patch(
            "survey_insight.embeddings.urllib.request.urlopen"
        ) as urlopen:
            with self.assertRaises(RuntimeError):
                _post_embeddings("secret", "https://example.invalid", "bearer", {"input": []})
        urlopen.assert_not_called()

    def test_placeholder_key_never_calls_provider(self) -> None:
        with patch("survey_insight.embeddings._post_embeddings") as post:
            result = embed_texts_with_provider(["평가 기준 개선"], "openai", "sk-test-placeholder")

        post.assert_not_called()
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.source, "embedding_unavailable")
        self.assertTrue(any("예시 API Key" in warning for warning in result.warnings))

    def test_gemini_embeddings_are_requested_with_clustering_task(self) -> None:
        calls: list[tuple[str, str, dict[str, object]]] = []

        def fake_post(api_key: str, url: str, header_mode: str, payload: dict[str, object]) -> dict[str, object]:
            calls.append((url, header_mode, payload))
            index = len(calls) - 1
            values = [1.0, 0.0, 0.0] if index == 0 else [0.0, 1.0, 0.0]
            return {"embedding": {"values": values}}

        with patch("survey_insight.embeddings._post_embeddings", side_effect=fake_post):
            result = embed_texts_with_provider(
                ["평가 기준이 모호합니다", "복지와 연차 사용이 좋습니다"],
                "gemini",
                "AIzaSyLiveKeyabcdef1234567890abcdef1234567890",
            )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.source, "gemini_embeddings")
        self.assertEqual(result.model, "gemini-embedding-001")
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.vectors.shape, (2, 3))
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0][0].endswith("/models/gemini-embedding-001:embedContent"))
        self.assertEqual(calls[0][1], "gemini")
        self.assertEqual(calls[0][2]["taskType"], "CLUSTERING")

    def test_claude_embeddings_fall_back_to_local_topic_models(self) -> None:
        result = embed_texts_with_provider(
            ["평가 기준이 모호합니다"],
            "claude",
            "sk-ant-api03-livekeyabcdef1234567890abcdef1234567890",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.source, "embedding_unavailable")
        self.assertEqual(result.vectors.size, 0)
        self.assertTrue(any("Claude" in warning for warning in result.warnings))

    def test_provider_failure_returns_safe_local_fallback(self) -> None:
        secret = "sk-live-secret-value-abcdef1234567890"
        with patch(
            "survey_insight.embeddings._post_embeddings",
            side_effect=RuntimeError(f"remote body contained {secret}"),
        ):
            result = embed_texts_with_provider(["평가 기준 개선"], "openai", secret)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.source, "embedding_unavailable")
        warning = " ".join(result.warnings)
        self.assertIn("로컬 토픽모델", warning)
        self.assertNotIn(secret, warning)
        self.assertNotIn("remote body", warning)


if __name__ == "__main__":
    unittest.main()
