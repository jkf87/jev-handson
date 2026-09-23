# jev-handson — Jev 특강 실습 코드 (1강~3강)

TypeSafe **Jev**(글을 쓰지 않고 선택지의 확률을 돌려주는 판단 모델)를 에이전트(Claude Code · Codex · OpenClaw)에 붙여 보는 실습 코드입니다.
라이브클래스 「[jev 특강](https://aifrenz.liveklass.com/classes/319648)」의 실습 자료이고, 모든 수치는 2026-09-23에 직접 돌려 본 값입니다.

| 강의 | 폴더 | 들어 있는 것 |
|---|---|---|
| 1강 · Jev 개념 · 이론 · 녹화 실습 | [`01_jev개념과연결/`](01_jev개념과연결/) | **녹화 실습** `jev-handson/`: OpenRouter로 Jev 호출 · noul · choice · score · 악플 댓글 100개로 일반 LLM vs Jev 비교 사이트(RouteLab) · 더 해 보기: TypeSafe 직접 호출 · 471건 LLM 비교 · 스킬 · 훅 · MCP |
| 2강 · 라우터와 LLM 호출 비용 | [`02_라우터/`](02_라우터/) | 빈 시작 폴더 · 메시지 라우터 완성본(40건 채점 · 서비스 · 두뇌 비교 · 비용 계산) · **에이전트별 라우터 3개**(OpenClaw 플러그인 · Codex 앞단 · Claude Code 스킬 라우터 훅) · 모델 라우터 |
| 3강 · Jev를 닮은 프로젝트들 | [`03_유사프로젝트/`](03_유사프로젝트/) | jev-ultrafast 실행 스크립트(구글 · 네이버 항공권) · 로컬 decider 서버 · API vs 로컬 채점 · 활용 사례 예제(컴퓨터 유즈 · 게임 · 로봇) · **Colab 노트북**(openjev 판단 뜯어보기 · [Colab에서 열기](https://colab.research.google.com/github/jkf87/jev-handson/blob/main/03_%EC%9C%A0%EC%82%AC%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8/colab/3%EA%B0%95_Jev%EB%8B%AE%EC%9D%80%EB%AA%A8%EB%8D%B8_Colab.ipynb)) |

## 실습은 프롬프트로

명령을 직접 치지 않고 에이전트에게 프롬프트로 시킵니다. 강의마다 `프롬프트.md`에 순서대로 붙여 넣을 문장과 예제 코드 위치, 9/23 실측이 있어요.

- 1강 [`01_jev개념과연결/프롬프트.md`](01_jev개념과연결/프롬프트.md) ①~④ 녹화 그대로 (+ 더 해 보기 A~C)
- 2강 [`02_라우터/프롬프트.md`](02_라우터/프롬프트.md) ①~⑩ (⑧~⑩ 에이전트별 라우터)
- 3강 [`03_유사프로젝트/프롬프트.md`](03_유사프로젝트/프롬프트.md) ①~⑥

## 준비

- Node.js 20 이상, Python 3.10 이상 (대부분 외부 패키지 없음)
- 에이전트 하나 이상: Claude Code · Codex · OpenClaw
- TypeSafe API 키: https://console.typesafe.ai → Keys. 폴더마다 있는 `.env.example`을 `.env`로 복사해 채웁니다. **`.env`는 커밋하지 마세요**(`.gitignore`에 들어 있음)
- 1강 녹화 실습은 OpenRouter 키를 씁니다: `01_jev개념과연결/code/jev-handson/env.txt`에 한 줄(이것도 `.gitignore`에 있음)
- 3강만: `uv`, Chrome, Ollama(`qwen3.5:4b`), [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast)(실습 중에 받음)

키가 없으면(2026-09-22부터 TypeSafe 신규 가입이 한동안 막혀 있었어요) 저장해 둔 Jev 응답으로 재생하거나, 3강의 로컬 서버로 주소만 바꿔서 해 볼 수 있어요.

```bash
# 저장소 맨 위에서, 키 없이
(cd 01_jev개념과연결/code/jev-handson/benchmark-site && npm install && npm run sample && npm start)   # RouteLab: 녹화 기준값 화면(키 없이)
(cd 01_jev개념과연결/code && python3 04_악플탐지/compare.py --jev 04_악플탐지/results/jev-20260923-163246.jsonl --llm 04_악플탐지/results/llm-claude_haiku-20260923-165842.jsonl)   # 악플 471건: LLM vs Jev
(cd 02_라우터/code && node --test && node mini/eval.mjs --replay results/router-jev-2026-09-22T20-05-42-399Z.json)
(cd 03_유사프로젝트/code && node evaluate.mjs)                     # API vs 로컬 표
(cd 03_유사프로젝트/code && node usecases/robot_action.mjs --replay usecases/results/robot_action-2026-09-23T05-48-14-430Z.json)
# 3강 로컬 서버(03_유사프로젝트/code/local)를 띄웠다면, 주소만 바꿔서
(cd 02_라우터/code && TYPESAFE_BASE_URL=http://127.0.0.1:8000 node router.mjs --all)
```

## 이 저장소에 없는 것

슬라이드와 실측 기록 전체(에이전트 실행 기록 · 화면 · 영상)는 강의 수강생 배포본에만 있어요. 문서 속 `evidence/…` 경로는 그 배포본 기준입니다.
코드가 직접 읽는 기록(3강 `evidence/api-vs-local/`, 네이버 시도 요약)과 재생용 응답(`results/`)은 여기 들어 있어요.

## 알아 둘 것

- 폴더 이름은 수강생 배포본과 같습니다. 문서와 코드 속 상대 경로(`../../02_라우터/code` 등)가 그대로 맞아요.
- 제3자 코드: `01_jev개념과연결/code/01_첫호출/jev.py`는 [jev-judgment](https://github.com/HyunjunJeon/jev-judgment)(MIT)의 스크립트 원본입니다 → [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
- 제3자 데이터: `01_jev개념과연결/code/04_악플탐지/data/` · `01_jev개념과연결/code/jev-handson/benchmark-site/data/sample-100.json`은 [korean-hate-speech](https://huggingface.co/datasets/nayohan/korean-hate-speech)(원본 BEEP!, **CC BY-SA 4.0**)입니다. **실제 악플이 들어 있어요.**
- 강의용 비공식 예제입니다. TypeSafe · Jev, Claude Code, Codex, OpenClaw는 각 회사·프로젝트의 제품이에요.
- 브라우저 실습(3강)은 평소 쓰는 Chrome과 분리된 임시 Chrome(`BU_NAME=jevlecture`, 포트 9333)에서만 하세요. 스크립트가 시작 전에 확인하고, 아니면 멈춥니다.
