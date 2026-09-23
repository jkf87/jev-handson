# 1강 · Jev 개념 · 이론 · 녹화 실습

- 강의 실습(2026-09-23 녹화 그대로): [`code/jev-handson/`](code/jev-handson/) — OpenRouter(`~typesafe/jev-latest`)로 Jev를 부르고, 한국어 악플 댓글 100개를 일반 LLM(`agy -p`)과 Jev로 분류하는 비교 사이트 RouteLab까지. 실행법 · 녹화 결과: [`code/jev-handson/README.md`](code/jev-handson/README.md)
- 에이전트에게 시킬 때: [`프롬프트.md`](프롬프트.md) ①~④(녹화에서 넣은 문장 그대로) + 「더 해 보기」 A~C
- 키: OpenRouter 키 한 줄을 `code/jev-handson/env.txt`에(채팅에 붙여 넣지 말고 경로만 알려 주기). 더 해 보기는 `code/.env.example` → `code/.env`(TypeSafe 키)

| 폴더 | 내용 |
|---|---|
| `code/jev-handson/` | **강의 실습**: `example.js`(질문 세 개를 한 요청에) · `three-examples.js`(noul · choice · score 따로) · `benchmark-site/`(RouteLab, 댓글 100개 샘플 포함) |
| `code/01_첫호출/` | 더 해 보기 A: TypeSafe API를 curl · 파이썬 표준 라이브러리 · `jev.py`(jev-judgment 스킬 스크립트)로 직접 부르기 |
| `code/04_악플탐지/` | 더 해 보기 B: 뉴스 댓글 471건(korean-hate-speech, CC BY-SA 4.0)을 Jev와 LLM(Claude CLI · Ollama)으로 거르고 두 출력 비교 · 기준 바꾸기 |
| `code/02_스킬설치/` · `code/demo-project/` · `code/03_연결/` · `code/jev-mcp/` | 더 해 보기 C: 스킬 설치 · 연결 확인 · Claude Code/Codex 훅 `jev_guard.py` · OpenClaw 연결 · Jev MCP 서버 |

녹화 결과 요약: 예시 호출 긴급 0.95 · billing 0.88 · 불만 score 1.05(확률이 아니라 단계의 기대값) / RouteLab 100개: `agy -p`(Gemini 3.8 Flash Low) 110.52초 · 62% vs Jev 3.15초 · 61%(약 35배 빠름). 더 해 보기 B(471건): Jev F1 0.883 · Claude Haiku 0.875, 지연 0.36초 vs 8.1초, 1,000건 $0.023 vs $3.62.
