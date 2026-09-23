# Claude Code 라우터 — 이번 턴에 어느 스킬을 불러야 하나 (Codex에도 그대로)

에이전트가 이번 턴에 **어떤 스킬을 불러야 하는지, 아니면 아무것도 부르지 말아야 하는지**를 Jev가 고르게 합니다.
[TypeSafe Skill suggestion 쿡북](https://docs.typesafe.ai/cookbooks/skill_suggestion)의 2요청 구조를 Node로 옮기고,
후보를 **각자 컴퓨터에 깔린 스킬**로 바꿨습니다. 스킬이 몇 개든, 어느 에이전트에 깔려 있든 돌게 만들었어요.

붙이는 자리는 `UserPromptSubmit` 훅입니다. 프롬프트가 들어오면 Jev가 스킬을 고르고, 답 대신 `<skill_relevance>` 한 줄을 그 턴에 덧붙여요.
**Codex도 같은 형식의 훅(`.codex/hooks.json`)을 지원해서 코드를 바꾸지 않고 붙습니다.** 스킬이 많아 Codex가 스킬 설명을 통째로 빼 버리는 문제("skills context budget")를 이 훅이 메워 줘요.

Node.js 20 이상, 외부 패키지 없음. 키는 환경변수 `TYPESAFE_API_KEY` → `--key-file` → 실행 폴더 `.env` → 이 폴더 `.env` 순서로 찾습니다.

## 빨리 해 보기

```sh
node --test suggest.test.mjs                 # 키 없이 18개 시험
node roster.mjs                              # 내 컴퓨터 스킬을 어디서 몇 개 찾았는지
node suggest.mjs "이 PDF에서 표만 뽑아서 엑셀로 줘"     # 내 스킬 중 무엇을 고르나
node evaluate.mjs --demo                     # 데모 스킬 26개 · 요청 26건으로 오류율 (누구나 같은 조건)
```

## 내 스킬을 어디서 찾나 (`skills.mjs`)

| 에이전트 | 찾는 곳 | 바꾸는 환경변수 |
|---|---|---|
| `claude` | `~/.claude/skills` · 프로젝트 `.claude/skills` · 설치된 플러그인(`plugins/installed_plugins.json`)의 `skills/` · `plugins/synced` | `CLAUDE_CONFIG_DIR` |
| `codex` | `~/.codex/skills` · `~/.codex/skills/.system` · 프로젝트 `.agents/skills` | `CODEX_HOME` |
| `openclaw` | `~/.openclaw/skills` · `~/.openclaw/workspace*/skills` · 프로젝트 `skills/` | `OPENCLAW_STATE_DIR` |
| `shared` | `~/.agents/skills` (skills CLI가 전역 설치 원본을 두는 곳) | |
| 폴더 직접 | `--dir <폴더>` (여러 번) · 훅은 `SKILL_ROUTER_DIRS` | |

- `--agent claude,codex`처럼 골라 쓰고, 안 적으면 전부(`all`)입니다. **훅은 Claude Code가 실제로 불러올 수 있는 `claude`만** 씁니다.
- `<폴더>/SKILL.md` 하나가 스킬 하나. SKILL.md가 없는 폴더는 건너뜁니다.
- 앞머리(YAML)는 관대하게 읽습니다: `>`·`|` 블록, 따옴표(콜론·이스케이프·줄 끝 주석), 여러 줄 평문, 중첩 매핑 건너뛰기, BOM·CRLF.
  설명(description)이 없으면 본문 첫 문단으로 채우고 표시해 둡니다.
- **합치기**: 같은 파일(심링크)·같은 내용(복사본)은 후보 하나로. 이름만 같고 내용이 다르면 `codex:pdf`처럼 에이전트 이름을 붙여 구분합니다.
- **캐시**: SKILL.md 경로·크기·수정 시각의 지문이 같으면 다시 읽지 않고, 스킬을 깔거나 지우면 다음 실행 때 저절로 다시 만듭니다.
  로스터·응답 캐시·훅 기록은 `~/.cache/jev-skill-router/`에 둡니다(`SKILL_ROUTER_CACHE_DIR`로 변경). **강의 폴더에는 내 스킬 목록이 남지 않아요.**

## 라우팅 구조 (`suggest.mjs`)

```text
사용자 요청
   │
   ▼  요청 1 — 전체 훑기
 Choice: 스킬 중 어느 것?                ← 한 줄 설명(160자)으로 랭킹
 Noul ×3: 스킬이 필요한 턴인가?          ← 사용자 시스템에 행동? / 문서화된 절차? / 말로 충분?(반전)
   │   스킬이 240개를 넘으면 200개 안팎의 조로 나눠 Choice 여러 개로 묻는다(Jev Choice는 선택지 2~255개)
   │   → 조마다 상위 3개를 모아 결선 Choice 한 번 더(조끼리는 확률을 직접 비교할 수 없어서)
   ├─ 게이트 평균 < 0.30 → 제안 없음
   ▼  요청 2 — 상위 3개 자세히
 Choice: 셋 중 어느 것?                  ← 전체 설명 + SKILL.md 본문 앞 700자(코드·태그·URL은 뺀 설명문)
 Noul ×3: 이 스킬이 정말 그 일을 하는가?  ← 후보마다 독립 판정
   │
   ├─ fits 최대 < 0.30 → 제안 없음
   ▼
 <skill_relevance> 한 줄을 시스템 프롬프트 뒤에 덧붙임
```

- 스킬이 하나뿐이면 "해당 없음" 선택지를 넣고, 하나도 없으면 호출 없이 "제안 없음"으로 끝냅니다.
- 본문 발췌에서 코드 블록·인라인 코드·HTML 태그·URL을 뺍니다. 판단에 필요한 건 "무엇을 하는 스킬인가"이고,
  **코드가 섞인 본문은 API 앞단 방화벽이 공격 패턴으로 보고 HTTP 403으로 막습니다**(9/23 실측: 어떤 pptx 스킬 본문이 든 요청만 403, 설명만 보내면 200).
  그래도 막히면 재검증을 설명만으로 한 번 더 묻고, 끝내 실패하면 제안 없이 끝냅니다(훅이 대화를 멈추지 않게).
- 문턱값은 쿡북 기본값(0.30 / 0.30)입니다. `evaluate.mjs --replay --gate … --fits …`로 API 없이 다시 계산해 내 데이터에 맞춥니다.

## 데모 실측 (2026-09-23, jev-1.13.0) — `demo/`, `evidence/demo-eval.json`

`demo/skills`는 이 강의용으로 새로 쓴 공개 스킬 26개입니다(일부러 비슷한 스킬 쌍, 문체·워크플로 스킬, 가장자리 경우를 넣었어요:
따옴표+주석 설명, 접은 설명(`>-`), 설명 없는 스킬, CRLF+BOM 파일, 한글 이름, 내용이 같은 복사본, SKILL.md 없는 폴더).
`demo/requests.json`은 스킬이 필요한 요청 18건 + 필요 없는 요청 8건입니다. 요청 1건당 입력 약 2,500토큰, 호출 중앙값 0.27초.

| 문턱값 (gate / fits) | 잘못된 제안 (18건) | 불필요한 제안 (8건) |
|---|---|---|
| **0.30 / 0.30 (쿡북 기본값)** | **11.1%** (2건) | **0%** |
| 0.30 / 0.40 | 11.1% | 0% |
| 0.20 / 0.30 ~ 0.60 | 0% | 0% |

같은 조건을 한 번 더 돌리면 값이 조금씩 흔들립니다(마스토돈 요청의 fits가 0.34 → 0.29, 앞 회차에선 불필요한 제안 12.5%). **문턱값을 고른 바로 그 26건으로 잰 값이라 새 요청에서도 같다는 증거는 아닙니다.**

**1. 게이트는 문체·문서 스킬을 놓친다.** "세미나 안내문을 카톡 단톡방 공지체로 써 줘"는 1위가 정답(`kakao-notice-style` 1.00), fits 0.96인데 게이트 평균이 0.26이라 막혔습니다. "공문 하나 한글 파일로"도 게이트 0.24로 막혔어요. 게이트 질문 셋은 "파일·계정에 행동하나, 절차를 따르나"를 묻는데, 글을 특정 형식으로 쓰는 요청은 말로 충분한 일로 보입니다. 게이트를 0.2로 낮추면 둘 다 살아납니다.

**2. 분리는 fits가 해낸다.** 스킬이 필요한 요청의 fits 최대는 0.78 이상, 필요 없는 요청은 0.36 이하였습니다. 게이트를 넘은 불필요 요청 셋("README 오타" 게이트 0.64, "노션에 페이지" 0.83, "마스토돈에 올려" 0.84)은 fits 0.17·0.17·0.29에서 걸러졌어요. 0.36은 게이트에서 이미 막힌 "점심 뭐 먹지"입니다.

**3. 같은 스킬이 두 번 있으면 확률이 쪼개진다.** 데모에는 `shorts-cutter`의 복사본이 들어 있습니다. 합치기를 끄면(`--no-dedupe`) "긴 인터뷰 영상을 쇼츠로" 요청에서 0.60 / 0.29로 나뉘고, 합치면 0.91입니다.

```sh
node suggest.mjs --demo "이 긴 인터뷰 영상에서 재밌는 구간 찾아서 쇼츠로 잘라 주고 자막 넣어 줘"
node suggest.mjs --demo --no-dedupe "이 긴 인터뷰 영상에서 재밌는 구간 찾아서 쇼츠로 잘라 주고 자막 넣어 줘"
```

**4. 비슷한 두 스킬은 2차가 가른다.** "강의 녹화본에서 쇼츠 5개, 채널 스타일 C타입" 요청에서 fits는 `channel-shorts` 0.78, `shorts-cutter` 0.75로 비슷했습니다. 본문(A·B·C타입 설명)을 읽는 2차 Choice가 `channel-shorts`를 골랐어요.

## 큰 로스터에서도 되나 (`stress.mjs`)

| 로스터 | 요청 흐름 | 결과 | 요청당 입력 |
|---|---|---|---|
| 598개 (데모 + 가짜 운영 스킬) | Choice 3개 → 결선 → 재검증 | 8/8 정답이 끝까지 | 약 2.6만 토큰 ≈ $0.0011 |
| 1,498개 | 요청 1이 두 번(조 8개, 동시) → 결선 → 재검증 | 4/4 | 약 6.7만 토큰 ≈ $0.0028, 1.5~2초 |
| 강사 PC 실제 스킬: 4개 에이전트 455개(SKILL.md 575개 중 122개 합침) / Claude Code만 93개 | 455개는 Choice 3개 → 결선 → 재검증, 93개는 요청 2번 | 455개에서 pptx·한국어 원고 검문 요청을 해당 스킬로, "점심 뭐 먹지"는 제안 없음 / 93개에서 hwpx·TTS 요청을 해당 스킬로 | — |

```sh
node stress.mjs --n 600 --k 8
```

## 내 스킬로 평가하기

1. `node roster.mjs --agent claude --list`로 후보 이름을 봅니다(화면 녹화 때는 `--list` 빼기).
2. 스킬이 필요한 요청 10개쯤(정답은 스킬 이름, 별칭도 됨)과 필요 없는 요청 5개쯤을 `my_requests.json`에 적습니다.
   ```json
   [
    {"id": "pdf", "text": "이 PDF에서 표만 뽑아 줘", "gold": ["pdf"]},
    {"id": "lunch", "text": "오늘 점심 뭐 먹을까", "gold": []}
   ]
   ```
3. `node evaluate.mjs --agent claude` → `node evaluate.mjs --replay --gate 0.2 --fits 0.4`로 문턱값을 맞춥니다.
   로스터에 없는 정답은 경고하고 건너뜁니다. 결과는 `~/.cache/jev-skill-router/eval-mine.json`.

`my_requests.json`은 `.gitignore`에 들어 있습니다(내 스킬 이름이 들어가니까요).

## Claude Code에 붙이기 (`hook.mjs`)

`UserPromptSubmit` 훅입니다. 8자 미만 프롬프트나 `/`로 시작하는 명령은 건너뛰고, 실패하면 조용히 통과합니다(fail-open).
`~/.claude/settings.json`의 `hooks`에 **기존 항목과 합쳐** 넣습니다(경로는 내 폴더로).

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {"hooks": [{"type": "command", "timeout": 10,
        "command": "SKILL_ROUTER_GATE=0.2 SKILL_ROUTER_FITS=0.4 node /내/경로/02_라우터/routers/claude-code/hook.mjs"}]}
    ]
  }
}
```

- 로스터는 `SKILL_ROUTER_AGENTS`(기본 `claude`), 폴더 추가는 `SKILL_ROUTER_DIRS`(`:`로 구분). 스킬을 깔면 다음 프롬프트부터 저절로 반영됩니다.
- 판정 기록은 `~/.cache/jev-skill-router/hook.log`(프롬프트 앞 120자가 남습니다).
- 9/23 실측(데모 로스터): Claude Code에서 "PDF 표를 엑셀로" 요청에 훅이 `pdf-toolkit`을 넣었고, 모델이 그 이름을 그대로 말함. 기록: `../../evidence/routers/claude_code_router_hook.txt`

## Codex에 붙이기

프로젝트의 `.codex/hooks.json`에 같은 모양으로 넣고, 로스터는 Codex 스킬로 바꿉니다.

```json
{ "hooks": { "UserPromptSubmit": [ { "hooks": [ { "type": "command", "timeout": 20,
    "command": "SKILL_ROUTER_AGENTS=codex node /내/경로/02_라우터/routers/claude-code/hook.mjs" } ] } ] } }
