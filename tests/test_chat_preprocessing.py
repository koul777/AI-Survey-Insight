from __future__ import annotations

import unittest

from survey_insight.chat_preprocessing import prepare_kakao_chat_rows


class KakaoChatPreprocessingTests(unittest.TestCase):
    def test_filters_chat_noise_and_builds_context_segments(self) -> None:
        rows = [
            {"날짜": "2026-09-07", "시간": "09:00", "작성자": "", "메시지": "입장", "유형": "시스템"},
            {"날짜": "2026-09-07", "시간": "09:00", "작성자": "오픈채팅봇", "메시지": "닉네임 변경", "유형": "메시지"},
            {"날짜": "2026-09-07", "시간": "09:01", "작성자": "가", "메시지": "사진", "유형": "메시지"},
            {"날짜": "2026-09-07", "시간": "09:02", "작성자": "가", "메시지": "ㅋㅋㅋㅋ", "유형": "메시지"},
            {"날짜": "2026-09-07", "시간": "09:03", "작성자": "가", "메시지": "공공기관의 AI 예산 확보가 어렵습니다", "유형": "메시지"},
            {"날짜": "2026-09-07", "시간": "09:04", "작성자": "나", "메시지": "보안 검토 절차도 개선이 필요합니다", "유형": "메시지"},
        ]

        segments, stats = prepare_kakao_chat_rows(rows)

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["원문메시지수"], 2)
        self.assertIn("AI 예산", segments[0]["메시지"])
        self.assertIn("보안 검토", segments[0]["메시지"])
        self.assertNotIn("사진", segments[0]["메시지"])
        self.assertEqual(stats["system_rows_removed"], 1)
        self.assertEqual(stats["bot_rows_removed"], 1)
        self.assertEqual(stats["noise_rows_removed"], 2)

    def test_splits_segments_on_message_limit_and_long_inactivity(self) -> None:
        rows = [
            {"날짜": "2026-09-07", "시간": "09:00", "작성자": "가", "메시지": "첫 번째 실질 대화입니다", "유형": "메시지"},
            {"날짜": "2026-09-07", "시간": "09:01", "작성자": "나", "메시지": "두 번째 실질 대화입니다", "유형": "메시지"},
            {"날짜": "2026-09-07", "시간": "10:00", "작성자": "다", "메시지": "새로운 시간대의 대화입니다", "유형": "메시지"},
        ]

        segments, stats = prepare_kakao_chat_rows(rows, max_messages_per_segment=2)

        self.assertEqual(len(segments), 2)
        self.assertEqual([segment["원문메시지수"] for segment in segments], [2, 1])
        self.assertEqual(stats["context_segments"], 2)
