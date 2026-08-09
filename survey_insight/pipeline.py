from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .ingestion import load_table, load_table_bytes
from .models import AnalysisPackage, TableData, to_jsonable
from .preprocessing import preprocess_documents, valid_documents
from .profiling import profile_table
from .topics import recommend_topics


def analyze_file(
    path: str | Path,
    project_name: str = "Survey Insight Project",
    sheet_name: str | None = None,
    text_column: str | None = None,
    group_columns: list[str] | None = None,
    embedding_provider: str | None = None,
    embedding_api_key: str | None = None,
    embedding_base_url: str | None = None,
    embedding_model: str | None = None,
    azure_api_version: str | None = None,
    seed: int = 42,
) -> AnalysisPackage:
    table = load_table(path, sheet_name=sheet_name)
    return analyze_table(
        table,
        project_name=project_name,
        text_column=text_column,
        group_columns=group_columns,
        embedding_provider=embedding_provider,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
        embedding_model=embedding_model,
        azure_api_version=azure_api_version,
        seed=seed,
    )


def analyze_file_bytes(
    data: bytes,
    filename: str,
    project_name: str = "Survey Insight Project",
    sheet_name: str | None = None,
    text_column: str | None = None,
    group_columns: list[str] | None = None,
    embedding_provider: str | None = None,
    embedding_api_key: str | None = None,
    embedding_base_url: str | None = None,
    embedding_model: str | None = None,
    azure_api_version: str | None = None,
    seed: int = 42,
) -> AnalysisPackage:
    table = load_table_bytes(data, filename, sheet_name=sheet_name)
    return analyze_table(
        table,
        project_name=project_name,
        text_column=text_column,
        group_columns=group_columns,
        embedding_provider=embedding_provider,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
        embedding_model=embedding_model,
        azure_api_version=azure_api_version,
        seed=seed,
    )


def analyze_table(
    table: TableData,
    project_name: str = "Survey Insight Project",
    text_column: str | None = None,
    group_columns: list[str] | None = None,
    dataset_id: str | None = None,
    embedding_provider: str | None = None,
    embedding_api_key: str | None = None,
    embedding_base_url: str | None = None,
    embedding_model: str | None = None,
    azure_api_version: str | None = None,
    seed: int = 42,
) -> AnalysisPackage:
    dataset_profile = profile_table(table, dataset_id=dataset_id)
    selected_text_column = text_column or _default_text_column(dataset_profile)
    selected_group_columns = group_columns if group_columns is not None else _default_group_columns(dataset_profile)
    documents = preprocess_documents(table.rows, selected_text_column, metadata_columns=selected_group_columns)
    recommendation = recommend_topics(
        documents,
        seed=seed,
        embedding_provider=embedding_provider,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
        embedding_model=embedding_model,
        azure_api_version=azure_api_version,
    )
    selected = recommendation.recommended
    cross = build_cross_analysis(valid_documents(documents), selected.assignments, selected.topics, selected_group_columns)
    privacy_review_flag_count = sum(bool(document.privacy_review_flags) for document in documents)
    return AnalysisPackage(
        project={
            "name": project_name,
            "analysis_seed": seed,
            "privacy_review_flag_count": privacy_review_flag_count,
        },
        dataset_profile=dataset_profile,
        text_column=selected_text_column,
        group_columns=selected_group_columns,
        documents=documents,
        recommendation=recommendation,
        selected_candidate_id=selected.candidate_id,
        selected_topics=selected.topics,
        assignments=selected.assignments,
        cross_analysis=cross,
    )


def build_cross_analysis(
    documents: list[Any],
    assignments: list[Any],
    topics: list[Any],
    group_columns: list[str],
    suppress_threshold: int = 5,
) -> list[dict[str, Any]]:
    doc_by_id = {doc.id: doc for doc in documents}
    topic_labels = {topic.topic_id: topic.label for topic in topics}
    assigned_topic = {assignment.document_id: assignment.topic_id for assignment in assignments}
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    totals: dict[tuple[str, str], int] = defaultdict(int)
    for doc in documents:
        topic_id = assigned_topic.get(doc.id)
        if not topic_id:
            continue
        for column in group_columns:
            value = _clean_group_value(doc.metadata.get(column))
            key = (column, value, topic_id)
            counts[key] += 1
            totals[(column, value)] += 1
    rows: list[dict[str, Any]] = []
    for (column, value, topic_id), count in sorted(counts.items()):
        total = totals[(column, value)]
        suppressed = count < suppress_threshold
        rows.append(
            {
                "group_column": column,
                "group_value": value,
                "topic_id": topic_id,
                "topic_label": topic_labels.get(topic_id, topic_id),
                "count": count,
                "share": round(count / max(1, total), 4),
                "display_count": None if suppressed else count,
                "suppressed": suppressed,
            }
        )
    return rows


def write_analysis_package(package: AnalysisPackage, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(to_jsonable(package), ensure_ascii=False, indent=2), encoding="utf-8")


def _default_text_column(dataset_profile: Any) -> str:
    if dataset_profile.recommended_text_columns:
        return dataset_profile.recommended_text_columns[0].column_name
    for column in dataset_profile.columns:
        if column.detected_type in {"Free-text Response", "Free-text Candidate"}:
            return column.column_name
    raise ValueError("No free-text response column was detected.")


def _default_group_columns(dataset_profile: Any) -> list[str]:
    groups = [
        column.column_name
        for column in dataset_profile.columns
        if column.detected_type == "Categorical Metadata" and column.missing_rate < 0.8
    ]
    return groups[:5]


def _clean_group_value(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return text or "(blank)"
