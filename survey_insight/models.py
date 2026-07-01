from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TableData:
    headers: list[str]
    rows: list[dict[str, Any]]
    sheet_name: str | None = None
    header_row_index: int = 0
    source_name: str | None = None


@dataclass
class ColumnProfile:
    column_name: str
    detected_type: str
    confidence: float
    missing_rate: float
    unique_rate: float
    text_score: float
    reasons: list[str] = field(default_factory=list)
    signals: dict[str, float] = field(default_factory=dict)
    sample_values: list[str] = field(default_factory=list)


@dataclass
class DatasetProfile:
    dataset_id: str
    sheet_name: str | None
    row_count: int
    column_count: int
    header_row_index: int
    columns: list[ColumnProfile]
    recommended_text_columns: list[ColumnProfile]
    warnings: list[str] = field(default_factory=list)


@dataclass
class TextDocument:
    id: str
    row_index: int
    text_column: str
    original_text: str
    redacted_text: str
    metadata: dict[str, Any]
    is_no_opinion: bool = False
    pii_found: list[str] = field(default_factory=list)


@dataclass
class Topic:
    topic_id: str
    label: str
    summary: str
    count: int
    share: float
    keywords: list[str]
    representative_responses: list[str]
    sentiment_label: str = "neutral"
    sentiment_score: float = 0.0
    urgency_score: float = 0.0
    sentiment_evidence: list[str] = field(default_factory=list)
    sentiment_method: str = "rule_lexicon_fallback"
    plain_language_summary: str = ""
    suggested_action: str = ""
    sentiment_plain_language: str = ""
    interpretation_source: str = "local_plain_language"
    parent_topic_id: str | None = None


@dataclass
class TopicAssignment:
    document_id: str
    topic_id: str
    probability: float
    is_outlier: bool
    assignment_source: str


@dataclass
class CandidateSolution:
    candidate_id: str
    topic_count: int
    params: dict[str, Any]
    metrics: dict[str, float]
    score: float
    rank: int = 0
    warnings: list[str] = field(default_factory=list)
    topics: list[Topic] = field(default_factory=list)
    assignments: list[TopicAssignment] = field(default_factory=list)


@dataclass
class Recommendation:
    run_id: str
    mode: str
    valid_response_count: int
    allowed_topic_range: tuple[int, int]
    minimum_topic_size: int
    recommended: CandidateSolution
    wider: CandidateSolution | None
    detailed: CandidateSolution | None
    candidates: list[CandidateSolution]
    warnings: list[str] = field(default_factory=list)
    plain_language_summary: str = ""
    topic_count_explanation: str = ""
    methodology_plain_language: str = ""
    quality_warnings: list[str] = field(default_factory=list)


@dataclass
class UserEdit:
    edit_type: str
    before: dict[str, Any]
    after: dict[str, Any]
    user_id: str
    timestamp: str = field(default_factory=utc_now)


@dataclass
class AnalysisPackage:
    project: dict[str, Any]
    dataset_profile: DatasetProfile
    text_column: str
    group_columns: list[str]
    documents: list[TextDocument]
    recommendation: Recommendation
    selected_candidate_id: str
    selected_topics: list[Topic]
    assignments: list[TopicAssignment]
    cross_analysis: list[dict[str, Any]]
    user_edits: list[UserEdit] = field(default_factory=list)
    methodology_note: str = (
        "분석 결과는 자유응답 기반 주제 탐색이며, 최종 해석은 담당자의 검토를 거쳤다."
    )
    created_at: str = field(default_factory=utc_now)


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {k: to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value
