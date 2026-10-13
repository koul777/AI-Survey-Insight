from __future__ import annotations

import csv
import hashlib
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any, Iterable, Sequence

from .preprocessing import Morpheme, analyze_morphemes, normalize_text, tokenizer_source
from .models import TextDocument

POLARITY_LABELS = ("positive", "neutral", "negative", "mixed")
LEXICON_VERSION = "1.0.0"
RULES_VERSION = "1.1.0"
SENTIMENT_METHOD = "korean_morph_lexicon_v1"


@dataclass(frozen=True)
class SentimentEvidence:
    term: str
    text: str
    start: int
    end: int
    weight: float
    negated: bool
    kind: str
    modifiers: tuple[str, ...] = ()


@dataclass(frozen=True)
class SentimentResult:
    text: str
    polarity_label: str
    polarity_score: float
    urgency_score: float
    evidence_terms: tuple[str, ...]
    source: str = SENTIMENT_METHOD
    evidence_spans: tuple[SentimentEvidence, ...] = ()
    evidence_status: str = "no_match"
    lexicon_version: str = LEXICON_VERSION
    needs_review: bool = False
    review_reasons: tuple[str, ...] = ()
    rules_version: str = RULES_VERSION


@dataclass(frozen=True)
class TopicSentimentAggregate:
    count: int
    average_polarity_score: float
    average_urgency_score: float
    dominant_label: str
    label_counts: dict[str, int]
    evidence_terms: tuple[str, ...]
    source: str = SENTIMENT_METHOD
    evidence_coverage: float = 0.0
    review_count: int = 0


@dataclass(frozen=True)
class LexiconEntry:
    term: str
    polarity: float
    urgency: float
    kind: str
    aliases: tuple[str, ...]


@lru_cache(maxsize=1)
def load_sentiment_lexicon() -> tuple[LexiconEntry, ...]:
    """Load the bundled dictionary; malformed data fails explicitly."""
    path = files("survey_insight").joinpath("data/sentiment_ko.tsv")
    with path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    entries: list[LexiconEntry] = []
    seen: set[str] = set()
    for row in rows:
        term = row["term"].strip()
        polarity, urgency = float(row["polarity"]), float(row["urgency"])
        if not term or term in seen or not -1 <= polarity <= 1 or not 0 <= urgency <= 1:
            raise ValueError("Invalid bundled sentiment dictionary entry")
        if row["kind"] not in {"polarity", "urgency", "request"}:
            raise ValueError("Invalid sentiment dictionary kind")
        seen.add(term)
        entries.append(LexiconEntry(term, polarity, urgency, row["kind"],
                                    tuple(filter(None, row["aliases"].split("|")))))
    return tuple(entries)


def sentiment_lexicon_info() -> dict[str, Any]:
    content = files("survey_insight").joinpath("data/sentiment_ko.tsv").read_bytes()
    return {
        "name": "Survey Insight Korean survey lexicon", "version": LEXICON_VERSION,
        "rules_version": RULES_VERSION,
        "entry_count": len(load_sentiment_lexicon()),
        "sha256": hashlib.sha256(content).hexdigest(), "source": "project_authored",
        "method": SENTIMENT_METHOD if tokenizer_source().startswith("kiwi") else "korean_surface_lexicon_fallback",
        "score_type": "rule_weight_not_probability",
    }


@lru_cache(maxsize=4)
def _compiled_lexicon(backend_source: str) -> dict[str, list[tuple[tuple[str, ...], LexiconEntry]]]:
    index: dict[str, list[tuple[tuple[str, ...], LexiconEntry]]] = {}
    for entry in load_sentiment_lexicon():
        phrases = {entry.term, *entry.aliases}
        if len(entry.term) >= 2 and not entry.term.endswith("다"):
            phrases.add(entry.term + "하다")
        sequences: set[tuple[str, ...]] = set()
        for phrase in sorted(phrases):
            tokens = list(analyze_morphemes(phrase))
            # Citation-form 다 may be tagged EC or EF depending on context
            # and Kiwi model version. Both must reduce to the same stem.
            while tokens and tokens[-1].tag in {"EF", "EC", "EP", "XSA", "XSV", "VCP"}:
                tokens.pop()
            signature = tuple(token.form for token in tokens)
            if signature and signature not in sequences:
                sequences.add(signature)
                index.setdefault(signature[0], []).append((signature, entry))
    for options in index.values():
        options.sort(key=lambda item: (-len(item[0]), -len(item[1].term), item[1].term))
    return index


