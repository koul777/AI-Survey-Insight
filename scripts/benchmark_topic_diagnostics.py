"""Measure diverse-language diagnostics without tuning to their broad labels."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sklearn.metrics import adjusted_rand_score
from survey_insight.models import TableData
from survey_insight.pipeline import analyze_table


def run(name: str, rows: list[dict[str, str]], local_embeddings: bool) -> dict:
    started = time.perf_counter()
    package = analyze_table(TableData(["response", "gold"], rows), text_column="response",
                            group_columns=[], local_embeddings=local_embeddings)
    assignments = {item.document_id: item.topic_id for item in package.assignments}
    candidate = package.recommendation.recommended
    return {
        "name": name, "local_embeddings": local_embeddings, "rows": len(rows),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "topic_count": candidate.topic_count,
        "ari_to_broad_analyst_categories": adjusted_rand_score(
            [row["gold"] for row in rows], [assignments[doc.id] for doc in package.documents]),
        "engine": candidate.params["engine"], "metrics": candidate.metrics,
        "metric_profile": candidate.params["metric_profile"],
        "quality_status": candidate.params.get("result_quality_status"),
        "quality_reasons": candidate.params.get("result_quality_reasons", []),
        "topics": [{"count": topic.count, "keywords": topic.keywords} for topic in candidate.topics],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("out_benchmark/topic_diagnostics.json"))
    parser.add_argument("--local-embeddings", action="store_true",
                        help="Also run the already-installed local E5 model; never downloads it.")
    args = parser.parse_args()
    fixture = json.loads((ROOT / "tests/fixtures/topic_paraphrases.json").read_text(encoding="utf-8"))
    rows = [{"response": text, "gold": subject} for subject, texts in fixture["topics"].items() for text in texts]
    results = [run("diverse_paraphrases", rows, False)]
    if args.local_embeddings:
        results.append(run("diverse_paraphrases", rows, True))
        imbalanced = [{"response": text, "gold": subject}
                      for subject, texts in fixture["topics"].items()
                      for text in texts[:4 if subject == "facilities" else 8]]
        results.append(run("imbalanced_paraphrases", imbalanced, True))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"scope": fixture["description"], "results": results},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
    for item in results:
        print(f"{item['name']} local={item['local_embeddings']}: "
              f"ARI={item['ari_to_broad_analyst_categories']:.3f}, "
              f"k={item['topic_count']}, quality={item['quality_status']}")
    print(f"Report: {args.out}")


if __name__ == "__main__":
    main()
