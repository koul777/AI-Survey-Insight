from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

import numpy as np
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
from sklearn.decomposition import LatentDirichletAllocation, NMF
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import Normalizer
from sklearn.decomposition import TruncatedSVD

from .embeddings import embed_texts_with_provider
from .explanations import apply_plain_language_explanations
from .labeling import label_topic
from .models import (
    CandidateSolution,
    Recommendation,
    TextDocument,
    Topic,
    TopicAssignment,
    new_id,
)
from .preprocessing import tokenize_keywords, tokenizer_source, valid_documents
from .sentiment import aggregate_topic_sentiment


def recommend_topics(
    documents: list[TextDocument],
    seed: int = 42,
    embedding_provider: str | None = None,
    embedding_api_key: str | None = None,
    embedding_base_url: str | None = None,
    embedding_model: str | None = None,
    azure_api_version: str | None = None,
) -> Recommendation:
    valid = valid_documents(documents)
    n = len(valid)
    mode, topic_range, min_topic_size, warnings = topic_policy(n)
    run_id = new_id("run")
    if n == 0:
        empty = _empty_candidate()
        recommendation = Recommendation(
            run_id=run_id,
            mode=mode,
            valid_response_count=0,
            allowed_topic_range=topic_range,
            minimum_topic_size=min_topic_size,
            recommended=empty,
            wider=None,
            detailed=None,
            candidates=[empty],
            warnings=warnings + ["분석 가능한 자유응답이 없습니다."],
        )
        return apply_plain_language_explanations(recommendation)
    texts = [doc.redacted_text for doc in valid]
    vectorizer, matrix = _vectorize(texts)
    embedding_result = embed_texts_with_provider(
        texts,
        embedding_provider,
        embedding_api_key,
        base_url=embedding_base_url,
        model=embedding_model,
        azure_api_version=azure_api_version,
    )
    candidates = _build_candidates(valid, vectorizer, matrix, topic_range, min_topic_size, seed)
    if embedding_result is not None and embedding_result.vectors.size:
        candidates.extend(
            _build_embedding_candidates(
                valid,
                vectorizer,
                matrix,
                embedding_result.vectors,
                topic_range,
                min_topic_size,
                seed,
                embedding_result.source,
                embedding_result.model,
            )
        )
    if not candidates:
        candidates = [_single_topic_candidate(valid, vectorizer, matrix, min_topic_size)]
    candidates.sort(key=lambda candidate: (candidate.score, -candidate.topic_count), reverse=True)
    for rank, candidate in enumerate(candidates, start=1):
        candidate.rank = rank
    recommended = _select_recommended(candidates)
    wider = _select_alternative(candidates, recommended.topic_count, direction=-1)
    detailed = _select_alternative(candidates, recommended.topic_count, direction=1)
    recommendation = Recommendation(
        run_id=run_id,
        mode=mode,
        valid_response_count=n,
        allowed_topic_range=topic_range,
        minimum_topic_size=min_topic_size,
        recommended=recommended,
        wider=wider,
        detailed=detailed,
        candidates=candidates,
        warnings=warnings + (embedding_result.warnings if embedding_result else []),
    )
    return apply_plain_language_explanations(recommendation)


def topic_policy(n: int) -> tuple[str, tuple[int, int], int, list[str]]:
    if n < 15:
        return "초소표본 모드", (1, 3), 2, ["통계적 토픽모델링보다 테마 코딩에 가까운 표본입니다."]
    if n < 30:
        return "소표본 모드", (2, 4), 2, ["유효 응답 수가 작아 결과는 탐색적 해석으로 사용해야 합니다."]
    if n < 50:
        return "소형 설문 모드", (3, 6), max(3, math.ceil(0.08 * n)), ["불안정 토픽 가능성을 확인해야 합니다."]
    if n < 200:
        return "표준 모드", (4, 10), max(4, math.ceil(0.04 * n)), []
    if n < 1000:
        return "대형 설문 모드", (6, 20), max(5, math.ceil(0.02 * n)), []
    return "대량 분석 모드", (10, 30), max(10, math.ceil(0.01 * n)), ["보고서용 토픽 수가 과도하게 늘지 않도록 검토해야 합니다."]


def _vectorize(texts: list[str]) -> tuple[TfidfVectorizer, Any]:
    vectorizer = TfidfVectorizer(
        tokenizer=tokenize_keywords,
        token_pattern=None,
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.95,
    )
    try:
        matrix = vectorizer.fit_transform(texts)
    except ValueError:
        vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), min_df=1)
        matrix = vectorizer.fit_transform(texts)
    return vectorizer, matrix


