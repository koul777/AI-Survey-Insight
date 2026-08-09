from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from survey_insight.evaluation import evaluate_sentiment_csv, evaluate_sentiment_rows


class SentimentEvaluationTests(unittest.TestCase):
    def test_labeled_rows_produce_confusion_and_macro_f1_without_raw_text(self) -> None:
        secret_text = "만족하고 도움이 됩니다"
        report = evaluate_sentiment_rows(
            [
                {"response": secret_text, "gold": "positive"},
                {"response": "업무가 과중하고 불편합니다", "gold": "negative"},
                {"response": "관련 내용을 확인했습니다", "gold": "neutral"},
                {"response": "만족하지만 개선이 필요합니다", "gold": "mixed"},
                {"response": "", "gold": "neutral"},
                {"response": "라벨 오류", "gold": "unsupported"},
            ],
            text_column="response",
            label_column="gold",
        )
        self.assertEqual(report["evaluated_count"], 4)
        self.assertEqual(report["skipped_empty_text"], 1)
        self.assertEqual(report["skipped_invalid_label"], 1)
        self.assertIn("macro_f1", report)
        self.assertIn("confusion_matrix", report)
        self.assertNotIn(secret_text, json.dumps(report, ensure_ascii=False))

    def test_csv_evaluation_writes_aggregate_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "labeled.csv"
            target = Path(tmp) / "report.json"
            source.write_text("response,gold\n만족합니다,positive\n불편합니다,negative\n", encoding="utf-8")
            evaluate_sentiment_csv(source, target, text_column="response", label_column="gold")
            payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["evaluated_count"], 2)
        self.assertEqual(payload["method"], "rule_lexicon_fallback")

    def test_no_valid_gold_rows_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "gold label"):
            evaluate_sentiment_rows(
                [{"response": "응답", "gold": "unknown"}],
                text_column="response",
                label_column="gold",
            )


if __name__ == "__main__":
    unittest.main()
