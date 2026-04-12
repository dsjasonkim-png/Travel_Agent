# Changes From Git Base

이 문서는 현재 작업 트리가 저장소에 기록되어 있던 이전 git 기준 버전과 비교해 무엇이 달라졌는지 설명합니다. 목적은 `git diff`를 직접 읽지 않아도 현재 코드가 어떤 방향으로 바뀌었는지 빠르게 파악할 수 있게 하는 것입니다.

## 요약

이번 변경의 핵심은 다음 다섯 가지입니다.

1. 실행용 supervisor를 단순한 책/데모 버전(`chapter_graph.py`)으로 분리하고, 실제 앱이 그 그래프를 사용하도록 바꿈
2. 서브 에이전트 실행 방식을 “일괄 실행”에서 “순차 실행 + 서비스별 HITL 가능” 구조로 변경
3. 항공 검색을 더미 응답에서 SerpApi 실조회로 전환
4. 날씨 경로를 루트 `.env` 기반 OpenWeather 실조회 경로로 정리
5. 로그를 LangGraph stream 중심의 짧은 요약 로그로 재설계

## 큰 방향의 변화

### 1. 실행 그래프의 기준이 바뀜

이전 기준:

- 저장소에는 다양한 supervisor 실험 코드가 섞여 있었고
- README도 예전 supervisor 흐름을 기준으로 서술하고 있었습니다.

현재 기준:

- `src/travel_agent/supervisor/__init__.py`가 `chapter_graph.py`의 `get_supervisor_graph()`를 export 합니다.
- 즉, UI와 서비스 실행은 `chapter_graph.py`를 실제 runtime supervisor로 사용합니다.
- `supervisor/graph.py`는 남아 있지만 활성 경로가 아닙니다.

영향:

- 코드 읽는 기준점이 명확해졌습니다.
- “어느 그래프가 실제로 실행되는가?”에 대한 혼동이 줄었습니다.

### 2. 서브 에이전트 실행 방식이 바뀜

이전 기준:

- 서비스 호출을 한 번에 묶어 처리하는 구조가 있었고
- 서비스별 HITL을 넣기 어려운 형태였습니다.

현재 기준:

- `weather -> hotel -> flight -> restaurant` 순서로 하나씩 실행합니다.
- 상태에 `current_service_index`가 추가되었습니다.
- 현재 서비스가 `flight`인데 `origin`이 비어 있으면 그 시점에만 `ask_origin_hitl`이 발생합니다.

영향:

- 특정 서브 에이전트에만 필요한 추가 질문을 해당 단계에서 처리할 수 있습니다.
- 향후 다른 서브 에이전트에도 동일한 패턴으로 HITL을 확장할 수 있습니다.

### 3. 항공 도메인이 실제 API 경로로 바뀜

이전 기준:

- 항공 응답은 더미 텍스트 중심이었습니다.
- 공항 코드 변환이나 실조회는 활성 경로가 아니었습니다.

현재 기준:

- `src/travel_agent/agents/flight/agent.py`가 실질적인 항공 도메인 진입점입니다.
- `src/travel_agent/agents/flight/flight_api_client.py`가 SerpApi Google Flights를 호출합니다.
- `flight_serpapi_api_key`를 루트 `.env`에서 읽어 사용합니다.
- 위치 문자열은
  - 하드코딩 alias
  - aggregate IATA 보정
  - LLM fallback
  순서로 공항 코드로 변환합니다.

영향:

- “서울 -> 도쿄”, “서울 출발 -> 제주도”, “인천공항 -> 일본 도쿄” 같은 입력이 실조회로 이어집니다.
- 예전처럼 단순 더미 추천만 반환하지 않습니다.

### 4. 날씨 도메인이 루트 설정 기반으로 정리됨

이전 기준:

- 날씨 쪽은 환경변수 접근 위치가 분산되어 있었고
- 디버그 출력과 직접 `os.getenv()` 접근이 섞여 있었습니다.

현재 기준:

- `src/travel_agent/config.py`가 루트 `.env`를 명시적으로 로드합니다.
- `src/travel_agent/agents/weather/tools.py`는 `config.py`의 `OPENWEATHER_API_KEY`를 직접 참조합니다.
- 요청에는 timeout이 들어가고, 불필요한 debug print는 제거됐습니다.

영향:

- 환경변수 소스가 일관됩니다.
- 런타임 동작을 재현하기 쉬워졌습니다.

### 5. 로그가 실사용 기준으로 정리됨

