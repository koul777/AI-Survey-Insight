from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from survey_insight.cli import create_demo_workbook
from survey_insight.llm_interpretation import enhance_with_user_llm
from survey_insight.pipeline import analyze_file


class LlmInterpretationTests(unittest.TestCase):
    def _package(self):
        with tempfile.TemporaryDirectory() as tmp:
            workbook_path = Path(tmp) / "demo.xlsx"
            create_demo_workbook(workbook_path)
            return analyze_file(workbook_path)

    def _fake_content(self, topic_id: str) -> dict[str, object]:
        return {
            "plain_language_summary": "응답을 읽기 쉬운 주제 묶음으로 정리했습니다.",
            "topic_count_explanation": "여러 후보를 비교해 가장 균형 잡힌 토픽 수를 선택했습니다.",
            "methodology_plain_language": "키워드와 대표 응답을 함께 보고 토픽을 해석했습니다.",
            "topics": [
                {
                    "topic_id": topic_id,
                    "label": "평가 제도 개선",
                    "summary": "평가 기준과 절차에 대한 개선 요구입니다.",
                    "plain_language_summary": "평가 기준이 명확하지 않다는 의견 묶음입니다.",
                    "suggested_action": "평가 기준 안내와 이의제기 절차를 강화하세요.",
                    "sentiment_label": "negative",
                    "sentiment_score": -0.68,
                    "sentiment_plain_language": "불만 표현과 개선 요구가 함께 나타납니다.",
                    "urgency_score": 0.72,
                    "sentiment_evidence": ["불만", "개선", "기준"],
                }
            ],
        }

    def test_openai_interpretation_updates_sentiment_with_evidence_method(self) -> None:
        package = self._package()
        topic_id = package.selected_topics[0].topic_id
        fake_content = self._fake_content(topic_id)
        fake_response = {"output_text": json.dumps(fake_content, ensure_ascii=False)}

        with patch("survey_insight.llm_interpretation._post_chat_completion", return_value=fake_response) as post:
            warnings = enhance_with_user_llm(
                package,
                "openai",
                "sk-proj-live-shaped-key-abcdef1234567890abcdef1234567890",
            )

        self.assertEqual(warnings, [])
        request_settings = post.call_args.args[1]
        payload = post.call_args.args[2]
        self.assertEqual(request_settings["provider_type"], "openai_responses")
        self.assertEqual(payload["model"], "gpt-5.5")
        self.assertEqual(payload["text"]["format"]["type"], "json_object")
        self.assertIn("instructions", payload)
        topic = package.selected_topics[0]
        self.assertEqual(topic.label, "평가 제도 개선")
        self.assertEqual(topic.sentiment_label, "negative")
        self.assertEqual(topic.sentiment_score, -0.68)
        self.assertEqual(topic.sentiment_method, "openai_llm_evidence")
        self.assertEqual(topic.urgency_score, 0.72)
        self.assertIn("불만", topic.sentiment_evidence)

    def test_gemini_interpretation_uses_generate_content_response_shape(self) -> None:
        package = self._package()
        topic_id = package.selected_topics[0].topic_id
        fake_content = self._fake_content(topic_id)
        fake_response = {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(fake_content, ensure_ascii=False)}]}}
            ]
        }

        with patch("survey_insight.llm_interpretation._post_chat_completion", return_value=fake_response) as post:
            warnings = enhance_with_user_llm(
                package,
                "gemini",
                "AIzaSyLiveKeyabcdef1234567890abcdef1234567890",
                model="gemini-3.5-flash",
            )

        self.assertEqual(warnings, [])
        request_settings = post.call_args.args[1]
        payload = post.call_args.args[2]
        self.assertEqual(request_settings["header_mode"], "gemini")
        self.assertIn("systemInstruction", payload)
        self.assertEqual(payload["generationConfig"]["responseMimeType"], "application/json")
        topic = package.selected_topics[0]
        self.assertEqual(topic.interpretation_source, "gemini_llm")
        self.assertEqual(topic.sentiment_method, "gemini_llm_evidence")

    def test_claude_interpretation_uses_messages_response_shape(self) -> None:
        package = self._package()
        topic_id = package.selected_topics[0].topic_id
        fake_content = self._fake_content(topic_id)
        fake_response = {"content": [{"type": "text", "text": json.dumps(fake_content, ensure_ascii=False)}]}

        with patch("survey_insight.llm_interpretation._post_chat_completion", return_value=fake_response) as post:
            warnings = enhance_with_user_llm(
                package,
                "claude",
                "sk-ant-api03-livekeyabcdef1234567890abcdef1234567890",
                model="claude-sonnet-5",
            )

        self.assertEqual(warnings, [])
        request_settings = post.call_args.args[1]
        payload = post.call_args.args[2]
        self.assertEqual(request_settings["header_mode"], "anthropic")
        self.assertEqual(payload["model"], "claude-sonnet-5")
        self.assertIn("system", payload)
        self.assertNotIn("temperature", payload)
        topic = package.selected_topics[0]
        self.assertEqual(topic.interpretation_source, "claude_llm")
        self.assertEqual(topic.sentiment_method, "claude_llm_evidence")

    def test_malformed_llm_sentiment_does_not_partially_overwrite_fallback_method(self) -> None:
        package = self._package()
        topic = package.selected_topics[0]
        before_label = topic.sentiment_label
        before_method = topic.sentiment_method
        before_urgency = topic.urgency_score
        before_evidence = list(topic.sentiment_evidence)
        fake_content = {
            "topics": [
                {
                    "topic_id": topic.topic_id,
                    "sentiment_label": "very_bad",
                    "urgency_score": 0.99,
                    "sentiment_evidence": ["LLM_ONLY"],
                }
            ]
        }
        fake_response = {"output_text": json.dumps(fake_content, ensure_ascii=False)}

        with patch("survey_insight.llm_interpretation._post_chat_completion", return_value=fake_response):
            warnings = enhance_with_user_llm(
                package,
                "openai",
                "sk-proj-live-shaped-key-abcdef1234567890abcdef1234567890",
            )

        self.assertEqual(warnings, [])
        self.assertEqual(topic.sentiment_label, before_label)
        self.assertEqual(topic.sentiment_method, before_method)
        self.assertEqual(topic.urgency_score, before_urgency)
        self.assertEqual(topic.sentiment_evidence, before_evidence)


if __name__ == "__main__":
    unittest.main()