def _build_candidates(
    documents: list[TextDocument],
    vectorizer: TfidfVectorizer,
    matrix: Any,
    topic_range: tuple[int, int],
    min_topic_size: int,
    seed: int,
) -> list[CandidateSolution]:
    candidates: list[CandidateSolution] = []
    n = len(documents)
    lower, upper = topic_range
    for labels in _cluster_dbscan_candidates(matrix, min_topic_size):
        natural_k = _topic_count_from_labels(labels)
        if lower <= natural_k <= min(upper, n):
            candidates.append(
                _candidate_from_labels(
                    documents, vectorizer, matrix, labels, natural_k, min_topic_size, "dbscan_lsa_natural"
                )
            )
    for k in range(lower, min(upper, n) + 1):
        labels = _cluster(matrix, k, seed)
        if labels is None:
            continue
        candidates.append(_candidate_from_labels(documents, vectorizer, matrix, labels, k, min_topic_size, "kmeans"))
        if n <= 250 and k > 1:
            agglom_labels = _cluster_agglomerative(matrix, k)
            if agglom_labels is not None:
                candidates.append(
                    _candidate_from_labels(
                        documents, vectorizer, matrix, agglom_labels, k, min_topic_size, "agglomerative"
                    )
                )
        nmf_labels = _cluster_nmf(matrix, k, seed)
        if nmf_labels is not None:
            candidates.append(_candidate_from_labels(documents, vectorizer, matrix, nmf_labels, k, min_topic_size, "nmf"))
        lda_labels = _cluster_lda(matrix, k, seed)
        if lda_labels is not None:
            candidates.append(_candidate_from_labels(documents, vectorizer, matrix, lda_labels, k, min_topic_size, "lda"))
    return candidates


def _build_embedding_candidates(
    documents: list[TextDocument],
    vectorizer: TfidfVectorizer,
    keyword_matrix: Any,
    embedding_matrix: np.ndarray,
    topic_range: tuple[int, int],
    min_topic_size: int,
    seed: int,
    embedding_source: str,
    embedding_model: str,
) -> list[CandidateSolution]:
    candidates: list[CandidateSolution] = []
    n = len(documents)
    lower, upper = topic_range
    engine_prefix = _embedding_engine_prefix(embedding_source)
    for labels in _cluster_embedding_dbscan_candidates(embedding_matrix, min_topic_size):
        natural_k = _topic_count_from_labels(labels)
        if lower <= natural_k <= min(upper, n):
            candidates.append(
                _candidate_from_labels(
                    documents,
                    vectorizer,
                    keyword_matrix,
                    labels,
                    natural_k,
                    min_topic_size,
                    f"{engine_prefix}_dbscan",
                    metric_matrix=embedding_matrix,
                    extra_params={"embedding_source": embedding_source, "embedding_model": embedding_model},
                )
            )
    for k in range(lower, min(upper, n) + 1):
        labels = _cluster_embeddings_kmeans(embedding_matrix, k, seed)
        if labels is not None:
            candidates.append(
                _candidate_from_labels(
                    documents,
                    vectorizer,
                    keyword_matrix,
                    labels,
                    k,
                    min_topic_size,
                    f"{engine_prefix}_kmeans",
                    metric_matrix=embedding_matrix,
                    extra_params={"embedding_source": embedding_source, "embedding_model": embedding_model},
                )
            )
        agglom_labels = _cluster_agglomerative(embedding_matrix, k)
        if agglom_labels is not None:
            candidates.append(
                _candidate_from_labels(
                    documents,
                    vectorizer,
                    keyword_matrix,
                    agglom_labels,
                    k,
                    min_topic_size,
                    f"{engine_prefix}_agglomerative",
                    metric_matrix=embedding_matrix,
                    extra_params={"embedding_source": embedding_source, "embedding_model": embedding_model},
                )
            )
    return candidates


def _embedding_engine_prefix(embedding_source: str) -> str:
    return {
        "openai_embeddings": "openai_embedding",
        "gemini_embeddings": "gemini_embedding",
        "azure_openai_embeddings": "azure_openai_embedding",
        "openai_compatible_embeddings": "openai_compatible_embedding",
    }.get(embedding_source, "semantic_embedding")


def _cluster(matrix: Any, k: int, seed: int) -> np.ndarray | None:
    n = matrix.shape[0]
    if k <= 1:
        return np.zeros(n, dtype=int)
    if n < k:
        return None
    model = KMeans(n_clusters=k, random_state=seed, n_init=10)
    return model.fit_predict(matrix)


