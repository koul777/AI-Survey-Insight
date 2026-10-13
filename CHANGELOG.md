# Changelog

이 프로젝트의 주목할 만한 변경은 이 파일에 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)를 따르며 버전은 [Semantic Versioning](https://semver.org/) 원칙을 사용합니다.

## [Unreleased]

## [0.2.0] - 2026-10-13

### Added

- Kiwi 전체 품사열과 내장 한국어 감정사전 160항목, 절 범위 부정·이중 부정·강조·근거 구간
- 응답별 감정 조회·필터, 토픽별 4종 감정 분포와 근거 포함률, Excel 감정 시트
- 명시적인 설치와 오프라인 추론을 분리한 Multilingual E5, 긴 문서 전체 구간 인코딩
- 카카오톡 CSV/TXT 전처리와 실제 BERTopic 후보, 대용량 MiniBatch NMF
- 자체 한국어 회귀 fixture와 재현 가능한 `scripts/benchmark_analysis.py`

### Changed

- 동일 문장은 한 번 적합하고 전체 응답 빈도를 복원하여 반복 자료의 과분할을 줄입니다.
- 후보 분리도를 공통 공간에서 비교하고 정규화 소속도와 실제 키워드 응답 설명률을 제공합니다.
- 무어휘 입력은 토픽 미배정으로 남기며 감정분석은 유지합니다.
- 감정 판정을 문서에 저장해 후보 비교·병합에서 재사용합니다.
- 최근 분석 목록과 권장안 요약 조회의 대용량 응답 처리를 개선합니다.
- 토픽 후보별 입력 표현과 사용자 표시 지표를 더 명확하게 설명합니다.
- 일반화 KL-NMF를 비교 후보로 추가하고, 후보 엔진을 독립 실행하도록 수정합니다.
- 하드 군집의 class-based TF-IDF 키워드 표현과 단어·구 포함 중복 억제를 추가합니다.
- 공개 프로젝트용 보안·기여·방법론·평가 문서를 정비합니다.
- 선정 후보의 부분표본 ARI 진단, 짧은 LDA 입력 관문, 비수렴 후보 제외를 추가합니다.
- 제한 범위 가중치 시나리오 선정률, assignment-conditional bootstrap 구조 관문 진단, 5회 부분표본 재적합 구간을 추가합니다.
- 외부 전송 사전 확인, 개인정보 문맥 검토 표시, 사람 승인·변경 후 재검토 기록을 추가합니다.
- 사용자 제공 감정 정답셋의 집계 평가 CLI를 추가합니다.

## [0.1.0] - 2026-08-09

### Added

- 한국어 설문 자유응답의 컬럼 프로파일링, 일부 식별정보 패턴 마스킹, 토픽 후보 비교, 감정 신호, 그룹 비교 기능
- 선택적 사용자-key provider 임베딩 및 해석 보강 경로
- Excel, Word, PowerPoint 보고서와 FastAPI 웹 UI·CLI
- SQLite 기반 로컬 dataset 및 분석 run 저장
- mock·합성 데이터 기반 unittest

[Unreleased]: https://github.com/koul777/AI-Survey-Insight/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/koul777/AI-Survey-Insight/releases/tag/v0.2.0
[0.1.0]: https://github.com/koul777/AI-Survey-Insight/releases/tag/v0.1.0
