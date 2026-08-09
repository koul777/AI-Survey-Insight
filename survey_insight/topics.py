from __future__ import annotations

import math
import warnings
from collections import Counter, defaultdict
from typing import Any

import numpy as np
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
from sklearn.decomposition import LatentDirichletAllocation, NMF
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics import adjusted_rand_score, silhouette_score
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


SCORE_WEIGHTS = {
    "semantic_quality": 0.30,
    "coherence": 0.25,
    "coverage": 0.15,
    "diversity": 0.10,
    "labelability": 0.10,
    "balance": 0.10,
}
WEIGHT_SENSITIVITY_SCENARIOS = 512
WEIGHT_MULTIPLIER_RANGE = (0.50, 1.50)
ASSIGNMENT_BOOTSTRAP_REPEATS = 500


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
    count_vectorizer, count_matrix = _count_vectorize(texts)
    embedding_result = embed_texts_with_provider(
        texts,
        embedding_provider,
        embedding_api_key,
        base_url=embedding_base_url,
        model=embedding_model,
        azure_api_version=azure_api_version,
    )
    candidates = _build_candidates(
        valid,
        vectorizer,
        matrix,
        count_vectorizer,
        count_matrix,
        topic_range,
        min_topic_size,
        seed,
    )
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
    _attach_weight_sensitivity(candidates, seed)
    candidates.sort(
        key=lambda candidate: (
            candidate.params.get("quality_gate_passed") is True,
            candidate.score,
            -candidate.topic_count,
        ),
        reverse=True,
    )
    for rank, candidate in enumerate(candidates, start=1):
        candidate.rank = rank
    recommended = _select_recommended(candidates)
    resampling_warning = _attach_resampling_diagnostic(
        recommended,
        valid,
        matrix,
        count_matrix,
        embedding_result.vectors if embedding_result is not None and embedding_result.vectors.size else None,
        seed,
    )
    bootstrap_warning = _attach_assignment_bootstrap(recommended, valid, seed)
    wider = _select_alternative(candidates, recommended.topic_count, direction=-1)
    detailed = _select_alternative(candidates, recommended.topic_count, direction=1)
    selection_warnings = []
    if not any(bool(candidate.params.get("quality_gate_passed")) for candidate in candidates):
        selection_warnings.append(
            "모든 후보가 최소 토픽 크기 또는 분석 포함률 구조 관문을 충족하지 못해 차선 후보를 제시합니다."
        )
    if resampling_warning:
        selection_warnings.append(resampling_warning)
    if bootstrap_warning:
        selection_warnings.append(bootstrap_warning)
    if recommended.metrics.get("weight_acceptability", 1.0) < 0.50:
        selection_warnings.append(
            "가중치 시나리오에 따라 다른 후보가 자주 선택되어 권장안의 가중치 민감도가 높습니다."
        )
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
        warnings=warnings + selection_warnings + (embedding_result.warnings if embedding_result else []),
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


def _count_vectorize(texts: list[str]) -> tuple[CountVectorizer, Any]:
    """Build non-negative integer term counts for probabilistic topic models."""

    vectorizer = CountVectorizer(
        tokenizer=tokenize_keywords,
        token_pattern=None,
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.95,
    )
    try:
        matrix = vectorizer.fit_transform(texts)
    except ValueError:
        vectorizer = CountVectorizer(analyzer="char", ngram_range=(2, 4), min_df=1)
        matrix = vectorizer.fit_transform(texts)
    return vectorizer, matrix


