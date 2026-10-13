from __future__ import annotations

from copy import deepcopy
from typing import Any

from .explanations import apply_topic_explanation
from .models import AnalysisPackage, Topic, UserEdit, utc_now
from .preprocessing import mask_pii, normalize_text
from .sentiment import aggregate_document_sentiment


def apply_edit(package: AnalysisPackage, edit_type: str, payload: dict[str, Any], user_id: str = "system") -> UserEdit:
    before = _snapshot(package)
    if edit_type == "record_review":
        _record_review(package, payload, user_id)
    elif edit_type == "rename_topic":
        _rename_topic(package, payload["topic_id"], payload["label"], payload.get("summary"))
    elif edit_type == "replace_representative":
        _replace_representative(package, payload["topic_id"], payload["response"])
    elif edit_type == "exclude_topic":
        _exclude_topic(package, payload["topic_id"])
    elif edit_type == "merge_topics":
        _merge_topics(package, payload["source_topic_ids"], payload["target_label"])
    else:
        raise ValueError(f"Unsupported edit_type: {edit_type}")
    if edit_type != "record_review":
        _mark_review_pending(package)
    if edit_type in {"merge_topics", "exclude_topic"}:
        from .pipeline import build_cross_analysis

        package.cross_analysis = build_cross_analysis(package.documents, package.assignments,
                                                      package.selected_topics, package.group_columns)
        _invalidate_model_diagnostics(package)
    _sync_selected_candidate(package)
    after = _snapshot(package)
    edit = UserEdit(edit_type=edit_type, before=before, after=after, user_id=user_id)
    package.user_edits.append(edit)
    return edit


def _rename_topic(package: AnalysisPackage, topic_id: str, label: str, summary: str | None) -> None:
    topic = _find_topic(package.selected_topics, topic_id)
    label = _clean_editor_text(label, "label")
    clean_summary = _clean_editor_text(summary, "summary", allow_empty=True) if summary is not None else None
    topic.label = label
    if summary is not None:
        topic.summary = clean_summary
    topic.interpretation_source = "user_edit_local"
    apply_topic_explanation(topic)
    for row in package.cross_analysis:
        if row.get("topic_id") == topic_id:
            row["topic_label"] = label


def _replace_representative(package: AnalysisPackage, topic_id: str, response: str) -> None:
    topic = _find_topic(package.selected_topics, topic_id)
    response = _clean_editor_text(response, "response")
    reps = [response] + [item for item in topic.representative_responses if item != response]
    topic.representative_responses = reps[:3]


def _exclude_topic(package: AnalysisPackage, topic_id: str) -> None:
    _find_topic(package.selected_topics, topic_id)
    excluded_ids = {item.document_id for item in package.assignments if item.topic_id == topic_id}
    for document in package.documents:
        if document.id in excluded_ids:
            document.topic_exclusion_reason = "user_excluded_topic"
    package.selected_topics = [topic for topic in package.selected_topics if topic.topic_id != topic_id]
    package.assignments = [assignment for assignment in package.assignments if assignment.topic_id != topic_id]
    for assignment in package.assignments:
        if topic_id not in assignment.membership_scores:
            continue
        assignment.membership_scores.pop(topic_id)
        total = sum(assignment.membership_scores.values())
        if total > 0:
            assignment.membership_scores = {
                key: round(value / total, 6) for key, value in assignment.membership_scores.items()
            }
            assignment.probability = assignment.membership_scores.get(assignment.topic_id, assignment.probability)
        assignment.score_method = "membership_conditional_on_retained_topics"
        assignment.needs_review = True
    package.cross_analysis = [row for row in package.cross_analysis if row.get("topic_id") != topic_id]
    _recalculate_topic_shares(package)


