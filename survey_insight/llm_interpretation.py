from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from .explanations import apply_topic_explanation
from .models import AnalysisPackage, Topic
from .provider_config import (
    ANTHROPIC_MESSAGES_URL,
    DEFAULT_AZURE_API_VERSION,
    GEMINI_API_BASE_URL,
    OPENAI_RESPONSES_URL,
    provider_config,
)
VALID_SENTIMENT_LABELS = {"positive", "neutral", "negative", "mixed"}


def enhance_with_user_llm(
    package: AnalysisPackage,
    provider: str | None,
    api_key: str | None,
    *,
    base_url: str | None = None,
    model: str | None = None,
    azure_api_version: str | None = None,
) -> list[str]:
    """Use a user-supplied API key once to improve explanations; never persist the key."""

    provider_name = (provider or "").strip().casefold()
    if not provider_name:
        return []
    if not api_key:
        return ["Provider가 선택되었지만 API Key가 없어 로컬 해석만 사용했습니다."]
    if _looks_like_placeholder_key(api_key):
        return ["테스트 또는 예시 API Key로 보여 외부 호출을 생략하고 로컬 해석만 사용했습니다."]
    try:
        request = _chat_request(provider_name, base_url, model, azure_api_version)
        payload = _build_provider_payload(package, request)
        response = _post_chat_completion(api_key.strip(), request, payload)
        content = _extract_chat_content(response, request)
        interpretation = _loads_json_object(content)
        _apply_llm_interpretation(package, interpretation, str(request["source"]))
        return []
    except Exception as exc:
        return [f"LLM 해석 보강에 실패해 로컬 해석만 사용했습니다: {_safe_error(exc)}"]


def _chat_request(
    provider_name: str,
    base_url: str | None,
    model: str | None,
    azure_api_version: str | None,
) -> dict[str, Any]:
    selected_model = (model or "").strip()
    if provider_name == "openai":
        default_model = provider_config("openai").default_chat_model or ""
        model_name = selected_model or os.environ.get("SURVEY_INSIGHT_OPENAI_MODEL", default_model)
        return {
            "url": OPENAI_RESPONSES_URL,
            "header_mode": "bearer",
            "payload_model": model_name,
            "model_label": model_name,
            "provider_type": "openai_responses",
            "source": "openai_llm",
        }
    if provider_name == "gemini":
        default_model = provider_config("gemini").default_chat_model or ""
        model_name = selected_model or os.environ.get("SURVEY_INSIGHT_GEMINI_MODEL", default_model)
        return {
            "url": f"{GEMINI_API_BASE_URL}/models/{model_name}:generateContent",
            "header_mode": "gemini",
            "payload_model": model_name,
            "model_label": model_name,
            "provider_type": "gemini",
            "source": "gemini_llm",
        }
    if provider_name == "claude":
        default_model = provider_config("claude").default_chat_model or ""
        model_name = selected_model or os.environ.get("SURVEY_INSIGHT_CLAUDE_MODEL", default_model)
        return {
            "url": ANTHROPIC_MESSAGES_URL,
            "header_mode": "anthropic",
            "payload_model": model_name,
            "model_label": model_name,
            "provider_type": "anthropic",
            "source": "claude_llm",
        }
    if provider_name == "azure_openai":
        endpoint = _require_url(base_url, "Azure OpenAI endpoint")
        deployment = _require_text(selected_model, "Azure chat deployment")
        api_version = (azure_api_version or DEFAULT_AZURE_API_VERSION).strip()
        return {
            "url": f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}",
            "header_mode": "azure",
            "payload_model": None,
            "model_label": deployment,
            "provider_type": "openai_compatible",
            "source": "azure_openai_llm",
        }
    if provider_name in {"custom", "openai_compatible"}:
        endpoint = _require_url(base_url, "OpenAI-compatible base URL")
        default_model = provider_config("openai_compatible").default_chat_model or ""
        model_name = selected_model or os.environ.get("SURVEY_INSIGHT_OPENAI_MODEL", default_model)
        return {
            "url": f"{endpoint}/chat/completions",
            "header_mode": "bearer",
            "payload_model": model_name,
            "model_label": model_name,
            "provider_type": "openai_compatible",
            "source": "openai_compatible_llm",
        }
    raise ValueError(f"Unsupported provider: {provider_name}")


def _build_provider_payload(package: AnalysisPackage, request: dict[str, Any]) -> dict[str, Any]:
    system_prompt = _system_prompt()
    user_content = json.dumps(_llm_input(package), ensure_ascii=False)
    if request.get("provider_type") == "openai_responses":
        return {
            "model": str(request["payload_model"]),
            "instructions": system_prompt,
            "input": user_content,
            "reasoning": {"effort": "low"},
            "max_output_tokens": 4096,
            "text": {"format": {"type": "json_object"}},
        }
    if request.get("provider_type") == "gemini":
        return {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
    if request.get("provider_type") == "anthropic":
        return {
            "model": str(request["payload_model"]),
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_content}],
        }
    payload: dict[str, Any] = {
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
    }
    if request.get("payload_model"):
        payload["model"] = str(request["payload_model"])
    return payload


