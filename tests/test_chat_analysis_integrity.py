from __future__ import annotations

import unittest

from survey_insight.chat_preprocessing import prepare_kakao_chat_rows
from survey_insight.models import TableData, TextDocument, Topic, TopicAssignment
from survey_insight.pipeline import analyze_table, build_cross_analysis


def chat_row(message: str, time: str = "09:00", author: str = "작성자") -> dict:
    return {"날짜": "2026-10-13", "시간": time, "작성자": author, "메시지": message, "유형": "메시지"}


class ChatAnalysisIntegrityTests(unittest.TestCase):
    def test_short_substantive_messages_survive_and_source_rows_are_traceable(self) -> None:
        messages = ["네", "불편해요", "임금체불", "앱 오류", "사진", "ㅋㅋㅋㅋ", "교육 좋아요"]
        segments, stats = prepare_kakao_chat_rows([chat_row(message) for message in messages])
        self.assertEqual(stats["retained_messages"], 4)
        self.assertEqual(segments[0]["_source_row_indices"], [2, 3, 4, 7])
        self.assertEqual(segments[0]["원문메시지수"], 4)
        for message in ("불편해요", "임금체불", "앱 오류"):
            self.assertIn(message, segments[0]["메시지"])

    def test_time_reversal_starts_a_new_context_without_reordering_input(self) -> None:
        segments, _ = prepare_kakao_chat_rows([
            chat_row("교육 자료", "10:00"), chat_row("급여 지급", "09:00")])
        self.assertEqual(len(segments), 2)
        self.assertEqual([row["_source_row_indices"] for row in segments], [[1], [2]])

    def test_long_normalized_reactions_remain_noise(self) -> None:
        segments, stats = prepare_kakao_chat_rows([chat_row("ㅋㅋㅋㅋㅋㅋㅋㅋ"), chat_row("ㅠㅠㅠㅠㅠㅠ")])
        self.assertEqual(segments, [])
        self.assertEqual(stats["noise_rows_removed"], 2)

    def test_invalid_segmentation_parameters_are_rejected(self) -> None:
        for parameter in ("max_messages_per_segment", "max_chars_per_segment", "inactivity_minutes"):
            with self.subTest(parameter=parameter), self.assertRaises(ValueError):
                prepare_kakao_chat_rows([], **{parameter: 0})

    def test_chat_units_and_mixed_authors_are_explicit(self) -> None:
        rows = [chat_row("교육에 만족합니다", author="A"),
                chat_row("교육 시설이 불편합니다", author="B")]
        package = analyze_table(TableData(list(rows[0]), rows), text_column="메시지", group_columns=["작성자"])
        summary = package.recommendation.sentiment_summary
        self.assertEqual(summary["analysis_unit"], "context_segment")
        self.assertEqual(summary["analyzed_count"], 1)
        self.assertEqual(summary["source_message_count"], 2)
        self.assertEqual(package.documents[0].metadata["_source_row_indices"], [1, 2])
        self.assertEqual(package.group_columns, [])
        self.assertEqual(package.cross_analysis, [])
        self.assertTrue(any("발화자" in warning for warning in package.recommendation.warnings))

    def test_cross_analysis_suppresses_every_small_cell_measure_and_excludes_outliers(self) -> None:
        documents = [TextDocument(str(i), i + 1, "response", "교육", "교육", {"group": "A"}) for i in range(8)]
        topics = [Topic("T1", "교육", "교육", 6, 1.0, ["교육"], [])]
        assignments = [TopicAssignment(doc.id, "T1", 1.0, False, "test") for doc in documents[:6]]
        assignments.extend([
            TopicAssignment(documents[6].id, "OUTLIER", 0.0, True, "test"),
            TopicAssignment(documents[7].id, "deleted_topic", 0.0, False, "test"),
        ])
        documents[0].metadata["group"] = "B"
        rows = build_cross_analysis(documents, assignments, topics, ["group"])
        self.assertEqual(len(rows), 2)
        small = next(row for row in rows if row["group_value"] == "B")
        for field in ("count", "display_count", "share", "sentiment_counts"):
            self.assertIsNone(small[field])
        large = next(row for row in rows if row["group_value"] == "A")
        self.assertEqual(large["count"], 5)
        self.assertEqual(large["share"], 1.0)

    def test_group_ratios_do_not_reveal_a_suppressed_sibling_cell(self) -> None:
        documents = [TextDocument(str(i), i + 1, "response", "교육", "교육", {"group": "A"}) for i in range(6)]
        topics = [Topic("T1", "교육", "", 5, 5 / 6, [], []), Topic("T2", "급여", "", 1, 1 / 6, [], [])]
        assignments = [TopicAssignment(doc.id, "T1" if i < 5 else "T2", 1.0, False, "test")
                       for i, doc in enumerate(documents)]
        rows = build_cross_analysis(documents, assignments, topics, ["group"])
        self.assertTrue(all(row["share"] is None for row in rows))
        self.assertEqual(next(row for row in rows if row["topic_id"] == "T1")["count"], 5)

    def test_missing_legacy_sentiment_is_unavailable_not_all_zero(self) -> None:
        documents = [TextDocument(str(i), i + 1, "response", "교육", "교육", {"group": "A"}) for i in range(6)]
        topics = [Topic("T1", "교육", "", 6, 1.0, [], [])]
        assignments = [TopicAssignment(doc.id, "T1", 1.0, False, "test") for doc in documents]
        documents[0].sentiment = {"polarity_label": "positive"}
        row = build_cross_analysis(documents, assignments, topics, ["group"])[0]
        self.assertEqual(row["count"], 6)
        self.assertIsNone(row["sentiment_counts"])


if __name__ == "__main__":
    unittest.main()