이전 기준:

- 루트 로거와 LangGraph stream 로그가 함께 보일 수 있었고
- JSON dump가 길게 찍혀 읽기 어려웠습니다.

현재 기준:

- 기본 출력은 `travel_agent.langgraph` 로거만 남깁니다.
- stream 로그는 요약 형태입니다.
- 기본 `INFO`에서는 `updates`와 최종 `wait/done`만 출력합니다.
- `DEBUG`에서만 task/debug/value 로그가 추가됩니다.

영향:

- 터미널에서 실제 필요한 단계만 빠르게 읽을 수 있습니다.

## 파일군별 상세 변경

### A. 런타임 진입점

#### `src/travel_agent/app.py`

- Gradio UI를 현재 상태 구조에 맞게 사용
- `result["__interrupt__"]`를 챗 메시지로 풀어 보여줌
- 상태 요약 패널에서
  - phase
  - slots
  - slot_values
  - sub_results
  를 확인 가능

#### `src/travel_agent/service.py`

- `thread_id`를 기준으로 HITL 재개를 관리
- 새 입력은 `messages` 기반 state payload로 시작
- resume 입력은 `Command(resume=...)`로 전달
- 실행 자체는 `run_with_stream_logging()`로 통일

#### `src/travel_agent/__main__.py`

- 모듈 엔트리포인트가 Gradio app 실행 경로를 따르도록 정리

### B. 설정과 환경변수

#### `src/travel_agent/config.py`

변경 사항:

- 프로젝트 루트 `.env`를 명시적으로 로드
- `FLIGHT_SERPAPI_API_KEY` 추가
- 루트 로그와 LangGraph 로그를 분리
- 기본 로그 레벨 조정
  - `TRAVEL_AGENT_LOG_LEVEL=WARNING`
  - `TRAVEL_AGENT_LANGGRAPH_LOG_LEVEL=INFO`
  - `TRAVEL_AGENT_LOG_PREVIEW=240`

의미:

- 런타임이 어느 `.env`를 읽는지 명확해졌고
- 내부 서브폴더 `.env`에 덜 의존하게 됨

### C. supervisor 계층

#### `src/travel_agent/supervisor/__init__.py`

- export 대상을 `chapter_graph.get_supervisor_graph`로 전환

#### `src/travel_agent/supervisor/chapter_graph.py`

새 파일로 추가됨.

주요 책임:

- 초기 안내 메시지
- LLM 기반 슬롯 추출
- 목적지/date HITL
- 서비스 순차 실행
- `flight` 전용 origin HITL
- 최종 결과 병합

핵심 노드:

- `initial_conversation`
- `collect_trip_details`
- `ask_destination_hitl`
- `ask_dates_hitl`
- `ask_origin_hitl`
- `prepare_services`
- `check_current_service`
- `execute_current_service`
- `finalize_subagent_results`

#### `src/travel_agent/supervisor/graph.py`

- 과거/실험용 supervisor 흐름이 남아 있음
- 현재 활성 런타임에서는 사용되지 않음
- 다만 저장소 diff 상 큰 변경량이 있어 참고용으로 유지되는 상태

### D. 상태와 슬롯

#### `src/travel_agent/state.py`

- `current_service_index` 추가
- 현재 순차 오케스트레이션을 추적할 수 있게 됨

#### `src/travel_agent/slots.py`

- 현재 서비스 순서와 필수 필드를 단순 명확하게 유지
- `flight`만 `origin`을 추가로 요구
- `get_departure_city()` 기본값은 `서울`

### E. 항공 도메인

#### `src/travel_agent/agents/flight/agent.py`

가장 큰 변경 포인트입니다.

추가/변경 내용:

- 더미 응답 전용 파일이 아니라 실조회 엔트리포인트가 됨
- 공항 코드 변환 규칙 추가
- aggregate IATA 보정 추가
- 자연어 변형 처리 추가
- LLM fallback 추가
- 실조회 결과 포맷팅 추가
- 사용자 안내 문구 개선
  - 예전처럼 “공항 코드 변환 실패”를 직접 노출하지 않음
  - 끝까지 실패하면 “더 구체적으로 입력해 달라”는 형태로 반환

#### `src/travel_agent/agents/flight/flight_api_client.py`

- `FLIGHT_SERPAPI_API_KEY`를 기본 소스로 사용
- SerpApi 요청 파라미터를 정리
- 빈 문자열 파라미터는 보내지 않도록 정리
- 출력 debug print 제거