def _cluster_embeddings_kmeans(matrix: np.ndarray, k: int, seed: int) -> np.ndarray | None:
    n = matrix.shape[0]
    if k <= 1:
        return np.zeros(n, dtype=int)
    if n < k:
        return None
    model = KMeans(n_clusters=k, random_state=seed, n_init=20)
    return model.fit_predict(matrix)


def _cluster_agglomerative(matrix: Any, k: int) -> np.ndarray | None:
    n = matrix.shape[0]
    if k <= 1 or n < k:
        return None
    dense = matrix.toarray() if hasattr(matrix, "toarray") else np.asarray(matrix)
    try:
        model = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average")
    except TypeError:
        model = AgglomerativeClustering(n_clusters=k, affinity="cosine", linkage="average")
    try:
        return model.fit_predict(dense)
    except ValueError:
        return None


def _cluster_dbscan_candidates(matrix: Any, min_topic_size: int) -> list[np.ndarray]:
    n_docs, n_features = matrix.shape
    if n_docs < max(4, min_topic_size * 2) or n_features < 2:
        return []
    dense = matrix.toarray() if hasattr(matrix, "toarray") else np.asarray(matrix)
    n_components = min(10, n_docs - 1, n_features - 1)
    if n_components < 2:
        reduced = dense
    else:
        reduced = TruncatedSVD(n_components=n_components, random_state=42).fit_transform(matrix)
    normalized = Normalizer(copy=False).fit_transform(reduced)
    candidates: list[np.ndarray] = []
    seen: set[tuple[int, ...]] = set()
    for eps in (0.35, 0.45, 0.55, 0.65, 0.75):
        labels = DBSCAN(eps=eps, min_samples=max(2, min_topic_size), metric="cosine").fit_predict(normalized)
        topic_count = _topic_count_from_labels(labels)
        if topic_count < 1:
            continue
        key = tuple(int(label) for label in labels)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(labels)
    return candidates


def _cluster_embedding_dbscan_candidates(matrix: np.ndarray, min_topic_size: int) -> list[np.ndarray]:
    n_docs = matrix.shape[0]
    if n_docs < max(4, min_topic_size * 2):
        return []
    candidates: list[np.ndarray] = []
    seen: set[tuple[int, ...]] = set()
    for eps in (0.15, 0.20, 0.25, 0.30, 0.35):
        labels = DBSCAN(eps=eps, min_samples=max(2, min_topic_size), metric="cosine").fit_predict(matrix)
        topic_count = _topic_count_from_labels(labels)
        if topic_count < 1:
            continue
        key = tuple(int(label) for label in labels)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(labels)
    return candidates


def _cluster_nmf(matrix: Any, k: int, seed: int) -> np.ndarray | None:
    n_docs, n_features = matrix.shape
    if k <= 1:
        return np.zeros(n_docs, dtype=int)
    if n_docs < k or n_features < k:
        return None
    init = "nndsvda" if min(n_docs, n_features) > k else "random"
    model = NMF(n_components=k, init=init, random_state=seed, max_iter=600)
    try:
        weights = model.fit_transform(matrix)
    except ValueError:
        return None
    labels = np.asarray(weights.argmax(axis=1), dtype=int)
    if len(set(labels)) != k:
        return None
    return labels


def _cluster_lda(matrix: Any, k: int, seed: int) -> np.ndarray | None:
    n_docs, n_features = matrix.shape
    if k <= 1:
        return np.zeros(n_docs, dtype=int)
    if n_docs < k or n_features < k:
        return None
    model = LatentDirichletAllocation(
        n_components=k,
        random_state=seed,
        learning_method="batch",
        max_iter=30,
    )
    try:
        weights = model.fit_transform(matrix)
    except ValueError:
        return None
    labels = np.asarray(weights.argmax(axis=1), dtype=int)
    if len(set(labels)) != k:
        return None
    return labels


