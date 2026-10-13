from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .models import TableData
from .preprocessing import normalize_text


KAKAO_CHAT_HEADERS = {"날짜", "시간", "작성자", "메시지", "유형"}
CHAT_BOT_NAMES = {"오픈채팅봇"}
ATTACHMENT_ONLY = re.compile(r"^(?:사진|동영상|이모티콘|파일)(?:\s*\d+장)?$")
# Include NFKC-normalized Hangul jamo as well as their compatibility forms.
REACTION_ONLY = re.compile(r"^[ㅋㅎㅠㅜ\u110f\u1112\u1172\u116e~!?.…\s]+$")
SHORT_CHAT_NOISE = {
    "네",
    "넵",
    "넹",
    "예",
    "아니요",
    "맞아요",
    "맞습니다",
    "그러게요",
    "그렇군요",
    "그렇네요",
    "저도요",
    "저도",
    "대박",
    "와우",
    "오",
    "아",
    "굿",
    "감사합니다",
    "고맙습니다",
    "안녕하세요",
    "반갑습니다",
    "그거",
    "이거",
    "이것",
    "그것",
}


def is_kakao_chat_table(table: TableData) -> bool:
    return KAKAO_CHAT_HEADERS.issubset(set(table.headers))


def prepare_kakao_chat_rows(
    rows: list[dict[str, Any]],
    *,
    max_messages_per_segment: int = 12,
    max_chars_per_segment: int = 1200,
    inactivity_minutes: int = 20,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if min(max_messages_per_segment, max_chars_per_segment, inactivity_minutes) < 1:
        raise ValueError("대화 구간의 메시지 수·글자 수·시간 간격은 1 이상이어야 합니다.")
    retained: list[dict[str, Any]] = []
    stats = {
        "source_rows": len(rows),
        "system_rows_removed": 0,
        "bot_rows_removed": 0,
        "noise_rows_removed": 0,
        "retained_messages": 0,
        "context_segments": 0,
    }
    for source_row_index, row in enumerate(rows, start=1):
        if normalize_text(row.get("유형")) != "메시지":
            stats["system_rows_removed"] += 1
            continue
        if normalize_text(row.get("작성자")) in CHAT_BOT_NAMES:
            stats["bot_rows_removed"] += 1
            continue
        message = normalize_text(row.get("메시지"))
        if _is_chat_noise(message):
            stats["noise_rows_removed"] += 1
            continue
        retained.append({**row, "메시지": message, "_source_row_index": source_row_index})

    segments: list[dict[str, Any]] = []
    buffer: list[dict[str, Any]] = []
    buffer_chars = 0
    last_timestamp: datetime | None = None

    def flush() -> None:
        nonlocal buffer, buffer_chars, last_timestamp
        if not buffer:
            return
        authors = list(dict.fromkeys(normalize_text(item.get("작성자")) for item in buffer))
        segments.append(
            {
                "날짜": normalize_text(buffer[0].get("날짜")),
                "시간": normalize_text(buffer[0].get("시간")),
                "작성자": ", ".join(author for author in authors if author),
                "메시지": "\n".join(str(item["메시지"]) for item in buffer),
                "유형": "대화구간",
                "원문메시지수": len(buffer),
                "_source_row_indices": [item["_source_row_index"] for item in buffer],
            }
        )
        buffer = []
        buffer_chars = 0
        last_timestamp = None

    for row in retained:
        timestamp = _row_timestamp(row)
        message_length = len(str(row["메시지"]))
        gap_is_large = (
            last_timestamp is not None
            and timestamp is not None
            and ((timestamp - last_timestamp).total_seconds() >= inactivity_minutes * 60
                 or timestamp < last_timestamp)
        )
        exceeds_size = bool(buffer) and (
            len(buffer) >= max_messages_per_segment
            or buffer_chars + message_length > max_chars_per_segment
        )
        if gap_is_large or exceeds_size:
            flush()
        buffer.append(row)
        buffer_chars += message_length
        last_timestamp = timestamp or last_timestamp
    flush()

    stats["retained_messages"] = len(retained)
    stats["context_segments"] = len(segments)
    return segments, stats


def _is_chat_noise(message: str) -> bool:
    compact = re.sub(r"\s+", "", message)
    if not compact:
        return True
    if ATTACHMENT_ONLY.fullmatch(message):
        return True
    if REACTION_ONLY.fullmatch(message):
        return True
    if compact.casefold() in {value.casefold() for value in SHORT_CHAT_NOISE}:
        return True
    # Length alone cannot distinguish a reaction from a substantive opinion:
    # e.g. "불편해요", "임금체불", "앱 오류". Only explicit noise is removed.
    return False


def _row_timestamp(row: dict[str, Any]) -> datetime | None:
    date_text = normalize_text(row.get("날짜"))
    time_text = normalize_text(row.get("시간"))
    try:
        return datetime.fromisoformat(f"{date_text}T{time_text}")
    except ValueError:
        return None