#### `src/travel_agent/agents/flight/graph.py`

- optional wrapper에서 origin HITL을 갖는 실제 subgraph wrapper로 확장
- standalone subgraph로 돌릴 때도 출발지 질문 가능

#### `src/travel_agent/agents/flight/tools.py`

- SerpApi 키를 `config.py` 상수로 통일
- 분산된 dotenv 로딩 정리

### F. 날씨 도메인

#### `src/travel_agent/agents/weather/agent.py`

- OpenWeather + OpenAI 경로를 결합한 weather orchestrator 역할
- LLM 경로 실패 시 direct tool 호출 fallback 유지

#### `src/travel_agent/agents/weather/tools.py`

- 루트 `.env` 기반 `OPENWEATHER_API_KEY` 사용
- timeout 추가
- debug print 제거
- 오류 메시지 정리

#### `src/travel_agent/agents/weather/graph.py`

- 현재 agent 함수를 감싸는 단순 wrapper graph 역할

### G. 호텔/맛집 도메인

#### `src/travel_agent/agents/hotel/agent.py`

- 지역별 더미 숙소 추천 응답 전용 파일로 분리

#### `src/travel_agent/agents/restaurant/agent.py`

- 지역별 더미 맛집 추천 응답 전용 파일로 분리

#### `src/travel_agent/agents/hotel/graph.py`
#### `src/travel_agent/agents/restaurant/graph.py`

- 각 `agent.py` 함수를 감싸는 단순 wrapper graph로 정리

### H. 로깅

#### `src/travel_agent/graph_stream.py`

변경 내용:

- 긴 raw JSON 로그 대신 요약 로그 도입
- `slot_values`, `sub_results`, `current_phase`, `current_service_index`, `interrupt` stage 중심으로 출력
- logger 레벨이 `DEBUG`일 때만 `debug` stream mode 활성화
- 실행 종료 시
  - `[LG wait]`
  - `[LG done]`
  형태의 요약 로그 추가

의미:

- 로그가 훨씬 짧고 읽기 쉬워짐

### I. 테스트

#### 새로 추가된 테스트

- `tests/test_graph_stream.py`
- `tests/test_service_flow.py`

#### 보강된 테스트

- `tests/test_flight_integration.py`
- `tests/test_weather_integration.py`

테스트 관점의 변화:

- 항공 실조회 파라미터 구성
- flight graph interrupt/resume
- supervisor의 순차 실행과 origin HITL
- weather direct tool 호출
- graph stream mode 제어

## 기능 변화 관점에서 보면

### 이전보다 좋아진 점

- 실제 앱이 어떤 supervisor를 쓰는지 명확함
- 항공은 더미가 아니라 실조회 가능
- 날씨 경로도 실조회 코드가 정리됨
- flight 단계에서 출발지 누락을 자연스럽게 HITL 처리
- 로그가 간결해짐
- 테스트 커버리지가 훨씬 넓어짐

### 아직 남아 있는 한계

- 호텔과 맛집은 여전히 더미 데이터
- weather는 실제 키 유효성에 따라 런타임 성공 여부가 갈림
- flight 위치 변환은 자동완성 API가 아니라 alias + LLM fallback이라 완전한 공항 검색 엔진은 아님
- `supervisor/graph.py`와 `supervisor/chapter_graph.py`가 동시에 존재해 코드베이스가 다소 이중화되어 보일 수 있음

## 운영 메모

현재 코드를 이해할 때 가장 중요한 기준은 아래입니다.

1. 실제 앱은 `chapter_graph.py`를 사용한다.
2. 서브 에이전트는 순차 실행된다.
3. `flight`만 현재 service-specific HITL이 들어가 있다.
4. 항공과 날씨는 실 API 경로가 있다.
5. 로그는 `travel_agent.langgraph` 요약 로그만 보면 된다.

## 권장 다음 작업

현재 코드 흐름을 더 안정적으로 만들려면 다음 우선순위를 추천합니다.

1. `weather` API 키 검증 상태를 UI에 명확히 표시
2. `hotel`, `restaurant`도 실 API 또는 검색 연동으로 전환
3. `flight` 위치 변환을 LLM fallback에서 autocomplete API 우선 구조로 확장
4. `supervisor/graph.py`와 `chapter_graph.py`의 역할을 정리하거나 하나로 수렴
5. README와 이 변경 문서를 기준으로 릴리스 노트 포맷 정착
