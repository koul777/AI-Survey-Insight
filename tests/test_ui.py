from __future__ import annotations

import unittest

from survey_insight.ui import app_html


class UiHtmlTests(unittest.TestCase):
    def test_app_html_contains_core_controls(self) -> None:
        html = app_html()
        expected_fragments = [
            'class="brand-mark"',
            "토픽모델링 · 감정 신호 · 보고서 자동화",
            'id="fileInput"',
            'id="uploadBtn"',
            'id="textColumn"',
            'id="groupColumns"',
            'id="llmProvider"',
            'id="llmApiKey"',
            'id="externalTransferConfirmed"',
            'id="llmBaseUrl"',
            'id="modelSelectField"',
            'id="llmModelSelect"',
            'id="llmModelCustomField"',
            'id="llmModel"',
            'id="embeddingModelField"',
            'id="embeddingModel"',
            'id="azureApiVersion"',
            "선택적 외부 AI 보강",
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
            'id="reviewBtn"',
            "담당자 검토 기록",
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
            "분석 결과 삭제",
            "원본·연결 분석 삭제",
            'method: "DELETE"',
            "이 작업은 되돌릴 수 없습니다.",
        ]
        for fragment in expected_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, html)

    def test_app_html_contains_plain_language_result_slots(self) -> None:
        html = app_html()
        expected_fragments = [
            'id="recommendationExplanation"',
            "전체 토픽 표",
            "권장안의 모든 토픽",
            "topicTable(topics)",
            "감정 신호 상세",
            "sentimentDetail(topic",
            "어휘 극성 신호",
            "처리 우선도",
            "전체 토픽을 처리 우선도 신호순으로 정렬",
            "쉽게 읽는 해석",
            "토픽 수를 정한 이유",
            "읽을 때 주의할 점",
            "plain_language_summary",
            "suggested_action",
            "sentiment_plain_language",
            "대응 방안",
            "감정 해석",
            "권장 토픽 수",
            "군집 품질 종합점수",
            "가중치 시나리오 선정률",
            "Bootstrap 구조 관문 통과율",
            "토픽 해석 가능성 점수",
            "군집 분리도",
            "분석 포함률",
            "토픽 키워드 다양성",
            "KL-NMF 토픽모델",
            "라벨 해석 가능성",
            "구조 관문",
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
        self.assertNotIn("최적 토픽 수", html)

    def test_app_html_contains_privacy_and_methodology_notices(self) -> None:
        html = app_html()
        for fragment in [
            "업로드 원본과 분석 결과는 기본적으로 로컬",
            "외부 AI를 선택하면 마스킹된 응답 또는 대표 의견",
            "API 키는 요청 중에만 사용하고 저장하지 않으며",
            "조직의 위탁처리·국외 이전·보존 정책을 확인했습니다",
            "아직 담당자 검토가 기록되지 않았습니다",
            "preset은 예시",
            "처리 우선도는 자동 판정이 아니라 담당자 검토용 보조정보",
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, html)

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
