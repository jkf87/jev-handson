# 3강 Colab 노트북 — Jev를 닮은 오픈 모델, 판단 한 번 뜯어보기

`3강_Jev닮은모델_Colab.ipynb` 하나로 두 가지를 해요.

1. **가벼운 실측**: Jev를 흉내 낸 오픈소스 **SemIf**(구 openjev, Qwen3.5-4B)를 무료 Colab T4에서 직접 돌려요. 강의 5케이스를 판정하고, 판단 한 번이 계산되는 과정을 7단계 위젯으로 열어 봐요.
2. **무거운 실험은 미리 잰 결과로**: 14B 모델 비교, llama.cpp CUDA 빌드, Mac·A4000 병렬 판단, API vs 로컬 40건은 이미 잰 기록(JSON)만 불러와 그려요.

## Colab에서 여는 법

1. [colab.research.google.com](https://colab.research.google.com) → **파일 → 노트북 업로드** → `3강_Jev닮은모델_Colab.ipynb`
   (Google Drive에 올린 뒤 더블클릭 → Colab으로 열기도 돼요)
2. **런타임 → 런타임 유형 변경 → T4 GPU** (무료 등급 OK)
3. 위에서부터 차례로 실행해요. **영상 3개는 셀 출력으로 이미 들어 있어서** 실행하지 않아도 보여요.

- GPU 없이 그림만 보려면: CPU 런타임에서 실행하면 자동으로 **precomputed(미리 잰 숫자) 모드**가 돼요. 모델 셀은 건너뛰고 강사 Mac에서 잰 숫자로 위젯·차트를 그려요(1분 안).
- `런타임 → 모두 실행`을 하면 영상 셀도 다시 실행돼서 영상이 안내 문구로 바뀌어요(Colab에는 `assets/` 영상 파일이 없어서요). 영상을 먼저 보거나 노트북을 다시 열면 돼요.

## 기본 실행과 시간

| 장 | 내용 | 기본 실행 | T4 예상 | 강사 Mac 실측* |
|---|---|:---:|---:|---:|
| 0 | 도우미·미리 잰 숫자 불러오기 | ✅ | 수 초 | 1초 미만 |
| 1 | 원리 — 영상 ① (27초) | 출력에 포함 | – | – |
| 2 | GPU 확인 · SemIf 설치(커밋 고정) · `hf download`(9개 파일, 9.3GB) | ✅ | 3~7분 | 4초 (이미 캐시에 있음) |
| 3 | 모델 올리기 (T4 float16) | ✅ | 1~2분 | 8초 |
| 4 | 영상 ③ + 7단계 위젯 (6케이스 + 보기 순서 바꾸기 42번) | ✅ | 20~60초 | 51초 |
| 5 | 강의 5케이스 판정 + A4000 비교 차트 | ✅ | 수 초 | 3초 |
| 6 | 영상 ② + 미리 잰 속도 차트 3개(Mac·A4000 병렬 판단 · 14B T4 · A4000 SemIf 따로/공유) + 공유 모드 실측(질문 8개) | ✅ | 10~30초 | 56초 |
| 7 | API vs 로컬 40건 + 보정 맛보기 + RLCR 생성 vs RLCD 읽기 (모두 미리 잰 값) | ✅ | 즉시 | 즉시 |
| 8 | 내 질문 (+ 선택: 내 질문 위젯) | ✅ | 수 초 | 1초 (+8초) |
| 9 | (선택) TypeSafe Jev API와 나란히 | 키가 있을 때만 | 수 초 | 키 없이 건너뜀 |
| 10 | (선택) Jev-Omni: `hf download --dry-run` · 파일 크기 · 검증 기록 · 80GB GPU 전용 빠른 시작 | 목록·기록만 | 수 초 | 6초 |
| | **합계** | | **약 5~10분** | **142초** (다운로드 제외) |

\* 강사 Mac(Apple M5 32GB, MPS, bfloat16)에서 `nbclient`로 노트북 전체를 돌린 셀별 시간이에요. 모델은 이미 캐시에 있었어요. 이후 두 번의 재실행은 609~627초였어요. 그때 Mac의 스왑이 24GB까지 차서 한 번 판정이 5~6초로 느려졌고(고른 보기는 5/5 그대로), MPS 시간은 메모리 상황에 따라 크게 흔들려요. MPS에는 Qwen3.5 선형 어텐션 가속 커널이 없어 한 번 판정이 0.55~0.85초로 느려요(A4000 기록은 0.10~0.13초). **T4 시간은 실제로 재지 못한 예상치**예요.

## 선택 항목과 이유

- **9장 TypeSafe Jev API**: 키가 필요하고(Colab 🔑 보안 비밀 `TYPESAFE_API_KEY`) 호출마다 아주 적은 비용이 들어요. TypeSafe는 2026-09-22부터 신규 가입을 잠시 멈췄어요. 셀은 키 값을 출력하지 않고, 파이썬 기본 User-Agent가 Cloudflare 403(error 1010)에 막히는 문제를 헤더로 피해요. `TYPESAFE_BASE_URL`로 주소를 바꿀 수 있어요(2강 코드와 같은 규칙).
- **10장 Jev-Omni**: 공식 로더가 저장소 전체 약 72GB + Gemma 4 12B 약 24GB를 받고 FP32 본체(약 48GB)를 GPU에 올려서 **80GB GPU**(A100 80GB·H100)가 필요해요. 기본은 받지 않고 `--dry-run`·메타데이터·모델이 스스로 올린 검증 기록만 봐요. 빠른 시작 셀은 GPU 75GB·디스크 110GB 미만이면 실행을 거절하고, `RUN_JEV_OMNI = True`로 바꿔야 돌아요.
- **14B·llama.cpp 재측정**: 예전 노트북(`parallel-decision-rlcd-20260922/colab-large-models/Colab_Local_16GB_Qwen14B.ipynb`) 안내만 남겼어요. 다운로드 약 39GB(14B 원본 + GGUF)와 T4용 llama.cpp CUDA 빌드가 필요해서 기본 경로에서 뺐어요.

## 폴더

| 파일 | 크기 | 내용 |
|---|---:|---|
| `3강_Jev닮은모델_Colab.ipynb` | 4.4MB | 셀 76개(코드 28 · 마크다운 48, 코드 셀마다 바로 앞에 설명). 영상 3개를 base64 `<video>` 출력으로 내장. Colab 메타데이터: GPU · T4 |
| `build_notebook.py` | 55KB | 노트북 생성기. 글·셀 순서는 여기, 코드·데이터·영상은 `assets/`에서 읽어요 |
| `assets/nb_visuals.py` | 36KB | 그림 도우미(영상 다시 보기, 위젯 호출, SVG 차트). 인터넷(CDN) 없이 그려요 |
| `assets/nb_explain.py` | 12KB | SemIf `score()` 그대로 판정하면서 위젯용 중간값(토큰·로짓 렌즈·상위 토큰·보기 순서 바꾸기)을 모으는 함수, 6장 공유 모드 실측 함수 |
| `assets/widget_template.html` | 43KB | 7단계 위젯(HTML/CSS/JS/SVG, 외부 파일 없음) |
| `assets/cases.json` | 6KB | 강의 5케이스 입력 + 강사 A4000 기록 + 8장 예시 질문 |
| `assets/widget_fallback.json` | 108KB | GPU가 없을 때 쓰는 위젯 숫자(강사 Mac, MPS, bfloat16) + 공유 모드 실측 |
| `assets/precomputed.json` | 25KB | 6·7·10장 차트 숫자. 묶음마다 `source`에 원본 경로 |
| `assets/scenes.py` | 19KB | Manim 장면 3개 소스 |
| `assets/clip1_generate_vs_read.mp4` | 1.6MB | 영상 ① 글로 답하기 vs 점수 읽기 (27초) |
| `assets/clip2_shared_prefix.mp4` | 0.7MB | 영상 ② 공통 앞부분은 한 번, 질문은 나란히 (22초) |
| `assets/clip3_logits_to_probs.mp4` | 0.8MB | 영상 ③ 점수 → 확률, 온도 (26초) |
| `assets/measure_local.py` | 5KB | `widget_fallback.json`을 만든 측정 스크립트 |
| `assets/collect_precomputed.py` | 11KB | `precomputed.json`을 원본 기록에서 모으는 스크립트 |

영상은 모두 1280×720 · 30fps · H.264, 흰 배경, 강의 덱 색(#19272D · #466A62 · #AA5238 · #F0F5F2 · #D6DED9), 글꼴 Noto Sans CJK KR이에요.

## 다시 만들기

```bash
# 노트북 (표준 라이브러리만. nbformat이 있으면 형식 검사도 해요)
python3 build_notebook.py

# 영상 (Manim Community 0.21 + Noto Sans CJK KR 글꼴)
cd assets && manim -qm --disable_caching --media_dir /tmp/jev3-media scenes.py GenerateVsRead SharedPrefix LogitsToProbs
ffmpeg -i /tmp/jev3-media/videos/scenes/720p30/GenerateVsRead.mp4 -c copy -movflags +faststart clip1_generate_vs_read.mp4   # ②③도 같은 식

# 위젯 대체 숫자 (SemIf 1f2dea3 설치 + Qwen3.5-4B@851bf6e 캐시가 있는 Apple Silicon Mac)
HF_HUB_OFFLINE=1 HF_DEACTIVATE_ASYNC_LOAD=1 python measure_local.py --dtype bfloat16 --explain --shared --out widget_fallback.json

# 미리 잰 숫자 (원본 기록 폴더가 있는 강사 Mac에서)
python collect_precomputed.py --fp16 dtype_float16.json --omni-dir <Jev-Omni 작은 파일(README.md·verification_unified.json) 폴더>
```

- Mac(MPS)에서 transformers 5.17의 병렬 가중치 로딩은 Metal 커널 캐시와 부딪혀 세그폴트(139)가 나요. `HF_DEACTIVATE_ASYNC_LOAD=1`로 한 줄씩 올리면 돼요(노트북도 MPS일 때 자동으로 켜요). CUDA에서는 필요 없어요.
- Manim `Text`는 작은 글씨에서 자간이 틀어져요("JS ON"). `scenes.py`는 4배로 그린 뒤 줄여요.

## 숫자 출처

| 노트북 위치 | 원본 |
|---|---|
| 5장 A4000 기록, 영상 ①③ 점수 | `~/jev/lecture-code/3강-오픈소스/openjev/results_a4000.jsonl` (bfloat16, 프롬프트 SHA-256 포함) |
| 4·5·6·8장 precomputed 숫자 | `assets/measure_local.py`로 강사 Mac에서 잰 값(2026-09-24) |
| 6-1 병렬 판단 vs JSON, 영상 ② 숫자 | `~/jev특강/output/parallel-decision-rlcd-20260922/` `summary.json` · `timings.csv` · `README.md` · `dense9b-a4000/summary.json` |
| 6-4 A4000 SemIf 따로/공유 vs RLCD | 같은 폴더 `semif-a4000/comparison.csv` |
| 7-2 RLCR 생성 vs RLCD 읽기 | 같은 폴더 `rlcr-vs-rlcd-a4000/summary.json` · `predictions.csv` |
| 6-2 14B Colab T4 | `~/Downloads/20260922-043237-7fa17c (1)/visualization/comparison_all.json` (+ `results.json`) |
| 7장 API vs 로컬 40건 · 보정 점 그림 | `03_유사프로젝트/evidence/api-vs-local/summary.json` · `out_openjev.jsonl` · `out_decider.jsonl` · `router-decider-mac-*.json`, `02_라우터/code/results/router-jev-*.json`, 정답 `03_유사프로젝트/code/data/routing_bodies.jsonl` |
| 10장 Jev-Omni | Hugging Face `akhilaaa3/Jev-Omni` @ c050d51: `README.md`, `unified/verification_unified.json`(주사위·구슬·회의·환불), 파일 크기는 HfApi 메타데이터(가중치 안 받음) |

## 로컬 검증 (2026-09-24, 강사 Mac M5 32GB · torch 2.13 MPS)

- **SemIf 판정 재현**: 커밋 1f2dea3 + Qwen3.5-4B@851bf6e로 강의 5케이스를 돌려 **프롬프트 SHA-256 5/5가 A4000 기록과 같고, 고른 보기 5/5가 같았어요.** 확률 차이는 최대 0.030(`route-vague` a4000 0.407 vs 0.378, bfloat16). float16(MPS)도 5/5 같고 최대 차이 0.019였어요.
- **노트북 실행**(`nbclient`): precomputed 모드 오류 0건(10~12초), MPS 실모드 오류 0건 3번(142초 · 스왑이 찬 상태의 재실행 609~627초, 모델 캐시 있음). 마지막 실모드 실행은 **최종본 파일 그대로**(SHA-256 `3c893a1d…`)를 돌린 거예요. 실모드에서 `hf download` · SemIf 로드 · 위젯 · 5케이스 · 공유 모드(3.3배) · 내 질문까지 모두 돌았어요.
- **위젯**: 헤드리스 Chrome(별도 프로필, 오프라인)에서 외부 요청 0건 · 콘솔 오류 0건. 온도·기준 슬라이더를 마우스로 끌어 값과 그림이 바뀌는 것, 보기 순서 바꾸기, 키보드 ←/→, 420px 좁은 화면(가로 스크롤 없음)을 확인했어요.
- **영상**: 3개 모두 끝까지 디코딩되고, 장면별 프레임을 뽑아 한글 글꼴과 넘침을 눈으로 확인했어요.
- **9장 API 셀**: 로컬 가짜 `/v1/systemone` 서버로 User-Agent 헤더 · 응답 해석 · 401 처리(첫 실패에서 멈춤)를 확인했어요. 진짜 키와 진짜 API는 쓰지 않았어요.
- **SemIf 고정 커밋**: GitHub에서 1f2dea3을 얕게 받아(37MB) 강의 사본과 `src/`가 같은 걸 확인했어요.

**확인하지 못한 것**: 실제 Colab T4 실행(설치·다운로드 시간, float16 CUDA 숫자, `score_shared`의 CUDA batch 경로 — 실패하면 Mac 기록으로 대신 보여 주게 해 뒀어요), Colab에서 '모두 실행' 뒤 영상 셀 모습, 80GB GPU에서 Jev-Omni 실행.
