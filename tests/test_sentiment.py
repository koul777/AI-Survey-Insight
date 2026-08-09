from __future__ import annotations

import unittest

from survey_insight.sentiment import analyze_text_sentiment, aggregate_topic_sentiment


class SentimentTests(unittest.TestCase):
    def test_positive_korean_hr_feedback(self) -> None:
        result = analyze_text_sentiment("교육 과정이 체계적이고 업무에 도움이 되어 만족합니다.")

        self.assertEqual(result.polarity_label, "positive")
        self.assertGreater(result.polarity_score, 0)
        self.assertEqual(result.urgency_score, 0.0)
        self.assertEqual(result.source, "rule_lexicon_fallback")
        self.assertIn("체계적", result.evidence_terms)
        self.assertIn("도움", result.evidence_terms)
        self.assertIn("만족", result.evidence_terms)

    def test_negative_korean_hr_feedback(self) -> None:
        result = analyze_text_sentiment("절차가 복잡하고 안내가 부족해서 불만이 많습니다.")

        self.assertEqual(result.polarity_label, "negative")
        self.assertLess(result.polarity_score, 0)
        self.assertIn("복잡", result.evidence_terms)
        self.assertIn("부족", result.evidence_terms)
        self.assertIn("불만", result.evidence_terms)

    def test_mixed_feedback_keeps_both_sides(self) -> None:
        result = analyze_text_sentiment("제도는 좋지만 신청 과정이 복잡하고 개선이 필요합니다.")

        self.assertEqual(result.polarity_label, "mixed")
        self.assertIn("좋", result.evidence_terms)
        self.assertIn("복잡", result.evidence_terms)
        self.assertIn("개선", result.evidence_terms)
        self.assertIn("필요", result.evidence_terms)

    def test_neutral_feedback_without_evidence_terms(self) -> None:
        result = analyze_text_sentiment("이번 분기에는 특별한 의견이 없습니다.")

        self.assertEqual(result.polarity_label, "neutral")
        self.assertEqual(result.polarity_score, 0.0)
        self.assertEqual(result.urgency_score, 0.0)
        self.assertEqual(result.evidence_terms, ())

    def test_simple_korean_negation_suppresses_false_polarity(self) -> None:
        positive_negated = analyze_text_sentiment("현재 교육에는 만족하지 않습니다.")
        negative_negated = analyze_text_sentiment("신청 절차가 더 이상 불편하지 않습니다.")

        self.assertEqual(positive_negated.polarity_label, "neutral")
        self.assertNotIn("만족", positive_negated.evidence_terms)
        self.assertEqual(negative_negated.polarity_label, "neutral")
        self.assertNotIn("불편", negative_negated.evidence_terms)

    def test_bulmanjok_does_not_double_count_positive_satisfaction(self) -> None:
        result = analyze_text_sentiment("평가 결과에 불만족합니다.")

        self.assertEqual(result.polarity_label, "negative")
        self.assertIn("불만", result.evidence_terms)
        self.assertNotIn("만족", result.evidence_terms)

    def test_urgency_uses_complaint_and_urgency_terms(self) -> None:
        result = analyze_text_sentiment("갑작스러운 일정 변경이 늦게 공유되어 시급한 개선이 필요합니다.")

        self.assertEqual(result.polarity_label, "negative")
        self.assertGreaterEqual(result.urgency_score, 0.8)
        self.assertIn("갑작", result.evidence_terms)
        self.assertIn("늦", result.evidence_terms)
        self.assertIn("시급", result.evidence_terms)

    def test_aggregate_topic_sentiment(self) -> None:
        aggregate = aggregate_topic_sentiment(
            [
                "교육 과정이 체계적이고 업무에 도움이 되어 만족합니다.",
                "절차가 복잡하고 안내가 부족해서 불만이 많습니다.",
                "갑작스러운 일정 변경이 늦게 공유되어 시급한 개선이 필요합니다.",
            ]
        )

        self.assertEqual(aggregate.count, 3)
        self.assertEqual(aggregate.dominant_label, "negative")
        self.assertEqual(aggregate.label_counts["negative"], 2)
        self.assertLess(aggregate.average_polarity_score, 0)
        self.assertGreater(aggregate.average_urgency_score, 0)
        self.assertIn("체계적", aggregate.evidence_terms)
        self.assertIn("불만", aggregate.evidence_terms)
        self.assertIn("시급", aggregate.evidence_terms)
        self.assertEqual(aggregate.source, "rule_lexicon_fallback")


if __name__ == "__main__":
    unittest.main()
