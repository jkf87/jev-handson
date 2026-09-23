# 3강 실습 — jev-ultrafast 실행, API vs 로컬 비교, 활용 사례 예제

결과 원본은 `../evidence/`(2026-09-23 실측). 에이전트에게 프롬프트로 시킬 때는 `../프롬프트.md`(①~⑥)를 이 폴더에서 차례로 붙여 넣습니다.
키는 2강 파일을 그대로 씁니다: `cp ../../02_라우터/실습/.env .env`

## 실습 ① jev-ultrafast로 항공권 찾기 (30분)

```bash
git clone https://github.com/browser-use/jev-ultrafast && cd jev-ultrafast && uv sync
cp .env.example .env   # 아래처럼 채우기
```
```ini
TYPESAFE_API_KEY=...
TEXT_MODEL_BASE_URL=http://127.0.0.1:11434/v1   # 로컬 Ollama (OpenRouter 키 없이)
TEXT_MODEL=qwen3.5:4b                           # ollama pull qwen3.5:4b
TEXT_MODEL_API_KEY=ollama
TEXT_MODEL_REASONING_EFFORT=none                # 없으면 Qwen이 생각 모드로 한 칸에 1분 넘게 씀
TEXT_MODEL_TEMPERATURE=0                        # 없으면 가끔 빈 값을 냄
```
```bash
# 평소 쓰는 Chrome과 분리된 임시 Chrome (빈 프로필)
bash <이 폴더>/ultrafast/start_chrome.sh            # 구글 항공권
bash <이 폴더>/ultrafast/start_chrome.sh --mobile   # 네이버 항공권 (모바일 화면)

# BU_NAME을 꼭 따로 준다. 기본 데몬(default)은 평소 쓰는 Chrome에 붙어 있을 수 있고, 그러면 BU_CDP_URL이 무시된다
BU_NAME=jevlecture BU_CDP_URL=http://127.0.0.1:9333 uv run --env-file .env \
  python <이 폴더>/ultrafast/run_flights.py --show --origin Seoul --destination Jeju --date 2026-10-20 --out runs/google
BU_NAME=jevlecture BU_CDP_URL=http://127.0.0.1:9333 uv run --env-file .env \
  python <이 폴더>/ultrafast/run_naver.py --show --mobile --viewport 430x932 --date 2026-10-20 --out runs/naver
```
- 두 스크립트 모두 시작 전에 연결 대상을 확인하고(`ensure_isolated_browser`), 임시 Chrome이 아니면 멈춘다.
- 원본 저장소 코드는 고치지 않는다. 필요한 보정은 실행 스크립트에서만 한다:
  - 글자 도우미에 `reasoning_effort`·`temperature` 전달, 한글을 `\uXXXX`로 바꾸지 않고 보내기
  - 네이버: 입력 뒤 0.8초 대기(자동완성이 0.6초 뒤에 뜸), 날짜 버튼 이름 보강(`2026년 10월 20일`), 화면 크기 지정
  - smart if: DONE 확률이 0.6 미만이면 끝내지 않고 WAIT (`--done-min-p`)
  - 가려진 요소 빼기: 새 프로필로 열면 전체 화면 이벤트 팝업이 폼을 덮는다. Jev는 요소 표만 보니 뒤의 '도착지'를 계속 고르고 클릭 직전 검사가 매번 취소(판단 120회·실행 0회) → 지금 누를 수 없는 요소는 표에서 뺀다. 그러자 첫 판단이 '닫기'(9/23 오후 프롬프트 시험에서 에이전트가 찾아 고침, 끄려면 `--keep-covered`)

