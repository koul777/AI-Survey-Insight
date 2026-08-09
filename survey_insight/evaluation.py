from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .sentiment import POLARITY_LABELS, analyze_text_sentiment


def evaluate_sentiment_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    text_column: str,
    label_column: str,
) -> dict[str, Any]:
    """Evaluate the local sentiment baseline against user-supplied gold labels.

    The returned report contains aggregate counts only. Raw evaluation text is
    intentionally omitted so the report can be reviewed without duplicating
    survey content.
    """

    labels = tuple(POLARITY_LABELS)
    confusion = {gold: {predicted: 0 for predicted in labels} for gold in labels}
    evaluated = 0
    skipped_empty_text = 0
    skipped_invalid_label = 0
    evidence_count = 0
    for row in rows:
        text = str(row.get(text_column, "") or "").strip()
        gold = str(row.get(label_column, "") or "").strip().casefold()
        if not text:
            skipped_empty_text += 1
            continue
        if gold not in labels:
            skipped_invalid_label += 1
            continue
        result = analyze_text_sentiment(text)
        confusion[gold][result.polarity_label] += 1
        evaluated += 1
        evidence_count += int(bool(result.evidence_terms))

    if evaluated == 0:
        raise ValueError("유효한 텍스트와 gold label이 없습니다.")

    per_class: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    correct = 0
    for label in labels:
        true_positive = confusion[label][label]
        false_positive = sum(confusion[gold][label] for gold in labels if gold != label)
        false_negative = sum(confusion[label][predicted] for predicted in labels if predicted != label)
        support = sum(confusion[label].values())
        precision = _safe_ratio(true_positive, true_positive + false_positive)
        recall = _safe_ratio(true_positive, true_positive + false_negative)
        f1 = _safe_ratio(2 * precision * recall, precision + recall)
        f1_values.append(f1)
        correct += true_positive
        per_class[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }

    return {
        "method": "rule_lexicon_fallback",
        "evaluated_count": evaluated,
        "skipped_empty_text": skipped_empty_text,
        "skipped_invalid_label": skipped_invalid_label,
        "labels": list(labels),
        "accuracy": round(correct / evaluated, 4),
        "macro_f1": round(sum(f1_values) / len(f1_values), 4),
        "evidence_coverage": round(evidence_count / evaluated, 4),
        "per_class": per_class,
        "confusion_matrix": confusion,
        "privacy_note": "평가 보고서에는 원문을 포함하지 않습니다.",
        "interpretation_note": "이 수치는 제공된 gold label 표본에만 적용되며 다른 조사로 일반화되지 않습니다.",
    }


def evaluate_sentiment_csv(
    input_path: str | Path,
    output_path: str | Path,
    *,
    text_column: str,
    label_column: str,
) -> Path:
    source = Path(input_path)
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    report = evaluate_sentiment_rows(rows, text_column=text_column, label_column=label_column)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0
