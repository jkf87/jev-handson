# 2강 실습 — 메시지와 작업을 나누는 라우터, LLM 호출 비용 비교

Node 20 이상, 외부 패키지 없음. 결과 원본은 `results/`(2026-09-23 실측).

**프롬프트로 따라 하기**: `../프롬프트.md`(슬라이드 「프롬프트 ①~⑥」). 에이전트를 `../실습/`(40건 데이터와 `jev_형식.md`만 든 폴더)에서 켜고 라우터를 직접 만들게 한 뒤,
이 폴더의 코드와 비교해요. 예제 답안은 두 벌: `mini/`(파일 하나 버전: router·eval·server) · 이 폴더(완성본: 형식 검사·재생·서비스·비교).
9/23 Claude Code로 프롬프트를 그대로 돌린 기록과 에이전트가 만든 코드: `../evidence/prompts/` (에이전트 라우터 32/40 → 위험 먼저 37/40)

## 구조
```
메시지 ──► Jev 1회 호출 (질문 3개를 같은 state에)
             route  : chat | task | unclear | spam        (choice)
             target : codex | claude_code | scheduler | gpu_worker | none   (choice)
             confirm: 사람 확인이 필요한 작업인가           (noul)
        ──► 정책 코드(lib/policy.mjs)가 행동을 정한다
             reply(대화로 답함) · dispatch(작업 넘김) · confirm(실행 전 확인) · clarify(되묻기) · block(차단) · review(사람 검토)
```
모델은 확률만 준다. 임계값·순서·실패 처리는 코드가 정한다.

## 실습 2A — 라우터 만들기 (30분)
```bash
cp ../../01_jev개념과연결/code/.env.example .env   # TYPESAFE_API_KEY 입력
node --test                                        # 키 없이 정책 테스트 9개
node router.mjs "내일 오전 9시에 팀 회의 알림 걸어 줘"
node router.mjs --all                              # data/messages.jsonl 40건 + 정답 비교
node server.mjs                                    # POST /route {"message": "..."}
```
실측(jev-1.13.0): **행동 일치 37/40 (92.5%)**, 지연 p50 247ms · p95 559ms, 40건 입력 토큰 33,151개 ≈ **$0.0014**

틀린 3건과 정책 바꿔 보기 (API 재호출 없이 `--replay`):
```bash
F=$(ls results/router-jev-*.json | head -1)
node router.mjs --all --replay $F                                   # 37/40
node router.mjs --all --replay $F --policy '{"riskFirst":true}'     # 38/40 — 위험하면 담당자보다 먼저 확인
node router.mjs --all --replay $F --policy '{"minRouteP":0.9,"minTargetP":0.9}'   # 28/40 — 너무 깐깐하면 되묻기만 늘어난다
```
- m24 "운영 DB users 테이블 전부 지우고…": confirm 0.96인데 담당자(none 0.54)가 애매해 '되묻기' → `riskFirst`로 해결
- m26 "force push 해서 어제 커밋 날려 줘": route가 chat 0.53로 흔들림 → 되묻기 (안전한 쪽으로 틀림)
- m20 "매주 월요일 커밋 요약 보내 줘": scheduler/claude_code 사이에서 애매 → 정답 라벨 자체도 토론거리

## 실습 2B — LLM 호출 비용 비교 (30분)
같은 40건·같은 행동 규칙으로 '라우터 두뇌'만 바꾼다.
```bash
node compare.mjs --engines jev,claude-cli:haiku,claude-cli:sonnet,ollama:qwen3.5:4b
node compare.mjs --report          # results/compare-summary.md
node compare.mjs --engines jev,claude-cli:haiku --limit 10   # 40건에서 고르게 10건만(맛보기, 약 2분)
```
키(`TYPESAFE_API_KEY`)는 **실행 폴더**의 `.env`나 환경변수에서 읽어요. 키가 없으면 Jev 엔진은 시작 전에 멈춥니다(9/23 프롬프트 시험에서 에이전트가 키 없는 폴더로 옮겨 가 40건이 전부 실패한 뒤 추가).
| 두뇌 | 행동 일치 | route 일치 | 지연 p50 | 평균 입력/출력 토큰 | 1,000건 비용 |
|---|---:|---:|---:|---:|---:|
| Jev (jev-1.13.0) | 92.5% | 97.5% | 0.25초 | 829 / 무료 | **$0.035** |
| Claude Haiku 4.5 | 85.0% | 90.0% | 6.8초 | 957 / 363 | $2.77 |
| Claude Sonnet 5 | 95.0% | 97.5% | 6.0초 | 1,211 / 24 | $5.08 |
| Qwen3.5-4B 로컬(Ollama, JSON 생성) | 92.5% | 100% | 4.2초 | 392 / 19 | $0 (장비·전기 제외) |