def _clause_end(token: Morpheme) -> bool:
    return token.tag in {"SF", "SP", "SSO", "SSC", "EF"} or (
        token.tag == "EC" and token.form not in {"지", "어", "아", "게"}
    )


def _following_clause(tokens: Sequence[Morpheme], start: int, end: int) -> list[Morpheme]:
    """A bounded clause window, including complements but never a new sentence.

    다고 is traversed only for the sentiment's reported proposition. Other
    coordinating/contrastive endings continue to close the window.
    """
    following: list[Morpheme] = []
    relative_clause = False
    for token in tokens[end:min(len(tokens), end + 24)]:
        if token.sentence != tokens[start].sentence:
            break
        following.append(token)
        relative_clause = relative_clause or token.tag == "ETM"
        if relative_clause and token.tag == "JKB":
            break
        if _clause_end(token) and token.form not in {"다고", "라고"}:
            break
    return following


def _is_request(tokens: Sequence[Morpheme]) -> bool:
    forms = [token.form for token in tokens]
    return (any(form in {"바라", "원하", "희망", "요청", "부탁"} for form in forms)
            or any(forms[index:index + 2] == ["원", "하"] for index in range(len(forms) - 1))
            or ("주" in forms and any(token.tag == "EF" and token.form in
                                      {"세요", "십시오", "셔요", "라", "어라"} for token in tokens)))


def _neutral_mention(entry: LexiconEntry, after: Sequence[Morpheme], tail: str) -> bool:
    """Exclude unambiguous subject names, without treating all nouns as neutral."""
    first = after[0].form if after else ""
    if entry.term == "안전" and first in {"교육", "수칙", "교육원", "매뉴얼", "점검", "관리"}:
        return True
    if entry.term == "감사" and first in {"자료", "결과", "보고서", "보고", "일정", "계획", "대상", "담당"}:
        return True
    if entry.term == "문제" and first in {"풀이", "정답", "출제", "유형", "번호"}:
        return True
    return bool(re.match(r"\s*(?:사항|여부|정도|도|사례|요인)\s*(?:을|를|에|의)?\s*"
                         r"(?:조사|확인|설문|측정|분석)", tail))


def _context(tokens: Sequence[Morpheme], start: int, end: int) -> tuple[list[Morpheme], list[Morpheme]]:
    before: list[Morpheme] = []
    for token in reversed(tokens[max(0, start - 4):start]):
        if _clause_end(token) or token.sentence != tokens[start].sentence:
            break
        before.insert(0, token)
    after: list[Morpheme] = []
    relative_clause = False
    reported_clause = False
    relative_subject_closed = False
    for token in tokens[end:min(len(tokens), end + 18)]:
        if token.sentence != tokens[start].sentence:
            break
        after.append(token)
        relative_clause = relative_clause or token.tag == "ETM"
        reported_clause = reported_clause or token.form in {"다고", "라고"}
        if relative_clause and not reported_clause:
            if relative_subject_closed and (
                (token.tag in {"NNG", "NNP"} and token.form not in {"해결", "해소"})
                or (token.tag in {"VA", "VV"} and token.form not in {"없", "아니", "있", "않", "못하", "못"})
            ):
                break
            relative_subject_closed = relative_subject_closed or token.tag in {"JKS", "JX"}
        if relative_clause and token.tag == "JKB":
            break
        if _clause_end(token) and token.form not in {"다고", "라고"}:
            break
        if (token.tag in {"NNG", "NNP"} and token.form not in {"해결", "해소"}
                and not relative_clause and not (reported_clause and token.form in {"생각", "판단", "평가", "말", "단정"})):
            break
    return before, after