def _system_prompt() -> str:
    return (
        "You are a Korean survey research analyst. Return only a JSON object. "
        "Explain topic modeling results in plain Korean for non-experts and perform evidence-grounded "
        "topic-level sentiment and urgency classification. Use local sentiment values only as hints. "
        "Base every sentiment label, urgency score, and suggested action on the provided keywords, "
        "representative responses, counts, and evidence terms. "
        "Call the topic count a recommendation, never a statistically optimal or validated value. "
        "Describe urgency_score only as priority-to-review, never an emergency, risk, clinical, or psychological diagnosis. "
        "Do not claim complete anonymization. Do not invent facts, departments, policies, or root causes."
    )


def _llm_input(package: AnalysisPackage) -> dict[str, Any]:
    rec = package.recommendation
    return {
        "task": (
            "Improve the plain Korean interpretation and classify each topic's sentiment from evidence. JSON schema: "
            "{plain_language_summary, topic_count_explanation, methodology_plain_language, topics:["
            "{topic_id,label,summary,plain_language_summary,suggested_action,"
            "sentiment_label,sentiment_score,sentiment_plain_language,urgency_score,sentiment_evidence}]}. "
            "sentiment_label must be one of positive, neutral, negative, mixed. "
            "sentiment_score must be -1.0 to 1.0 where negative is dissatisfaction, positive is satisfaction, and 0 is neutral. "
            "urgency_score must be 0.0-1.0 and means priority-to-review, not necessarily an emergency."
        ),
        "analysis_context": {
            "valid_response_count": rec.valid_response_count,
            "recommended_topic_count": rec.recommended.topic_count,
            "allowed_topic_range": list(rec.allowed_topic_range),
            "mode": rec.mode,
            "candidate_engines": sorted(
                {str(candidate.params.get("engine", "")) for candidate in rec.candidates if candidate.params}
            ),
            "warnings": rec.warnings + rec.quality_warnings,
        },
        "topics": [_topic_payload(topic) for topic in package.selected_topics],
    }


def _topic_payload(topic: Topic) -> dict[str, Any]:
    return {
        "topic_id": topic.topic_id,
        "current_label": topic.label,
        "current_summary": topic.summary,
        "count": topic.count,
        "share": topic.share,
        "keywords": topic.keywords[:8],
        "representative_responses": [_shorten(response, 280) for response in topic.representative_responses[:3]],
        "local_sentiment_label": topic.sentiment_label,
        "local_sentiment_score": topic.sentiment_score,
        "local_urgency_score": topic.urgency_score,
        "sentiment_evidence": topic.sentiment_evidence[:8],
        "sentiment_method": topic.sentiment_method,
    }


def _post_chat_completion(api_key: str, request_settings: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if os.environ.get("SURVEY_INSIGHT_DISABLE_NETWORK", "").strip().casefold() in {"1", "true", "yes"}:
        raise RuntimeError("External network calls are disabled.")
    headers = {"Content-Type": "application/json"}
    header_mode = request_settings.get("header_mode")
    if header_mode == "azure":
        headers["api-key"] = api_key
    elif header_mode == "gemini":
        headers["x-goog-api-key"] = api_key
    elif header_mode == "anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        str(request_settings["url"]),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_chat_content(response: dict[str, Any], request_settings: dict[str, Any]) -> str:
    provider_type = request_settings.get("provider_type")
    if provider_type == "gemini":
        candidates = response.get("candidates") or []
        if not candidates:
            raise ValueError("Gemini response did not include candidates.")
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        text = "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict)).strip()
        if not text:
            raise ValueError("Gemini response did not include text content.")
        return text
    if provider_type == "anthropic":
        blocks = response.get("content") or []
        text = "".join(str(block.get("text") or "") for block in blocks if isinstance(block, dict)).strip()
        if not text:
            raise ValueError("Claude response did not include text content.")
        return text
    if provider_type == "openai_responses":
        direct_text = response.get("output_text")
        if isinstance(direct_text, str) and direct_text.strip():
            return direct_text.strip()
        chunks: list[str] = []
        for item in response.get("output") or []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue
                text = content.get("text") or content.get("output_text")
                if isinstance(text, str):
                    chunks.append(text)
        text = "".join(chunks).strip()
        if not text:
            raise ValueError("OpenAI Responses API did not include text content.")
        return text
    choices = response.get("choices") or []
    if not choices:
        raise ValueError("OpenAI response did not include choices.")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("OpenAI response did not include text content.")
    return content


def _loads_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S)
    if fenced:
        text = fenced.group(1).strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("LLM interpretation must be a JSON object.")
    return parsed


