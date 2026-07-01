from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Sequence


POLARITY_LABELS = ("positive", "neutral", "negative", "mixed")


@dataclass(frozen=True)
class SentimentResult:
    text: str
    polarity_label: str
    polarity_score: float
    urgency_score: float
    evidence_terms: tuple[str, ...]
    source: str = "rule_lexicon_fallback"


@dataclass(frozen=True)
class TopicSentimentAggregate:
    count: int
    average_polarity_score: float
    average_urgency_score: float
    dominant_label: str
    label_counts: dict[str, int]
    evidence_terms: tuple[str, ...]
    source: str = "rule_lexicon_fallback"


@dataclass(frozen=True)
class _LexiconTerm:
    canonical: str
    patterns: tuple[str, ...]
    polarity_weight: float = 0.0
    urgency_weight: float = 0.0


_NEGATIVE_TERMS = (
    _LexiconTerm("불만", ("불만", "불만족"), -0.80, 0.15),
    _LexiconTerm("어렵", ("어렵", "어려"), -0.55, 0.15),
    _LexiconTerm("부족", ("부족",), -0.60, 0.20),
    _LexiconTerm("개선", ("개선",), -0.35, 0.25),
    _LexiconTerm("필요", ("필요",), -0.35, 0.25),
    _LexiconTerm("복잡", ("복잡",), -0.50, 0.10),
    _LexiconTerm("늦", ("늦", "지연"), -0.45, 0.25),
    _LexiconTerm("갑작", ("갑작", "갑자기"), -0.40, 0.25),
    _LexiconTerm("눈치", ("눈치",), -0.45, 0.15),
    _LexiconTerm("불편", ("불편",), -0.55, 0.20),
    _LexiconTerm("과중", ("과중",), -0.50, 0.20),
    _LexiconTerm("힘듦", ("힘들", "힘든", "힘듦"), -0.50, 0.15),
)

_POSITIVE_TERMS = (
    _LexiconTerm("좋", ("좋",), 0.55),
    _LexiconTerm("만족", ("만족",), 0.75),
    _LexiconTerm("도움", ("도움",), 0.50),
    _LexiconTerm("체계적", ("체계적",), 0.60),
    _LexiconTerm("명확", ("명확",), 0.45),
    _LexiconTerm("효율", ("효율",), 0.45),
    _LexiconTerm("원활", ("원활",), 0.45),
)

_URGENCY_TERMS = (
    _LexiconTerm("즉시", ("즉시",), urgency_weight=0.90),
    _LexiconTerm("당장", ("당장",), urgency_weight=0.90),
    _LexiconTerm("긴급", ("긴급",), urgency_weight=0.85),
    _LexiconTerm("시급", ("시급",), urgency_weight=0.85),
    _LexiconTerm("급히", ("급히",), urgency_weight=0.70),
    _LexiconTerm("빨리", ("빨리",), urgency_weight=0.65),
    _LexiconTerm("조속", ("조속",), urgency_weight=0.65),
    _LexiconTerm("심각", ("심각",), urgency_weight=0.55),
    _LexiconTerm("우선", ("우선",), urgency_weight=0.30),
)

_ALL_TERMS = _NEGATIVE_TERMS + _POSITIVE_TERMS + _URGENCY_TERMS
_NEGATED_NEGATIVE_MARKERS = ("없", "않", "아니", "해소", "해결")
_NEGATED_POSITIVE_MARKERS = ("않", "못", "아니", "없")


def analyze_text_sentiment(text: str) -> SentimentResult:
    """Analyze one Korean HR survey free-text response with deterministic rules."""

    normalized = _normalize(text)
    matches = _collect_matches(normalized)
    polarity_matches = [match for match in matches if match.term.polarity_weight]
    urgency_weights = [match.term.urgency_weight for match in matches if match.term.urgency_weight > 0]

    positive_total = sum(match.term.polarity_weight for match in polarity_matches if match.term.polarity_weight > 0)
    negative_total = -sum(match.term.polarity_weight for match in polarity_matches if match.term.polarity_weight < 0)
    polarity_score = _polarity_score(positive_total, negative_total)
    polarity_label = _polarity_label(positive_total, negative_total, polarity_score)
    urgency_score = _combined_urgency(urgency_weights)
    evidence_terms = tuple(_unique_in_order(match.term.canonical for match in matches))

    return SentimentResult(
        text=text,
        polarity_label=polarity_label,
        polarity_score=polarity_score,
        urgency_score=urgency_score,
        evidence_terms=evidence_terms,
    )


