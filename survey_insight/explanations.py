from __future__ import annotations

from collections import Counter

from .models import Recommendation, Topic


ENGINE_LABELS = {
    "dbscan_lsa_natural": "자연 군집 탐색",
    "kmeans": "KMeans 군집",
    "agglomerative": "계층 군집",
    "nmf": "NMF 토픽모델",
    "lda": "LDA 토픽모델",
    "openai_embedding_kmeans": "OpenAI 의미 임베딩 KMeans",
    "openai_embedding_agglomerative": "OpenAI 의미 임베딩 계층 군집",
    "openai_embedding_dbscan": "OpenAI 의미 임베딩 자연 군집",
    "gemini_embedding_kmeans": "Gemini 의미 임베딩 KMeans",
    "gemini_embedding_agglomerative": "Gemini 의미 임베딩 계층 군집",
    "gemini_embedding_dbscan": "Gemini 의미 임베딩 자연 군집",
    "azure_openai_embedding_kmeans": "Azure OpenAI 의미 임베딩 KMeans",
    "azure_openai_embedding_agglomerative": "Azure OpenAI 의미 임베딩 계층 군집",
    "azure_openai_embedding_dbscan": "Azure OpenAI 의미 임베딩 자연 군집",
    "openai_compatible_embedding_kmeans": "OpenAI 호환 의미 임베딩 KMeans",
    "openai_compatible_embedding_agglomerative": "OpenAI 호환 의미 임베딩 계층 군집",
    "openai_compatible_embedding_dbscan": "OpenAI 호환 의미 임베딩 자연 군집",
    "semantic_embedding_kmeans": "의미 임베딩 KMeans",
    "semantic_embedding_agglomerative": "의미 임베딩 계층 군집",
    "semantic_embedding_dbscan": "의미 임베딩 자연 군집",
    "single-topic": "단일 토픽",
    "none": "분석 없음",
}


def apply_plain_language_explanations(recommendation: Recommendation) -> Recommendation:
    """Attach non-technical Korean explanations to a recommendation tree."""

    recommendation.plain_language_summary = _recommendation_summary(recommendation)
    recommendation.topic_count_explanation = _topic_count_explanation(recommendation)
    recommendation.methodology_plain_language = _methodology_explanation(recommendation)
    recommendation.quality_warnings = _quality_warnings(recommendation)
    for candidate in recommendation.candidates:
        for topic in candidate.topics:
            apply_topic_explanation(topic)
    return recommendation


def apply_topic_explanation(topic: Topic) -> Topic:
    topic.plain_language_summary = _topic_summary(topic)
    topic.suggested_action = _topic_action(topic)
    topic.sentiment_plain_language = _sentiment_summary(topic)
    if not topic.interpretation_source:
        topic.interpretation_source = "local_plain_language"
    return topic


def _recommendation_summary(recommendation: Recommendation) -> str:
    rec = recommendation.recommended
    weight_acceptability = rec.metrics.get("weight_acceptability")
    sensitivity_text = (
        f" 가중치 변동 시나리오 선정률은 {weight_acceptability:.0%}였습니다."
        if weight_acceptability is not None
        else ""
    )
    return (
        f"유효 자유응답 {recommendation.valid_response_count}건을 읽기 쉬운 묶음으로 나누어 보니 "
        f"{rec.topic_count}개 토픽이 현재 복합 평가 기준의 권장안으로 선택되었습니다. "
        f"{sensitivity_text}"
        "토픽이 너무 적으면 서로 다른 의견이 섞이고, 너무 많으면 비슷한 이야기가 잘게 쪼개질 수 있어 "
        "대표 응답 검토가 가능한 중간 지점을 권장값으로 잡았습니다. 이 값은 통계적으로 검증된 최적값이 아닙니다."
    )


def _topic_count_explanation(recommendation: Recommendation) -> str:
    rec = recommendation.recommended
    engines = _candidate_engine_summary(recommendation)
    wider = f"{recommendation.wider.topic_count}개" if recommendation.wider else "없음"
    detailed = f"{recommendation.detailed.topic_count}개" if recommendation.detailed else "없음"
    return (
        f"허용 범위 {recommendation.allowed_topic_range[0]}-{recommendation.allowed_topic_range[1]}개 안에서 "
        f"{engines}을 함께 비교했습니다. 토픽 수는 두 가지 관점으로 정했습니다. "
        "첫째, 키워드 동시출현, 군집 분리도, 포함률과 토픽 크기 균형을 결합한 휴리스틱 점수를 확인했습니다. "
        "둘째, 문서화된 가중치를 범위 안에서 바꾼 시나리오에서도 어떤 후보가 선택되는지 확인했습니다. "
        "셋째, 담당자가 실제로 읽고 이름을 붙일 수 있을 만큼 토픽이 너무 크거나 잘게 쪼개지지 않았는지 확인했습니다. "
        f"작은 토픽이 과하게 생기지 않는지, 사람이 라벨을 붙일 수 있는지도 함께 평가했습니다. "
        f"그 결과 {rec.topic_count}개 토픽을 권장하며, 더 넓게 보는 대안은 {wider}, 더 세분화하는 대안은 {detailed}입니다. "
        "권장안과 대안의 대표 응답을 사람이 비교한 뒤 최종 토픽 수를 결정해야 합니다."
    )


