# TripBuddy API · v0.2

기본 주소 `http://127.0.0.1:8001`. `/docs`에 실행 중 서버의 OpenAPI 명세가 있다. 기본 모드는 `demo`, 실제 모델은 명시적 opt-in이 필요한 `live`다.

## 인증

`POST /sessions`에서 `{id, token, mode}`를 받는다. 이후 요청은 `Authorization: Bearer <token>`을 전송한다. 세션 토큰을 쿼리나 이벤트 URL에 넣지 않는다. 다른 세션의 작업·결과를 요청하면 404를 반환한다. 현재 API 세션은 서버 메모리에서만 유지된다.

## 경로

| 메서드·경로 | 역할 |
| --- | --- |
| GET /health | alive, ready, mode, 안전한 startup 오류 코드 |
| POST /sessions | 새 익명 세션 생성 |
| GET /sessions/{id} | messages, result, active_job 복원 |
| POST /sessions/{id}/messages | {message, request_id}를 접수하고 {job_id, duplicate} 반환 |
| GET /jobs/{id} | queued/running/completed/failed, 결과·이벤트 조회 |
| GET /jobs/{id}/events | SSE 진행, after 또는 Last-Event-ID 이후 재생 |
| GET /sessions/{id}/export | 마지막 코스의 Markdown |

## 요청과 처리

message는 공백 제외 1~3000자, request_id는 영문·숫자·하이픈 8~80자다. 동일 request_id·동일 문장은 같은 작업을 반환한다. 같은 ID에 다른 문장을 보내면 409다. 동일 세션에서 동시 생성·수정은 409다. 큐·메모리 용량이 차면 429, 엔진 준비가 안 되면 503이다. 유효성 오류는 입력 전문을 반영하지 않는다.

엔진은 원본 인터프리터와 작업 디렉터리를 사용하는 단일 장기 실행 프로세스다. API 큐에서 한 요청씩 처리하므로 검색 모델과 체크포인터를 병렬로 건드리지 않는다. SSE가 끊겨도 작업은 별도로 계속되며, 재연결·상태 조회는 새 생성을 시작하지 않는다.

## 이벤트

각 이벤트는 `{id, type, ...}`이며 id는 작업 안에서 1부터 증가한다.

- queued: 대기열 접수
- started: 엔진 실행 시작
- progress: 실제로 완료한 노드 `node`
- completed: 최종 `result`
- failed: 안전한 오류 `code`

SSE 본문에 id/event/data 필드를 포함한다. 이벤트 간 heartbeat는 주석이다. 토큰 단위 스트리밍이 아니라 그래프 노드 완료 상태다. 클라이언트는 마지막 id를 기억해 중복 표시를 막는다.

## result

`answer`(ask_back/abstain/course/error), `request`, `weather`, `violations`, `mode`(new/edit), `source`(demo/live), `places`, `credit`, `markdown`을 반환한다. 전체 그래프 State·검색 후보 전문·프롬프트는 노출하지 않는다.

course의 날짜별 슬롯은 id·이름·유형·주소·좌표·고른 이유·휴무 등의 facts·무장애 정보·직전 장소 직선거리다. places에는 선택된 장소의 사진 주소·수정일·수집일·좌표를 담는다. `leg_km`는 직선거리이며 실제 이동시간이 아니다. 검증기에서 제외한 칸이나 정보 부족 안내를 숨기지 않는다.

## 현재 제한

세션과 작업은 재시작 시 사라진다. 진행 중 작업의 프로세스 장애는 failed로 끝내고 엔진을 재시작한다. 장기 작업 저장·TTL·취소·계정·공개 운영 인증은 후속 범위다. 기본 CORS는 localhost/127.0.0.1의 5174 포트만 허용한다. 서버 바인딩은 loopback이며 이 상태를 그대로 공개 배포하지 않는다.
