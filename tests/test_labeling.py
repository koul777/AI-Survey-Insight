from __future__ import annotations

import unittest

from survey_insight.labeling import (
    CONSERVATIVE_LABEL,
    CONSERVATIVE_SUMMARY,
    OptionalLLMLabeler,
    RuleBasedTopicLabeler,
    get_topic_labeler,
)


class LabelingTests(unittest.TestCase):
    def test_default_labeler_is_rule_based(self) -> None:
        self.assertIsInstance(get_topic_labeler({}), RuleBasedTopicLabeler)

    def test_rule_based_labeler_is_keyword_grounded_and_deterministic(self) -> None:
        labeler = RuleBasedTopicLabeler()
        first = labeler.label_topic(
            ["pay", "benefits", "pay"],
            ["Pay increases and benefits are the recurring concern."],
        )
        second = labeler.label_topic(
            ["pay", "benefits", "pay"],
            ["Pay increases and benefits are the recurring concern."],
        )

        self.assertEqual(first, second)
        self.assertEqual(first.label, "pay/benefits")
        self.assertIn("Evidence keywords: pay, benefits.", first.summary)
        self.assertIn("Pay increases and benefits", first.summary)

    def test_optional_llm_labeler_uses_safe_fallback(self) -> None:
        env = {
            "SURVEY_INSIGHT_TOPIC_LABELER": "llm",
            "SURVEY_INSIGHT_LLM_LABELER_PROVIDER": "example-provider",
            "SURVEY_INSIGHT_LLM_LABELER_MODEL": "example-model",
        }
        selected = get_topic_labeler(env)
        self.assertIsInstance(selected, OptionalLLMLabeler)

        fallback = RuleBasedTopicLabeler().label_topic(
            ["schedule", "staffing"],
            ["Schedules and staffing levels are hard to manage."],
        )
        result = selected.label_topic(
            ["schedule", "staffing"],
            ["Schedules and staffing levels are hard to manage."],
        )

        self.assertEqual(result.label, fallback.label)
        self.assertEqual(result.summary, fallback.summary)
        self.assertEqual(result.source, "optional_llm_fallback")
        self.assertTrue(result.fallback_used)

    def test_empty_evidence_returns_conservative_label(self) -> None:
        result = RuleBasedTopicLabeler().label_topic([], [])

        self.assertEqual(result.label, CONSERVATIVE_LABEL)
        self.assertEqual(result.summary, CONSERVATIVE_SUMMARY)


if __name__ == "__main__":
    unittest.main()
