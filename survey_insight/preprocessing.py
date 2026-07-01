from __future__ import annotations

import re
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
}

_TOKENIZER_BACKEND: Any | None = None
_TOKENIZER_SOURCE = ""

PII_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    ("phone", re.compile(r"\b(?:010|011|016|017|018|019)[-. ]?\d{3,4}[-. ]?\d{4}\b"), "[PHONE]"),
    ("employee_id", re.compile(r"\b(?:사번|직번|employee\s*id)[:\s-]*[A-Za-z0-9-]{4,}\b", re.I), "[EMPLOYEE_ID]"),
]


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_no_opinion(value: Any) -> bool:
    text = normalize_text(value).lower()
    text = re.sub(r"\s+", " ", text)
    return text in NO_OPINION_VALUES


def mask_pii(text: str) -> tuple[str, list[str]]:
    found: list[str] = []
    masked = text
    for name, pattern, replacement in PII_PATTERNS:
        if pattern.search(masked):
            found.append(name)
            masked = pattern.sub(replacement, masked)
    return masked, found


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
            )
        )
    return documents


def valid_documents(documents: list[TextDocument]) -> list[TextDocument]:
    return [doc for doc in documents if not doc.is_no_opinion and doc.redacted_text]


def tokenize_keywords(text: str) -> list[str]:
    tokenizer = _get_tokenizer_backend()
    if tokenizer[0].startswith("kiwi"):
        tokens = _kiwi_nouns(tokenizer[1], text)
    elif tokenizer[0].startswith("konlpy_okt"):
        tokens = _okt_nouns(tokenizer[1], text)
    else:
        tokens = re.findall(r"[가-힣A-Za-z0-9]{2,}", normalize_text(text).lower())
    cleaned: list[str] = []
    for token in tokens:
        normalized = normalize_text(token).lower()
        if normalized in STOPWORDS:
            continue
        if normalized.isdigit():
            continue
        if len(normalized) < 2:
            continue
        cleaned.append(normalized)
    return cleaned


def tokenizer_source() -> str:
    return _get_tokenizer_backend()[0]


def _get_tokenizer_backend() -> tuple[str, Any | None]:
    global _TOKENIZER_BACKEND, _TOKENIZER_SOURCE
    if _TOKENIZER_SOURCE:
        return _TOKENIZER_SOURCE, _TOKENIZER_BACKEND
    try:
        from kiwipiepy import Kiwi  # type: ignore

        _TOKENIZER_BACKEND = Kiwi()
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


def _kiwi_nouns(kiwi: Any, text: str) -> list[str]:
    nouns: list[str] = []
    for token in kiwi.tokenize(normalize_text(text)):
        if str(getattr(token, "tag", "")).startswith("N"):
            nouns.append(str(getattr(token, "form", "")))
    return nouns


def _okt_nouns(okt: Any, text: str) -> list[str]:
    return [str(noun) for noun in okt.nouns(normalize_text(text))]