def _adjust_match(text: str, tokens: Sequence[Morpheme], start: int, end: int,
                  entry: LexiconEntry) -> tuple[SentimentEvidence, float] | None:
    before, after = _context(tokens, start, end)
    following = _following_clause(tokens, start, end)
    # 별로 is a polarity term in "별로예요", but an adverb modifying
    # the following predicate in "별로 좋지 않다". Do not count both.
    if entry.term == "별로" and tokens[start].tag == "MAG" and any(
        token.tag in {"VA", "VV", "XR", "NNG"} for token in after
    ):
        return None
    # Do not count 만족 inside 불만족 as a separate positive observation.
    if start and tokens[start - 1].tag == "XPN" and tokens[start - 1].end == tokens[start].start:
        return None
    tail = text[tokens[end - 1].end:tokens[end - 1].end + 32]
    if _neutral_mention(entry, following, tail):
        return None
    # 지침 (guideline) is a noun homograph of the nominalized verb 지치다.
    if entry.term == "지치다" and tokens[start].form == "지침" and tokens[start].tag == "NNG":
        return None
    pre_negations = [t for index, t in enumerate(before)
                     if t.form in {"안", "못"} and t.tag in {"MAG", "VX"}
                     and all(later.tag == "MAG" for later in before[index + 1:])]
    post_negations = [t for t in after if (t.form in {"안", "않", "못하", "못"} and t.tag in {"VX", "VV", "MAG"})
                      or (t.form == "아니" and t.tag == "VCN") or (t.form == "없" and t.tag == "VA")
                      or (t.form == "없이" and t.tag == "MAG")]
    negations = pre_negations + post_negations
    resolution = [t for t in after if t.form in {"해결", "해소"}]
    # A requested resolution is not an accomplished positive experience.
    if entry.polarity < 0 and resolution and not _is_request(following):
        resolution_start = next(i for i, token in enumerate(following) if token.form in {"해결", "해소"})
        resolution_tail = following[resolution_start + 1:]
        if (resolution_tail and resolution_tail[0].form in {"하", "되"}
                and resolution_tail[0].tag in {"VV", "XSV"}
                and not any(t.form in {"필요", "겠", "예정", "계획"} for t in resolution_tail)):
            negations += resolution
    modifiers: list[str] = []
    indirect_denial: list[Morpheme] = []
    weight, urgency = entry.polarity, entry.urgency
    if negations:
        weight *= (-0.75) ** len(negations)
        urgency = 0.0
        modifiers.append("negation" if len(negations) == 1 else "double_negation")
    if any(t.form in {"다고", "라고"} for t in after):
        modifiers.append("reported_proposition")
        # '좋다고 보기 어렵다' denies the judgment; 어렵다 remains its own
        # negative evidence rather than being counted as a positive judgment.
        if any(t.form == "어렵" for t in after) and not negations:
            weight *= -0.75
            indirect_denial = [token for token in after if token.form == "어렵"]
            modifiers.append("indirect_negation")
    intensity = [t.form for t in before if t.tag == "MAG"]
    if any(form in {"매우", "정말", "너무", "아주", "전혀", "정말로"} for form in intensity):
        weight *= 1.25
        modifiers.append("intensifier")
    elif any(form in {"조금", "다소", "약간"} for form in intensity):
        weight *= 0.65
        modifiers.append("diminisher")
    if any(t.form in {"으면", "면", "다면", "겠"} for t in after):
        weight = 0.0
        urgency = 0.0
        modifiers.append("hypothetical")
    if entry.polarity > 0 and _is_request(following):
        weight = 0.0
        urgency = 0.0
        modifiers.append("desired_state")
    span_start = min([tokens[start].start, *[t.start for t in pre_negations]])
    span_end = max([tokens[end - 1].end, *[t.end for t in negations + indirect_denial]])
    return SentimentEvidence(entry.term, text[span_start:span_end], span_start, span_end,
                             round(max(-1.0, min(1.0, weight)), 3), bool(negations),
                             entry.kind, tuple(modifiers)), urgency