def _build_candidates(
    documents: list[TextDocument],
    vectorizer: TfidfVectorizer,
    matrix: Any,
    count_vectorizer: CountVectorizer,
    count_matrix: Any,
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
                    documents,
                    vectorizer,
                    matrix,
                    labels,
                    natural_k,
                    min_topic_size,
                    "dbscan_lsa_natural",
                    extra_params={"feature_space": "tfidf_lsa"},
                )
            )
    for k in range(lower, min(upper, n) + 1):
        labels = _cluster(matrix, k, seed)
        if labels is None:
            continue
        candidates.append(
            _candidate_from_labels(
                documents,
                vectorizer,
                matrix,
                labels,
                k,
                min_topic_size,
                "kmeans",
                extra_params={"feature_space": "tfidf"},
            )
        )
        if n <= 250 and k > 1:
            agglom_labels = _cluster_agglomerative(matrix, k)
            if agglom_labels is not None:
                candidates.append(
                    _candidate_from_labels(
                        documents,
                        vectorizer,
                        matrix,
                        agglom_labels,
                        k,
                        min_topic_size,
                        "agglomerative",
                        extra_params={"feature_space": "tfidf"},
                    )
                )
        nmf_solution = _fit_nmf(matrix, k, seed)
        if nmf_solution is not None:
            nmf_labels, nmf_weights, nmf_components = nmf_solution
            candidates.append(
                _candidate_from_labels(
                    documents,
                    vectorizer,
                    matrix,
                    nmf_labels,
                    k,
                    min_topic_size,
                    "nmf",
                    document_topic_weights=nmf_weights,
                    topic_components=nmf_components,
                    extra_params={"feature_space": "tfidf", "topic_terms": "nmf_components"},
                )
            )
        lda_solution = _fit_lda(count_matrix, k, seed)
        if lda_solution is not None:
            lda_labels, lda_weights, lda_components = lda_solution
            candidates.append(
                _candidate_from_labels(
                    documents,
                    count_vectorizer,
                    count_matrix,
                    lda_labels,
                    k,
                    min_topic_size,
                    "lda",
                    metric_matrix=matrix,
                    document_topic_weights=lda_weights,
                    topic_components=lda_components,
                    extra_params={"feature_space": "term_count", "topic_terms": "lda_components"},
                )
            )
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
                    extra_params={
                        "embedding_source": embedding_source,
                        "embedding_model": embedding_model,
                        "feature_space": "embedding",
                    },
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
                    extra_params={
                        "embedding_source": embedding_source,
                        "embedding_model": embedding_model,
                        "feature_space": "embedding",
                    },
                )
            )
        agglom_labels = _cluster_agglomerative(embedding_matrix, k) if n <= 250 else None
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
                    extra_params={
                        "embedding_source": embedding_source,
                        "embedding_model": embedding_model,
                        "feature_space": "embedding",
                    },
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
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        labels = model.fit_predict(matrix)
    if any(issubclass(item.category, ConvergenceWarning) for item in caught):
        return None
    return labels if len(set(int(label) for label in labels)) == k else None


def _cluster_embeddings_kmeans(matrix: np.ndarray, k: int, seed: int) -> np.ndarray | None:
    n = matrix.shape[0]
    if k <= 1:
        return np.zeros(n, dtype=int)
    if n < k:
        return None
    model = KMeans(n_clusters=k, random_state=seed, n_init=20)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        labels = model.fit_predict(matrix)
    if any(issubclass(item.category, ConvergenceWarning) for item in caught):
        return None
    return labels if len(set(int(label) for label in labels)) == k else None


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


def _fit_nmf(matrix: Any, k: int, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    n_docs, n_features = matrix.shape
    if k <= 1:
        weights = np.ones((n_docs, 1), dtype=float)
        components = np.asarray(matrix.mean(axis=0), dtype=float).reshape(1, -1)
        return np.zeros(n_docs, dtype=int), weights, components
    if n_docs < k or n_features < k:
        return None
    init = "nndsvda" if min(n_docs, n_features) > k else "random"
    model = NMF(n_components=k, init=init, random_state=seed, max_iter=600)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ConvergenceWarning)
            weights = model.fit_transform(matrix)
    except ValueError:
        return None
    if any(issubclass(item.category, ConvergenceWarning) for item in caught):
        return None
    labels = np.asarray(weights.argmax(axis=1), dtype=int)
    if len(set(labels)) != k:
        return None
    return labels, np.asarray(weights), np.asarray(model.components_)


