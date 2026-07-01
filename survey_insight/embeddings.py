from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from sklearn.preprocessing import Normalizer


OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_AZURE_API_VERSION = "2024-10-21"


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: np.ndarray
    source: str
    model: str
    warnings: list[str]


def embed_texts_with_provider(
    texts: Sequence[str],
    provider: str | None,
    api_key: str | None,
    *,
    base_url: str | None = None,
    model: str | None = None,
    azure_api_version: str | None = None,
) -> EmbeddingResult | None:
    provider_name = (provider or "").strip().casefold()
    if not provider_name:
        return None
    if not api_key:
        return _unavailable(
            f"{_provider_display(provider_name)} Provider가 선택되었지만 API Key가 없어 의미 임베딩 토픽모델링은 실행하지 않았습니다."
        )
    if _looks_like_placeholder_key(api_key):
        return _unavailable("테스트 또는 예시 API Key로 보여 의미 임베딩 토픽모델링은 실행하지 않았습니다.")
    if provider_name == "claude":
        return _unavailable("Claude는 별도 임베딩 API를 제공하지 않아 로컬 토픽모델 후보만 사용했습니다.")

    try:
        request = _embedding_request(provider_name, base_url, model, azure_api_version)
        if request["provider_type"] == "gemini":
            vectors = _embed_gemini_batches(list(texts), api_key.strip(), request)
        else:
            vectors = _embed_openai_compatible_batches(list(texts), api_key.strip(), request)
        normalized = Normalizer(copy=False).fit_transform(vectors)
        return EmbeddingResult(
            vectors=normalized,
            source=str(request["source"]),
            model=str(request["model_label"]),
            warnings=[],
        )
    except Exception as exc:
        return _unavailable(
            f"{_provider_display(provider_name)} 임베딩 토픽모델링에 실패해 로컬 토픽모델만 사용했습니다: {_safe_error(exc)}"
        )


def _embedding_request(
    provider_name: str,
    base_url: str | None,
    model: str | None,
    azure_api_version: str | None,
) -> dict[str, object]:
    selected_model = (model or "").strip()
    if provider_name == "openai":
        model_name = selected_model or os.environ.get("SURVEY_INSIGHT_OPENAI_EMBEDDING_MODEL", DEFAULT_OPENAI_EMBEDDING_MODEL)
        return {
            "url": OPENAI_EMBEDDINGS_URL,
            "header_mode": "bearer",
            "payload_model": model_name,
            "model_label": model_name,
            "source": "openai_embeddings",
            "provider_type": "openai_compatible",
        }
    if provider_name == "gemini":
        model_name = selected_model or os.environ.get("SURVEY_INSIGHT_GEMINI_EMBEDDING_MODEL", DEFAULT_GEMINI_EMBEDDING_MODEL)
        return {
            "url": f"{GEMINI_API_BASE_URL}/models/{model_name}:embedContent",
            "header_mode": "gemini",
            "payload_model": model_name,
            "model_label": model_name,
            "source": "gemini_embeddings",
            "provider_type": "gemini",
        }
    if provider_name == "azure_openai":
        endpoint = _require_url(base_url, "Azure OpenAI endpoint")
        deployment = _require_text(selected_model, "Azure embedding deployment")
        api_version = (azure_api_version or DEFAULT_AZURE_API_VERSION).strip()
        return {
            "url": f"{endpoint}/openai/deployments/{deployment}/embeddings?api-version={api_version}",
            "header_mode": "azure",
            "payload_model": None,
            "model_label": deployment,
            "source": "azure_openai_embeddings",
            "provider_type": "openai_compatible",
        }
    if provider_name in {"custom", "openai_compatible"}:
        endpoint = _require_url(base_url, "OpenAI-compatible base URL")
        model_name = selected_model or os.environ.get("SURVEY_INSIGHT_OPENAI_EMBEDDING_MODEL", DEFAULT_OPENAI_EMBEDDING_MODEL)
        return {
            "url": f"{endpoint}/embeddings",
            "header_mode": "bearer",
            "payload_model": model_name,
            "model_label": model_name,
            "source": "openai_compatible_embeddings",
            "provider_type": "openai_compatible",
        }
    raise ValueError(f"Unsupported provider: {provider_name}")


def _embed_openai_compatible_batches(texts: list[str], api_key: str, request: dict[str, object]) -> np.ndarray:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), 128):
        batch = [text[:12000] for text in texts[start : start + 128]]
        payload: dict[str, object] = {"input": batch, "encoding_format": "float"}
        if request.get("payload_model"):
            payload["model"] = str(request["payload_model"])
        response = _post_embeddings(api_key, str(request["url"]), str(request["header_mode"]), payload)
        rows = response.get("data") or []
        rows.sort(key=lambda item: int(item.get("index", 0)))
        vectors.extend(row["embedding"] for row in rows)
    if len(vectors) != len(texts):
        raise ValueError("Embedding response count did not match input count.")
    return np.asarray(vectors, dtype=float)


def _embed_gemini_batches(texts: list[str], api_key: str, request: dict[str, object]) -> np.ndarray:
    vectors: list[list[float]] = []
    model_name = str(request["payload_model"])
    for text in texts:
        payload: dict[str, object] = {
            "model": f"models/{model_name}",
            "content": {"parts": [{"text": text[:12000]}]},
        }
        if model_name == "gemini-embedding-001":
            payload["taskType"] = "CLUSTERING"
        response = _post_embeddings(api_key, str(request["url"]), "gemini", payload)
        vectors.append(_extract_gemini_embedding(response))
    if len(vectors) != len(texts):
        raise ValueError("Embedding response count did not match input count.")
    return np.asarray(vectors, dtype=float)


def _post_embeddings(api_key: str, url: str, header_mode: str, payload: dict[str, object]) -> dict[str, object]:
    headers = {"Content-Type": "application/json"}
    if header_mode == "azure":
        headers["api-key"] = api_key
    elif header_mode == "gemini":
        headers["x-goog-api-key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_gemini_embedding(response: dict[str, object]) -> list[float]:
    embedding = response.get("embedding")
    if isinstance(embedding, dict) and isinstance(embedding.get("values"), list):
        return [float(value) for value in embedding["values"]]
    embeddings = response.get("embeddings")
    if isinstance(embeddings, list) and embeddings:
        first = embeddings[0]
        if isinstance(first, dict) and isinstance(first.get("values"), list):
            return [float(value) for value in first["values"]]
    raise ValueError("Gemini embedding response did not include values.")


def _unavailable(message: str) -> EmbeddingResult:
    return EmbeddingResult(vectors=np.empty((0, 0)), source="embedding_unavailable", model="none", warnings=[message])


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


def _provider_display(provider_name: str) -> str:
    return {
        "openai": "OpenAI",
        "gemini": "Gemini",
        "claude": "Claude",
        "azure_openai": "Azure OpenAI",
        "custom": "OpenAI-compatible",
        "openai_compatible": "OpenAI-compatible",
    }.get(provider_name, provider_name)


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return "network error"
    return exc.__class__.__name__
