# 1강 · Jev 개념 · 설치 · 악플 탐지

- 에이전트에게 시킬 때: [`프롬프트.md`](프롬프트.md) ①~④ (첫 호출 → 스킬 설치 → Jev로 악플 거르기 → LLM으로 걸러서 두 출력 비교)
- 직접 칠 때: [`code/README.md`](code/README.md)
- 키: `code/.env.example` → `code/.env`

| 폴더 | 내용 |
|---|---|
| `code/01_첫호출/` | curl · 파이썬 표준 라이브러리 · `jev.py`(jev-judgment 스킬 스크립트)로 첫 호출. noul · choice · score 질문을 한 요청에 |
| `code/02_스킬설치/` | 공식 `typesafe-ai` + 커뮤니티 `jev-judgment` 스킬 설치 스크립트, 연결 확인 프롬프트 |
| `code/04_악플탐지/` | 뉴스 댓글 악플 데이터(korean-hate-speech 471건, CC BY-SA 4.0) · `jev_filter.py`(Jev) · `llm_filter.py`(Claude CLI · Ollama) · `compare.py`(두 출력 비교 · 기준 바꾸기) |
| `code/demo-project/` | 스킬 설치 실습용 작은 프로젝트 |
| `code/03_연결/` · `code/jev-mcp/` | 더 해 보기(강의에서는 안 다룸): Claude Code/Codex 훅 `jev_guard.py` · OpenClaw 연결 · Jev MCP 서버 |

9/23 실측 요약: 첫 호출 0.57초 · 악플 거르기는 Jev F1 0.883 · Claude Haiku 0.875로 비슷, 지연 0.36초 vs 8.1초, 1,000건 $0.023 vs $3.62. Jev는 기준(악플 확률)을 코드로 바꿔 자동 숨김 · 사람 검토 구간을 나눌 수 있음.