def _candidate_from_labels(
    documents: list[TextDocument],
    vectorizer: TfidfVectorizer,
    matrix: Any,
    labels: np.ndarray,
    k: int,
    min_topic_size: int,
    source: str,
    metric_matrix: Any | None = None,
    extra_params: dict[str, Any] | None = None,
) -> CandidateSolution:
    topics, assignments = _topics_from_labels(documents, vectorizer, matrix, labels)
    metrics = _metrics(vectorizer, metric_matrix if metric_matrix is not None else matrix, labels, topics, min_topic_size)
    penalty = _penalty(labels, topics, min_topic_size)
    score = (
        0.25 * metrics["stability"]
        + 0.20 * metrics["coherence"]
        + 0.20 * metrics["semantic_quality"]
        + 0.15 * metrics["coverage"]
        + 0.10 * metrics["diversity"]
        + 0.10 * metrics["labelability"]
        - penalty
    )
    warnings = []
    if any(topic.count < min_topic_size for topic in topics):
        warnings.append("최소 토픽 크기보다 작은 토픽이 포함되어 있습니다.")
    if metrics["diversity"] < 0.45:
        warnings.append("유사 키워드가 중복되는 토픽이 있습니다.")
    return CandidateSolution(
        candidate_id=new_id("candidate"),
        topic_count=k,
        params={
            "engine": source,
            "min_topic_size": min_topic_size,
            "tokenizer": tokenizer_source(),
            **(extra_params or {}),
        },
        metrics={**metrics, "penalty": round(penalty, 3)},
        score=round(max(0.0, min(1.0, score)), 3),
        warnings=warnings,
        topics=topics,
        assignments=assignments,
    )


def _topics_from_labels(
    documents: list[TextDocument],
    vectorizer: TfidfVectorizer,
    matrix: Any,
    labels: np.ndarray,
) -> tuple[list[Topic], list[TopicAssignment]]:
    feature_names = np.array(vectorizer.get_feature_names_out())
    label_to_indices: dict[int, list[int]] = defaultdict(list)
    for idx, label in enumerate(labels):
        if int(label) == -1:
            continue
        label_to_indices[int(label)].append(idx)
    topics: list[Topic] = []
    topic_ids: dict[int, str] = {}
    for order, (label, indices) in enumerate(sorted(label_to_indices.items()), start=1):
        topic_id = f"T{order:02d}"
        topic_ids[label] = topic_id
        sub_matrix = matrix[indices]
        mean_vector = np.asarray(sub_matrix.mean(axis=0)).ravel()
        top_indices = mean_vector.argsort()[::-1][:8]
        keywords = [feature_names[i] for i in top_indices if mean_vector[i] > 0][:6]
        reps = _representative_responses([documents[i] for i in indices], sub_matrix, mean_vector)
        topic_label = label_topic(keywords, reps)
        sentiment = aggregate_topic_sentiment([documents[i].redacted_text for i in indices])
        topics.append(
            Topic(
                topic_id=topic_id,
                label=topic_label.label,
                summary=topic_label.summary,
                count=len(indices),
                share=round(len(indices) / max(1, len(documents)), 4),
                keywords=keywords,
                representative_responses=reps,
                sentiment_label=sentiment.dominant_label,
                sentiment_score=sentiment.average_polarity_score,
                urgency_score=sentiment.average_urgency_score,
                sentiment_evidence=list(sentiment.evidence_terms),
                sentiment_method=sentiment.source,
            )
        )
    assignments = [
        TopicAssignment(
            document_id=doc.id,
            topic_id=topic_ids.get(int(labels[idx]), "OUTLIER"),
            probability=0.0 if int(labels[idx]) == -1 else 1.0,
            is_outlier=int(labels[idx]) == -1,
            assignment_source="model",
        )
        for idx, doc in enumerate(documents)
    ]
    return topics, assignments


def _representative_responses(
    documents: list[TextDocument], sub_matrix: Any, mean_vector: np.ndarray
) -> list[str]:
    dense = sub_matrix.toarray() if hasattr(sub_matrix, "toarray") else np.asarray(sub_matrix)
    if dense.size == 0:
        return []
    norms = np.linalg.norm(dense, axis=1) * max(np.linalg.norm(mean_vector), 1e-9)
    similarities = np.divide(dense @ mean_vector, norms, out=np.zeros(dense.shape[0]), where=norms != 0)
    order = similarities.argsort()[::-1]
    reps: list[str] = []
    for idx in order[:3]:
        text = documents[int(idx)].redacted_text
        if text not in reps:
            reps.append(text)
    return reps


def _metrics(
    vectorizer: TfidfVectorizer,
    matrix: Any,
    labels: np.ndarray,
    topics: list[Topic],
    min_topic_size: int,
) -> dict[str, float]:
    counts = [topic.count for topic in topics]
    semantic_quality = _silhouette(matrix, labels)
    coverage = sum(int(label) != -1 for label in labels) / max(1, len(labels))
    diversity = _topic_diversity(topics)
    coherence = _coherence(topics)
    labelability = sum(1.0 if topic.label and topic.representative_responses else 0.4 for topic in topics) / max(1, len(topics))
    balance = _balance(counts)
    small_topic_ratio = sum(count < min_topic_size for count in counts) / max(1, len(counts))
    stability = max(0.0, min(1.0, (semantic_quality * 0.35) + (coherence * 0.30) + (balance * 0.25) + 0.10 - small_topic_ratio * 0.2))
    return {
        "stability": round(stability, 3),
        "coherence": round(coherence, 3),
        "semantic_quality": round(semantic_quality, 3),
        "coverage": round(coverage, 3),
        "diversity": round(diversity, 3),
        "labelability": round(labelability, 3),
        "balance": round(balance, 3),
    }