def analyze_sentiment(text: str) -> SentimentResult:
    """Backward-friendly alias for single-text sentiment analysis."""

    return analyze_text_sentiment(text)


def aggregate_topic_sentiment(texts: Sequence[str]) -> TopicSentimentAggregate:
    """Aggregate sentiment over a topic's representative or assigned texts."""

    results = [analyze_text_sentiment(text) for text in texts]
    if not results:
        return TopicSentimentAggregate(
            count=0,
            average_polarity_score=0.0,
            average_urgency_score=0.0,
            dominant_label="neutral",
            label_counts={label: 0 for label in POLARITY_LABELS},
            evidence_terms=(),
        )

    average_polarity = round(sum(result.polarity_score for result in results) / len(results), 3)
    average_urgency = round(sum(result.urgency_score for result in results) / len(results), 3)
    label_counts = Counter(result.polarity_label for result in results)
    all_counts = {label: label_counts.get(label, 0) for label in POLARITY_LABELS}
    evidence_terms = tuple(
        _unique_in_order(term for result in results for term in result.evidence_terms)
    )

    return TopicSentimentAggregate(
        count=len(results),
        average_polarity_score=average_polarity,
        average_urgency_score=average_urgency,
        dominant_label=_dominant_label(label_counts, average_polarity),
        label_counts=all_counts,
        evidence_terms=evidence_terms,
    )


@dataclass(frozen=True)
class _Match:
    start: int
    end: int
    term: _LexiconTerm


def _normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _collect_matches(text: str) -> list[_Match]:
    selected: dict[str, _Match] = {}
    for term in _ALL_TERMS:
        match = _first_valid_match(text, term)
        if match is None:
            continue
        current = selected.get(term.canonical)
        if current is None or match.start < current.start:
            selected[term.canonical] = match
    return sorted(selected.values(), key=lambda match: (match.start, match.term.canonical))


def _first_valid_match(text: str, term: _LexiconTerm) -> _Match | None:
    for pattern in term.patterns:
        for found in re.finditer(re.escape(pattern), text):
            start, end = found.span()
            if _is_suppressed(text, start, end, term):
                continue
            return _Match(start=start, end=end, term=term)
    return None


def _is_suppressed(text: str, start: int, end: int, term: _LexiconTerm) -> bool:
    before = text[max(0, start - 2) : start]
    after = text[end : min(len(text), end + 8)]
    if term.polarity_weight > 0:
        if before.endswith("불"):
            return True
        return any(marker in after for marker in _NEGATED_POSITIVE_MARKERS)
    if term.polarity_weight < 0:
        return any(marker in after for marker in _NEGATED_NEGATIVE_MARKERS)
    return False


def _polarity_score(positive_total: float, negative_total: float) -> float:
    if positive_total == 0 and negative_total == 0:
        return 0.0
    denominator = max(1.0, positive_total + negative_total)
    return round(max(-1.0, min(1.0, (positive_total - negative_total) / denominator)), 3)


def _polarity_label(positive_total: float, negative_total: float, score: float) -> str:
    if positive_total > 0 and negative_total > 0:
        return "mixed"
    if score >= 0.15:
        return "positive"
    if score <= -0.15:
        return "negative"
    return "neutral"


def _combined_urgency(weights: Iterable[float]) -> float:
    remaining = 1.0
    used = False
    for weight in weights:
        used = True
        remaining *= 1.0 - max(0.0, min(1.0, weight))
    if not used:
        return 0.0
    return round(1.0 - remaining, 3)


def _dominant_label(label_counts: Counter[str], average_polarity: float) -> str:
    top_count = max(label_counts.values())
    top_labels = {label for label, count in label_counts.items() if count == top_count}
    if len(top_labels) == 1:
        return next(iter(top_labels))
    if "mixed" in top_labels:
        return "mixed"
    if {"positive", "negative"}.issubset(top_labels):
        return "mixed"
    if average_polarity >= 0.15 and "positive" in top_labels:
        return "positive"
    if average_polarity <= -0.15 and "negative" in top_labels:
        return "negative"
    if "neutral" in top_labels:
        return "neutral"
    return sorted(top_labels)[0]


def _unique_in_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
