"""Reproduce authored regression and optional synthetic scaling checks."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sklearn.metrics import adjusted_rand_score
from survey_insight.evaluation import evaluate_sentiment_rows
from survey_insight.models import TableData
from survey_insight.pipeline import analyze_table


def analyze_topics(rows: list[dict[str, str]], local_embeddings: bool = False) -> dict:
    started = time.perf_counter()
    package = analyze_table(TableData(["response", "gold"], rows), text_column="response",
                            group_columns=[], local_embeddings=local_embeddings)
    assigned = {a.document_id: a.topic_id for a in package.assignments}
    return {
        "rows": len(rows), "elapsed_seconds": round(time.perf_counter() - started, 2),
        "topic_count": len(package.selected_topics),
        "ari": adjusted_rand_score([r["gold"] for r in rows], [assigned[d.id] for d in package.documents]),
        "engine": package.recommendation.recommended.params["engine"],
        "candidate_engines": sorted({c.params["engine"] for c in package.recommendation.candidates}),
        "counts": [t.count for t in package.selected_topics],
        "sentiment": package.recommendation.sentiment_summary,
        "diagnostics": package.recommendation.analysis_diagnostics,
        "warnings": package.recommendation.warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("out_benchmark/regression.json"))
    parser.add_argument("--stress-rows", type=int, default=0)
    parser.add_argument("--local-embeddings", action="store_true")
    args = parser.parse_args()
    if args.stress_rows < 0:
        parser.error("--stress-rows must be non-negative")
    fixture = json.loads((ROOT / "tests/fixtures/korean_analysis.json").read_text(encoding="utf-8"))
    rows = [{"text": text, "label": label} for text, label in fixture["sentiment"]]
    topic_rows = [{"response": text, "gold": label} for label, texts in fixture["topics"].items() for text in texts]
    report = {
        "scope": "Authored development regression; not independent generalization accuracy.",
        "sentiment": evaluate_sentiment_rows(rows, text_column="text", label_column="label"),
        "topics": analyze_topics(topic_rows, args.local_embeddings),
        "repeated_topics": analyze_topics(topic_rows * 3, args.local_embeddings),
    }
    if args.stress_rows:
        subjects = ["교육 강의 실습 교재 과정이 유익합니다.", "급여 연봉 보상 수당 기준이 불공정합니다.",
                    "주차 시설 식당 화장실 공간이 쾌적합니다."]
        stress_rows = [{"response": f"{subjects[i % 3]} ({i})", "gold": str(i % 3)} for i in range(args.stress_rows)]
        report["stress"] = analyze_topics(stress_rows, args.local_embeddings)
        report["stress"]["scope"] = "Three repeated templates with row numbers; scaling check, not diverse-language validation."
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Benchmark saved: {args.out}")
    print(f"Sentiment accuracy on authored cases: {report['sentiment']['accuracy']:.3f}")
    print(f"Topic ARI: {report['topics']['ari']:.3f}; repeated: {report['repeated_topics']['ari']:.3f}")


if __name__ == "__main__":
    main()