def _morph_matches(text: str) -> list[tuple[SentimentEvidence, float]]:
    tokens = analyze_morphemes(text)
    index = _compiled_lexicon(tokenizer_source())
    forms = tuple(t.form for t in tokens)
    matches: list[tuple[SentimentEvidence, float]] = []
    position = 0
    while position < len(tokens):
        for signature, entry in index.get(forms[position], []):
            end = position + len(signature)
            if forms[position:end] != signature:
                continue
            # In '나쁘다고 보기 어렵다', 어렵다 negates the reported
            # judgment; it is not a second independent negative experience.
            if (entry.term == "어렵" and matches
                    and "indirect_negation" in matches[-1][0].modifiers
                    and matches[-1][0].end >= tokens[position].end):
                position = end
                break
            adjusted = _adjust_match(text, tokens, position, end, entry)
            if adjusted is not None:
                matches.append(adjusted)
            position = end
            break
        else:
            position += 1
    return matches


def _surface_matches(text: str) -> list[tuple[SentimentEvidence, float]]:
    """Conservative degraded path, explicitly labelled and requiring review."""
    found: list[tuple[int, int, LexiconEntry]] = []
    for entry in load_sentiment_lexicon():
        for phrase in {entry.term, *entry.aliases}:
            for match in re.finditer(r"(?<![가-힣A-Za-z])" + re.escape(phrase.removesuffix("다")), text):
                found.append((match.start(), match.end(), entry))
    selected: list[tuple[SentimentEvidence, float]] = []
    last_end = -1
    for start, end, entry in sorted(found, key=lambda x: (x[0], -(x[1] - x[0]))):
        if start < last_end:
            continue
        last_end = end
        tail = re.split(r"[.!?;,\n]|지만|는데|하고|이고", text[end:end + 18])[0]
        negated = bool(re.search(r"(?:지\s*않|지\s*못|없|아니)", tail)
                       or re.search(r"(?:안|못)\s*$", text[max(0, start - 4):start]))
        selected.append((SentimentEvidence(entry.term, text[start:end], start, end,
                                            entry.polarity * (-0.75 if negated else 1),
                                            negated, entry.kind, ("surface_fallback",)),
                         0.0 if negated else entry.urgency))
    return selected


def _has_possible_irony(text: str, spans: Sequence[SentimentEvidence]) -> bool:
    """Flag a negative experience followed by an ironic positive cue locally."""
    for cue in re.finditer(r"(?:참|정말|아주)\s*(?:좋|감사)", text):
        sentence_start = max(text.rfind(mark, 0, cue.start()) for mark in ".!?。！？") + 1
        for evidence in spans:
            if evidence.weight >= 0 or not sentence_start <= evidence.start < cue.start():
                continue
            if not re.search(r"지만|반면|다만", text[evidence.end:cue.start()]):
                return True
    return False


