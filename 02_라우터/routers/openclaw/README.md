# OpenClaw 라우터 — 메시지가 모델에 닿기 전에 Jev가 먼저 가른다

2강 메시지 라우터를 OpenClaw 플러그인으로 옮겼습니다. 채널(텔레그램·디스코드·슬랙…)로 들어온 메시지마다 Jev에 **질문 하나**를 묻고, 모델을 부르기 전에 처리합니다.

| Jev 판정 | 플러그인이 하는 일 | 모델 호출 |
|---|---|---|
| spam (0.8 이상) | 답하지 않음 | 없음 |
| unclear | "무엇을 도와드리면 될까요? …"로 되묻기 | 없음 |
| chat | 가벼운 모델(`lightModel`)로 바꿔서 답하게 | 가벼운 모델 |
| task | 원래 모델 그대로 | 원래 모델 |
| 확률 0.6 미만 · Jev 호출 실패 | 아무것도 안 함(원래대로) | 원래 모델 |

- 쿡북: [Confidence-gated routing](https://docs.typesafe.ai/patterns/confidence-routing)(답은 무엇을, 확률은 할지 말지) · [Guardrails for LLMs](https://docs.typesafe.ai/cookbooks/llm_guardrails)(통과·차단·경로 바꾸기)
- 판정 정의(chat·task·unclear·spam)는 2강 `code/lib/questions.mjs`와 같습니다.

## 구조

```text
메시지 ─► before_agent_reply ─► Jev(route 1문항, 0.3~0.5초)
            │   spam  → {handled: true}                 답하지 않음
            │   unclear → {handled: true, reply: 되묻기}  모델 호출 없이 끝
            ▼
         before_model_resolve ─► 같은 턴의 판정 재사용(runId)
                chat → {providerOverride, modelOverride}  가벼운 모델로
```

한 턴에 Jev는 한 번만 부릅니다. 두 훅이 판정을 2분 동안 공유합니다(`lib/plugin.js`).

## 설치 (내 OpenClaw)

```sh
openclaw plugins install --link <이 폴더 절대경로> --force --accept-capabilities
openclaw plugins enable jev-router
openclaw config set plugins.entries.jev-router.hooks.allowConversationAccess true   # 대화 훅 권한
openclaw config set plugins.entries.jev-router.config.lightModel "anthropic/claude-haiku-4-5"   # 내 모델 중 가벼운 것
openclaw config set plugins.entries.jev-router.config.keyFile "<TYPESAFE_API_KEY가 든 .env 절대경로>"
openclaw config set plugins.entries.jev-router.config.logFile "jev-router.log"      # 상태 폴더 기준 → ~/.openclaw/jev-router.log
openclaw gateway restart
openclaw plugins inspect jev-router --runtime --json    # status loaded, typedHooks 두 개
openclaw agent --local --agent main -m "[광고] 코인 무료 에어드랍 지금 클릭하세요" --json   # payloads [] 이면 성공(모델 호출 없음)
```

- 설정은 `openclaw` 명령으로만 바꾸세요. 설정 파일에는 채널 토큰 같은 비밀값이 들어 있고, OpenClaw가 바꿀 때마다 `openclaw.json.bak`을 남깁니다. `--link`는 폴더를 복사하지 않고 연결만 합니다.
- 키는 게이트웨이 환경변수 `TYPESAFE_API_KEY`가 있으면 그걸 쓰고, 없으면 `keyFile`에서 읽습니다. 2강 `실습/.env`를 그대로 가리켜도 돼요. 3강 로컬 서버를 쓰려면 `baseUrl`만 바꿉니다.
- `keyFile`·`logFile`의 상대 경로는 OpenClaw 상태 폴더 기준입니다(`--profile`·`--dev`로 띄우면 그 프로필 폴더). 마지막 줄은 스팸 한 줄로 모델을 부르지 않고 끝나는지 보는 확인이에요. 대화 문장으로 시험하면 실제 모델이 불립니다.
- 판정 기록에는 메시지 본문을 남기지 않습니다(길이·판정·확률·지연만).
- 플러그인은 게이트웨이 프로세스 안에서 돕니다. 코드를 읽어 보고 설치하세요(전부 이 폴더 안, 외부 패키지 없음).

## 시험

```sh
npm test                                        # 키 없이 7개
node try.mjs "[광고] 코인 무료 에어드랍"          # 이 메시지를 어떻게 처리할지 (OpenClaw 없이)
node try.mjs --all                              # 2강 메시지 40건
```

## 9/23 실측

- `node try.mjs --all`: **행동 일치 39/40**, 40건 중 8건(스팸 3 · 되묻기 5)은 모델 호출 없이 끝남, Jev 지연 중앙값 263ms.
  틀린 1건은 "버그가 있는 것 같긴 한데 어디가 문제인지…"(chat 0.50) → 확률이 낮아 원래 모델로 넘김(안전한 쪽)
- OpenClaw 2026.9.4 격리 프로필(`openclaw --dev`)에서 실제 설치·실행: 스팸은 빈 응답, "그거 좀 다시 해 줘"는 되묻기 문장,
  대화는 `provider overridden to anthropic` · `model overridden to claude-haiku-4-5`. 기록: `../../evidence/routers/openclaw_dev_profile.txt`

## 파일

| 파일 | 역할 |
|---|---|
| `index.js` | 플러그인 진입점(`definePluginEntry`) |
| `lib/router.js` | 요청 본문(질문 1개)과 정책(`decide`) |
| `lib/plugin.js` | 훅 두 개 등록, 턴별 판정 공유, 기록 |
| `lib/jev.js` | Jev 호출(키는 환경변수 → keyFile) |
| `try.mjs` | OpenClaw 없이 판단만 시험 |
| `openclaw.plugin.json` | 매니페스트와 설정 항목 |