def _methodology_explanation(recommendation: Recommendation) -> str:
    tokenizer = recommendation.recommended.params.get("tokenizer", "regex_keyword_fallback")
    engine = recommendation.recommended.params.get("engine", "unknown")
    embedding_model = recommendation.recommended.params.get("embedding_model")
    embedding_text = f" 의미 임베딩 모델은 {embedding_model}입니다." if embedding_model else ""
    return (
        "분석은 무응답과 개인정보 단서를 먼저 정리한 뒤, 한국어 키워드를 뽑고 여러 토픽 후보를 만들어 비교하는 순서로 진행됩니다. "
        f"이번 권장안은 {ENGINE_LABELS.get(engine, engine)} 결과이며, 키워드 추출 방식은 {tokenizer}입니다. "
        f"{embedding_text}"
        "가중치 시나리오 선정률과 bootstrap 구조 관문 통과율은 선택 민감도와 표본 변동성을 보여주는 진단값입니다. "
        "정확도, p-value 또는 통계적 검정력이 아니며 최종 의사결정에는 대표 의견 원문을 함께 확인해야 합니다."
    )


def _quality_warnings(recommendation: Recommendation) -> list[str]:
    warnings = list(dict.fromkeys(recommendation.warnings + recommendation.recommended.warnings))
    if recommendation.valid_response_count < 30:
        warnings.append("응답 수가 적기 때문에 토픽 이름과 비율은 확정 결론보다 탐색용 단서로 읽어야 합니다.")
    if any(topic.sentiment_method == "rule_lexicon_fallback" for topic in recommendation.recommended.topics):
        warnings.append("감정 결과는 규칙·어휘 기반 신호입니다. 심리 진단이나 긴급성 판정이 아니므로 대표 응답과 함께 검토하세요.")
    if recommendation.recommended.params.get("tokenizer") == "regex_keyword_fallback":
        warnings.append("한국어 형태소 분석기가 설치되어 있지 않아 2글자 이상 키워드 추출 fallback을 사용했습니다.")
    if recommendation.recommended.metrics.get("weight_acceptability", 1.0) < 0.50:
        warnings.append("가중치 범위에 따라 권장 후보가 달라질 수 있으므로 대안 후보도 함께 비교하세요.")
    if recommendation.recommended.metrics.get("bootstrap_gate_pass_rate", 1.0) < 0.80:
        warnings.append("Bootstrap에서 작은 토픽 또는 포함률 관문이 자주 흔들려 토픽 비율을 확정값으로 읽으면 안 됩니다.")
    return warnings


def _topic_summary(topic: Topic) -> str:
    keywords = _join_keywords(topic.keywords[:4])
    share = f"{topic.share:.1%}"
    if keywords:
        return (
            f"이 토픽은 {keywords} 같은 표현이 함께 나온 응답 묶음입니다. "
            f"전체 유효 응답 중 {share}, {topic.count}건을 차지합니다."
        )
    return f"이 토픽은 비슷한 표현을 가진 응답 {topic.count}건을 묶은 결과입니다."


def _topic_action(topic: Topic) -> str:
    if topic.urgency_score >= 0.5:
        return "처리 우선도 신호가 높으므로 담당 부서가 대표 의견을 먼저 읽고 단기 조치가 필요한 항목을 분리하세요."
    if topic.sentiment_label == "negative":
        return "불만 또는 개선 요구가 포함된 묶음이므로 원인 확인, 담당 부서 지정, 개선 가능성 검토 순서로 대응하세요."
    if topic.sentiment_label == "positive":
        return "긍정 신호가 있는 묶음이므로 현재 잘 작동하는 요인을 확인하고 유지하거나 다른 조직에 확산할 수 있는지 검토하세요."
    if topic.sentiment_label == "mixed":
        return "긍정과 부정이 함께 보이므로 만족 요인과 불편 요인을 나누어 읽고, 같은 제도 안의 장단점을 구분하세요."
    return "감정 방향이 강하지 않은 묶음이므로 대표 의견을 읽어 실제 요구사항인지 단순 언급인지 먼저 확인하세요."


def _sentiment_summary(topic: Topic) -> str:
    label_text = {
        "positive": "긍정 표현이 상대적으로 많습니다.",
        "negative": "불만이나 개선 요구 표현이 상대적으로 많습니다.",
        "mixed": "긍정과 부정 표현이 함께 나타납니다.",
        "neutral": "뚜렷한 감정 단서는 많지 않습니다.",
    }.get(topic.sentiment_label, "감정 방향을 단정하기 어렵습니다.")
    evidence = _join_keywords(topic.sentiment_evidence[:4])
    evidence_text = f" 근거 단어는 {evidence}입니다." if evidence else ""
    return f"{label_text} 처리 우선도는 {topic.urgency_score:.2f}입니다.{evidence_text}"


def _candidate_engine_summary(recommendation: Recommendation) -> str:
    counts = Counter(str(candidate.params.get("engine", "unknown")) for candidate in recommendation.candidates)
    labels = [ENGINE_LABELS.get(engine, engine) for engine, _ in counts.most_common()]
    if not labels:
        return "후보 모델"
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + f", {labels[-1]}"


def _join_keywords(values: list[str]) -> str:
    return ", ".join(value for value in values if value)