def _cluster_nmf(matrix: Any, k: int, seed: int) -> np.ndarray | None:
    solution = _fit_nmf(matrix, k, seed)
    return solution[0] if solution is not None else None


def _fit_lda(matrix: Any, k: int, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    n_docs, n_features = matrix.shape
    if k <= 1:
        weights = np.ones((n_docs, 1), dtype=float)
        components = np.asarray(matrix.mean(axis=0), dtype=float).reshape(1, -1)
        return np.zeros(n_docs, dtype=int), weights, components
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
    return labels, np.asarray(weights), np.asarray(model.components_)


def _cluster_lda(matrix: Any, k: int, seed: int) -> np.ndarray | None:
    solution = _fit_lda(matrix, k, seed)
    return solution[0] if solution is not None else None


def _candidate_from_labels(
    documents: list[TextDocument],
    vectorizer: TfidfVectorizer | CountVectorizer,
    matrix: Any,
    labels: np.ndarray,
    k: int,
    min_topic_size: int,
    source: str,
    metric_matrix: Any | None = None,
    document_topic_weights: np.ndarray | None = None,
    topic_components: np.ndarray | None = None,
    extra_params: dict[str, Any] | None = None,
) -> CandidateSolution:
    if document_topic_weights is not None and topic_components is not None:
        topics, assignments = _topics_from_components(
            documents,
            vectorizer,
            labels,
            document_topic_weights,
            topic_components,
        )
    else:
        topics, assignments = _topics_from_labels(documents, vectorizer, matrix, labels)
    actual_topic_count = _topic_count_from_labels(labels)
    metrics = _metrics(
        vectorizer,
        metric_matrix if metric_matrix is not None else matrix,
        labels,
        topics,
        min_topic_size,
        coherence_matrix=matrix,
    )
    penalty = _penalty(labels, topics, min_topic_size)
    score = _composite_score(metrics, penalty, SCORE_WEIGHTS)
    warnings = []
    if any(topic.count < min_topic_size for topic in topics):
        warnings.append("최소 토픽 크기보다 작은 토픽이 포함되어 있습니다.")
    if metrics["diversity"] < 0.45:
        warnings.append("유사 키워드가 중복되는 토픽이 있습니다.")
    if actual_topic_count != k:
        warnings.append(f"요청한 {k}개 중 실제로 구분된 토픽은 {actual_topic_count}개입니다.")
    quality_gate_reasons = _quality_gate_reasons(labels, topics, min_topic_size)
    input_diagnostics: dict[str, Any] = {}
    if source == "lda":
        input_diagnostics = _lda_input_diagnostics(matrix)
        if not input_diagnostics["input_evidence_sufficient"]:
            quality_gate_reasons.append(
                "LDA 입력의 절반 이상이 서로 다른 유효 단어 3개 미만인 짧은 응답입니다."
            )
    if quality_gate_reasons:
        warnings.extend(f"구조 관문 보류: {reason}" for reason in quality_gate_reasons)
    return CandidateSolution(
        candidate_id=new_id("candidate"),
        topic_count=actual_topic_count,
        params={
            "engine": source,
            "min_topic_size": min_topic_size,
            "tokenizer": tokenizer_source(),
            "metric_profile": "heuristic_v3_weight_sensitivity_bootstrap",
            "requested_topic_count": k,
            "quality_gate_passed": not quality_gate_reasons,
            "quality_gate_reasons": quality_gate_reasons,
            **input_diagnostics,
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
    vectorizer: TfidfVectorizer | CountVectorizer,
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


def _topics_from_components(
    documents: list[TextDocument],
    vectorizer: TfidfVectorizer | CountVectorizer,
    labels: np.ndarray,
    document_topic_weights: np.ndarray,
    topic_components: np.ndarray,
) -> tuple[list[Topic], list[TopicAssignment]]:
    """Build latent-model topics from their own term and document weights."""

    feature_names = np.asarray(vectorizer.get_feature_names_out())
    active_labels = sorted({int(label) for label in labels if int(label) != -1})
    topic_ids = {label: f"T{order:02d}" for order, label in enumerate(active_labels, start=1)}
    topics: list[Topic] = []
    for label in active_labels:
        indices = np.flatnonzero(labels == label)
        component = np.asarray(topic_components[label], dtype=float).ravel()
        top_indices = component.argsort()[::-1][:8]
        keywords = [str(feature_names[index]) for index in top_indices if component[index] > 0][:6]
        ranked = sorted(indices.tolist(), key=lambda index: float(document_topic_weights[index, label]), reverse=True)
        reps: list[str] = []
        for index in ranked:
            text = documents[index].redacted_text
            if text not in reps:
                reps.append(text)
            if len(reps) == 3:
                break
        topic_label = label_topic(keywords, reps)
        sentiment = aggregate_topic_sentiment([documents[index].redacted_text for index in indices])
        topics.append(
            Topic(
                topic_id=topic_ids[label],
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
    assignments: list[TopicAssignment] = []
    for index, document in enumerate(documents):
        label = int(labels[index])
        if label == -1:
            probability = 0.0
        else:
            row = np.asarray(document_topic_weights[index], dtype=float)
            probability = float(row[label] / row.sum()) if row.sum() > 0 else 0.0
        assignments.append(
            TopicAssignment(
                document_id=document.id,
                topic_id=topic_ids.get(label, "OUTLIER"),
                probability=round(max(0.0, min(1.0, probability)), 4),
                is_outlier=label == -1,
                assignment_source="model",
            )
        )
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
    vectorizer: TfidfVectorizer | CountVectorizer,
    matrix: Any,
    labels: np.ndarray,
    topics: list[Topic],
    min_topic_size: int,
    coherence_matrix: Any | None = None,
) -> dict[str, float]:
    counts = [topic.count for topic in topics]
    semantic_quality = _silhouette(matrix, labels)
    coverage = sum(int(label) != -1 for label in labels) / max(1, len(labels))
    diversity = _topic_diversity(topics)
    coherence = _coherence(vectorizer, coherence_matrix if coherence_matrix is not None else matrix, topics)
    labelability = sum(
        min(1.0, (min(len(topic.keywords), 5) / 5.0) * 0.6 + (min(len(topic.representative_responses), 3) / 3.0) * 0.4)
        for topic in topics
    ) / max(1, len(topics))
    balance = _balance(counts)
    small_topic_ratio = sum(count < min_topic_size for count in counts) / max(1, len(counts))
    # Backward-compatible field name. This is a composite heuristic, not
    # repeated-sample or repeated-initialization statistical stability.
    stability = max(
        0.0,
        min(1.0, (semantic_quality * 0.40) + (coherence * 0.30) + (balance * 0.20) + 0.10 - small_topic_ratio * 0.2),
    )
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
    labels = np.asarray(labels)
    included = labels != -1
    filtered_labels = labels[included]
    unique_labels = set(int(label) for label in filtered_labels)
    if len(unique_labels) <= 1 or filtered_labels.shape[0] <= len(unique_labels):
        return 0.0
    filtered_matrix = matrix[included]
    try:
        raw = silhouette_score(filtered_matrix, filtered_labels, metric="cosine")
    except Exception:
        return 0.0
    return round(max(0.0, min(1.0, raw)), 3)


def _topic_diversity(topics: list[Topic]) -> float:
    keywords = [keyword for topic in topics for keyword in topic.keywords[:5]]
    if not keywords:
        return 0.0
    return len(set(keywords)) / len(keywords)


def _coherence(
    vectorizer: TfidfVectorizer | CountVectorizer,
    matrix: Any,
    topics: list[Topic],
) -> float:
    """Return a bounded UMass-style document co-occurrence heuristic.

    The raw UMass measure is the mean log conditional co-occurrence of ordered
    top-word pairs. ``exp(raw)`` maps it to 0..1 for the existing API. This is
    useful for ranking candidates in one corpus but is not a calibrated
    probability or a replacement for human topic-interpretability review.
    """

    if not topics or matrix.shape[0] == 0:
        return 0.0
    vocabulary = getattr(vectorizer, "vocabulary_", {})
    binary = (matrix > 0).astype(np.uint8)
    scores: list[float] = []
    for topic in topics:
        indices = [vocabulary[word] for word in topic.keywords[:5] if word in vocabulary]
        pair_scores: list[float] = []
        for later in range(1, len(indices)):
            for earlier in range(later):
                left = binary[:, indices[later]]
                right = binary[:, indices[earlier]]
                co_documents = float(left.multiply(right).sum())
                reference_documents = max(1.0, float(right.sum()))
                raw = math.log(min(1.0, (co_documents + 1.0) / reference_documents))
                pair_scores.append(raw)
        if pair_scores:
            scores.append(math.exp(sum(pair_scores) / len(pair_scores)))
    return sum(scores) / len(scores) if scores else 0.0


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


def _quality_gate_reasons(
    labels: np.ndarray,
    topics: list[Topic],
    min_topic_size: int,
) -> list[str]:
    """Return hard structural failures before heuristic candidate ranking."""

    if not topics:
        return ["유효 토픽이 생성되지 않았습니다."]
    reasons: list[str] = []
    small_count = sum(topic.count < min_topic_size for topic in topics)
    if small_count:
        reasons.append(f"최소 크기 {min_topic_size}건 미만 토픽이 {small_count}개입니다.")
    coverage = sum(int(label) != -1 for label in labels) / max(1, len(labels))
    if coverage < 0.70:
        reasons.append(f"분석 포함률이 {coverage:.0%}로 구조 관문 70%보다 낮습니다.")
    return reasons


def _lda_input_diagnostics(matrix: Any) -> dict[str, Any]:
    distinct_terms = np.asarray((matrix > 0).sum(axis=1)).ravel()
    if distinct_terms.size == 0:
        return {
            "input_median_distinct_terms": 0.0,
            "input_short_response_share": 1.0,
            "input_evidence_sufficient": False,
        }
    median_terms = float(np.median(distinct_terms))
    short_share = float(np.mean(distinct_terms < 3))
    return {
        "input_median_distinct_terms": round(median_terms, 3),
        "input_short_response_share": round(short_share, 3),
        "input_evidence_sufficient": short_share < 0.50,
    }


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


def _composite_score(
    metrics: dict[str, float],
    penalty: float,
    weights: dict[str, float],
) -> float:
    weighted = sum(
        float(weights.get(metric, 0.0)) * float(metrics.get(metric, 0.0))
        for metric in SCORE_WEIGHTS
    )
    return max(0.0, min(1.0, weighted - float(penalty)))


def _attach_weight_sensitivity(
    candidates: list[CandidateSolution],
    seed: int,
    scenarios: int = WEIGHT_SENSITIVITY_SCENARIOS,
    multiplier_range: tuple[float, float] = WEIGHT_MULTIPLIER_RANGE,
) -> None:
    """Attach an SMAA-inspired weight-sensitivity diagnostic.

    The diagnostic does not learn or claim objective weights. It perturbs each
    documented base weight inside a declared range, normalizes the weight
    vector, and reports how often each structurally eligible candidate would be
    selected under the existing near-best/parsimony rule.
    """

    if not candidates:
        return
    passed = [
        candidate
        for candidate in candidates
        if candidate.params.get("quality_gate_passed") is True
    ]
    pool = passed or candidates
    scenarios = max(1, int(scenarios))
    low, high = multiplier_range
    if low <= 0 or high < low:
        raise ValueError("weight multiplier range must be positive and ordered")

    metric_names = list(SCORE_WEIGHTS)
    base = np.asarray([SCORE_WEIGHTS[name] for name in metric_names], dtype=float)
    rng = np.random.default_rng(seed + 7919)
    multipliers = rng.uniform(low, high, size=(scenarios, len(metric_names)))
    sampled_weights = multipliers * base
    sampled_weights /= sampled_weights.sum(axis=1, keepdims=True)
    values = np.asarray(
        [[float(candidate.metrics.get(name, 0.0)) for name in metric_names] for candidate in pool],
        dtype=float,
    )
    penalties = np.asarray(
        [float(candidate.metrics.get("penalty", 0.0)) for candidate in pool],
        dtype=float,
    )
    scenario_scores = np.clip(values @ sampled_weights.T - penalties[:, None], 0.0, 1.0)
    wins = np.zeros(len(pool), dtype=int)
    for scenario_index in range(scenarios):
        scores = scenario_scores[:, scenario_index]
        best_score = float(scores.max())
        threshold = max(0.03, best_score * 0.05)
        near_best = [
            index
            for index, score in enumerate(scores)
            if best_score - float(score) <= threshold
        ]
        winner = min(
            near_best,
            key=lambda index: (pool[index].topic_count, -float(scores[index]), index),
        )
        wins[winner] += 1

    pool_indices = {id(candidate): index for index, candidate in enumerate(pool)}
    for candidate in candidates:
        candidate.params["base_score_weights"] = dict(SCORE_WEIGHTS)
        candidate.params["weight_sensitivity_profile"] = "bounded_monte_carlo_v1"
        candidate.params["weight_sensitivity_scenarios"] = scenarios
        candidate.params["weight_multiplier_range"] = [float(low), float(high)]
        pool_index = pool_indices.get(id(candidate))
        if pool_index is None:
            candidate.params["weight_sensitivity_status"] = "excluded_by_quality_gate"
            candidate.metrics["weight_acceptability"] = 0.0
            continue
        candidate.params["weight_sensitivity_status"] = "evaluated"
        acceptability = float(wins[pool_index] / scenarios)
        candidate.metrics["weight_acceptability"] = round(acceptability, 3)
        candidate.metrics["weight_acceptability_mcse"] = round(
            math.sqrt(acceptability * (1.0 - acceptability) / scenarios), 4
        )
        candidate.metrics["weight_score_p10"] = round(
            float(np.quantile(scenario_scores[pool_index], 0.10)), 3
        )
        candidate.metrics["weight_score_p90"] = round(
            float(np.quantile(scenario_scores[pool_index], 0.90)), 3
        )


def _select_recommended(candidates: list[CandidateSolution]) -> CandidateSolution:
    passed = [candidate for candidate in candidates if candidate.params.get("quality_gate_passed") is True]
    pool = passed or candidates
    best_score = max(candidate.score for candidate in pool)
    threshold = max(0.03, best_score * 0.05)
    near_best = [candidate for candidate in pool if best_score - candidate.score <= threshold]
    near_best.sort(
        key=lambda candidate: (
            -candidate.metrics.get("weight_acceptability", 0.0),
            candidate.topic_count,
            -candidate.score,
        )
    )
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
    passed = [candidate for candidate in pool if candidate.params.get("quality_gate_passed") is True]
    return (passed or pool)[0] if pool else None


def _attach_resampling_diagnostic(
    candidate: CandidateSolution,
    documents: list[TextDocument],
    tfidf_matrix: Any,
    count_matrix: Any,
    embedding_matrix: np.ndarray | None,
    seed: int,
    repeats: int = 5,
    fraction: float = 0.80,
) -> str | None:
    """Attach a post-selection subsample agreement diagnostic.

    This is deliberately not part of the product heuristic score. It measures
    how often the selected partition is recovered on deterministic stratified
    partial samples and must not be described as proof of statistical
    stability.
    """

    candidate.params["resampling_fraction"] = fraction
    candidate.params["resampling_repeats"] = repeats
    engine = str(candidate.params.get("engine", ""))
    if candidate.topic_count <= 1:
        candidate.params["resampling_status"] = "not_informative_single_topic"
        return None
    if "dbscan" in engine:
        candidate.params["resampling_status"] = "unsupported_for_density_candidate"
        return "선정 후보가 DBSCAN이어서 부분표본 일치도를 계산하지 않았습니다."

    reference = _labels_from_assignments(candidate, documents)
    scores: list[float] = []
    for repeat in range(repeats):
        indices = _stratified_subsample_indices(reference, fraction, seed + 1009 * (repeat + 1))
        if len(indices) <= candidate.topic_count:
            continue
        fitted = _refit_candidate_labels(
            engine,
            tfidf_matrix[indices],
            count_matrix[indices],
            embedding_matrix[indices] if embedding_matrix is not None else None,
            candidate.topic_count,
            seed + repeat + 1,
        )
        if fitted is None or len(fitted) != len(indices):
            continue
        score = adjusted_rand_score(reference[indices], fitted)
        scores.append(max(0.0, min(1.0, float(score))))

    candidate.params["resampling_successful_repeats"] = len(scores)
    if len(scores) < 2:
        candidate.params["resampling_status"] = "insufficient_successful_repeats"
        return "부분표본 반복 적합이 충분히 성공하지 않아 토픽 구성을 추가로 검토해야 합니다."

    stability = round(sum(scores) / len(scores), 3)
    candidate.metrics["resampling_stability"] = stability
    candidate.metrics["resampling_stability_p10"] = round(float(np.quantile(scores, 0.10)), 3)
    candidate.metrics["resampling_stability_p90"] = round(float(np.quantile(scores, 0.90)), 3)
    candidate.params["resampling_scores"] = [round(score, 3) for score in scores]
    candidate.params["resampling_status"] = "evaluated"
    if stability < 0.60:
        candidate.warnings.append("부분표본 일치도가 0.60 미만입니다.")
        return f"부분표본 일치도가 {stability:.2f}로 낮아 토픽 수와 대표 응답을 재검토해야 합니다."
    return None


def _attach_assignment_bootstrap(
    candidate: CandidateSolution,
    documents: list[TextDocument],
    seed: int,
    repeats: int = ASSIGNMENT_BOOTSTRAP_REPEATS,
) -> str | None:
    """Estimate assignment-conditional structural uncertainty by bootstrap.

    Documents are sampled with replacement while their selected assignments
    stay fixed. This measures uncertainty in observed topic shares and quality
    gate support conditional on this fitted solution. It does not refit the
    model and is not a confidence interval for topic correctness.
    """

    repeats = max(1, int(repeats))
    candidate.params["bootstrap_repeats"] = repeats
    candidate.params["bootstrap_profile"] = "assignment_conditional_percentile_v1"
    if not documents or candidate.topic_count <= 0:
        candidate.params["bootstrap_status"] = "not_informative"
        return None

    labels = _labels_from_assignments(candidate, documents)
    topic_labels = sorted(int(value) for value in set(labels) if int(value) != -1)
    if not topic_labels:
        candidate.params["bootstrap_status"] = "not_informative"
        return None

    min_topic_size = int(candidate.params.get("min_topic_size", 1))
    rng = np.random.default_rng(seed + 15401)
    coverage_values: list[float] = []
    balance_values: list[float] = []
    minimum_share_values: list[float] = []
    topic_share_values = {label: [] for label in topic_labels}
    gate_passes = 0
    n = len(labels)
    for _ in range(repeats):
        sampled = labels[rng.integers(0, n, size=n)]
        counts = [int(np.count_nonzero(sampled == label)) for label in topic_labels]
        included = sum(counts)
        coverage = included / n
        coverage_values.append(coverage)
        balance_values.append(_balance(counts) if included else 0.0)
        minimum_share_values.append(min(counts) / n)
        for label, count in zip(topic_labels, counts):
            topic_share_values[label].append(count / n)
        if coverage >= 0.70 and all(count >= min_topic_size for count in counts):
            gate_passes += 1

    intervals = []
    topic_id_by_number = {
        index: topic.topic_id for index, topic in enumerate(candidate.topics)
    }
    for label in topic_labels:
        values = topic_share_values[label]
        intervals.append(
            {
                "topic_id": topic_id_by_number.get(label, f"T{label + 1:02d}"),
                "estimate": round(float(np.mean(labels == label)), 3),
                "p025": round(float(np.quantile(values, 0.025)), 3),
                "p975": round(float(np.quantile(values, 0.975)), 3),
            }
        )

    gate_pass_rate = gate_passes / repeats
    candidate.params["bootstrap_topic_share_intervals"] = intervals
    candidate.params["bootstrap_status"] = "evaluated"
    candidate.metrics["bootstrap_gate_pass_rate"] = round(float(gate_pass_rate), 3)
    candidate.metrics["bootstrap_coverage_p025"] = round(
        float(np.quantile(coverage_values, 0.025)), 3
    )
    candidate.metrics["bootstrap_coverage_p975"] = round(
        float(np.quantile(coverage_values, 0.975)), 3
    )
    candidate.metrics["bootstrap_balance_p025"] = round(
        float(np.quantile(balance_values, 0.025)), 3
    )
    candidate.metrics["bootstrap_min_topic_share_p025"] = round(
        float(np.quantile(minimum_share_values, 0.025)), 3
    )
    if gate_pass_rate < 0.80:
        candidate.warnings.append("Bootstrap 구조 관문 통과율이 0.80 미만입니다.")
        return (
            f"{repeats}회 assignment-conditional bootstrap의 구조 관문 통과율이 {gate_pass_rate:.0%}로 낮아 "
            "토픽 비율과 작은 토픽을 재검토해야 합니다."
        )
    return None


def _labels_from_assignments(candidate: CandidateSolution, documents: list[TextDocument]) -> np.ndarray:
    assignment_by_document = {assignment.document_id: assignment for assignment in candidate.assignments}
    topic_numbers = {topic.topic_id: index for index, topic in enumerate(candidate.topics)}
    return np.asarray(
        [
            -1
            if assignment_by_document[document.id].is_outlier
            else topic_numbers[assignment_by_document[document.id].topic_id]
            for document in documents
        ],
        dtype=int,
    )


def _stratified_subsample_indices(labels: np.ndarray, fraction: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    selected: list[int] = []
    for label in sorted(set(int(value) for value in labels if int(value) != -1)):
        group = np.flatnonzero(labels == label)
        sample_size = max(1, min(len(group), int(math.ceil(len(group) * fraction))))
        selected.extend(int(index) for index in rng.choice(group, size=sample_size, replace=False))
    return np.asarray(sorted(selected), dtype=int)


def _refit_candidate_labels(
    engine: str,
    tfidf_matrix: Any,
    count_matrix: Any,
    embedding_matrix: np.ndarray | None,
    topic_count: int,
    seed: int,
) -> np.ndarray | None:
    if engine == "kmeans":
        return _cluster(tfidf_matrix, topic_count, seed)
    if engine == "agglomerative":
        return _cluster_agglomerative(tfidf_matrix, topic_count)
    if engine == "nmf":
        solution = _fit_nmf(tfidf_matrix, topic_count, seed)
        return solution[0] if solution is not None else None
    if engine == "lda":
        solution = _fit_lda(count_matrix, topic_count, seed)
        return solution[0] if solution is not None else None
    if engine.endswith("_kmeans") and embedding_matrix is not None:
        return _cluster_embeddings_kmeans(embedding_matrix, topic_count, seed)
    if engine.endswith("_agglomerative") and embedding_matrix is not None:
        return _cluster_agglomerative(embedding_matrix, topic_count)
    return None


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
