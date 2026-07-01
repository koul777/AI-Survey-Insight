from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Any

from .models import ColumnProfile, DatasetProfile, TableData, new_id
from .preprocessing import is_no_opinion, normalize_text

HEADER_TEXT_KEYWORDS = {
    "의견",
    "건의",
    "기타",
    "개선",
    "불편",
    "사유",
    "이유",
    "comment",
    "comments",
    "feedback",
    "opinion",
    "suggestion",
    "free text",
}
IDENTIFIER_KEYWORDS = {"id", "email", "e-mail", "이메일", "사번", "직번", "참여자", "성명", "이름", "전화"}
TIME_KEYWORDS = {"일시", "시간", "응답일", "제출", "timestamp", "date", "time"}
METADATA_KEYWORDS = {"성별", "연령", "직종", "근속", "부서", "직급", "지역", "소속"}
LIKERT_WORDS = {"매우 그렇다", "그렇다", "보통", "아니다", "전혀 아니다", "만족", "불만족"}


def profile_table(table: TableData, dataset_id: str | None = None) -> DatasetProfile:
    dataset_id = dataset_id or new_id("dataset")
    columns = [profile_column(header, [row.get(header) for row in table.rows]) for header in table.headers]
    recommended = sorted(
        [col for col in columns if col.text_score >= 0.50],
        key=lambda col: col.text_score,
        reverse=True,
    )
    warnings: list[str] = []
    if not recommended:
        warnings.append("자유응답 후보 컬럼을 찾지 못했습니다.")
    return DatasetProfile(
        dataset_id=dataset_id,
        sheet_name=table.sheet_name,
        row_count=len(table.rows),
        column_count=len(table.headers),
        header_row_index=table.header_row_index,
        columns=columns,
        recommended_text_columns=recommended,
        warnings=warnings,
    )


def profile_column(column_name: str, values: list[Any]) -> ColumnProfile:
    normalized = [normalize_text(value) for value in values]
    non_empty = [value for value in normalized if value]
    missing_rate = 1.0 - (len(non_empty) / max(1, len(values)))
    unique_rate = len(set(non_empty)) / max(1, len(non_empty))
    text_score, signals, reasons = compute_text_score(column_name, non_empty, missing_rate, unique_rate)
    detected_type, confidence = detect_column_type(column_name, non_empty, text_score, missing_rate, unique_rate)
    sample_values = non_empty[:5]
    return ColumnProfile(
        column_name=column_name,
        detected_type=detected_type,
        confidence=round(confidence, 3),
        missing_rate=round(missing_rate, 3),
        unique_rate=round(unique_rate, 3),
        text_score=round(text_score, 3),
        reasons=reasons,
        signals={key: round(value, 3) for key, value in signals.items()},
        sample_values=sample_values,
    )


def compute_text_score(
    column_name: str,
    non_empty: list[str],
    missing_rate: float,
    unique_rate: float,
) -> tuple[float, dict[str, float], list[str]]:
    header = column_name.lower()
    content_values = [value for value in non_empty if not is_no_opinion(value)]
    scoring_values = content_values or non_empty
    content_unique_rate = len(set(content_values)) / max(1, len(content_values))
    lengths = [len(value) for value in scoring_values]
    avg_len = sum(lengths) / max(1, len(lengths))
    p75 = _percentile(lengths, 0.75)
    p95 = _percentile(lengths, 0.95)
    newline_ratio = sum("\n" in value for value in scoring_values) / max(1, len(scoring_values))
    header_semantic = max(_contains_keyword(header, HEADER_TEXT_KEYWORDS), 0.15 if "?" in header else 0.0)
    length_signal = _clamp(max(avg_len / 35.0, p75 / 60.0, p95 / 100.0, newline_ratio))
    value_type_signal = _natural_language_ratio(scoring_values)
    cardinality_signal = _clamp(content_unique_rate if content_values else unique_rate)
    sentence_signal = _sentence_likeness(scoring_values)
    model_vote = _clamp((header_semantic * 0.45) + (value_type_signal * 0.30) + (sentence_signal * 0.25))
    score = (
        0.25 * header_semantic
        + 0.25 * length_signal
        + 0.20 * value_type_signal
        + 0.15 * cardinality_signal
        + 0.10 * sentence_signal
        + 0.05 * model_vote
    )
    if missing_rate > 0.95:
        score *= 0.65
    reasons = []
    if header_semantic >= 0.9:
        reasons.append("헤더가 자유응답 의미 키워드를 포함합니다.")
    if avg_len >= 20 or p95 >= 80:
        reasons.append("응답 길이가 서술형 컬럼 패턴입니다.")
    if unique_rate >= 0.7:
        reasons.append("고유값 비율이 높아 선택지 반복 컬럼일 가능성이 낮습니다.")
    if sentence_signal >= 0.5:
        reasons.append("한국어 문장형 표현이 다수 포함되어 있습니다.")
    if not reasons and score >= 0.5:
        reasons.append("값 분포가 자유응답 후보 패턴과 유사합니다.")
    return _clamp(score), {
        "HeaderSemantic": header_semantic,
        "LengthSignal": length_signal,
        "ValueTypeSignal": value_type_signal,
        "CardinalitySignal": cardinality_signal,
        "SentenceSignal": sentence_signal,
        "ModelVote": model_vote,
    }, reasons


