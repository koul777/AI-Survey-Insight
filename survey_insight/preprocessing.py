from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from threading import RLock
from typing import Any

from .models import TextDocument, new_id

NO_OPINION_VALUES = {
    "",
    ".",
    "-",
    "--",
    "없음",
    "없습니다",
    "없다",
    "무",
    "해당없음",
    "해당 없음",
    "특이사항 없음",
    "의견 없음",
    "n/a",
    "na",
    "none",
    "no",
}

STOPWORDS = {
    "그리고",
    "하지만",
    "그러나",
    "대한",
    "위한",
    "관련",
    "사항",
    "기타",
    "의견",
    "건의",
    "개선",
    "있습니다",
    "합니다",
    "하면",
    "하는",
    "되어",
    "해서",
    "너무",
    "정말",
    # 짧은 메신저 대화에서 주제를 가리지 못하는 지시어·맞장구 표현
    "이거",
    "그거",
    "저거",
    "이것",
    "그것",
    "저것",
    "이게",
    "그게",
    "저게",
    "저도",
    "저희",
    "근데",
    "필요", "요청", "부분", "경우", "생각", "정도", "때문", "이번", "현재",
    "만족", "불만", "불만족", "불편", "부족", "친절", "유익", "유용",
    "도움", "문제", "아쉬움", "감사", "실망",
}

_TOKENIZER_BACKEND: Any | None = None
_TOKENIZER_SOURCE = ""
_TOKENIZER_LOCK = RLock()
_PLACEHOLDER = re.compile(r"\[(?:EMAIL|PHONE|EMPLOYEE_ID)\]", re.I)
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_SINGLE_NOUNS = {"앱", "일", "밥", "돈", "집", "몸", "차", "책", "법", "병", "휴"}


@dataclass(frozen=True)
class Morpheme:
    form: str
    tag: str
    start: int
    end: int
    sentence: int = 0

PII_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    ("phone", re.compile(r"\b(?:010|011|016|017|018|019)[-. ]?\d{3,4}[-. ]?\d{4}\b"), "[PHONE]"),
    (
        "employee_id",
        re.compile(
            r"(?<![A-Za-z0-9])(?:사번|직번|employee\s*id)[:#\s-]*[A-Za-z0-9][A-Za-z0-9-]{3,}(?![A-Za-z0-9-])",
            re.I,
        ),
        "[EMPLOYEE_ID]",
    ),
]

PRIVACY_REVIEW_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("explicit_name_context", re.compile(r"(?:이름|성명)\s*[:：]")),
    ("explicit_address_context", re.compile(r"(?:주소|거주지)\s*[:：]")),
    ("national_id_context", re.compile(r"(?:주민등록번호|주민번호)")),
    ("financial_account_context", re.compile(r"(?:계좌번호|통장번호)")),
]


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    if isinstance(value, float) and value != value:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_no_opinion(value: Any) -> bool:
    text = normalize_text(value).lower()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" .!?~。！")
    return text in NO_OPINION_VALUES or bool(re.fullmatch(r"(?:의견|특이\s*사항|건의\s*사항)\s*(?:이\s*)?없(?:음|습니다|어요|다)", text))


def mask_pii(text: str) -> tuple[str, list[str]]:
    found: list[str] = []
    masked = text
    for name, pattern, replacement in PII_PATTERNS:
        if pattern.search(masked):
            found.append(name)
            masked = pattern.sub(replacement, masked)
    return masked, found


def detect_privacy_review_flags(text: str) -> list[str]:
    """Flag explicit high-risk contexts without broadly masking normal prose."""

    return [name for name, pattern in PRIVACY_REVIEW_PATTERNS if pattern.search(text)]


def preprocess_documents(
    rows: list[dict[str, Any]],
    text_column: str,
    metadata_columns: list[str] | None = None,
) -> list[TextDocument]:
    metadata_columns = metadata_columns or []
    documents: list[TextDocument] = []
    for idx, row in enumerate(rows, start=1):
        original = normalize_text(row.get(text_column))
        no_opinion = is_no_opinion(original)
        redacted, pii_found = mask_pii(original)
        privacy_review_flags = detect_privacy_review_flags(original)
        metadata = {col: row.get(col) for col in metadata_columns if col in row}
        if original == "" and not no_opinion:
            no_opinion = True
        documents.append(
            TextDocument(
                id=new_id("doc"),
                row_index=idx,
                text_column=text_column,
                original_text=original,
                redacted_text=redacted,
                metadata=metadata,
                is_no_opinion=no_opinion,
                pii_found=pii_found,
                privacy_review_flags=privacy_review_flags,
            )
        )
    return documents


def valid_documents(documents: list[TextDocument]) -> list[TextDocument]:
    return [doc for doc in documents if not doc.is_no_opinion and doc.redacted_text]


