# 에이전트별 라우터 세 개

1강에서 Jev를 붙인 세 에이전트(OpenClaw · Codex · Claude Code)마다, 그 에이전트가 가장 자주 갈리는 곳에 Jev 라우터를 하나씩 붙였습니다.
셋 다 모델은 확률만 주고, 무엇을 할지는 코드(정책)가 정합니다. Jev 호출이 실패하면 아무것도 하지 않고 원래대로 돕니다(fail-open).

| 에이전트 | 폴더 | 붙는 자리 | Jev에게 묻는 것 | 결과 | 쿡북 | 9/23 실측 |
|---|---|---|---|---|---|---|
| OpenClaw | `openclaw/` | 플러그인 훅 `before_agent_reply` · `before_model_resolve` | 이 메시지는 대화·작업·되묻기·스팸 중 무엇인가 | 스팸은 무시, 애매하면 되묻기(모델 호출 없음), 대화는 가벼운 모델 | Confidence-gated routing · Guardrails | 40건 행동 일치 39/40, 8건은 모델 호출 없이 끝. 실제 OpenClaw(격리 프로필)에서 세 경로 확인 |
| Codex | `codex/` | Codex 앞단 로컬 서비스 → `codex exec` | 무엇을(목록·원문·분석·되묻기·지원 밖) · 어느 프로젝트 | 조회는 코드가 바로, 분석만 Codex로(읽기 전용) | Function calling · Confidence-gated routing | 실제 Jev 10/10(후보 설명 고치기 전 7/10), Codex 인계 35.5초 |
| Claude Code | `claude-code/` | `UserPromptSubmit` 훅(Codex `.codex/hooks.json`도 같은 형식) | 내 스킬 중 어느 것 · 스킬이 필요한 턴인가 · 정말 그 일을 하나 | 그 턴에 `<skill_relevance>` 한 줄 | Skill suggestion | 데모 26건 잘못된 제안 11.1% · 불필요 0%. Claude Code·Codex 모두 훅이 고른 스킬 이름이 답에 나옴 |

- 2강 본 실습의 **메시지 라우터**(`../code`, `../실습`)는 에이전트 앞 메신저 봇용입니다. OpenClaw 라우터는 같은 판정 정의를 OpenClaw 안에서 씁니다.
- 실측 원본: `../evidence/routers/`
- 프롬프트로 설치·시험하기: `../프롬프트.md`의 「에이전트별 라우터」(프롬프트 8~10)
- 9/23 프롬프트 시험(Claude Code): ⑧ 47초 · ⑨ 7/7, 31초 · ⑩ 설치부터 스팸 확인까지 80초(격리 프로필) → `../evidence/prompts/`
- 3강 로컬 서버로 바꾸기: 셋 다 `TYPESAFE_BASE_URL=http://127.0.0.1:8000`만 붙이면 키 없이 돕니다(OpenClaw 플러그인은 설정 `baseUrl`)

## 고를 때

- 메시지가 여러 채널로 들어오고 에이전트가 답한다 → **OpenClaw 라우터**: 모델을 부르기 전에 걸러서 호출 수를 줄인다
- 작업을 코딩 에이전트에 넘기는 입구가 있다 → **Codex 라우터**: 코드로 끝나는 일은 에이전트를 깨우지 않는다
- 스킬이 많아 에이전트가 엉뚱한 스킬을 부르거나 설명이 잘린다 → **Claude Code 라우터**(Codex에도 같은 훅)
