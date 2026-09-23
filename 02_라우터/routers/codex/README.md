# Codex 라우터 — 이 요청이 Codex까지 가야 하나

Codex(코딩 에이전트)를 깨우기 전에 Jev가 먼저 **무엇을 하려는지(action)**와 **어느 프로젝트인지(target)**를 한 번에 판단합니다.
파일 목록·README 원문처럼 코드로 끝나는 일은 Codex 없이 바로 답하고, 읽고 분석·작성해야 하는 일만 `codex exec`(읽기 전용)로 넘깁니다.

```text
요청 → 로컬 서비스 → Jev(action + target, Choice 2개를 한 요청에) → 정책 → TOOL / CODEX / ASK / STOP
```

| 경로 | 언제 | 하는 일 |
|---|---|---|
| TOOL | 파일 목록 · README 원문 조회 | 코드가 바로 답함(Codex 안 부름) |
| CODEX | 읽고 설명·분석·초안 작성 | `codex exec -s read-only -C <프로젝트>`, 요청은 stdin으로 |
| ASK | 대상·작업이 불분명하거나 판단 서비스가 실패 | 되묻기(reason으로 원인 구분) |
| STOP | 등록 안 된 대상·지원 밖 | 거절 |

- 쿡북: [Function calling](https://docs.typesafe.ai/cookbooks/function_calling)(닫힌 함수·인자 고르기) · [Confidence-gated routing](https://docs.typesafe.ai/patterns/confidence-routing)(답은 무엇을, confidence는 할지 말지)
- 정책은 고른 답의 `confidence`가 0.8(`ROUTE_CONFIDENCE`) 미만이면 ASK입니다. 교육용 시작값이에요.
- 프로젝트 경로는 서버의 허용 목록(`config/projects.json`)에서만 고르고, Jev에는 별칭과 설명만 보냅니다.

## 준비

```sh
cp .env.example .env      # 편집기로 열어 키를 넣고 JEV_MODE=live (채팅에 붙여 넣지 않기)
npm test                  # 키 없이 8개
```

| `.env` | 뜻 |
|---|---|
| `JEV_MODE=mock` / `live` | 고정 예제 응답 / 실제 Jev API |
| `CODEX_MODE=dry-run` / `live` | 실행 계획만 / 실제 `codex exec`(읽기 전용) |
| `CODEX_MODEL` | 비우면 Codex 기본 모델 |
| `TYPESAFE_BASE_URL` | 3강 로컬 호환 서버를 쓸 때만 |

## 실행

```sh
npm start                              # 127.0.0.1:8427 (다른 터미널에서 아래)
node cli.mjs --all                     # config/cases.json 6건
node cli.mjs "앱 코드에 테스트를 어떻게 붙이면 좋을지 설명해줘"
```

## 9/23 실측

- **실제 Jev(`JEV_MODE=live`, `CODEX_MODE=dry-run`): 10/10** — 예제 6건 + 새 문장 4건, 판단 0.2~0.4초.
- 처음엔 **7/10**이었습니다. "문서 프로젝트"를 가리킨 3건이 action은 맞았는데 target이 흔들려(docs 0.53~0.86, none 0.14~0.46) ASK로 빠졌어요.
  프로젝트 설명에 부르는 이름("문서 프로젝트(docs): …")을 넣자 10/10. **후보 설명 한 줄이 target을 가릅니다.**
  기록: `../../evidence/routers/codex_router_live_dryrun_설명고치기전.json` → `codex_router_live_dryrun.json`
- **실제 Codex 인계(`CODEX_MODE=live`)**: "앱 프로젝트의 코드를 읽고 오류 원인과 수정안을 설명해줘" → CODEX → `codex exec` 읽기 전용 35.5초,
  빈 배열에서 `NaN`이 나는 원인과 수정안을 설명, 파일은 바꾸지 않음. 기록: `../../evidence/routers/codex_router_live_codex_exec.json`
- 파일 목록·README 조회 요청은 Codex를 부르지 않고 코드가 바로 답합니다(`codexExecuted: false`).

## 내 프로젝트로 바꾸기

`config/projects.json`에 별칭·설명·경로를 넣습니다(상대 경로는 `config/` 기준). **설명에는 내가 그 프로젝트를 부르는 이름을 넣으세요.**
처음에는 실습용 복사본을 등록하고, `config/cases.json`에 내 문장과 기대 경로를 추가해 회귀 시험합니다.

## 에이전트에게 시키기

`CODEX_PROMPTS.md`에 Codex(또는 Claude Code)에 순서대로 붙여 넣을 프롬프트가 있습니다: 이해 → 실제 Jev 연결 → 후보 설명 고치기 → 내 프로젝트 추가 → Codex 인계 → 잘못된 라우팅 고치기.

## 파일

| 파일 | 역할 |
|---|---|
| `questions.mjs` | action·target 질문(Choice 2개) |
| `judge.mjs` | 실제 Jev 호출 / 모의 응답 |
| `policy.mjs` | 형식·confidence·대상 검사 → 네 경로 |
| `handlers.mjs` | TOOL 조회와 `codex exec` 인계(쉘 없이 인자·stdin) |
| `service.mjs` · `cli.mjs` | 로컬 HTTP 입구 · 요청 보내기 |
| `config/projects.json` · `config/cases.json` | 허용 프로젝트 · 예제 요청과 기대 경로 |
| `workspaces/` | 연습용 프로젝트 두 개(docs · app) |

원본은 같은 날 다른 세션에서 만든 `lesson02-router-lab`입니다. 이번에 Astra(모델 이름) 대신 Codex로 이름을 바꾸고, 모델을 비우면 Codex 기본 모델을 쓰게 하고, 로컬 호환 서버 주소를 받게 했습니다.