def tokenize_keywords(text: str) -> list[str]:
    # Topic vocabulary describes subjects. Sentiment uses the full POS stream
    # separately so adjectives and negation do not disappear from its input.
    cleaned_text = _URL.sub(" ", _PLACEHOLDER.sub(" ", normalize_text(text)))
    tokens = [token.form for token in analyze_morphemes(cleaned_text)
              if token.tag in {"NNG", "NNP", "SL", "XR", "UNKNOWN"}]
    cleaned: list[str] = []
    for token in tokens:
        normalized = normalize_text(token).lower()
        if normalized in STOPWORDS:
            continue
        if normalized.isdigit():
            continue
        if len(normalized) < 2 and normalized not in _SINGLE_NOUNS:
            continue
        cleaned.append(normalized)
    return cleaned


def tokenizer_source() -> str:
    return _get_tokenizer_backend()[0]


def _get_tokenizer_backend() -> tuple[str, Any | None]:
    with _TOKENIZER_LOCK:
        return _initialize_tokenizer()


def _initialize_tokenizer() -> tuple[str, Any | None]:
    global _TOKENIZER_BACKEND, _TOKENIZER_SOURCE
    if _TOKENIZER_SOURCE:
        return _TOKENIZER_SOURCE, _TOKENIZER_BACKEND
    try:
        from kiwipiepy import Kiwi  # type: ignore

        _TOKENIZER_BACKEND = Kiwi(num_workers=2)
        _TOKENIZER_SOURCE = "kiwi_noun_extractor"
        return _TOKENIZER_SOURCE, _TOKENIZER_BACKEND
    except Exception:
        pass
    try:
        from konlpy.tag import Okt  # type: ignore

        _TOKENIZER_BACKEND = Okt()
        _TOKENIZER_SOURCE = "konlpy_okt_noun_extractor"
        return _TOKENIZER_SOURCE, _TOKENIZER_BACKEND
    except Exception:
        _TOKENIZER_BACKEND = None
        _TOKENIZER_SOURCE = "regex_keyword_fallback"
        return _TOKENIZER_SOURCE, _TOKENIZER_BACKEND


@lru_cache(maxsize=4096)
def analyze_morphemes(text: str) -> tuple[Morpheme, ...]:
    """Immutable POS/lemma stream; offsets refer to the normalized input.

    A bounded in-process cache shares expensive Korean parsing across model
    candidates. No raw text or cache is written to disk.
    """
    text = normalize_text(text)
    source, backend = _get_tokenizer_backend()
    if source.startswith("kiwi"):
        return tuple(Morpheme(str(t.form).lower(), str(t.tag).split("-")[0],
                              int(t.start), int(t.start + t.len), int(t.sent_position))
                     for t in backend.tokenize(text, normalize_coda=True, split_complex=True))
    if source.startswith("konlpy_okt"):
        # Okt does not provide reliable character spans; use the conservative
        # lexical fallback for sentiment and preserve its noun extraction.
        nouns = set(backend.nouns(text))
    else:
        nouns = set()
    return tuple(Morpheme(m.group().lower(), "NNG" if m.group() in nouns else "UNKNOWN",
                          m.start(), m.end())
                 for m in re.finditer(r"[가-힣A-Za-z]+|[.!?;\n]", text))


def preprocessing_diagnostics(documents: list[TextDocument]) -> dict[str, Any]:
    valid = valid_documents(documents)
    counts = [len(tokenize_keywords(doc.redacted_text)) for doc in valid]
    versions = {}
    for package in ("kiwipiepy", "kiwipiepy_model", "scikit-learn", "numpy"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "unavailable"
    return {
        "library_versions": versions,
        "tokenizer": tokenizer_source(),
        "normalization": "NFKC, zero-width removal, whitespace, Kiwi normalize_coda + split_complex",
        "topic_pos": ["NNG", "NNP", "SL", "XR"],
        "sentiment_pos": "full morphology with negation and clause boundaries",
        "input_count": len(documents),
        "no_opinion_count": len(documents) - len(valid),
        "empty_topic_vocabulary_count": sum(count == 0 for count in counts),
        "duplicate_response_count": len(valid) - len({doc.redacted_text for doc in valid}),
        "topic_token_count": sum(counts),
        "degraded": not tokenizer_source().startswith("kiwi"),
    }
def _kiwi_nouns(kiwi: Any, text: str) -> list[str]:
    nouns: list[str] = []
    for token in kiwi.tokenize(normalize_text(text)):
        if str(getattr(token, "tag", "")).startswith("N"):
            nouns.append(str(getattr(token, "form", "")))
    return nouns


def _okt_nouns(okt: Any, text: str) -> list[str]:
    return [str(noun) for noun in okt.nouns(normalize_text(text))]