def _silhouette(matrix: Any, labels: np.ndarray) -> float:
    if len(set(labels)) <= 1 or matrix.shape[0] <= len(set(labels)):
        return 0.0
    dense = matrix.toarray() if hasattr(matrix, "toarray") else np.asarray(matrix)
    try:
        raw = silhouette_score(dense, labels, metric="cosine")
    except Exception:
        return 0.0
    return round(max(0.0, min(1.0, (raw + 1.0) / 2.0)), 3)


def _topic_diversity(topics: list[Topic]) -> float:
    keywords = [keyword for topic in topics for keyword in topic.keywords[:5]]
    if not keywords:
        return 0.0
    return len(set(keywords)) / len(keywords)


def _coherence(topics: list[Topic]) -> float:
    if not topics:
        return 0.0
    scores = []
    for topic in topics:
        keyword_count = min(len(topic.keywords), 5)
        rep_count = len(topic.representative_responses)
        scores.append(min(1.0, 0.25 + keyword_count * 0.10 + rep_count * 0.10))
    return sum(scores) / len(scores)


def _balance(counts: list[int]) -> float:
    if not counts:
        return 0.0
    total = sum(counts)
    shares = [count / total for count in counts]
    max_share = max(shares)
    if len(counts) == 1:
        return 0.75
    entropy = -sum(share * math.log(share + 1e-9) for share in shares) / math.log(len(counts))
    dominance_penalty = max(0.0, max_share - 0.65)
    return max(0.0, min(1.0, entropy - dominance_penalty))


def _penalty(labels: np.ndarray, topics: list[Topic], min_topic_size: int) -> float:
    counts = Counter(label for label in labels if int(label) != -1)
    if not counts:
        return 0.35
    small = sum(count < min_topic_size for count in counts.values()) / max(1, len(counts))
    largest = max(counts.values()) / max(1, len(labels))
    over_fragmentation = max(0.0, len(counts) / max(1, len(labels)) - 0.35)
    dominance = max(0.0, largest - 0.75)
    noise = sum(int(label) == -1 for label in labels) / max(1, len(labels))
    duplicate = max(0.0, 0.55 - _topic_diversity(topics))
    return min(0.35, small * 0.12 + over_fragmentation * 0.20 + dominance * 0.15 + noise * 0.18 + duplicate * 0.10)


def _topic_count_from_labels(labels: np.ndarray) -> int:
    return len({int(label) for label in labels if int(label) != -1})


def _select_recommended(candidates: list[CandidateSolution]) -> CandidateSolution:
    best_score = max(candidate.score for candidate in candidates)
    threshold = max(0.03, best_score * 0.05)
    near_best = [candidate for candidate in candidates if best_score - candidate.score <= threshold]
    near_best.sort(key=lambda candidate: (candidate.topic_count, -candidate.score))
    return near_best[0]


def _select_alternative(
    candidates: list[CandidateSolution], recommended_k: int, direction: int
) -> CandidateSolution | None:
    if direction < 0:
        pool = [candidate for candidate in candidates if candidate.topic_count < recommended_k]
        pool.sort(key=lambda candidate: (-candidate.topic_count, -candidate.score))
    else:
        pool = [candidate for candidate in candidates if candidate.topic_count > recommended_k]
        pool.sort(key=lambda candidate: (candidate.topic_count, -candidate.score))
    return pool[0] if pool else None


def _single_topic_candidate(
    documents: list[TextDocument], vectorizer: TfidfVectorizer, matrix: Any, min_topic_size: int
) -> CandidateSolution:
    labels = np.zeros(len(documents), dtype=int)
    return _candidate_from_labels(documents, vectorizer, matrix, labels, 1, min_topic_size, "single-topic")


def _empty_candidate() -> CandidateSolution:
    return CandidateSolution(
        candidate_id=new_id("candidate"),
        topic_count=0,
        params={"engine": "none"},
        metrics={
            "stability": 0.0,
            "coherence": 0.0,
            "semantic_quality": 0.0,
            "coverage": 0.0,
            "diversity": 0.0,
            "labelability": 0.0,
            "balance": 0.0,
            "penalty": 0.0,
        },
        score=0.0,
    )