def _merge_topics(package: AnalysisPackage, source_topic_ids: list[str], target_label: str) -> None:
    if len(source_topic_ids) < 2:
        raise ValueError("merge_topics requires at least two source_topic_ids")
    target_id = source_topic_ids[0]
    source_set = set(source_topic_ids)
    merged = [topic for topic in package.selected_topics if topic.topic_id in source_set]
    if len(source_set) != len(source_topic_ids) or len(merged) != len(source_set):
        raise ValueError("merge_topics requires distinct existing topic IDs")
    target_label = _clean_editor_text(target_label, "target_label")
    total = sum(topic.count for topic in merged)
    all_keywords: list[str] = []
    all_reps: list[str] = []
    for topic in merged:
        all_keywords.extend(topic.keywords)
    # Interleave source topics so one topic's first three examples do not erase
    # the other source topics from the merged explanation.
    for rank in range(max((len(topic.representative_responses) for topic in merged), default=0)):
        for topic in merged:
            if rank < len(topic.representative_responses):
                all_reps.append(mask_pii(topic.representative_responses[rank])[0])
    document_ids = {a.document_id for a in package.assignments if a.topic_id in source_set and not a.is_outlier}
    sentiment = aggregate_document_sentiment([doc for doc in package.documents if doc.id in document_ids])
    replacement = Topic(
        topic_id=target_id,
        label=target_label,
        summary=f"{target_label} 관련 의견을 병합한 토픽입니다.",
        count=total,
        share=round(total / max(1, len(package.assignments)), 4),
        keywords=list(dict.fromkeys(all_keywords))[:8],
        representative_responses=list(dict.fromkeys(all_reps))[:3],
        sentiment_label=sentiment.dominant_label,
        sentiment_score=sentiment.average_polarity_score,
        urgency_score=sentiment.average_urgency_score,
        sentiment_evidence=list(sentiment.evidence_terms),
        sentiment_method=sentiment.source,
        sentiment_distribution=sentiment.label_counts,
        sentiment_evidence_coverage=sentiment.evidence_coverage,
        sentiment_review_count=sentiment.review_count,
    )
    apply_topic_explanation(replacement)
    package.selected_topics = [topic for topic in package.selected_topics if topic.topic_id not in source_set]
    package.selected_topics.append(replacement)
    package.selected_topics.sort(key=lambda topic: topic.topic_id)
    for assignment in package.assignments:
        had_membership = bool(assignment.membership_scores)
        combined_membership = sum(assignment.membership_scores.pop(source_id, 0.0) for source_id in source_set)
        if had_membership:
            assignment.membership_scores[target_id] = round(combined_membership, 6)
            assignment.score_method = "merged_model_membership"
            if combined_membership > assignment.probability:
                assignment.needs_review = True
        if assignment.topic_id in source_set:
            assignment.topic_id = target_id
            assignment.assignment_source = "user_edit"
            assignment.probability = assignment.membership_scores.get(target_id, assignment.probability)
            assignment.score_method = "merged_model_membership"
            assignment.needs_review = True
    for row in package.cross_analysis:
        if row.get("topic_id") in source_set:
            row["topic_id"] = target_id
            row["topic_label"] = target_label
    _recalculate_topic_shares(package)


def _clean_editor_text(value: str, field_name: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not normalize_text(value)):
        raise ValueError(f"{field_name} must be non-empty text")
    return mask_pii(normalize_text(value))[0]


def _invalidate_model_diagnostics(package: AnalysisPackage) -> None:
    """Keep the fitted model evidence, explicitly scoped to its pre-edit state."""
    warning = "토픽 병합·제외 후의 구성은 다시 적합하지 않았습니다. 모델 점수와 진단은 편집 전 원본 후보에만 해당합니다."
    candidates = [package.recommendation.recommended] + [
        candidate for candidate in package.recommendation.candidates
        if candidate.candidate_id == package.selected_candidate_id
    ]
    for candidate in candidates:
        if "original_model_diagnostics" not in candidate.params:
            candidate.params["original_model_diagnostics"] = {
                "topic_count": candidate.topic_count,
                "score": candidate.score,
                "metrics": deepcopy(candidate.metrics),
                "quality_gate_passed": candidate.params.get("quality_gate_passed"),
            }
        candidate.params["diagnostics_status"] = "invalidated_by_user_edit"
        candidate.params["quality_gate_passed"] = False
        candidate.params["result_quality_status"] = "review_required"
        if warning not in candidate.warnings:
            candidate.warnings.append(warning)
    recommendation = package.recommendation
    for messages in (recommendation.warnings, recommendation.quality_warnings):
        if warning not in messages:
            messages.append(warning)
    recommendation.plain_language_summary = (
        f"사용자 편집 후 {len(package.selected_topics)}개 토픽을 표시합니다. {warning}"
    )
    recommendation.topic_count_explanation = "현재 토픽 수는 자동 권장값이 아니라 사용자가 편집한 구성입니다."


