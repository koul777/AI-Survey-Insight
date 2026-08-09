# 기능 검증 및 결과 점검

이 문서는 정확도 benchmark가 아니라, 현재 샘플 데이터와 테스트로 분석 파이프라인의 구조·재현성·개인정보 보호 동작을 확인하는 절차입니다. 샘플에 임의의 정답 토픽을 붙여 정확도를 계산하지 않습니다.

## 자동 검증

개발 환경을 설치한 뒤 다음을 실행합니다.

```powershell
python -m pip install -e ".[test]"
python -m unittest discover -s tests -v
python -m compileall survey_insight tests
```

테스트가 확인하는 핵심 항목은 다음과 같습니다.

- 자유응답 컬럼 탐지와 유효 응답 수
- Kiwi 명사 토큰화와 무응답 제외
- 이메일·휴대전화 번호·사번 패턴 마스킹
- LDA가 TF-IDF가 아닌 정수 단어 빈도를 입력으로 사용함
- KMeans의 군집 붕괴 후보 제외
- 한 엔진이 붕괴해도 같은 토픽 수의 다른 엔진 후보를 계속 평가하는지
- Frobenius NMF와 일반화 KL-NMF 후보의 목적함수 기록
- DBSCAN 노이즈 제외 후 cosine silhouette 계산
- class-based TF-IDF의 군집 고유어 강조와 단어·구 포함 중복 억제
- 키워드 문서 동시출현 기반 토픽 해석 가능성 점수
- LDA 성분 키워드와 0–1 문서–토픽 배정값
- 허용 토픽 수 범위와 소표본 경고
- 같은 입력·같은 seed의 로컬 결과 재현성
- 512개 제한 범위 가중치 시나리오의 후보 선정률과 동일 seed 재현성
- 선정 배정의 500회 assignment-conditional bootstrap 구조 관문 통과율·토픽 비율 구간
- 선정 후보의 5회 층화 80% 부분표본 일치도와 낮은 일치도 경고
- LDA 입력이 지나치게 짧을 때의 근거 부족 관문
- 대표 응답과 보고서 파일 구조
- Excel에 `original_text`가 없고 마스킹 텍스트만 포함되는지
- 외부 provider mock 및 실패 시 로컬 후보 유지
- 감정 어휘, 단순 부정, `불만족` 중복 방지, 혼합 극성과 처리 우선도 결합식
- 외부 AI 감정값의 허용 범위와 근거 관문; 무근거·범위 이탈 시 로컬 신호 유지
- 외부 전송 사전 확인과 담당자 승인 기록·변경 후 승인 무효화

## 샘플 데이터 smoke evaluation

저장소의 모의 설문을 직접 분석하려면 다음 명령을 사용합니다.

```powershell
python -m survey_insight.cli analyze `
  --input .\sample_data\mock_survey_responses.csv `
  --out .\out_evaluation `
  --seed 42
