# Changelog

이 프로젝트의 주목할 만한 변경은 이 파일에 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)를 따르며 버전은 [Semantic Versioning](https://semver.org/) 원칙을 사용합니다.

## [Unreleased]

### Changed

- 토픽 후보별 입력 표현과 사용자 표시 지표를 더 명확하게 설명합니다.
- 공개 프로젝트용 보안·기여·방법론·평가 문서를 정비합니다.
- 선정 후보의 부분표본 ARI 진단, 짧은 LDA 입력 관문, 비수렴 후보 제외를 추가합니다.
- 외부 전송 사전 확인, 개인정보 문맥 검토 표시, 사람 승인·변경 후 재검토 기록을 추가합니다.
- 사용자 제공 감정 정답셋의 집계 평가 CLI를 추가합니다.

## [0.1.0] - 2026-08-09

### Added

- 한국어 설문 자유응답의 컬럼 프로파일링, 일부 식별정보 패턴 마스킹, 토픽 후보 비교, 감정 신호, 그룹 비교 기능
- 선택적 사용자-key provider 임베딩 및 해석 보강 경로
- Excel, Word, PowerPoint 보고서와 FastAPI 웹 UI·CLI
- SQLite 기반 로컬 dataset 및 분석 run 저장
- mock·합성 데이터 기반 unittest

[Unreleased]: https://github.com/koul777/AI-Survey-Insight/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/koul777/AI-Survey-Insight/releases/tag/v0.1.0
