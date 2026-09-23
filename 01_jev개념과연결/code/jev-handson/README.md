# 1강 실습 — OpenRouter로 Jev 바로 써 보기 (녹화 실습 그대로)

2026-09-23 녹화한 1강 실습 폴더입니다. Codex(데스크톱 앱)에 프롬프트 네 개를 차례로 넣어 만들었어요. 프롬프트 전문: `../../프롬프트.md` ①~④

| 파일 | 무엇 | 만든 프롬프트 |
|---|---|---|
| `example.js` | OpenRouter 문서의 예시 그대로: 질문 세 개(noul · choice · score)를 한 요청에 | ① |
| `three-examples.js` | noul · choice · score를 하나씩 따로 호출 | ② |
| `benchmark-site/` | **RouteLab**: 한국어 악플 100개를 일반 LLM(`agy -p`)과 Jev로 분류해 속도·품질 비교하는 로컬 사이트 | ③ → ④ |

## 준비

TypeSafe 가입이 막혀 있을 때(2026-09-22부터 한동안) OpenRouter에서 같은 모델을 `~typesafe/jev-latest`로 쓸 수 있어요.

1. https://openrouter.ai 가입(GitHub·Google 로그인) → Keys → Create Key (녹화에서는 한도 $50)
2. 이 폴더에 `env.txt`를 만들고 키 한 줄만 붙여 넣기. **키를 채팅에 붙여 넣지 말고 파일 경로만 알려 주세요** (`.gitignore`에 `env.txt`가 들어 있어요)
3. Node.js 20 이상. 없으면 에이전트가 설치해요

```bash
npm install
npm start                 # example.js
npm run examples          # three-examples.js
cd benchmark-site && npm install && npm run sample && npm start   # http://127.0.0.1:4173
```

TypeSafe 계정이 있으면 https://console.typesafe.ai 에서 키를 받아 같은 요청을 보낼 수 있어요(Playground에서 noul · choice · score를 눌러 보며 시험 가능, 가입하면 $5 무료).

## 녹화 결과 (2026-09-23)

- **① example.js**: 긴급 확률 0.95 · 부서 billing(billing 0.88 · technical 0.12 · sales 0) · 불만 점수 1.05 → "Escalation condition matched: urgent billing issue."
  - score 1.05 = 0단계 × P(Calm) + 1단계 × P(Frustrated) + 2단계 × P(Very angry). 확률이 아니라 **단계의 기대값**이에요
- **② three-examples.js**: noul 0.95(긴급) · choice billing 1.0(중복 결제 환불 요청) · score 2(Very angry)
- **③ 데이터 보고 고르기**: `nayohan/korean-hate-speech`의 `hate` 열(none · offensive · hate)이 세 후보 중 하나를 고르는 일이라 **choice**가 맞다고 판단. `bias`(gender · others · none)도 choice로 같이 물을 수 있음
- **④ RouteLab** (100개 · 배치 10 · 동시 1, `benchmark-site/data/baseline-summary.json`)

| 방법 | 총 시간 | 처리량 | 정확도 | macro-F1 | 경로(허용 · 검토 · 차단) |
|---|---:|---:|---:|---:|---|
| 일반 LLM: `agy -p` (Gemini 3.8 Flash Low) | 110.52초 | 0.90건/초 | 62% | 0.619 | 40 · 41 · 19 |
| **Jev** (`~typesafe/jev-latest`, choice) | **3.15초** | **31.78건/초** | 61% | 0.613 | 26 · 57 · 17 |

같은 조건에서 **Jev가 약 35배 빨랐고 정확도는 1%p 차이**였어요. 경로는 none → 허용(allow), offensive → 검토(review), hate → 차단(block).
사이트에서 배치 크기를 바꿔 다시 돌리면 값이 조금씩 달라져요(녹화 중 Jev 단독 실행: 5.85초 · 59.0% · macro-F1 0.597).

## 알아 둘 것

- 지시문(instructions · criteria)은 영어로, 댓글은 한국어 그대로 넣었어요. 9/23 따로 잰 비교(2강 메시지 40건): 영어·한국어 지시문 모두 37/40으로 같았고, 한국어 지시문은 입력 토큰이 16% 더 들었어요
- RouteLab은 Jev에 댓글 10개를 한 요청으로 보내요(댓글마다 choice 질문 하나, 질문 10개를 한 번에). 일반 LLM도 10개씩 묶어 JSON으로 받아요
- `agy -p`는 로컬에 깔린 Google Antigravity CLI의 헤드리스 호출이에요. 없으면 에이전트에게 Gemini·OpenAI API로 바꿔 달라고 하면 돼요
- 데이터: [nayohan/korean-hate-speech](https://huggingface.co/datasets/nayohan/korean-hate-speech)(원본 BEEP!, **CC BY-SA 4.0**) train에서 고정 시드로 hate 34 · offensive 33 · none 33 → `benchmark-site/data/sample-100.json`. **실제 악플이 들어 있어요**
- 녹화는 Windows(PowerShell)에서 했어요. macOS·Linux도 명령은 같아요