def _find_topic(topics: list[Topic], topic_id: str) -> Topic:
    for topic in topics:
        if topic.topic_id == topic_id:
            return topic
    raise ValueError(f"Topic not found: {topic_id}")


def _record_review(package: AnalysisPackage, payload: dict[str, Any], user_id: str) -> None:
    decision = str(payload.get("decision", "")).strip().casefold()
    if decision not in {"approved", "changes_requested"}:
        raise ValueError("record_review decision must be approved or changes_requested")
    reviewer = str(user_id or "").strip()
    if not reviewer or reviewer == "system":
        raise ValueError("record_review requires an identified reviewer")
    notes = str(payload.get("notes", "") or "").strip()
    if len(notes) > 2000:
        raise ValueError("record_review notes must be 2000 characters or fewer")
    package.project["human_review"] = {
        "status": decision,
        "reviewer": reviewer,
        "notes": notes,
        "reviewed_at": utc_now(),
        "selected_candidate_id": package.selected_candidate_id,
        "topic_count": len(package.selected_topics),
        "edit_count_at_review": len(package.user_edits),
    }


def _mark_review_pending(package: AnalysisPackage) -> None:
    review = package.project.get("human_review")
    if not isinstance(review, dict) or review.get("status") != "approved":
        return
    package.project["human_review"] = {
        **review,
        "status": "changes_pending_review",
        "invalidated_reason": "analysis_changed_after_approval",
    }


def _snapshot(package: AnalysisPackage) -> dict[str, Any]:
    return {
        "human_review": deepcopy(package.project.get("human_review", {"status": "not_reviewed"})),
        "topics": [
            {
                "topic_id": topic.topic_id,
                "label": topic.label,
                "summary": topic.summary,
                "count": topic.count,
                "share": topic.share,
                "representative_responses": topic.representative_responses,
                "sentiment_distribution": topic.sentiment_distribution,
            }
            for topic in deepcopy(package.selected_topics)
        ]
    }


def _sync_selected_candidate(package: AnalysisPackage) -> None:
    package.recommendation.recommended.topics = package.selected_topics
    package.recommendation.recommended.assignments = package.assignments
    package.recommendation.recommended.topic_count = len(package.selected_topics)
    for candidate in package.recommendation.candidates:
        if candidate.candidate_id != package.selected_candidate_id:
            continue
        candidate.topics = package.selected_topics
        candidate.assignments = package.assignments
        candidate.topic_count = len(package.selected_topics)
        break


def _recalculate_topic_shares(package: AnalysisPackage) -> None:
    selected_ids = {topic.topic_id for topic in package.selected_topics}
    counts: dict[str, int] = {}
    for assignment in package.assignments:
        if assignment.is_outlier or assignment.topic_id not in selected_ids:
            continue
        counts[assignment.topic_id] = counts.get(assignment.topic_id, 0) + 1
    denominator = max(1, sum(counts.values()))
    for topic in package.selected_topics:
        topic.count = counts.get(topic.topic_id, 0)
        topic.share = round(topic.count / denominator, 4)
        topic.interpretation_source = "user_edit_local"
        apply_topic_explanation(topic)
        topic.plain_language_summary = topic.plain_language_summary.replace(
            "전체 유효 응답 중", "현재 남은 토픽 배정 중"
        )
