# 2강 실습 시작 폴더

여기서 에이전트(Claude Code · Codex)를 켜고 `../프롬프트.md`의 프롬프트를 ①부터 순서대로 붙여 넣습니다.
에이전트가 여기에 router.mjs · eval.mjs · server.mjs를 만들어요. 막히면 예제 답안과 비교하세요: `../code/mini/`(파일 하나 버전), `../code/`(완성본).
⑧~⑩(에이전트별 라우터)도 이 폴더에서 붙여 넣어요. 완성본 `../routers/`(claude-code · codex · openclaw)를 에이전트가 돌리고, 훅·플러그인으로 붙여 줍니다.

```bash
cp .env.example .env      # 편집기로 열어 TYPESAFE_API_KEY=... 입력 (채팅에 키를 붙여 넣지 않기)
claude                    # 또는 codex
```

| 파일 | 내용 |
|---|---|
| `data/messages.jsonl` | 한국어 메시지 40건 + 정답(route·target·confirm) |
| `jev_형식.md` | Jev 요청·응답 형식 (에이전트가 읽고 코드를 씀) |
| `.env.example` | 키 자리 |

키가 없으면: `node ../code/mini/eval.mjs --replay ../code/results/router-jev-2026-09-22T20-05-42-399Z.json`로 저장된 Jev 답을 재생해 채점 실습을 할 수 있어요.
