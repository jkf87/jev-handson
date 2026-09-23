# 1강 · Jev 개념과 에이전트 연결

- 에이전트에게 시킬 때: [`프롬프트.md`](프롬프트.md) ①~⑤ (첫 호출 → 스킬 설치 → 훅 → Codex → MCP)
- 직접 칠 때: [`code/README.md`](code/README.md)
- 키: `code/.env.example` → `code/.env`

| 폴더 | 내용 |
|---|---|
| `code/01_첫호출/` | curl · 파이썬 표준 라이브러리 · `jev.py`(jev-judgment 스킬 스크립트)로 첫 호출. noul · choice · score 질문을 한 요청에 |
| `code/02_스킬설치/` | 공식 `typesafe-ai` + 커뮤니티 `jev-judgment` 스킬 설치 스크립트, 연결 확인 프롬프트 |
| `code/03_연결/claude-code/` | PreToolUse 훅 `jev_guard.py`(위험 명령 앞에서 Jev에 묻기) · 훅만 시험하는 `test_guard.py` · CLAUDE.md · MCP 설정 |
| `code/03_연결/codex/` | 같은 훅의 Codex 판(`.codex/hooks.json`) · AGENTS.md 규칙 · `config.toml` 예시 |
| `code/03_연결/openclaw/` | OpenClaw 연결 방법 |
| `code/jev-mcp/` | Jev MCP 서버(도구 `jev_decide` · `jev_ask`) |
| `code/demo-project/` | 훅 실습용 작은 프로젝트 |

9/23 실측 요약: 첫 호출 0.57초 · `model` 빠지면 HTTP 422 · 파이썬 기본 User-Agent는 HTTP 403(헤더 넣어 둠) · Codex 훅은 ask가 아니라 deny여야 막힘.