```

또는 CLI가 자체 생성하는 고정 fixture로 보고서 전체 흐름을 확인합니다.

```powershell
python -m survey_insight.cli demo --out .\out_evaluation --seed 42
```

구조적으로 기대하는 결과는 다음과 같습니다.

1. `analysis_package.json`에 `dataset_profile`, `recommendation`, `selected_topics`, `assignments`가 존재합니다.
2. 권장 토픽 수가 `recommendation.allowed_topic_range` 안에 있습니다.
3. `recommendation.candidates`에 로컬 KMeans, Frobenius NMF, KL-NMF, LDA 후보가 생성됩니다. 데이터 구조나 수렴 여부에 따라 계층 군집·DBSCAN 및 각 엔진의 후보 수는 달라질 수 있습니다.
4. 권장 후보의 `params.feature_space`와 `params.metric_profile`로 입력 표현과 평가 버전을 추적할 수 있습니다.
5. 권장 후보에 `metrics.weight_acceptability`, `metrics.bootstrap_gate_pass_rate`, `params.bootstrap_topic_share_intervals`가 있으며 모두 선언된 범위 안에 있습니다.
6. 각 토픽에 키워드와 최대 3개의 대표 응답이 생성됩니다.
7. Excel, Word, PowerPoint 파일이 열 수 있는 OOXML 구조로 생성됩니다.
8. 같은 환경에서 같은 입력과 `--seed 42`로 두 번 실행했을 때 권장 엔진, 토픽 수, 점수, 가중치 선정률, bootstrap 결과, 토픽별 키워드·건수가 같습니다. 실행 ID는 달라도 정상입니다.

이 점검에서 “통계적 검정력”을 통과 조건으로 두지 않습니다. 현재 파이프라인에는 검정할 귀무가설·효과크기·정답 토픽이 없기 때문입니다. 대신 가중치 선택 민감도와 재표본 변동성을 구조적 결과로 기록하며, 이를 정확도나 p-value로 해석하지 않습니다.

검증 후 `out_evaluation/`은 실제 설문을 담을 수 있는 로컬 산출물이므로 Git에 추가하지 말고 필요 없으면 삭제합니다.

## 수동 검토표

자동 점수로 대체할 수 없는 항목은 최소 2명의 업무 이해관계자가 독립적으로 읽고 차이를 기록하는 방식을 권장합니다. 이것은 현재 제품이 자동으로 수행하는 평가가 아닙니다.

| 검토 항목 | 질문 | 기록 예시 |
|---|---|---|
| 토픽 라벨 적절성 | 상위 키워드와 대표 응답을 과장 없이 요약하는가? | 적절/수정 필요 + 이유 |
| 토픽 내부 일관성 | 같은 토픽의 응답이 실제로 같은 업무 이슈를 말하는가? | 반례 응답 행 번호 |
| 토픽 간 구분 | 두 토픽이 사실상 같은 내용을 쪼갠 것은 아닌가? | 병합 후보 토픽 ID |
| 대표 의견 적합성 | 대표 응답이 토픽의 전형을 보여주고 예외를 숨기지 않는가? | 교체 후보 행 번호 |
| 감정 해석 적절성 | 부정·혼합·긍정 신호와 근거 어휘가 문맥에 맞는가? | 오분류와 부정 범위 |
| 대응 방안 유용성 | 제안이 조직의 권한·일정·자원 안에서 실행 가능한가? | 담당 부서/기한/보완점 |
| 개인정보 | 마스킹 후에도 개인을 추론할 희귀 정보가 남는가? | 추가 삭제·일반화 항목 |

## 결과 보고 시 금지할 표현

- “정확도 90%”처럼 정답 라벨 검증 없이 만든 수치
- “통계적으로 최적 토픽 수” 또는 “검증된 안정성”
- “완전 익명화” 또는 “개인정보가 없다”
- 처리 우선도를 긴급성·위험도·심리 상태 판정으로 해석하는 문구

대신 “현재 후보군과 휴리스틱에서 권장된 토픽 수”, “일부 식별정보 패턴을 마스킹함”, “담당자 검토가 필요한 탐색 결과”라고 기록합니다.

## 감정 신호를 연구 수준으로 평가하려면

현재 sample data는 감정 정답셋이 아니므로 정확도를 계산하지 않습니다. 별도 평가를 수행할 때는 다음을 사전에 고정해야 합니다.

1. 분석 단위(응답 전체 또는 문장/측면)와 `positive/neutral/negative/mixed` 정의
2. 처리 우선도를 감정과 분리한 라벨링 지침
3. 개인정보를 제거한 실제 목표 도메인 표집 방식
4. 서로의 판단을 보지 않는 2명 이상의 평가자와 불일치 조정 절차
5. 평가자 합의도와 class별 precision·recall·F1, macro-F1, 혼동행렬
6. 어휘가 하나도 포착되지 않은 응답 비율과 부정·반어·복합 측면 오류 분석
7. 어휘·임계값을 고친 개발 표본과 마지막에 한 번만 평가할 hold-out 표본의 분리

이 절차와 결과가 공개되기 전에는 “학계에서 검증된 모델” 또는 특정 정확도를 주장하지 않습니다.

라벨링한 CSV가 준비되면 원문을 결과 JSON에 복사하지 않는 집계 평가 명령을 사용할 수 있습니다. `gold` 값은 `positive`, `neutral`, `negative`, `mixed` 중 하나여야 합니다.

```powershell
python -m survey_insight.cli evaluate-sentiment `
  --input .\private_labeled_sentiment.csv `
  --text-column response `
  --label-column gold `
  --out .\out_evaluation\sentiment_metrics.json
```

출력에는 class별 precision·recall·F1, macro-F1, 혼동행렬, 근거 어휘 coverage와 제외 건수만 들어갑니다. 입력 원문이나 개별 예측은 복제하지 않습니다. 이 명령이 평가자 합의도, 표집 대표성 또는 hold-out 분리를 자동으로 보장하지는 않습니다.
