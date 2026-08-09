from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import AnalysisPackage, Topic, UserEdit, utc_now


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
    _sync_selected_candidate(package)
    after = _snapshot(package)
    edit = UserEdit(edit_type=edit_type, before=before, after=after, user_id=user_id)
    package.user_edits.append(edit)
    return edit


def _rename_topic(package: AnalysisPackage, topic_id: str, label: str, summary: str | None) -> None:
    topic = _find_topic(package.selected_topics, topic_id)
    topic.label = label
    if summary is not None:
        topic.summary = summary
    for row in package.cross_analysis:
        if row.get("topic_id") == topic_id:
            row["topic_label"] = label


def _replace_representative(package: AnalysisPackage, topic_id: str, response: str) -> None:
    topic = _find_topic(package.selected_topics, topic_id)
    reps = [response] + [item for item in topic.representative_responses if item != response]
    topic.representative_responses = reps[:3]


def _exclude_topic(package: AnalysisPackage, topic_id: str) -> None:
    package.selected_topics = [topic for topic in package.selected_topics if topic.topic_id != topic_id]
    package.assignments = [assignment for assignment in package.assignments if assignment.topic_id != topic_id]
    package.cross_analysis = [row for row in package.cross_analysis if row.get("topic_id") != topic_id]
    _recalculate_topic_shares(package)


def _merge_topics(package: AnalysisPackage, source_topic_ids: list[str], target_label: str) -> None:
    if len(source_topic_ids) < 2:
        raise ValueError("merge_topics requires at least two source_topic_ids")
    target_id = source_topic_ids[0]
    source_set = set(source_topic_ids)
    merged = [topic for topic in package.selected_topics if topic.topic_id in source_set]
    if not merged:
        raise ValueError(f"No topics found for merge: {source_topic_ids}")
    total = sum(topic.count for topic in merged)
    all_keywords: list[str] = []
    all_reps: list[str] = []
    for topic in merged:
        all_keywords.extend(topic.keywords)
        all_reps.extend(topic.representative_responses)
    replacement = Topic(
        topic_id=target_id,
        label=target_label,
        summary=f"{target_label} 관련 의견을 병합한 토픽입니다.",
        count=total,
        share=round(total / max(1, len(package.assignments)), 4),
        keywords=list(dict.fromkeys(all_keywords))[:8],
        representative_responses=list(dict.fromkeys(all_reps))[:3],
    )
    package.selected_topics = [topic for topic in package.selected_topics if topic.topic_id not in source_set]
    package.selected_topics.append(replacement)
    package.selected_topics.sort(key=lambda topic: topic.topic_id)
    for assignment in package.assignments:
        if assignment.topic_id in source_set:
            assignment.topic_id = target_id
            assignment.assignment_source = "user_edit"
    for row in package.cross_analysis:
        if row.get("topic_id") in source_set:
            row["topic_id"] = target_id
            row["topic_label"] = target_label
    _recalculate_topic_shares(package)


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
    denominator = max(1, len(package.assignments))
    counts: dict[str, int] = {}
    for assignment in package.assignments:
        counts[assignment.topic_id] = counts.get(assignment.topic_id, 0) + 1
    for topic in package.selected_topics:
        topic.count = counts.get(topic.topic_id, topic.count)
        topic.share = round(topic.count / denominator, 4)
