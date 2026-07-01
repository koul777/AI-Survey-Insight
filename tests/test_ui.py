from __future__ import annotations

import unittest

from survey_insight.ui import app_html


class UiHtmlTests(unittest.TestCase):
    def test_app_html_contains_core_controls(self) -> None:
        html = app_html()
        expected_fragments = [
            'class="brand-mark"',
            "토픽모델링 · 감정분석 · 보고서 자동화",
            'id="fileInput"',
            'id="uploadBtn"',
            'id="textColumn"',
            'id="groupColumns"',
            'id="llmProvider"',
            'id="llmApiKey"',
            'id="llmBaseUrl"',
            'id="modelSelectField"',
            'id="llmModelSelect"',
            'id="llmModelCustomField"',
            'id="llmModel"',
            'id="embeddingModelField"',
            'id="embeddingModel"',
            'id="azureApiVersion"',
            "정밀 분석 Provider",
            "Gemini",
            "Claude",
            "OpenAI",
            "Azure OpenAI",
            "OpenAI 호환 서버",
            "gpt-5.5",
            "gpt-5.4-mini",
            "gemini-3.5-flash",
            "gemini-3.1-pro-preview",
            "claude-sonnet-5",
            "claude-opus-4-8",
            "Claude Haiku 4.5",
            "직접 입력",
            "MODEL_OPTIONS",
            "selectedChatModel()",
            "토픽 임베딩/감정/해석 실행 시에만 전송",
            "저장하지 않음",
            '$("llmApiKey").value = "";',
            '$("llmProvider").value === "claude" ? null : $("embeddingModel").value || null',
            'id="runBtn"',
            'class="tabs"',
            'data-tab="profile"',
            'data-tab="recommendation"',
            'data-tab="topics"',
            'id="excelBtn"',
            "Excel 생성",
            'id="wordBtn"',
            "Word 생성",
            'id="powerpointBtn"',
            "PowerPoint 생성",
        ]
        for fragment in expected_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, html)

    def test_app_html_contains_history_panel_support(self) -> None:
        html = app_html()
        expected_fragments = [
            'data-tab="history"',
            'id="historyList"',
            'id="historyStatus"',
            'id="historyRefreshBtn"',
            'fetch("/projects/recent")',
            "최근 분석 이력이 없습니다.",
        ]
        for fragment in expected_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, html)

    def test_app_html_contains_plain_language_result_slots(self) -> None:
        html = app_html()
        expected_fragments = [
            'id="recommendationExplanation"',
            "전체 토픽 표",
            "추천된 모든 토픽",
            "topicTable(topics)",
            "감정 상세",
            "sentimentDetail(topic",
            "감정 강도",
            "처리 우선도",
            "전체 토픽을 처리 우선순위대로 정렬",
            "쉽게 읽는 해석",
            "토픽 수를 정한 이유",
            "읽을 때 주의할 점",
            "plain_language_summary",
            "suggested_action",
            "sentiment_plain_language",
            "대응 방안",
            "감정 해석",
        ]
        for fragment in expected_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, html)
        removed_fragments = [
            'id="generateTopicImages"',
            "요약 이미지",
            "generate_topic_images",
            "summary-visual-card",
        ]
        for fragment in removed_fragments:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, html)
        self.assertNotIn(".sort((a, b) => priorityScore(b) - priorityScore(a))\n        .slice(0, 3)", html)

    def test_app_html_renders_without_python_formatting_errors(self) -> None:
        try:
            html = app_html()
        except (IndexError, KeyError, ValueError) as exc:
            self.fail(f"app_html raised a Python formatting error: {exc}")
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertTrue(html.rstrip().endswith("</html>"))
        self.assertIn("* { box-sizing: border-box; }", html)
        self.assertIn("${", html)


if __name__ == "__main__":
    unittest.main()
