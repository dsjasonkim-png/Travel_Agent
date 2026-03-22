# Travel Agent

LangGraph 기반 멀티에이전트 여행 플래너 (슈퍼바이저 + 서브 에이전트).

- **슈퍼바이저**: 초기 대화로 슬롯 결정, slot filling 방식으로 여행 요소 수집 후 서브 에이전트 라우팅
- **서브 에이전트**: 날씨, 호텔, 항공, 맛집 (각각 서브그래프, 목업)

## 설정

1. 의존성 설치: `uv sync`
2. OpenAI API 키: 프로젝트 루트에 `.env` 파일을 만들고 아래 변수를 설정합니다.
   - `OPENAI_API_KEY`: OpenAI API 키 (의도분류·대화용 LLM)
   - `OPENAI_MODEL`: 사용할 모델 (기본값 `gpt-5-nano`)

   예시는 `.env.example`을 참고하고, `.env`는 git에 포함되지 않습니다.

## 실행

- **챗봇 앱 (Gradio):** 브라우저에서 여행 에이전트와 대화할 수 있습니다.
  ```bash
  uv run python -m travel_agent.app
  ```
  실행 후 터미널에 나오는 주소(예: http://127.0.0.1:7860)로 접속하세요.
- **CLI (한 번 실행):** `uv run python -m travel_agent`

## 구조

- `src/travel_agent/app.py` — Gradio 챗봇 UI
- `src/travel_agent/service.py` — 에이전트 실행 로직
- `src/travel_agent/state.py` — 공유 상태·슬롯 스키마
- `src/travel_agent/slots.py` — 슬롯 후보·동적 결정
- `src/travel_agent/supervisor/` — 슈퍼바이저 그래프
- `src/travel_agent/agents/{weather,hotel,flight,restaurant}/` — 서브 에이전트
