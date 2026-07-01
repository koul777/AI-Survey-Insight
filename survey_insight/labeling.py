from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from typing import Mapping, Protocol, Sequence


CONSERVATIVE_LABEL = "General feedback"
CONSERVATIVE_SUMMARY = "Insufficient topic evidence is available for a more specific summary."


@dataclass(frozen=True)
class TopicLabelResult:
    label: str
    summary: str
    source: str
    fallback_used: bool = False


class TopicLabeler(Protocol):
    def label_topic(
        self,
        keywords: Sequence[str],
        representative_responses: Sequence[str],
    ) -> TopicLabelResult:
        ...


class RuleBasedTopicLabeler:
    """Deterministic labeler that only uses topic keywords and representatives."""

    source = "rule"

    def label_topic(
        self,
        keywords: Sequence[str],
        representative_responses: Sequence[str],
    ) -> TopicLabelResult:
        clean_keywords = _clean_unique(keywords)
        clean_responses = _clean_unique(representative_responses)

        if clean_keywords:
            label = _label_from_terms(clean_keywords)
            summary = _summary_from_keywords(clean_keywords, clean_responses)
            return TopicLabelResult(label=label, summary=summary, source=self.source)

        response_terms = _terms_from_responses(clean_responses)
        if response_terms:
            label = _label_from_terms(response_terms)
            summary = _summary_from_responses(clean_responses)
            return TopicLabelResult(label=label, summary=summary, source=self.source)

        return TopicLabelResult(
            label=CONSERVATIVE_LABEL,
            summary=CONSERVATIVE_SUMMARY,
            source=self.source,
        )


class OptionalLLMLabeler:
    """Environment-selected LLM extension stub.

    This class is intentionally non-networked. It records the requested provider
    settings and delegates to a deterministic fallback until a local, audited
    provider implementation is explicitly added.
    """

    source = "optional_llm_fallback"

    def __init__(
        self,
        fallback: TopicLabeler | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.fallback = fallback or RuleBasedTopicLabeler()
        self.env = env if env is not None else os.environ
        self.provider = self.env.get("SURVEY_INSIGHT_LLM_LABELER_PROVIDER", "")
        self.model = self.env.get("SURVEY_INSIGHT_LLM_LABELER_MODEL", "")

    def label_topic(
        self,
        keywords: Sequence[str],
        representative_responses: Sequence[str],
    ) -> TopicLabelResult:
        result = self.fallback.label_topic(keywords, representative_responses)
        return replace(result, source=self.source, fallback_used=True)


def get_topic_labeler(env: Mapping[str, str] | None = None) -> TopicLabeler:
    settings = env if env is not None else os.environ
    requested = settings.get("SURVEY_INSIGHT_TOPIC_LABELER", "rule").strip().casefold()
    llm_requested = requested in {"llm", "optional_llm"} or any(
        settings.get(name)
        for name in (
            "SURVEY_INSIGHT_LLM_LABELER_PROVIDER",
            "SURVEY_INSIGHT_LLM_LABELER_MODEL",
        )
    )
    if llm_requested:
        return OptionalLLMLabeler(env=settings)
    return RuleBasedTopicLabeler()


def label_topic(
    keywords: Sequence[str],
    representative_responses: Sequence[str],
    labeler: TopicLabeler | None = None,
) -> TopicLabelResult:
    selected = labeler or get_topic_labeler()
    return selected.label_topic(keywords, representative_responses)


def _clean_unique(values: Sequence[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _collapse_whitespace(str(value)).strip(" ,;:/|")
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(_shorten(text, 80))
    return cleaned


def _label_from_terms(terms: Sequence[str]) -> str:
    primary = terms[0]
    label_terms = [primary]
    if len(terms) > 1 and terms[1].casefold() not in primary.casefold():
        label_terms.append(terms[1])
    return _shorten("/".join(label_terms), 80)


def _summary_from_keywords(keywords: Sequence[str], responses: Sequence[str]) -> str:
    evidence = f"Evidence keywords: {', '.join(keywords[:4])}."
    if responses:
        return f'{evidence} Representative response: "{_shorten(responses[0], 140)}"'
    return evidence


def _summary_from_responses(responses: Sequence[str]) -> str:
    return f'Representative response: "{_shorten(responses[0], 180)}"'


def _terms_from_responses(responses: Sequence[str]) -> list[str]:
    counts: dict[str, int] = {}
    display: dict[str, str] = {}
    first_seen: dict[str, int] = {}
    position = 0
    for response in responses:
        for match in re.finditer(r"[^\W_]{2,}", response, flags=re.UNICODE):
            raw = match.group(0)
            key = raw.casefold()
            if raw.isdigit() or key in _RESPONSE_STOPWORDS:
                continue
            if key not in first_seen:
                first_seen[key] = position
                display[key] = raw
            counts[key] = counts.get(key, 0) + 1
            position += 1
    ordered = sorted(counts, key=lambda key: (-counts[key], first_seen[key]))
    return [_shorten(display[key], 48) for key in ordered[:4]]


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _shorten(value: str, limit: int) -> str:
    text = _collapse_whitespace(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


_RESPONSE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "from",
    "has",
    "have",
    "into",
    "our",
    "the",
    "this",
    "that",
    "with",
}
