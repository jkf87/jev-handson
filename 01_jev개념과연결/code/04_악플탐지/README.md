# 악플 탐지 — 같은 댓글을 LLM과 Jev로 거르고 두 출력 비교하기 (1강 프롬프트 ③④)

**주의: 실제 악플(욕설·혐오 표현)이 들어 있는 데이터입니다.**

## 데이터
- [nayohan/korean-hate-speech](https://huggingface.co/datasets/nayohan/korean-hate-speech) 검증 세트 471건 → `data/valid.jsonl`
  - 원본: [kocohub/korean-hate-speech](https://github.com/kocohub/korean-hate-speech) (BEEP!, Moon et al. 2020) · **CC BY-SA 4.0** (이 폴더의 `data/`도 같은 라이선스)
  - 연예 뉴스 기사 제목(`news_title`) + 댓글(`comment`) + 사람이 붙인 정답(`hate`: none · offensive · hate)
  - 정답 분포: none 160 · offensive 189 · hate 122. test 세트는 정답이 공개돼 있지 않아서 쓰지 않아요
- 다시 받기: `python3 get_data.py` (표준 라이브러리만, Hugging Face 데이터셋 서버에서 JSON으로)

## 실행 (키는 `../.env`, 파이썬 표준 라이브러리만)

```bash
cd 01_jev개념과연결/code
python3 04_악플탐지/jev_filter.py --limit 50      # Jev: 댓글마다 choice 질문 하나 (50건 몇 초)
python3 04_악플탐지/llm_filter.py --limit 50      # LLM: 로그인된 claude CLI로 Claude Haiku (50건 1~2분)
python3 04_악플탐지/compare.py                    # 두 출력 비교 → 04_악플탐지/results/compare.md
```
- `--limit`을 빼면 471건 전부(Jev 30초 안팎, Haiku 15분 안팎). 두 필터는 **같은 `--limit`**으로 돌려야 같은 댓글끼리 맞춰 볼 수 있어요
- LLM을 바꾸려면 `--engine claude:sonnet` · `--engine ollama:qwen3.5:4b`(로컬, 무료)
- 3강 로컬 서버로 Jev를 바꾸려면 `TYPESAFE_BASE_URL=http://127.0.0.1:8000`

## 무엇을 비교하나

| | LLM | Jev |
|---|---|---|
| 묻는 법 | 시스템 프롬프트에 세 라벨 정의 + "JSON으로 라벨 하나만" | state(기사 제목 + 댓글) + choice 질문 하나(후보 = 세 라벨 정의) |
| 받는 것 | 라벨 하나 (`{"label": "offensive"}`) | 세 라벨의 확률 (예: `none 0.07 · offensive 0.74 · hate 0.19`) |
| 숨길지 | 라벨이 offensive·hate면 숨김 | 악플 확률(offensive + hate)이 기준 이상이면 숨김. **기준은 코드가 정하고 API 재호출 없이 바꿀 수 있음** |

두 쪽 모두 같은 정의 문장(`common.py`의 `LABELS`)을 씁니다. 지시문은 영어, 댓글은 한국어 그대로예요.

## 9/23 실측 (471건 전부)

둘 다 성공한 462건 기준(Haiku는 471건 중 9건 실패: 시간 초과 7 · 형식 오류 2). 기록: `results/` (`compare.md`가 전체 비교표)

| 방법 | 악플 정밀도 | 악플 재현율 | F1 | 3분류 정확도 | 지연 중앙값 | 1,000건 비용 |
|---|---:|---:|---:|---:|---:|---:|
| Jev (jev-1.13.0, 기준 0.5) | 95.1% | 82.5% | 0.883 | 63.0% | 0.36초 | $0.023 |
| Claude Haiku 4.5 (claude CLI) | 95.7% | 80.5% | 0.875 | 67.3% | 8.1초 | $3.62 (정가) |

- **숨길 댓글을 고르는 실력은 비슷하고, Jev가 23배 빠르고 1,000건 비용이 약 150분의 1**이에요.
- 3분류는 Haiku가 나아요. 둘 다 사람이 hate로 붙인 댓글을 offensive로 보는 일이 많았어요(122건 중 Jev 101 · Haiku 76). 혐오와 공격의 경계는 사람도 헷갈리는 곳이라 숨길지만 보면 크게 상관없어요.
- 두 출력은 89% 같았어요. 갈린 50건: Jev만 숨김 29(진짜 악플 22) · LLM만 숨김 21(진짜 악플 16). 둘 다 놓치는 건 욕 없이 깎아내리는 말("나이가 아쉽다")이에요.
- **Jev는 기준을 바꿔 다시 채점할 수 있어요(API 재호출 없음).** 471건:

| 악플 확률 기준 | 숨김 | 정밀도 | 재현율 | F1 |
|---:|---:|---:|---:|---:|
| 0.3 | 302 | 91.7% | 89.1% | 0.904 |
| 0.5 | 270 | 94.8% | 82.3% | 0.881 |
| 0.7 | 226 | 96.9% | 70.4% | 0.816 |
| 0.9 | 177 | 98.3% | 55.9% | 0.713 |

  운영 예: 0.7 이상 자동 숨김 226건(그중 정상 7건) · 0.3~0.7 사람 검토 76건 · 0.3 미만 그대로 169건(놓친 악플 34건).
- 같은 댓글을 Haiku가 50건 시험(프롬프트 ④) 땐 잡고 471건 땐 놓친 경우가 있었어요. LLM은 돌릴 때마다 답이 바뀌고, Jev 확률은 0.22 → 0.24로 거의 같았어요.
- 키 없이 비교표만 다시 보기: `python3 04_악플탐지/compare.py --jev 04_악플탐지/results/jev-20260923-163246.jsonl --llm 04_악플탐지/results/llm-claude_haiku-20260923-165842.jsonl`

## 파일

| 파일 | 역할 |
|---|---|
| `get_data.py` | 데이터 받기 (Hugging Face 데이터셋 서버 → `data/valid.jsonl`) |
| `common.py` | 라벨 정의(`LABELS`), 데이터 읽기(`--limit`은 파일 전체에서 고르게), 키 찾기, 채점(정밀도·재현율·F1) |
| `jev_filter.py` | Jev로 거르기 → `results/jev-<시각>.jsonl` |
| `llm_filter.py` | LLM으로 거르기(claude CLI · Ollama) → `results/llm-<엔진>-<시각>.jsonl` |
| `compare.py` | 두 출력 맞춰 보기 · 갈린 댓글 · Jev 기준 바꾸기 → `results/compare.md` |