읽는 법
- Claude는 로그인된 Claude Code CLI(`claude -p`)로 불렀다. 사용자 설정·도구·MCP를 모두 끄고 시스템 프롬프트만 줬지만 CLI가 붙이는 문맥이 있어 순수 API보다 토큰이 조금 많다. 비용은 CLI가 보고한 정가(list) 기준이다.
- 지연에는 CLI 프로세스 시작 시간이 들어 있다. API 순수 처리 시간은 기록 파일의 `apiMs`.
- Haiku는 40건 모두 답을 코드펜스(```json)로 감쌌다. 파서가 처리했지만 형식은 늘 흔들린다.
- Haiku의 출력 363토큰은 '생각' 토큰이 섞인 값이다. 생각을 끈 순수 API라면 더 싸진다.
- 설정을 그대로 둔 채 `claude -p`로 한 번 분류하면 문맥 1.9만 토큰, **$0.043, 19초**였다. 에이전트에게 작은 판단을 맡길 때 드는 실제 비용이다.
- 가격: `prices.json` (2026-09-23 공식 가격표, 출처 포함)

## 실습 2C — 파이프라인 전체 비용 (15분)
```bash
node cost_calc.mjs                                   # 40건 구성 + 기본 가정
N=1000000 AGENT_TASK_USD=0.2 node cost_calc.mjs      # 내 숫자로
```
라우터가 없으면 인사·스팸까지 에이전트 세션이 받는다. 절감의 대부분(약 52%)은 **보내지 않은 호출**에서 나온다.
라우터 두뇌 비용은 규모가 커질 때 갈린다: 100만 건 기준 Jev $35 · Haiku $2,775 · Sonnet $5,079.
작업 1건 처리 비용(`AGENT_TASK_USD`)은 가정값이다. 내 에이전트 사용 기록으로 바꿔 넣는다.

## 더 가 보기 — 에이전트별 라우터 (`../routers/`)
같은 판단을 에이전트 안쪽에 붙인 완성본 세 개예요. 프롬프트 ⑧~⑩으로 에이전트가 돌리고 붙여 줘요. 한눈에 보기: `../routers/README.md`
- `claude-code/` — 이번 턴에 부를 스킬 고르기(Skill suggestion 쿡북). **각자 컴퓨터에 깔린 스킬**을 에이전트별 폴더(Claude Code·Codex·OpenClaw·`~/.agents`)에서 찾아 쓰고, 240개가 넘으면 조로 나눠 묻는다. `UserPromptSubmit` 훅이라 Codex(`.codex/hooks.json`)에도 그대로 붙는다. 데모 26건: 잘못된 제안 11.1% · 불필요 0%(쿡북 기본값), 1,498개 로스터도 4/4
- `codex/` — Codex를 깨우기 전에 action·target을 한 번에 판단해 조회는 코드가, 분석만 `codex exec`(읽기 전용)가. 실제 Jev 10/10(후보 설명 고치기 전 7/10)
- `openclaw/` — OpenClaw 플러그인. 스팸은 무시, 애매하면 되묻기(모델 호출 없음), 대화는 가벼운 모델. 40건 행동 일치 39/40, 8건은 모델 호출 없이 끝

그리고 `../extra/lesson02-model-router/` — 작업마다 "충분한 모델 중 가장 싼 것" 고르기(Score 45개를 요청 1번에), Claude로 실제 실행·독립 검사

## 파일
| 경로 | 내용 |
|---|---|
| `mini/router.mjs` · `mini/eval.mjs` · `mini/server.mjs` | 프롬프트 ①~④의 예제 답안(파일 하나씩). 질문 문구·정책이 완성본과 같고, 40건 재채점 결과가 완성본과 한 건도 안 다름(120/120) |
| `lib/questions.mjs` | 메시지 → Jev 요청 본문 (질문 3개, no-match 후보 포함) |
| `lib/policy.mjs` | 확률 → 행동 (임계값, riskFirst, 형식 검사) |
| `lib/jev.mjs` | Jev 클라이언트 (TYPESAFE_BASE_URL만 바꾸면 로컬 호환 서버로) |
| `lib/llm.mjs` | 비교용 LLM 라우터 (claude-cli · ollama · openai 호환 · anthropic) |
| `router.mjs` · `server.mjs` | CLI · HTTP 서비스 |
| `compare.mjs` · `cost_calc.mjs` | 두뇌별 비교 · 파이프라인 비용 |
| `data/messages.jsonl` | 한국어 메시지 40건 + 정답 (chat 12 · task 19 · unclear 6 · spam 3) |
| `results/` | 실측 원본 (재생·재채점용) |
