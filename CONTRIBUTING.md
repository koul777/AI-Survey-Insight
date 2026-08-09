# Contributing

기여해 주셔서 감사합니다. 이 프로젝트는 실제 설문 데이터와 API 키가 없어도 전체 테스트를 재현할 수 있어야 합니다.

## 개발 환경

Python 3.11 이상에서 별도 가상환경을 권장합니다.

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall survey_insight tests
```

기존 설치 흐름인 `python -m pip install -r requirements.txt`도 유지합니다. 웹 앱은 다음과 같이 실행합니다.

```powershell
python -m uvicorn survey_insight.api:app --host 127.0.0.1 --port 8001
```

## 코드 스타일과 테스트

- 4칸 들여쓰기, 타입 힌트, 작은 명시적 함수를 사용합니다.
- 함수·변수·모듈은 `snake_case`, dataclass는 `PascalCase`를 사용합니다.
- 저장되는 dataclass 필드는 JSON 직렬화 가능해야 합니다.
- 테스트는 표준 `unittest`와 `tests/test_*.py` 구조를 사용합니다.
- 외부 API 호출은 반드시 mock 처리합니다. 실제 키·네트워크·provider 가용성에 의존하는 테스트는 받지 않습니다.
- 실패 경로에는 결정적인 로컬 fallback과 credential을 숨긴 오류 메시지가 있어야 합니다.

## 개인정보 관련 변경

- 실제 설문 원자료, API 키, DB, 생성 보고서를 commit하지 마세요.
- 마스킹 패턴을 추가할 때는 정상 문장을 과도하게 가리지 않는 양성·음성 단위 테스트를 함께 추가하세요.
- `original_text`가 새 export나 외부 provider payload에 들어가는 변경은 명시적으로 검토하고 문서화해야 합니다.
- 그룹 통계의 작은 셀, 희귀 속성, 교차 결합에 따른 재식별 위험을 검토하세요.
- “완전 익명화”, 검증되지 않은 정확도·공정성·보안성을 주장하지 마세요.

## 분석 알고리즘 변경

토큰화, 후보 모델, 토픽 수 정책, 점수 산식, 감정 규칙을 변경하면 다음을 함께 갱신해 주세요.

1. 결정적 fixture 또는 mock 기반 테스트
2. `docs/METHODOLOGY.md`의 실제 계산 설명
3. `docs/EVALUATION.md`의 재현 점검 항목
4. UI와 Excel·Word·PowerPoint의 사용자 표시 용어
5. 하위 호환성에 영향이 있다면 migration 또는 alias 설명

## Pull Request 체크리스트

- [ ] 사용자에게 보이는 변경과 이유를 설명했습니다.
- [ ] 개인정보·저장·외부 전송 영향을 설명했습니다.
- [ ] 분석 방법 또는 점수 의미의 변화를 설명했습니다.
- [ ] 실제 실행한 테스트 명령과 결과를 적었습니다.
- [ ] 실제 API 키와 네트워크 호출 없이 테스트했습니다.
- [ ] `out*/`, DB, 실제 원자료, credential이 diff에 없는지 확인했습니다.
- [ ] 알고리즘 변경에 맞춰 테스트와 방법론 문서를 갱신했습니다.
- [ ] 기존 CSV/XLSX, API, Windows 실행 흐름의 회귀 여부를 확인했습니다.