실측
| 사이트 | 결과 | 기록 |
|---|---|---|
| 구글 항공권 (데스크톱) | 17.7초 · 동작 10번 · Jev 판단 18번 · 검증 6/6 | `../evidence/ultrafast/google-flights/` |
| 네이버 항공권 (모바일) | 8.5초 · 동작 6번 · Jev 판단 11번 · 검증 5/5 | `../evidence/ultrafast/naver-mobile-timing/` |
| 네이버 항공권 (데스크톱) | 9회 모두 실패(시도 13회 중 데스크톱 9회) — 움직이는 배너·자동완성 지연·이름 없는 날짜 버튼·안쪽 스크롤 달력 | `../evidence/ultrafast/naver_attempts_summary.json` |

## 실습 ② API vs 로컬 — 2강 40건을 그대로 (30분)

로컬 서버(decider, Jev와 같은 `/v1/systemone` 형식):
```bash
cd local
uv venv .venv-decider --python 3.12
uv pip install --python .venv-decider/bin/python "decider-ai[serve,metal]==1.1.2"
DECIDER_MODEL=Mapika/decider-2b .venv-decider/bin/uvicorn decider.serve:app --host 127.0.0.1 --port 8000
```
2강 라우터를 주소만 바꿔 실행 (키 불필요):
```bash
cd ../../02_라우터/code
TYPESAFE_BASE_URL=http://127.0.0.1:8000 ROUTER_TAG=decider-mac \
  ROUTER_RESULTS_DIR=../../03_유사프로젝트/evidence/api-vs-local node router.mjs --all
```
GPU 서버(A4000 등)에서는 `a4000/run_decider.py`(decider-2b, CUDA)와 `a4000/run_openjev.py`(상주 OpenJev 서비스, 질문 3개를 따로 호출)를 쓴다. 입력은 `data/routing_bodies.jsonl`(2강 요청 본문 40개 그대로).

모두 모아 같은 정책으로 채점:
```bash
node evaluate.mjs      # → ../evidence/api-vs-local/summary.md
```
| 엔진 | 위치 | 행동 일치 | 지연 p50 | 1,000건 |
|---|---|---:|---:|---:|
| Jev API | 클라우드 | 92.5% | 0.25초 | $0.035 |
| decider-2b | A4000 | 72.5% | 0.21초 | $0 |
| decider-2b | Mac (MPS) | 72.5% | 1.9초 | $0 |
| OpenJev Qwen3.5-4B (질문 3번 따로) | A4000 | 67.5% | 0.57초 | $0 |
| Qwen3.5-4B JSON 생성 (Ollama) | Mac | 92.5% | 4.2초 | $0 |

주의: Mac 서버 첫 호출은 워밍업으로 15초 제한을 넘길 수 있다(라우터는 이때 자동 실행하지 않고 review로 보냄).

## 활용 사례 예제 (`usecases/`) — 프롬프트 ⑤
컴퓨터 유즈(요소 표에서 누를 것) · 게임(틱택토 수) · 로봇(센서 글 → 다음 행동)을 Jev가 고르고 코드가 실행·확인·멈춤을 정하는 예제 세 개. Node 20, 외부 패키지 없음.
```bash
node usecases/pick_element.mjs      # 3/3
node usecases/game_move.mjs         # 3/3 · --play 로 규칙 봇과 한 판(무승부)
node usecases/robot_action.mjs      # 3/4 (배터리 4%에 앞으로 가기를 고름 → 코드 규칙으로 고칠 곳)
node --test usecases/usecases.test.mjs
```
자세한 설명과 9/23 실측: `usecases/README.md`. 키가 없으면 `--replay usecases/results/<기록>.json`.

## 활용 사례 자료 (`../evidence/usecases/`)
- `computer-use/` — jev-ultrafast(1kpapers 클릭), typesafe-computer-use, mobile-jev 단일 판단 기록
- `games/` — CMO(판단 14번·비행, Codex 완주 화면), decider 게임 벤치·Pong·Breakout 영상, jevlike Doom·체스 영상, jev-doom-agent API 기록
- `robot-sim/` — jev-drone 8초 영상·결과, OpenJev 0.8B NLI 로봇 컵 질문
게임 수치 중 decider·jevlike는 TypeSafe Jev가 아니라 로컬 복제 모델 결과다.
