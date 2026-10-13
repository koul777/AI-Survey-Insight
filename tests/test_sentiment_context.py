"""Authored adversarial regressions, not an independent accuracy benchmark."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from survey_insight.models import TextDocument
from survey_insight.preprocessing import normalize_text
from survey_insight.sentiment import (
    aggregate_document_sentiment,
    aggregate_topic_sentiment,
    analyze_text_sentiment,
    sentiment_payload,
)


# These sentences are written for this test suite; they contain no user data.
CONTEXT_CASES = [
    ("부족한 점이 없습니다.", "positive"),
    ("불편한 점은 전혀 없었습니다.", "positive"),
    ("불만이 없는 것은 아닙니다.", "negative"),
    ("안 좋은 것은 아닙니다.", "positive"),
    ("만족스럽다고 할 수 없습니다.", "negative"),
    ("좋다고 보기는 어렵습니다.", "negative"),
    ("불편하다고 느끼지 않습니다.", "positive"),
    ("친절하다고 생각하지 않습니다.", "negative"),
    ("불편함이 해결되었습니다.", "positive"),
    ("불편함이 해결되지 않았습니다.", "negative"),
    ("불만을 해소해 주셔서 감사합니다.", "positive"),
    ("좋은 강의 자료가 없습니다.", "negative"),
    ("친절한 직원이 없습니다.", "negative"),
    ("불편한 절차가 없어졌습니다.", "positive"),
    ("자료는 좋고 설명은 친절하지 않습니다.", "mixed"),
    ("자료는 좋습니다. 안내는 친절하지 않습니다.", "mixed"),
    ("좋지는 않지만 그렇다고 나쁘지도 않습니다.", "mixed"),
    ("안내가 부족하고 직원도 친절하지 않습니다.", "negative"),
    ("문제없이 이용했습니다.", "positive"),
    ("업무에 도움이 되지 않았습니다.", "negative"),
    ("문제 해결이 필요합니다.", "negative"),
    ("불편을 해소해 주세요.", "negative"),
    ("친절하게 안내해 주세요.", "neutral"),
    ("자료가 충분했으면 합니다.", "neutral"),
    ("더 안전한 환경을 바랍니다.", "neutral"),
    ("교육이 좋아지기를 바랍니다.", "neutral"),
    ("안전 교육은 다음 주에 진행합니다.", "neutral"),
    ("감사 자료를 내일까지 제출합니다.", "neutral"),
    ("감사 결과를 공유했습니다.", "neutral"),
    ("문제 풀이 시간을 안내합니다.", "neutral"),
    ("실패 사례를 분석하는 교육입니다.", "neutral"),
    ("업무 지침을 확인했습니다.", "neutral"),
    ("위험 요인을 조사합니다.", "neutral"),
    ("만족도 조사를 실시합니다.", "neutral"),
    ("어려운 내용도 쉽게 설명해 주셨습니다.", "mixed"),
    ("매우 만족하고 적극 추천합니다.", "positive"),
    ("전혀 부담스럽지 않고 편안합니다.", "positive"),
    ("일정이 갑자기 변경되어 불편했습니다.", "negative"),
    ("직원은 친절하지만 처리 속도는 느립니다.", "mixed"),
    ("업무가 많아 몸도 마음도 지칩니다.", "negative"),
]

REVIEW_CASES = [
    "서비스가 좋다는 말에 동의하지 않습니다.",
    "친절하다는 평가가 맞는지 모르겠습니다.",
    "직원이 '불친절하다'고 누군가 말했습니다.",
    "주변에서는 시설이 좋다고 하더군요.",
    "이렇게 늦게 처리해 주시니 참 좋네요.",
    "이게 정말 좋은 서비스입니까?",
    "개선될 거라고 생각했는데 잘 모르겠습니다.",
    "나쁘다고 말할 정도는 아닙니다.",
]


class KoreanSentimentContextTests(unittest.TestCase):
    def test_aggregate_preserves_review_count_for_texts_and_saved_documents(self) -> None:
        texts = ["교육에 만족합니다.", "서비스가 좋다는 말에 동의하지 않습니다.", "친절하게 안내해 주세요."]
        aggregate = aggregate_topic_sentiment(texts)
        self.assertEqual(aggregate.count, 3)
        self.assertEqual(aggregate.review_count, 2)
        documents = [TextDocument(str(index), index, "text", text, text, {})
                     for index, text in enumerate(texts)]
        for document in documents:
            document.sentiment = sentiment_payload(analyze_text_sentiment(document.redacted_text))
        with patch("survey_insight.sentiment.analyze_text_sentiment", side_effect=AssertionError("use saved analysis")):
            persisted = aggregate_document_sentiment(documents)
        self.assertEqual(persisted.review_count, 2)
        self.assertEqual(persisted.label_counts, aggregate.label_counts)
        self.assertEqual(aggregate_topic_sentiment([]).review_count, 0)

    def test_authored_context_challenge(self) -> None:
        for text, expected in CONTEXT_CASES:
            with self.subTest(text=text):
                result = analyze_text_sentiment(text)
                self.assertEqual(result.polarity_label, expected)
                for evidence in result.evidence_spans:
                    self.assertEqual(normalize_text(text)[evidence.start:evidence.end], evidence.text)

    def test_ambiguous_statements_require_review(self) -> None:
        for text in REVIEW_CASES:
            with self.subTest(text=text):
                result = analyze_text_sentiment(text)
                self.assertTrue(result.needs_review)
                self.assertTrue(result.review_reasons)

    def test_scoped_rules_preserve_minimal_pairs(self) -> None:
        cases = [
            ("좋은 환경에서 불편함 없이 근무합니다.", "positive"),
            ("친절한 직원에게 도움을 받지 못했습니다.", "mixed"),
            ("불편함이 해결된 것은 아닙니다.", "negative"),
            ("불편함이 해결되는 방법을 알려 주세요.", "negative"),
            ("좋다고는 생각하지 않지만 나쁘지도 않습니다.", "mixed"),
            ("감사합니다. 안전하게 잘 도착했습니다.", "positive"),
            ("야근 때문에 지쳐 있습니다.", "negative"),
            ("안전한 교육 시설입니다.", "positive"),
            ("안전 교육이 지루합니다.", "negative"),
            ("좋은 시설에서 친절하게 안내해 주세요.", "positive"),
            ("불편 해결 방법을 검토합니다.", "negative"),
            ("불만 해소 계획을 작성했습니다.", "negative"),
            ("교육이 유익하지 못했습니다.", "negative"),
            ("친절한 직원이 없지 않았습니다.", "positive"),
            ("좋은 점도 없지는 않아요.", "positive"),
            ("좋은 시설을 원하지 않습니다.", "neutral"),
            ("좋은 시설이 불편하지 않습니다.", "positive"),
            ("좋은 자료가 나쁘지 않습니다.", "positive"),
            ("나쁘다고 보기는 어렵습니다.", "positive"),
            ("불편하다고 말하기는 어렵습니다.", "positive"),
            ("친절하다고 말하기는 어렵습니다.", "negative"),
            ("교육이 업무에 도움이 안 됩니다.", "negative"),
            ("평가 제도에 신뢰가 안 갑니다.", "negative"),
            ("말도 안 되게 유익한 교육이었습니다.", "positive"),
            ("말도 안 되게 불편한 절차였습니다.", "negative"),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(analyze_text_sentiment(text).polarity_label, expected)

    def test_hypothetical_complaint_does_not_create_urgency(self) -> None:
        result = analyze_text_sentiment("불편하면 말씀하세요.")
        self.assertEqual(result.polarity_label, "neutral")
        self.assertEqual(result.urgency_score, 0)
        self.assertIn("hypothetical", result.review_reasons)

    def test_irony_review_does_not_cross_sentence_or_contrast(self) -> None:
        for text in ["처리가 늦어서 불편했습니다. 직원은 참 좋았습니다.",
                     "처리는 늦지만 직원은 참 좋았습니다."]:
            with self.subTest(text=text):
                result = analyze_text_sentiment(text)
                self.assertEqual(result.polarity_label, "mixed")
                self.assertNotIn("possible_irony", result.review_reasons)

    def test_negation_templates_apply_across_lexicon_entries(self) -> None:
        for stem, polarity in [("친절", "positive"), ("유익", "positive"),
                               ("편리", "positive"), ("불편", "negative"),
                               ("불공정", "negative"), ("부적절", "negative")]:
            inverse = "negative" if polarity == "positive" else "positive"
            cases = [
                (f"{stem}한 부분이 없습니다.", inverse),
                (f"{stem}한 부분이 없지는 않습니다.", polarity),
                (f"{stem}하다고 보기 어렵습니다.", inverse),
                (f"{stem}하다고 생각하지 않습니다.", inverse),
            ]
            for text, expected in cases:
                with self.subTest(text=text):
                    self.assertEqual(analyze_text_sentiment(text).polarity_label, expected)

    def test_rules_have_separate_provenance_from_lexicon(self) -> None:
        result = analyze_text_sentiment("교육에 만족합니다.")
        self.assertEqual(result.rules_version, "1.1.0")
        self.assertEqual(result.lexicon_version, "1.0.0")


if __name__ == "__main__":
    unittest.main()
