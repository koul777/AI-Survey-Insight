# AI Survey Insight

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://github.com/koul777/AI-Survey-Insight/actions/workflows/test.yml/badge.svg)](https://github.com/koul777/AI-Survey-Insight/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<p align="center">
  <img src="docs/images/readme-cover.jpg" alt="AI Survey Insight 대표 프로젝트 소개 이미지" width="100%" />
</p>

한국어 설문 자유응답을 로컬에서 프로파일링·마스킹·토픽 분석하고 Excel, Word, PowerPoint 검토 자료로 만드는 FastAPI 도구입니다.

**[v0.2.1 다운로드](https://github.com/koul777/AI-Survey-Insight/releases/tag/v0.2.1)** · [변경 기록과 검증 범위](docs/RELEASE_0.2.1.md)

## 해결하려는 문제

설문 자유응답은 양이 늘수록 사람이 일관된 기준으로 분류하고 대표 의견을 찾기 어렵습니다. AI Survey Insight는 자유응답 컬럼 탐지부터 전처리, 여러 토픽 후보 비교, 감정 신호, 그룹 비교, 보고서 생성까지 한 흐름으로 묶습니다. 결과는 자동 의사결정이 아니라 담당자가 원문과 함께 검토할 **탐색적 분석 후보**입니다.

## 핵심 특징

- CSV/XLSX/TXT 업로드, 카카오톡 대화 전처리, 헤더 탐지, 자유응답·그룹 컬럼 추천
- Kiwi 형태소·품사 분석, Unicode 정규화, 불용어·조사 제거, 무응답 제외
- 이메일·국내 이동전화 번호·사번/직번 패턴 마스킹
- KMeans, 계층 군집, Frobenius NMF, KL-NMF, LDA, DBSCAN/LSA와 BERTopic 후보 비교
- NMF에는 TF-IDF, LDA에는 정수 단어 빈도를 사용하고 잠재 성분의 키워드·문서 가중치를 보존
- 하드 군집의 class-based TF-IDF 키워드 표현과 단어·구 포함 중복 억제
- 최소 토픽 크기와 70% 분석 포함률 구조 관문 후 휴리스틱 복합 평가
- 같은 입력·같은 seed의 로컬 결과 재현성 검사
- 내장 한국어 감정사전 160항목, 활용형·부정문·강조 표현 처리와 응답별 근거 구간
- 토픽별 긍정·중립·부정·혼합 분포, 사전 근거 포함률, 응답별 조회·필터
- 동일 문장은 한 번 적합하고 실제 응답 빈도를 복원해 반복 응답에 따른 과분할 방지
- 설치형 Multilingual E5 의미 임베딩을 외부 전송 없이 선택적으로 사용
- 선택적 AI provider 임베딩·근거 해석 보강 및 실패 시 로컬 fallback
- Excel, Word, PowerPoint 보고서와 사용자 수정 이력

0.2.1에서는 `문제 해결이 필요하다`를 해결 완료로 읽는 오류와 중립 명사·간접 부정의 감정 오판을 보완했습니다. 가정·인용·희망·반어 가능성은 검토 사유와 함께 표시합니다. NMF 소속도는 성분 배율에 영향을 받지 않도록 계산하며, 토픽 병합·제외 후에는 편집 전 점수를 현재 품질처럼 표시하지 않습니다.

카카오톡 분석은 **맥락 구간 기준**입니다. 짧은 실질 의견을 보존하고 구간마다 원본 데이터 행 번호를 제공합니다. 한 구간에 여러 발화자가 포함될 수 있어 사람 수·개별 메시지 감정과 구분하며, 발화자별 교차표는 생성하지 않습니다.

## 실제 사용 화면

아래 이미지는 0.1.x에서 `sample_data/mock_survey_responses.csv`를 분석한 예시입니다. 0.2.0의 감정 분포와 응답별 근거 조회는 추가된 화면이므로 이 이미지에 포함되지 않습니다. 권장 토픽 수와 점수는 버전에 따라 바뀔 수 있습니다.

<table>
  <tr>
    <td width="50%"><img src="docs/images/readme-01-app-column-profile.jpg" alt="컬럼 프로파일 화면" width="100%" /><br /><strong>컬럼 프로파일</strong><br />행·컬럼 수와 자유응답 후보를 확인합니다.</td>
    <td width="50%"><img src="docs/images/readme-04-topic-recommendation.jpg" alt="토픽 권장안 화면" width="100%" /><br /><strong>토픽 권장안</strong><br />권장 토픽 수, 대안, 구조 관문과 휴리스틱 점수를 검토합니다.</td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/images/readme-05-priority-topics.jpg" alt="먼저 검토할 토픽 화면" width="100%" /><br /><strong>먼저 검토할 토픽</strong><br />비중·부정 표현·검토 우선도 신호를 함께 봅니다.</td>
    <td width="50%"><img src="docs/images/readme-06-topic-table.jpg" alt="전체 토픽 표" width="100%" /><br /><strong>전체 토픽</strong><br />키워드, 대표 의견, 감정 근거와 담당자 설명을 비교합니다.</td>
  </tr>
</table>

## 빠른 시작

Python 3.11 이상이 필요합니다.

릴리스의 소스 ZIP을 풀어 다음 명령을 실행합니다. 설치용 wheel을 받았다면 `python -m pip install .\ai_survey_insight-0.2.1-py3-none-any.whl`로 설치할 수도 있습니다.

```powershell
python -m pip install -e .
python -m uvicorn survey_insight.api:app --host 127.0.0.1 --port 8001
```

브라우저에서 `http://127.0.0.1:8001`을 엽니다. 기존 설치 방식도 지원합니다.

```powershell
python -m pip install -r requirements.txt
```

Windows에서는 `start_app.bat` 또는 `start_app.ps1`로 실행할 수 있습니다. 샘플 파일은 `sample_data/mock_survey_responses.csv`입니다.

### 로컬 의미 모델 설치

기본 NMF·LDA 분석과 감정사전은 API 키 없이 작동합니다. 서로 다른 표현의 의미까지 비교하려면 다음 명령으로 E5 모델을 한 번 내려받습니다.

```powershell
python -m survey_insight.cli setup-local-model
```

모델은 `out_models/multilingual-e5-small/`에 저장되며 Git이나 보고서에 포함되지 않습니다. 설치 시 모델 파일만 다운로드하고 설문 응답은 전송하지 않습니다. 설치 후 화면의 **로컬 의미 모델 함께 비교**가 활성화됩니다. 분석 시에는 `local_files_only=True`로 동작하며 자동 다운로드하지 않습니다. `SURVEY_INSIGHT_LOCAL_MODEL_PATH`로 경로를 지정할 수 있습니다.

```powershell
python -m survey_insight.cli analyze --input .\sample_data\mock_survey_responses.csv --out .\out_semantic --local-embeddings
```

한국어를 지원하는 [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small)은 MIT 모델이며, 설치한 revision을 모델 폴더의 `survey_insight_model.json`에 기록합니다. E5와 NMF·LDA를 함께 비교하므로 E5가 항상 선택되지는 않습니다. 긴 응답은 480 모델 토큰씩 모두 인코딩하고 토큰 수 가중 평균으로 결합하므로 뒤쪽 내용을 단순 절단하지 않습니다.

소스 수정이나 테스트 실행이 목적이라면 FastAPI 테스트 클라이언트용 선택 의존성까지 설치합니다. 일반 실행에는 이 추가 설치가 필요하지 않습니다.

```powershell
python -m pip install -e ".[test]"
```

## 분석 흐름

1. CSV/XLSX를 업로드하고 추천된 자유응답 컬럼을 확인합니다.
2. 선택한 그룹 컬럼과 원문을 로컬 SQLite에 저장합니다.
3. 무응답을 제외하고 일부 식별정보 패턴을 마스킹합니다.
4. 같은 문장을 중복 제거한 뒤 1개 토픽부터 후보를 비교합니다. 카카오톡 대화에는 BERTopic 후보도 생성합니다.
5. 구조 관문을 통과한 후보를 여섯 구성 지표와 감점으로 비교합니다.
6. 원래 응답 수를 복원하고 각 응답의 감정과 토픽별 감정 분포를 함께 확인합니다.
7. 필요할 때만 외부 AI 보강을 요청하고, 최종 라벨과 해석을 수정합니다.
8. 보고서를 생성하고 배포 전 개인정보·소그룹·표현을 재검토합니다.

## 보고서 산출물

<table>
  <tr>
    <td width="33%"><img src="docs/images/05-excel-export-topic-mapping.jpg" alt="Excel 토픽 배정" width="100%" /><br /><strong>Excel</strong><br />토픽 요약, 마스킹 텍스트 배정, 그룹 비교, 모델 설정</td>
    <td width="33%"><img src="docs/images/readme-03-word-report.jpg" alt="Word 보고서" width="100%" /><br /><strong>Word</strong><br />요약, 토픽, 지표, 방법론과 주의사항</td>
    <td width="33%"><img src="docs/images/readme-02-powerpoint-report.jpg" alt="PowerPoint 보고서" width="100%" /><br /><strong>PowerPoint</strong><br />발표용 요약, 핵심 토픽과 대표 의견</td>
  </tr>
</table>

CLI 데모는 고정 fixture와 세 보고서를 만듭니다.

```powershell
python -m survey_insight.cli demo --out .\out --seed 42
```

실제 파일은 다음과 같이 분석합니다.

```powershell
python -m survey_insight.cli analyze --input .\sample_data\mock_survey_responses.csv --out .\out --seed 42
```

`out/` 아래에는 원문이 포함된 `analysis_package.json`, 데모 원본, 보고서가 생성될 수 있습니다. Git에 추가하거나 검토 없이 공유하지 마세요.

## 로컬 분석과 선택적 AI 보강

| 구분 | 로컬 기본 분석 | 외부 AI 보강 |
|---|---|---|
| 토픽 후보 | TF-IDF/빈도 기반 KMeans·Frobenius NMF·KL-NMF·LDA·계층·DBSCAN, 카카오톡 대화용 BERTopic | provider embedding 후보와 카카오톡 BERTopic 입력에 선택 provider 임베딩 사용 가능 |
| 감정 | 형태소·감정사전·부정문 규칙, 응답별 근거와 분포 | 대표 텍스트 근거 해석 보강; 응답별 사전 집계와 구분 |
| 네트워크 | 외부 서버로 자동 전송하지 않음 | 선택한 provider로 마스킹 텍스트 또는 대표 응답이 전송될 수 있음 |
| 실패 | 로컬 결과 제공 | 안전한 경고 후 로컬 결과 유지 |

지원 UI는 OpenAI, Gemini, Claude, Azure OpenAI, OpenAI-compatible provider를 선택할 수 있습니다. 화면의 모델 preset은 편의를 위한 **예시**이며 provider의 현재 제공 여부를 보장하지 않습니다. 직접 모델명 또는 deployment 이름을 입력할 수 있습니다. Claude 선택 시 별도 embedding 후보 없이 로컬 토픽 모델을 사용하고, 채팅 해석만 시도합니다.

API 키는 분석 요청 처리 중에만 사용하며 SQLite, 분석 package JSON, 보고서에 저장하지 않습니다. 예시·placeholder 키는 외부 호출을 건너뜁니다. UI와 API는 실제 키를 사용하는 외부 분석 전에 전송 안내 확인을 요구합니다. 외부 호출 오류의 원문 본문이나 credential을 사용자 화면에 그대로 표시하지 않는 것을 설계 원칙으로 합니다.

## 개인정보·데이터 저장 정책

“로컬 실행”은 “아무것도 저장하지 않음”과 다릅니다.

- 기본 SQLite 경로는 `out/app.db`이며 `SURVEY_INSIGHT_DB_PATH`로 바꿀 수 있습니다.
- 업로드 원본 bytes, 파일 메타데이터·컬럼 프로파일, 분석 package가 SQLite에 저장됩니다. 분석 package에는 원문과 마스킹 텍스트가 모두 포함될 수 있습니다.
- 보고서와 CLI 산출물은 사용자가 지정한 `out*/` 경로에 생성됩니다.
- 분석 이력의 **분석 결과 삭제**는 run과 서버 export를 지우고, **원본·연결 분석 삭제**는 업로드 원본과 연결 run·서버 export를 함께 지웁니다. 이미 내려받거나 복사한 파일은 별도로 삭제해야 합니다.
- 외부 provider를 선택하지 않으면 설문 텍스트를 외부 서버로 자동 전송하지 않습니다.
- 외부 provider를 선택하면 마스킹된 자유응답 또는 대표 응답이 해당 provider로 전송될 수 있습니다. 조직의 위탁처리·국외 이전·보존 정책을 먼저 확인하세요.

이메일, 휴대전화 번호, 사번 등 일부 식별정보 패턴을 마스킹합니다. `성명:`, `주소:`, 주민등록번호·계좌번호 문맥은 자동 익명화를 주장하지 않고 `privacy_review_flags`로 표시합니다. 모든 개인정보를 완벽하게 탐지하거나 익명화하는 기능은 아니므로, 실제 보고서 배포 전 담당자의 검토가 필요합니다. 그룹 비교의 5건 미만 표시 억제도 완전한 재식별 방지를 보장하지 않습니다.

현재 버전에서 데이터를 지우는 방법과 API는 [SECURITY.md](SECURITY.md)에 정리합니다. DB 파일을 직접 삭제할 때는 앱을 종료하고 정확한 `SURVEY_INSIGHT_DB_PATH`와 `out*/` 보고서 경로를 확인하세요.

프로세스 종료 시 자동 소멸하는 `ephemeral` 저장 모드는 아직 구현하지 않았습니다. 민감한 운영 환경에서는 격리된 작업 디렉터리·암호화된 디스크·최소 보존기간을 적용하고 분석 후 UI 삭제와 별도 복사본 삭제를 수행하세요.

## 분석 방법론과 한계

0.2.0에서는 토픽과 감정을 독립적으로 분석한 후 연결합니다. `만족하지 않습니다`는 부정, `불편하지 않습니다`는 약한 긍정으로 반전하고, `개선이 필요합니다`만으로 부정 감정이라고 판단하지 않습니다. 중립에는 사전 근거가 없는 응답이 포함되므로 `evidence_status`와 근거 포함률을 함께 보세요. 사전은 [프로젝트에서 작성한 TSV](survey_insight/data/sentiment_ko.tsv)이며 KNU 사전이나 학습된 감정 분류기로 표시하지 않습니다.

주제 단어가 없는 응답은 임의의 문자 조각으로 토픽을 만들지 않고 미배정으로 남기며 감정분석은 유지합니다. 토픽별 건수·감정 집계는 원래 빈도 기준이고 모델 점수·bootstrap·부분표본 진단은 중복 제거 문장 기준입니다. 선택된 임베딩이 있으면 모든 후보의 분리도를 같은 임베딩 공간에서 비교합니다. 없으면 같은 TF-IDF 공간을 사용합니다. `probability`는 하위 호환 필드명이며 `score_method`에 따라 LDA 사후 가중치, 정규화 NMF 가중치 또는 상대적 중심 유사도입니다. 분류 정확도나 보정된 신뢰확률이 아닙니다.

권장 토픽 수는 “통계적 최적값”이 아닙니다. 최소 토픽 크기·분석 포함률 구조 관문을 통과한 후보에서 다음 지표를 결합한 제품용 휴리스틱입니다.

- `stability` → **군집 품질 종합점수**: 하위 호환 필드이며 반복 표본의 통계적 안정성이 아님
- `coherence` → **토픽 해석 가능성 점수**: 상위 키워드의 문서 동시출현을 이용한 bounded UMass-style 값
- `semantic_quality` → **군집 분리도**: 노이즈 제외 cosine silhouette
- `coverage` → **분석 포함률**
- `diversity` → **토픽 키워드 다양성**: 단어·구 포함 중복을 억제한 상위 키워드의 토픽 간 고유 비율
- `labelability` → **라벨 해석 가능성**
- `balance` → **토픽 크기 균형**
- `weight_acceptability` → **가중치 시나리오 선정률**: 기본 가중치를 각각 50–150% 범위에서 바꾼 512개 시나리오의 선정 비율이며 정확도 확률이 아님
- `bootstrap_gate_pass_rate` → **Bootstrap 구조 관문 통과율**: 현재 배정에 조건부인 500회 복원추출 진단이며 통계적 검정력이 아님
- `resampling_stability` → **부분표본 일치도**: 선정 후보의 5회 80% 층화 부분표본 재적합 ARI 진단이며 권장 점수에는 미포함

기본 복합 가중치는 외부 정답으로 학습된 값이 아닙니다. 거의 동점인 후보에서는 제한 범위 가중치 시나리오 선정률을 먼저 보고, 같으면 더 단순한 토픽 수를 선택합니다. NMF는 Frobenius와 일반화 KL 두 목적함수를 별도 후보로 비교하고, NMF/LDA는 모델 성분에서 키워드를 뽑고 문서–토픽 가중치로 대표 응답을 정합니다. KMeans·계층·DBSCAN은 군집별 class-based TF-IDF로 키워드를 표현하고 군집 중심에 가까운 응답을 사용합니다.

BERTopic `0.17.x` 후보는 공식 라이브러리의 모듈형 파이프라인을 사용합니다. 문서 임베딩을 UMAP으로 축소하고 HDBSCAN으로 자연 군집과 이상치를 찾은 뒤 class-based TF-IDF로 토픽을 표현합니다. 사용자가 OpenAI·Gemini·Azure/OpenAI-compatible 임베딩을 선택했다면 같은 임베딩을 BERTopic에도 전달합니다. 외부 임베딩이 없으면 선택한 로컬 E5를 사용하고, E5도 없으면 TF-IDF를 TruncatedSVD로 축소한 LSA 벡터를 사용하며, transformer 모델을 자동 다운로드하거나 설문 원문을 별도 서비스로 전송하지 않습니다. 따라서 이 로컬 fallback은 이름과 달리 BERT 의미 임베딩을 사용하지 않으며, BERTopic이라는 이유만으로 결과 품질이 보장되지는 않습니다. BERTopic이 만든 자연 토픽 수가 현재 표본 정책 범위를 벗어나거나 구조 관문을 통과하지 못하면 권장 후보로 채택되지 않습니다. 카카오 대화에서는 구조 관문과 70% 포함률을 통과한 BERTopic 후보의 cosine silhouette가 기존 최고 후보보다 0.05 이상 높을 때 의미 분리가 더 나은 후보로 우선합니다. 선택 후 품질 기준이 약하면 화면에 `품질 검토 필요 후보`로 표시되므로 확정 결과로 사용하면 안 됩니다. 공식 프로젝트와 설치법은 [MaartenGr/BERTopic](https://github.com/MaartenGr/BERTopic)을 참고하세요.

BERTopic은 `sentence-transformers`, UMAP, HDBSCAN 등을 함께 설치하므로 최초 설치 용량과 시간이 늘어납니다.

```powershell
python -m pip install "bertopic>=0.17.4,<0.18"
```

점수는 같은 코퍼스의 후보를 비교하는 용도이며 서로 다른 조사 사이의 정확도 비교에 사용할 수 없습니다.

명시적 귀무가설·효과크기·정답 토픽·사전 표본설계가 없으므로 고전적 의미의 통계적 검정력이나 p-value를 제공하지 않습니다. bootstrap과 부분표본 일치도는 표본 및 모델 선택 민감도를 드러내는 진단이며, 담당자의 토픽 라벨·대표 응답 검토를 대체하지 않습니다.

감정 결과는 규칙·어휘 기반 **감정 신호 분석**이고 심리 진단이나 임상적 판단이 아닙니다. 처리 우선도는 긴급성·위험도를 판정하지 않고 먼저 검토할 표현을 정렬하는 보조지표입니다.

분석 후 UI 또는 `record_review` edit API로 검토자·판정·메모를 기록할 수 있습니다. 승인 이후 토픽 구조를 변경하면 승인 상태가 자동으로 재검토 필요 상태로 바뀝니다. 정답 라벨 CSV가 있는 경우 `survey-insight evaluate-sentiment`로 원문이 없는 집계 평가 JSON을 만들 수 있습니다.

계산식, 후보별 입력 공간, 소표본 정책과 알려진 한계는 [분석 방법론](docs/METHODOLOGY.md), 재현 가능한 점검 절차는 [기능 검증 및 결과 점검](docs/EVALUATION.md)을 확인하세요. 실제 운영 전에는 [책임 있는 AI 운영 점검표](docs/RESPONSIBLE_AI_CHECKLIST.md)를 적용하고, 판정 추적 방식은 [재현 가능한 예시](docs/TRACEABLE_EXAMPLES.md)를 참고하세요.

### 0.2.0 회귀 검증

```powershell
python scripts/benchmark_analysis.py --out out_benchmark/regression.json
python scripts/benchmark_analysis.py --stress-rows 6000 --out out_benchmark/stress.json
```

2026-10-13에 추가한 [한국어 자체 회귀 예제](tests/fixtures/korean_analysis.json)에서 감정 분류는 수정 전 12/32에서 수정 후 32/32로 개선되었습니다. 교육·급여·시설의 세 주제에 긍정과 부정 표현을 섞은 24개 응답은 ARI 1.0으로 분리되며, 같은 코퍼스를 3회 반복해도 세 주제를 유지하고 건수는 복원합니다. **개발에 사용한 자체 예제이므로 외부 정확도나 일반화 성능을 의미하지 않습니다.** 별도의 실제 설문 라벨 자료는 `evaluate-sentiment`로 검증하세요.

문맥이 섞인 대화는 자동 분석이 완료되어도 품질 기준을 통과하지 못할 수 있습니다. 낮은 분리도나 재표본 안정성은 화면에서 검토 필요로 표시하며, 모델 이름만으로 분석 성공을 판정하지 않습니다. 최신 기능·검증 범위는 [0.2.1 변경 기록](docs/RELEASE_0.2.1.md)에 정리합니다.

### 0.2.1 추가 문맥·무결성 검증

별도로 작성한 감정 문맥 40개는 19/40에서 40/40으로 개선했습니다. 인용·가정 등 8개 사례의 검토 표시도 2/8에서 8/8로 보완했습니다. 모두 개발에 사용한 회귀 사례이며 외부 정확도가 아닙니다.

반복 어휘가 적은 [24문장 토픽 진단 자료](tests/fixtures/topic_paraphrases.json)에서는 로컬 E5를 사용해도 분석자가 붙인 넓은 주제와의 ARI가 약 0.504였습니다. 단어 기반 결과는 더 낮았습니다. 이 결과도 공개하여 쉬운 예제의 ARI 1.0을 일반 성능으로 오해하지 않도록 합니다.

```powershell
python scripts/benchmark_topic_diagnostics.py --local-embeddings --out out_benchmark/topic_diagnostics.json
python -m unittest discover -s tests -v
```

보고서는 소수 집단 셀의 건수·비율·감정값을 함께 숨기고, 사용자 입력을 Excel 수식으로 실행하지 않습니다. 대표 의견과 편집 이력에도 개인정보 패턴 마스킹을 적용합니다. 기존 결과는 열 수 있지만 새 규칙의 감정·토픽 값을 얻으려면 다시 분석해야 합니다.

### 이전 버전의 샘플 점검 기록

아래 값은 0.1.0 당시 `sample_data/mock_survey_responses.csv`의 **구조적 smoke evaluation 기록**입니다. 0.2.0의 현재 실행값이 아닙니다. 2026-08-09에 Python 3.12, scikit-learn 1.9, seed 42와 외부 네트워크 비활성 조건으로 실행한 기록을 보존합니다.

```powershell
$env:SURVEY_INSIGHT_DISABLE_NETWORK='1'
python -m survey_insight.cli analyze `
  --input .\sample_data\mock_survey_responses.csv `
  --out .\out_evaluation `
  --seed 42
```

| 확인 항목 | 재현 결과 | 해석 범위 |
|---|---:|---|
| 입력 / 유효 자유응답 | 80 / 76 | 무응답 4건 제외 |
| 허용 토픽 수 | 4–10 | 표준 모드의 제품 정책 범위 |
| 생성 후보 | 31개 | KMeans 7, 계층 7, Frobenius NMF 5, KL-NMF 7, LDA 5 |
| 권장 후보 | Frobenius NMF, 5개 토픽 | 현재 후보군과 휴리스틱에서의 권장안 |
| 복합 평가값 | 0.584 | 같은 코퍼스 후보 사이의 비교값 |
| 가중치 시나리오 선정률 | 0.742 ± 0.0193 MCSE | 선언된 가중치 범위의 선택 민감도이며 정확도 확률이 아님 |
| Bootstrap 구조 관문 통과율 | 0.850 | 현재 배정에 조건부인 표본 구성 진단 |
| 80% 부분표본 재적합 ARI | 평균 0.243, 10–90백분위 0.146–0.370 | 현재 경고 기준 0.60보다 낮아 구조 검토 필요 |

KL-NMF 후보도 4–10개 토픽 범위에서 실제로 비교했지만 이 샘플에서는 선택되지 않았습니다. 이는 특정 엔진을 항상 “최고 모델”로 고정하지 않고 입력별로 후보를 비교한다는 뜻입니다. 반면 낮은 부분표본 ARI는 문서 일부가 달라지면 분할도 달라질 수 있음을 보여 줍니다. 따라서 NMF 5개 결과를 정답으로 간주하지 말고 더 단순한 후보, 키워드, 대표 응답을 함께 읽어 사람이 승인해야 합니다.

샘플은 합성 데이터이며 정답 토픽 라벨이 없습니다. 위 수치는 모델 정확도, 통계적 유의성 또는 다른 설문에서의 성능을 입증하지 않으며 라이브러리 버전·전처리·입력 변화에 따라 달라질 수 있습니다. 더 자세한 후보별 근거와 판정 순서는 [재현 가능한 판정 추적 예시](docs/TRACEABLE_EXAMPLES.md)에 기록합니다.

## 테스트

먼저 테스트용 선택 의존성을 설치한 뒤 외부 API 호출 없이 전체 테스트를 실행합니다.

```powershell
python -m pip install -e ".[test]"
python -m unittest discover -s tests -v
python -m compileall survey_insight tests
```

GitHub Actions도 같은 테스트 선택 의존성을 설치하고 Python 3.11·3.12에서 위 검사를 실행합니다. `SURVEY_INSIGHT_DISABLE_NETWORK=1`을 설정하며 provider 테스트는 mock을 사용하므로 실제 API 키나 외부 AI 호출에 의존하지 않습니다.

테스트는 API·SQLite round trip, 전처리, 토픽 후보와 구조 관문, 동일 seed 재현성, provider mock/fallback, API 키 비저장, export 개인정보 보호와 OOXML 구조, UI 핵심 문구를 확인합니다. 이는 기능 동작 점검이며 분석 정확도나 통계적 타당성을 보증하지 않습니다. 실제 실행 결과는 릴리스나 PR에서 명령·통과 수와 함께 기록해야 합니다.

## 프로젝트 구조

```text
survey_insight/
  api.py                 FastAPI 라우트와 웹 진입점
  ui.py                  브라우저 UI
  pipeline.py            분석 파이프라인과 그룹 비교
  preprocessing.py       한국어 전처리·일부 PII 패턴 마스킹
  topics.py              토픽 후보·구조 관문·휴리스틱 평가
  embeddings.py          선택 provider 임베딩
  local_embeddings.py    다운로드와 분리된 오프라인 E5 추론
  sentiment.py           형태소·사전·부정문 기반 감정과 근거
  data/sentiment_ko.tsv  버전 관리되는 내장 한국어 감정사전
  evaluation.py          사용자 제공 감정 정답셋 집계 평가
  llm_interpretation.py  선택 provider 근거 해석
  exports.py             Excel·Word·PowerPoint 출력
  storage.py             로컬 SQLite 저장소
docs/                    방법론·평가·책임 있는 AI 점검·추적 예시와 화면 이미지
sample_data/             합성·모의 데이터
tests/                   unittest 테스트
out*/                    로컬 DB·생성 보고서(소스 아님)
```

주요 API는 `POST /datasets/upload`, `GET /datasets/{dataset_id}/profile`, `DELETE /datasets/{dataset_id}?delete_runs=true`, `POST /model-runs`, `GET /model-runs/{run_id}/recommendation`, `DELETE /model-runs/{run_id}`, `POST /model-runs/{run_id}/edits`, `POST /exports`, `GET /projects/recent`입니다. 업로드 API는 파일 bytes를 요청 본문으로 받습니다. 연결 run이 있는 dataset은 기본 삭제를 거부하며, 함께 삭제하려면 `delete_runs=true`를 명시해야 합니다.

`GET /analysis-capabilities`에서 형태소·감정사전 버전과 로컬 모델 준비 상태를 확인할 수 있습니다. `GET /model-runs/{run_id}/documents?topic_id=T01&sentiment_label=negative&offset=0&limit=25`는 마스킹된 응답·형태소·감정 근거·소속도만 반환합니다. `limit`은 최대 100입니다. Excel의 `감정분포`와 `원자료_토픽배정` 시트에도 같은 정보가 포함됩니다.

## 라이선스

소스 코드는 [MIT License](LICENSE)로 배포합니다. 외부 라이브러리와 사용자가 선택한 AI provider에는 각각의 라이선스·약관이 적용됩니다.

## 면책 및 책임 있는 사용

이 프로젝트는 HR 의사결정을 자동화하거나 법률·노무·보안 자문을 제공하지 않습니다. 채용, 평가, 보상, 징계, 구조조정 등 개인에게 중대한 영향을 주는 결정의 단독 근거로 사용하지 마세요. 토픽 라벨, 대표 의견, 감정 신호, 그룹 차이는 편향·표본 크기·문맥 손실의 영향을 받으므로 원자료와 조직 맥락을 아는 사람이 검토하고 이의를 제기하거나 수정할 절차를 마련해야 합니다.
