# TripBuddy backend · 1단계 연결 실험

이 폴더에는 API 서버가 아닌 **오프라인 엔진 연결 검증 도구**가 있습니다. 실제 `graph.runtime.make_graph`와 LangGraph 노드·검증기를 실행하되, 검색·LLM·날씨·상세 조회는 합성 데이터로 대체합니다. 네트워크 연결은 프로세스 내부에서 차단합니다.

기존 tour-planner 소스와 가상환경은 명시적으로 지정합니다. 기존 소스 사본을 만들거나 sys.path를 바꾸지 않습니다. 자식 프로세스만 원본 엔진 디렉터리에서 실행하며, 현재 터미널 위치와 환경을 변경하지 않습니다. 원본 Python을 별도 프로세스로 사용하는 임시 로컬 연결 방식이며, 배포용 패키징은 아직 아닙니다.

## 실행

프로젝트의 `backend` 폴더로 이동합니다. 아래 경로는 현재 기기 기준이며 다른 기기에서는 실제 경로로 바꿉니다.

```sh
cd /Users/fastcampus_m/Desktop/fastcampus/trip-buddy/backend
/Users/fastcampus_m/Desktop/fastcampus/tour-planner/.venv/bin/python -m tripbuddy_backend.probe \
  --engine-root /Users/fastcampus_m/Desktop/fastcampus/tour-planner \
  --engine-python /Users/fastcampus_m/Desktop/fastcampus/tour-planner/.venv/bin/python \
  --output ../docs/engine-probe-results.json
```

출력은 합성 장소로 실행한 검사 요약이며 실제 여행 추천 결과가 아닙니다. 명령은 5개 시나리오를 검사하고 요약 JSON을 만듭니다. 실제 API 호출이나 모델 다운로드는 하지 않습니다. 기존 엔진의 `config.py`는 평소처럼 자체 환경 설정을 로드하지만 비밀 값을 출력하지 않습니다.

## 테스트

```sh
cd /Users/fastcampus_m/Desktop/fastcampus/trip-buddy/backend
TRIPBUDDY_ENGINE_ROOT=/Users/fastcampus_m/Desktop/fastcampus/tour-planner \
TRIPBUDDY_ENGINE_PYTHON=/Users/fastcampus_m/Desktop/fastcampus/tour-planner/.venv/bin/python \
/Users/fastcampus_m/Desktop/fastcampus/tour-planner/.venv/bin/python -m unittest discover -s tests -v
```

연결 시험은 표준 라이브러리만 사용합니다. 자식 프로세스에는 원본 엔진 의존성이 설치된 Python이 필요합니다. FastAPI는 아직 설치·구현하지 않았습니다.

## 현재 보장하는 것

- 실제 runtime이 Streamlit 없이 실행됨
- 날짜 되묻기 후 기존 조건을 이어서 코스를 생성함
- 점심만 수정하고 다른 슬롯은 보존함
- 후보 부족과 검색 예외를 2회 재검색 후 포기로 처리함
- 상세 조회 실패 시 저장분 표시가 유지됨
- 노드 진행·턴 완료·최종 완료를 순번 있는 JSON 이벤트로 변환함
- 타임아웃·잘못된 프로토콜이 사용자 데이터나 자식 오류 원문을 노출하지 않음

## 현재 한계

`probe`는 프로세스 종료 후 이벤트 목록을 반환합니다. 실시간 SSE가 아니며 장기 실행 서버·HTTP 경로·사용자 세션·요청 중복 방지·작업 큐는 없습니다. 다중 턴은 한 프로세스 안의 메모리 체크포인트로만 검증했습니다. 실제 모델 속도와 색인 로딩 메모리, 실 API 결과 품질, 브라우저와 엔진 연결은 검증 전입니다.

합성 장소와 고정 날짜는 테스트 전용입니다. 운영 요청의 날짜는 서버 시각(Asia/Seoul) 기준으로 별도 처리해야 합니다. 프런트엔드의 현행 디자인 체험 응답은 아직 교체하지 않습니다.
