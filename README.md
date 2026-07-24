# AI Survey Insight

<p align="center">
  <img src="docs/images/readme-cover.jpg" alt="AI Survey Insight 대표 프로젝트 소개 이미지" width="100%" />
</p>

AI Survey Insight는 한국어 설문 자유응답을 업로드하면 컬럼을 자동 점검하고, 토픽모델링과 감정분석을 실행한 뒤 Excel, Word, PowerPoint 보고서까지 생성하는 로컬 분석 도구입니다.

비전공자도 결과를 바로 검토할 수 있도록 토픽 수 추천 이유, 우선 확인할 토픽, 감정 근거, 대표 의견, 다음 대응 방향을 쉬운 한국어로 정리합니다. OpenAI, Gemini, Claude, Azure OpenAI, OpenAI 호환 서버를 선택적으로 연결할 수 있으며, API 키는 분석 요청 중에만 사용하고 저장하지 않습니다.

## 대표 프로젝트 소개

AI Survey Insight는 대량의 주관식 설문 응답을 담당자가 바로 검토할 수 있는 분석 결과와 보고서로 바꾸는 프로젝트입니다. 단순히 토픽 키워드만 보여주는 것이 아니라, 응답 컬럼 탐지부터 개인정보 마스킹, 토픽 수 추천, 감정 신호, 대표 의견, 보고서 생성까지 하나의 흐름으로 묶었습니다.

- **문제**: 자유응답 설문은 응답량이 많아질수록 사람이 직접 분류하기 어렵고, 분석 기준이 담당자마다 달라지기 쉽습니다.
- **접근**: 로컬 기본 분석을 우선 제공하고, 필요할 때만 사용자가 입력한 AI provider 키로 임베딩과 해석을 보강합니다.
- **결과**: 웹 대시보드에서 토픽과 우선순위를 검토하고, Excel/Word/PowerPoint 산출물로 회의와 보고에 바로 사용할 수 있습니다.

## 주요 기능

- XLSX/CSV 설문 파일 업로드 및 컬럼 프로파일링
- 자유응답 컬럼 자동 추천과 그룹 컬럼 선택
- Kiwi 기반 한국어 명사 추출, 개인정보 마스킹, 무응답 필터링
- LDA, NMF, KMeans, 계층 군집, DBSCAN/LSA 기반 토픽 후보 비교
- 안정성, 응집도, 분리도, 커버리지를 함께 고려한 토픽 수 추천
- 토픽별 감정 방향, 감정 강도, 처리 우선도, 근거 표현 제공
- 선택형 AI provider 기반 토픽 해석, 임베딩, 감정 보강
- Excel, Word, PowerPoint 보고서 자동 생성
- API 키와 endpoint를 SQLite나 보고서에 저장하지 않는 로컬 우선 설계

## 빠른 시작

Python 3.11 이상을 권장합니다.

```powershell
python -m pip install -r requirements.txt
python -m uvicorn survey_insight.api:app --host 127.0.0.1 --port 8001
```

브라우저에서 `http://127.0.0.1:8001`을 엽니다. Windows에서는 다음 파일로도 실행할 수 있습니다.

```text
start_app.bat
```

샘플 흐름은 웹 화면에서 `sample_data/mock_survey_responses.csv`를 업로드해 확인할 수 있습니다.

## 사용 흐름

1. 설문 XLSX/CSV 파일을 업로드합니다.
2. 앱이 컬럼 유형과 자유응답 후보를 자동 점검합니다.
3. 자유응답 컬럼과 비교용 그룹 컬럼을 확인합니다.
4. 표준 모드 또는 AI provider 보강 모드로 분석을 실행합니다.
5. 토픽 추천, 감정 신호, 대표 의견을 검토합니다.
6. Excel, Word, PowerPoint 보고서를 내려받습니다.

## 사용 화면

아래 화면은 `sample_data/mock_survey_responses.csv`를 업로드해 분석한 실제 예시입니다. 샘플 데이터는 총 80행이며, 유효 자유응답 76건이 분석되었습니다.

<table>
  <tr>
    <td width="50%">
      <img src="docs/images/readme-01-app-column-profile.jpg" alt="컬럼 프로파일 화면" width="100%" />
      <br />
      <strong>컬럼 프로파일</strong>
      <br />
      업로드한 데이터의 행 수, 컬럼 수, 헤더 위치, 자유응답 후보를 확인합니다.
    </td>
    <td width="50%">
      <img src="docs/images/readme-04-topic-recommendation.jpg" alt="토픽 추천 요약 화면" width="100%" />
      <br />
      <strong>토픽 추천 요약</strong>
      <br />
      권장 토픽 수, 대안, 추천 이유, 품질 점수를 한 화면에서 검토합니다.
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="docs/images/readme-05-priority-topics.jpg" alt="우선 확인할 토픽 상세 화면" width="100%" />
      <br />
      <strong>우선 확인할 토픽</strong>
      <br />
      비중, 부정 신호, 개선 요구를 함께 보아 먼저 확인할 주제를 정렬합니다.
    </td>
    <td width="50%">
      <img src="docs/images/readme-06-topic-table.jpg" alt="전체 토픽 표 화면" width="100%" />
      <br />
      <strong>전체 토픽 표</strong>
      <br />
      분야, 핵심어, 감정 상세, 담당자용 설명, 대표 의견을 표로 비교합니다.
    </td>
  </tr>