@lru_cache(maxsize=4096)
def analyze_text_sentiment(text: str) -> SentimentResult:
    """Explainable Korean polarity rules; scores are not confidence estimates."""
    normalized = normalize_text(text)
    degraded = not tokenizer_source().startswith("kiwi")
    matches = _surface_matches(normalized) if degraded else _morph_matches(normalized)
    positive = sum(e.weight for e, _ in matches if e.weight > 0)
    negative = -sum(e.weight for e, _ in matches if e.weight < 0)
    score = round(math.tanh((positive - negative) / 1.5), 3)
    if positive >= 0.15 and negative >= 0.15:
        label = "mixed"
    elif score >= 0.10:
        label = "positive"
    elif score <= -0.10:
        label = "negative"
    else:
        label = "neutral"
    spans = tuple(e for e, _ in matches)
    status = "matched" if positive or negative else ("request_only" if matches else "no_match")
    quoted_judgment = bool(re.search(r"(?:다는|라는)\s*(?:말|의견|평가|주장)|(?:다고|라고)\s*(?:하|말)|[\"“”'‘’]", normalized))
    uncertain_judgment = bool(re.search(r"모르겠|[?？]", normalized))
    # Contradictory polarity in a clause containing an irony cue deserves a
    # human check; the dictionary cannot establish sarcasm from tone alone.
    possible_irony = positive > 0 and negative > 0 and _has_possible_irony(normalized, spans)
    review_reasons = tuple(reason for reason, applies in (
        ("degraded_tokenizer", degraded), ("quoted_judgment", quoted_judgment),
        ("uncertain_or_question", uncertain_judgment), ("possible_irony", possible_irony),
        ("no_dictionary_evidence", status == "no_match"),
        ("hypothetical", any("hypothetical" in evidence.modifiers for evidence in spans)),
        ("desired_state", any("desired_state" in evidence.modifiers for evidence in spans)),
        ("reported_proposition", any("reported_proposition" in evidence.modifiers for evidence in spans)),
    ) if applies)
    return SentimentResult(
        text=text, polarity_label=label, polarity_score=score,
        urgency_score=_combined_urgency(u for _, u in matches),
        evidence_terms=tuple(dict.fromkeys(e.term for e in spans)),
        source="korean_surface_lexicon_fallback" if degraded else SENTIMENT_METHOD,
        evidence_spans=spans, evidence_status=status,
        needs_review=bool(review_reasons), review_reasons=review_reasons,
    )


def analyze_sentiment(text: str) -> SentimentResult:
    return analyze_text_sentiment(text)


def sentiment_payload(result: SentimentResult) -> dict[str, Any]:
    payload = asdict(result)
    payload.pop("text")
    return payload


def aggregate_topic_sentiment(texts: Sequence[str]) -> TopicSentimentAggregate:
    return _aggregate_payloads([sentiment_payload(analyze_text_sentiment(text)) for text in texts])


def aggregate_document_sentiment(documents: Sequence[TextDocument]) -> TopicSentimentAggregate:
    """Reuse each response's persisted analysis across candidates and edits."""
    for document in documents:
        if not document.sentiment:
            document.sentiment = sentiment_payload(analyze_text_sentiment(document.redacted_text))
    return _aggregate_payloads([document.sentiment for document in documents])


def _aggregate_payloads(results: Sequence[dict[str, Any]]) -> TopicSentimentAggregate:
    count = len(results)
    counts = Counter(result["polarity_label"] for result in results)
    average = round(sum(r["polarity_score"] for r in results) / max(1, count), 3)
    sources = {r.get("source", SENTIMENT_METHOD) for r in results}
    source = next(iter(sources)) if len(sources) == 1 else (SENTIMENT_METHOD if not sources else "mixed_sentiment_methods")
    return TopicSentimentAggregate(
        count=count, average_polarity_score=average,
        average_urgency_score=round(sum(r["urgency_score"] for r in results) / max(1, count), 3),
        dominant_label=_dominant_label(counts, average) if count else "neutral",
        label_counts={label: counts.get(label, 0) for label in POLARITY_LABELS},
        evidence_terms=tuple(dict.fromkeys(term for r in results for term in r["evidence_terms"])),
        source=source,
        evidence_coverage=round(sum(r.get("evidence_status") == "matched" for r in results) / max(1, count), 4),
        review_count=sum(bool(result.get("needs_review")) for result in results),
    )


def _combined_urgency(weights: Iterable[float]) -> float:
    remaining = 1.0
    for weight in weights:
        remaining *= 1.0 - max(0.0, min(1.0, weight))
    return round(1.0 - remaining, 3)


def _dominant_label(label_counts: Counter[str], average_polarity: float) -> str:
    top_count = max(label_counts.values())
    top_labels = {label for label, count in label_counts.items() if count == top_count}
    if len(top_labels) == 1:
        return next(iter(top_labels))
    if "mixed" in top_labels or {"positive", "negative"}.issubset(top_labels):
        return "mixed"
    if average_polarity >= 0.1 and "positive" in top_labels:
        return "positive"
    if average_polarity <= -0.1 and "negative" in top_labels:
        return "negative"
    return "neutral" if "neutral" in top_labels else sorted(top_labels)[0]