```

- Codex 훅은 신뢰 등록이 필요합니다(한 번 시험은 `codex exec --dangerously-bypass-hook-trust …`).
- 9/23 실측(Codex 0.154, 데모 로스터): "PDF 표" → `pdf-toolkit`, "영수증 사진에서 금액·날짜" → `영수증-정리`(2번 모두). Codex 답에 그 이름이 그대로 나옴.
- 함정: `hooks.json`에 이벤트 여러 개(UserPromptSubmit·SessionStart·PreToolUse)를 한꺼번에 넣었을 때는 하나도 돌지 않았고, 하나씩 넣으면 돌았어요. 붙인 뒤 꼭 한 번 확인하세요(`~/.cache/jev-skill-router/hook.log`에 줄이 생기는지).
- OpenClaw에는 이 훅 자리가 없어서 `../openclaw` 플러그인을 씁니다(메시지를 모델보다 먼저 가르는 라우터).

## 파일

| 파일 | 역할 |
|---|---|
| `skills.mjs` | 로스터 추상화: 에이전트별 출처(`SOURCES`), SKILL.md 읽기, 합치기, 지문 캐시 |
| `roster.mjs` | 어디서 몇 개 찾았는지 보기 (`--agent` `--dir` `--demo` `--list` `--no-dedupe` `--refresh`) |
| `suggest.mjs` | 요청 1(조 나누기·결선)·요청 2·정책(`decide`). `node suggest.mjs "요청"` |
| `evaluate.mjs` | 오류율 측정 (`--demo` / `--requests`), `--replay`로 문턱값 재계산 |
| `hook.mjs` | Claude Code `UserPromptSubmit` 훅 |
| `jev.mjs` | System One 클라이언트: 키 찾기, 응답 캐시, 429·5xx 재시도 |
| `stress.mjs` | 큰 로스터 시험(가짜 스킬을 섞어 N개) |
| `demo/skills` · `demo/requests.json` | 강의 데모 스킬 26개 · 라벨 붙은 요청 26건 |
| `evidence/demo-eval.json` | 위 데모 실측 원본 |

## 쿡북과 다른 점

- 에이전트를 실제로 돌려 로드 여부를 세지 않았습니다. 측정은 **라우터 단독**의 제안 정확도입니다.
- 1차 설명 길이를 60자 대신 160자로 잡았습니다. 한국어 설명은 60자에 담기는 정보가 너무 적습니다.
- 요청이 한국어라 Choice 지시문에 한 줄을 더했습니다. Jev 문서는 영어가 주 학습 언어라고 밝힙니다.
- 스킬이 많으면 조로 나눠 결선을 한 번 더 합니다(쿡북 로스터 182개는 한 번에 들어감).
- 평가 때는 게이트 아래 요청도 2차를 돌려(`alwaysRerank`) 저장합니다. 그래야 게이트 문턱을 낮춘 경우를 API 없이 재계산할 수 있습니다.