</table>

## 보고서 산출물

분석 결과는 검토 방식에 맞게 세 가지 형식으로 저장할 수 있습니다.

<table>
  <tr>
    <td width="33%">
      <img src="docs/images/05-excel-export-topic-mapping.jpg" alt="Excel 보고서 토픽 매칭 예시" width="100%" />
      <br />
      <strong>Excel</strong>
      <br />
      토픽 요약, 원자료 토픽 매칭, 그룹 비교를 시트별로 저장합니다.
    </td>
    <td width="33%">
      <img src="docs/images/readme-02-powerpoint-report.jpg" alt="PowerPoint 보고서 예시" width="100%" />
      <br />
      <strong>PowerPoint</strong>
      <br />
      발표용 요약, 핵심 발견, 주요 토픽, 대표 의견을 슬라이드로 생성합니다.
    </td>
    <td width="33%">
      <img src="docs/images/readme-03-word-report.jpg" alt="Word 보고서 예시" width="100%" />
      <br />
      <strong>Word</strong>
      <br />
      Executive Summary, 쉬운 해석, 방법론, 주의사항을 문서로 정리합니다.
    </td>
  </tr>
</table>

CLI 데모로 동일한 산출물을 생성할 수도 있습니다.

```powershell
python -m survey_insight.cli demo --out .\out
```

생성 결과:

- `out\demo_survey.xlsx`
- `out\analysis_package.json`
- `out\survey_insight_report.xlsx`
- `out\survey_insight_report.docx`
- `out\survey_insight_report.pptx`

## AI Provider 설정

기본 분석은 로컬에서 동작합니다. 더 정밀한 해석이 필요할 때만 화면에서 provider와 API 키를 입력합니다.

- OpenAI: `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, 직접 입력
- Gemini: `gemini-3.5-flash`, `gemini-3.1-pro-preview`, `gemini-3.1-flash`, `gemini-3.1-flash-lite`, 직접 입력
- Claude: `claude-sonnet-5`, `claude-opus-4-8`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`, 직접 입력
- Azure OpenAI: Azure endpoint, chat deployment, embedding deployment 직접 입력
- OpenAI 호환 서버: base URL과 모델명 직접 입력

테스트용 또는 예시처럼 보이는 키는 외부 호출을 건너뛰고 로컬 분석으로 대체합니다.

## 프로젝트 구조

```text
survey_insight/
  api.py                 FastAPI 라우트와 웹 진입점
  ui.py                  브라우저 UI
  pipeline.py            분석 파이프라인
  preprocessing.py       한국어 전처리, Kiwi 토큰화, PII 마스킹
  topics.py              토픽 후보 생성 및 평가
  embeddings.py          선택 provider 임베딩 호출
  sentiment.py           로컬 감정/처리 우선도 보조 분석
  llm_interpretation.py  선택 provider 기반 근거 해석
  exports.py             Excel, Word, PowerPoint 출력
  storage.py             SQLite 저장소
sample_data/             테스트용 모의 데이터
docs/images/             README 사용 화면 이미지
tests/                   unittest 테스트
out*/                    로컬 생성 결과물
```

## 테스트

```powershell
python -m unittest discover -s tests -v
```

테스트는 API 흐름, 저장소 round-trip, 한국어 토큰화, 토픽 후보 생성, provider embedding/LLM mock 경로, export 개인정보 보호, UI 렌더링을 확인합니다.

## API 개요

- `POST /datasets/upload?filename=survey.xlsx`
- `GET /datasets/{dataset_id}/profile`
- `POST /model-runs`
- `GET /model-runs/{run_id}/recommendation`
- `POST /model-runs/{run_id}/edits`
- `POST /exports`
- `GET /exports/{run_id}/{excel|word|powerpoint}/download`
- `GET /projects/recent`

`POST /datasets/upload`는 요청 본문에 파일 bytes를 그대로 받습니다.

## 개인정보 및 보안

분석 전 개인정보 마스킹을 수행합니다. 외부 provider를 사용할 때도 원문 전체가 아니라 마스킹된 텍스트와 대표 응답 중심으로 전송합니다. Excel export는 기본적으로 `redacted_text`를 사용하며 `original_text`를 포함하지 않습니다.

`out/`, `out_debug/`, `out_validation/`, `out_precision_validation/`, `out/app.db`는 로컬 생성물입니다. 실제 설문 데이터가 포함될 수 있으므로 공유 전 내용을 확인하세요.