def detect_column_type(
    column_name: str,
    non_empty: list[str],
    text_score: float,
    missing_rate: float,
    unique_rate: float,
) -> tuple[str, float]:
    header = column_name.lower()
    if missing_rate > 0.98:
        return "Noise/Empty", 0.95
    if _contains_keyword(header, IDENTIFIER_KEYWORDS):
        return "Identifier", 0.90
    if _contains_keyword(header, TIME_KEYWORDS) or _looks_timestamp(non_empty):
        return "Timestamp", 0.85
    if text_score >= 0.70:
        return "Free-text Response", text_score
    if _looks_scale(non_empty):
        return "Scale", 0.82
    if _contains_keyword(header, METADATA_KEYWORDS) or unique_rate <= 0.25:
        return "Categorical Metadata", 0.75
    if 0.50 <= text_score < 0.70:
        return "Free-text Candidate", text_score
    return "Noise/Empty" if not non_empty else "Categorical Metadata", 0.55


def _contains_keyword(text: str, keywords: set[str]) -> float:
    return 1.0 if any(keyword.lower() in text for keyword in keywords) else 0.0


def _natural_language_ratio(values: list[str]) -> float:
    if not values:
        return 0.0
    good = 0
    for value in values:
        letters = len(re.findall(r"[가-힣A-Za-z]", value))
        digits = len(re.findall(r"\d", value))
        if letters >= 3 and letters >= digits:
            good += 1
    return good / len(values)


def _sentence_likeness(values: list[str]) -> float:
    if not values:
        return 0.0
    endings = re.compile(r"(다|요|음|함|됨|니다|습니다|라고|다고|하게|해서|하여|이며|이고|입니다)[.!?]?$")
    score = 0.0
    for value in values:
        has_space = " " in value.strip()
        has_ending = bool(endings.search(value.strip()))
        has_punct = any(mark in value for mark in ".!?。")
        if has_space:
            score += 0.35
        if has_ending:
            score += 0.45
        if has_punct:
            score += 0.20
    return _clamp(score / len(values))


def _looks_scale(values: list[str]) -> bool:
    if not values:
        return False
    counts = Counter(values)
    if len(counts) > 12:
        return False
    numeric = 0
    for value in values:
        try:
            number = float(value)
        except ValueError:
            continue
        if 0 <= number <= 10 and math.isfinite(number):
            numeric += 1
    if numeric / max(1, len(values)) >= 0.8:
        return True
    likert_hits = sum(any(word in value for word in LIKERT_WORDS) for value in values)
    return likert_hits / max(1, len(values)) >= 0.6


def _looks_timestamp(values: list[str]) -> bool:
    if not values:
        return False
    checked = values[:30]
    hits = 0
    for value in checked:
        if re.search(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", value):
            hits += 1
            continue
        try:
            datetime.fromisoformat(value)
            hits += 1
        except ValueError:
            pass
    return hits / max(1, len(checked)) >= 0.7


def _percentile(values: list[int], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] * (upper - pos) + ordered[upper] * (pos - lower)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