def _apply_llm_interpretation(package: AnalysisPackage, interpretation: dict[str, Any], llm_source: str) -> None:
    rec = package.recommendation
    rec.plain_language_summary = _clean_text(
        interpretation.get("plain_language_summary"), rec.plain_language_summary
    )
    rec.topic_count_explanation = _clean_text(
        interpretation.get("topic_count_explanation"), rec.topic_count_explanation
    )
    rec.methodology_plain_language = _clean_text(
        interpretation.get("methodology_plain_language"), rec.methodology_plain_language
    )
    topics_by_id = {topic.topic_id: topic for topic in package.selected_topics}
    for item in interpretation.get("topics") or []:
        if not isinstance(item, dict):
            continue
        topic = topics_by_id.get(str(item.get("topic_id") or ""))
        if topic is None:
            continue
        _apply_topic_item(topic, item, llm_source)
    rec.recommended.topics = package.selected_topics
    for topic in package.selected_topics:
        if not topic.plain_language_summary or not topic.suggested_action:
            apply_topic_explanation(topic)


def _apply_topic_item(topic: Topic, item: dict[str, Any], llm_source: str) -> None:
    topic.label = _clean_text(item.get("label"), topic.label, max_length=80)
    topic.summary = _clean_text(item.get("summary"), topic.summary, max_length=240)
    topic.plain_language_summary = _clean_text(
        item.get("plain_language_summary"), topic.plain_language_summary, max_length=300
    )
    topic.suggested_action = _clean_text(item.get("suggested_action"), topic.suggested_action, max_length=300)
    topic.sentiment_plain_language = _clean_text(
        item.get("sentiment_plain_language"), topic.sentiment_plain_language, max_length=260
    )
    _apply_sentiment_item(topic, item, llm_source)
    topic.interpretation_source = llm_source


def _apply_sentiment_item(topic: Topic, item: dict[str, Any], llm_source: str) -> None:
    sentiment_label = str(item.get("sentiment_label") or "").casefold()
    urgency_score = _optional_score(item.get("urgency_score"))
    sentiment_score = _optional_signed_score(item.get("sentiment_score"))
    evidence = item.get("sentiment_evidence")
    grounded_evidence = _grounded_sentiment_evidence(topic, evidence)
    if (
        sentiment_label not in VALID_SENTIMENT_LABELS
        or urgency_score is None
        or sentiment_score is None
        or not grounded_evidence
        or not _sentiment_label_matches_score(sentiment_label, sentiment_score)
    ):
        return
    topic.sentiment_label = sentiment_label
    topic.sentiment_method = f"{llm_source}_evidence"
    topic.urgency_score = urgency_score
    topic.sentiment_score = sentiment_score
    topic.sentiment_evidence = grounded_evidence


def _grounded_sentiment_evidence(topic: Topic, evidence: Any) -> list[str]:
    if not isinstance(evidence, list):
        return []
    source = " ".join(
        [*topic.keywords, *topic.representative_responses, *topic.sentiment_evidence]
    ).casefold()
    grounded: list[str] = []
    for value in evidence:
        cleaned = _clean_text(value, "", max_length=40)
        if cleaned and cleaned.casefold() in source and cleaned not in grounded:
            grounded.append(cleaned)
    return grounded[:8]


def _sentiment_label_matches_score(label: str, score: float) -> bool:
    if label == "positive":
        return score >= 0.15
    if label == "negative":
        return score <= -0.15
    if label == "neutral":
        return -0.15 < score < 0.15
    return label == "mixed"


def _copy_topic_interpretation(source: Topic, target: Topic) -> None:
    target.label = source.label
    target.summary = source.summary
    target.plain_language_summary = source.plain_language_summary
    target.suggested_action = source.suggested_action
    target.sentiment_label = source.sentiment_label
    target.sentiment_score = source.sentiment_score
    target.urgency_score = source.urgency_score
    target.sentiment_evidence = list(source.sentiment_evidence)
    target.sentiment_plain_language = source.sentiment_plain_language
    target.sentiment_method = source.sentiment_method
    target.interpretation_source = source.interpretation_source


def _optional_score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= score <= 1.0:
        return None
    return round(score, 3)


def _optional_signed_score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if not -1.0 <= score <= 1.0:
        return None
    return round(score, 3)


def _clean_text(value: Any, fallback: str, max_length: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return fallback
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _looks_like_placeholder_key(api_key: str) -> bool:
    key = api_key.strip().casefold()
    markers = ("test", "dummy", "example", "placeholder", "not-stored", "changeme")
    return len(key) < 30 or any(marker in key for marker in markers)


def _require_url(value: str | None, label: str) -> str:
    text = str(value or "").strip().rstrip("/")
    if not text:
        raise ValueError(f"{label} is required.")
    if not text.startswith(("https://", "http://")):
        raise ValueError(f"{label} must start with http:// or https://.")
    return text


def _require_text(value: str | None, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required.")
    return text


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return "network error"
    return exc.__class__.__name__


def _shorten(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
