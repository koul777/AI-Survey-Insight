from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any, Sequence

import numpy as np

from .embeddings import EmbeddingResult

MODEL_ID = "intfloat/multilingual-e5-small"
_MODEL_LOCK = RLock()


def local_model_path() -> Path:
    return Path(os.environ.get("SURVEY_INSIGHT_LOCAL_MODEL_PATH", "out_models/multilingual-e5-small")).resolve()


def local_embedding_status() -> dict[str, Any]:
    path = local_model_path()
    ready = all((path / name).is_file() for name in (
        "config.json", "model.safetensors", "tokenizer.json", "modules.json", "1_Pooling/config.json", "survey_insight_model.json"))
    return {"available": ready, "model": MODEL_ID, "runtime_network": False}


def download_local_model() -> Path:
    """Explicit setup operation. Analysis never initiates model downloads."""
    if os.environ.get("SURVEY_INSIGHT_DISABLE_NETWORK", "").lower() in {"1", "true", "yes"}:
        raise RuntimeError("Model download is disabled by SURVEY_INSIGHT_DISABLE_NETWORK.")
    from huggingface_hub import HfApi, snapshot_download

    revision = HfApi().model_info(MODEL_ID).sha
    path = local_model_path()
    snapshot_download(
        repo_id=MODEL_ID, revision=revision, local_dir=str(path),
        allow_patterns=["*.json", "*.txt", "*.model", "model.safetensors", "1_Pooling/*", "README.md"],
    )
    (path / "survey_insight_model.json").write_text(
        json.dumps({"model_id": MODEL_ID, "revision": revision, "license": "MIT"}, indent=2), encoding="utf-8")
    return path


@lru_cache(maxsize=1)
def _load_model(path: str) -> Any:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(path, local_files_only=True, trust_remote_code=False, device="cpu")
    model.max_seq_length = 512
    return model


def embed_texts_locally(texts: Sequence[str]) -> EmbeddingResult:
    if not local_embedding_status()["available"]:
        return EmbeddingResult(np.empty((0, 0)), "local_model_unavailable", MODEL_ID,
                               ["로컬 의미 모델이 설치되지 않아 형태소 기반 토픽모델만 실행했습니다. setup-local-model 명령으로 설치할 수 있습니다."])
    try:
        with _MODEL_LOCK:
            model = _load_model(str(local_model_path()))
            chunks: list[str] = []
            owners: list[int] = []
            weights: list[int] = []
            for index, text in enumerate(texts):
                ids = model.tokenizer.encode(text, add_special_tokens=False, truncation=False, verbose=False)
                if len(ids) <= 480:
                    chunks.append("query: " + text)
                    owners.append(index)
                    weights.append(max(1, len(ids)))
                else:
                    for start in range(0, len(ids), 480):
                        part = ids[start:start + 480]
                        chunks.append("query: " + model.tokenizer.decode(part, skip_special_tokens=True))
                        owners.append(index)
                        weights.append(len(part))
            # E5's documented clustering prefix. Long responses retain all
            # token chunks instead of silently discarding everything after 512.
            encoded = np.asarray(model.encode(chunks,
                                                batch_size=16, normalize_embeddings=True,
                                                show_progress_bar=False, convert_to_numpy=True))
            if encoded.ndim != 2 or len(encoded) != len(chunks) or not np.isfinite(encoded).all():
                raise ValueError("Invalid local embedding output")
            vectors = np.zeros((len(texts), encoded.shape[1]), dtype=float)
            for owner, weight, vector in zip(owners, weights, encoded):
                vectors[owner] += weight * vector
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            if np.any(norms == 0):
                raise ValueError("Zero local embedding")
            vectors /= norms
        if vectors.ndim != 2 or len(vectors) != len(texts) or not np.isfinite(vectors).all():
            raise ValueError("Invalid local embedding output")
        manifest_path = local_model_path() / "survey_insight_model.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        return EmbeddingResult(vectors, "local_sentence_transformer", MODEL_ID, [],
                               {"input_documents": len(texts), "encoded_chunks": len(chunks),
                                "model_revision": manifest.get("revision", "unknown"),
                                "long_text_strategy": "480_token_weighted_pooling", "max_sequence_length": 512})
    except Exception:
        return EmbeddingResult(np.empty((0, 0)), "local_model_unavailable", MODEL_ID,
                               ["로컬 의미 모델을 실행하지 못해 형태소 기반 토픽모델만 사용했습니다. 모델 설치와 sentence-transformers 의존성을 확인하세요."])
