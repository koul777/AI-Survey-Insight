from __future__ import annotations

import unittest

from survey_insight.ingestion import load_table_bytes


class IngestionTests(unittest.TestCase):
    def test_plain_txt_treats_each_non_empty_line_as_a_response(self) -> None:
        table = load_table_bytes(
            "교육이 유익했습니다.\n\n실습 시간이 더 필요합니다.\n".encode("utf-8"),
            "responses.txt",
        )

        self.assertEqual(table.headers, ["response"])
        self.assertEqual(
            table.rows,
            [
                {"response": "교육이 유익했습니다."},
                {"response": "실습 시간이 더 필요합니다."},
            ],
        )
        self.assertEqual(table.source_name, "responses.txt")

    def test_tab_delimited_txt_is_loaded_as_a_table(self) -> None:
        table = load_table_bytes(
            "department\tfeedback\n인사\t교육이 좋았습니다\n개발\t실습을 늘려주세요\n".encode("utf-8"),
            "responses.txt",
        )

        self.assertEqual(table.headers, ["department", "feedback"])
        self.assertEqual(table.rows[0]["department"], "인사")
        self.assertEqual(table.rows[1]["feedback"], "실습을 늘려주세요")

    def test_incidental_tab_does_not_turn_plain_text_into_a_table(self) -> None:
        table = load_table_bytes(
            "첫 번째 응답\n들여쓰기\t하나가 있는 응답\n세 번째 응답\n".encode("utf-8"),
            "responses.txt",
        )

        self.assertEqual(table.headers, ["response"])
        self.assertEqual(len(table.rows), 3)
        self.assertEqual(table.rows[1]["response"], "들여쓰기\t하나가 있는 응답")

    def test_utf16_txt_is_decoded(self) -> None:
        table = load_table_bytes("첫 번째 응답\n두 번째 응답".encode("utf-16"), "responses.txt")

        self.assertEqual([row["response"] for row in table.rows], ["첫 번째 응답", "두 번째 응답"])

    def test_kakao_message_csv_keeps_the_explicit_first_header_row(self) -> None:
        data = (
            "날짜,시간,작성자,메시지,유형\n"
            "2026-09-07,,,입장했습니다,시스템\n"
            "2026-09-07,09:00,사용자,첫 메시지,메시지\n"
            "2026-09-07,09:01,사용자,두 번째 메시지,메시지\n"
        ).encode("utf-8-sig")

        table = load_table_bytes(data, "KakaoTalk_messages.csv")

        self.assertEqual(table.header_row_index, 0)
        self.assertEqual(table.headers, ["날짜", "시간", "작성자", "메시지", "유형"])
        self.assertEqual(table.rows[1]["메시지"], "첫 메시지")


if __name__ == "__main__":
    unittest.main()
