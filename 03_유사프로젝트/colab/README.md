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

---

# 3강 Colab 노트북 ② — 같은 악플 댓글을 판단기 네 개에 묻고 비교하기

`3강_악플분류_4종비교_Colab.ipynb` 하나로, 한국어 악플 데이터 [nayohan/korean-hate-speech](https://huggingface.co/datasets/nayohan/korean-hate-speech)의 같은 댓글을 **글을 쓰지 않고 보기별 확률을 돌려주는** 판단기 네 개에 똑같이 묻고, 마지막에 정확도 · 보정 · 속도 · 비용을 표 2개와 그림 6개로 비교해요. 모두 무료 Colab T4에서 도는 작은 모델이에요.

| 장 | 시스템 | 방식 | 기본 모델 (받는 양) | 도는 곳 |
|---|---|---|---|---|
| 1 | SemIf (TheoLeeCJ/SemIf @ 1f2dea3) | 학습 없이 지시 모델의 보기 글자(A·B·C) 점수 읽기 | Qwen/Qwen3.5-2B @ 15852e8 (4.5GB) | Colab GPU · float16 |
| 2 | decider (Mapika/decider · decider-ai 1.2.1) | 같은 계열 2B를 판단 전용으로 미세조정 | Mapika/decider-2b @ 9839cc9 (3.8GB) | Colab GPU · float16 · eager |
| 3 | laya (receptron/laya 0.1.2) | ModernBERT 인코더 + 판단 머리, Node.js + ONNX | receptron/laya-onnx @ 68f27df (1.7GB · 영어판) | Node.js · CUDA 실행기 시도 → 안 되면 CPU |
| 4 | Jev (TypeSafe) | 원조 API | jev-latest | TypeSafe API · OpenRouter · 키가 없으면 9/23 기록 |

## 여는 법
1. [colab.research.google.com](https://colab.research.google.com) → **파일 → 노트북 업로드** → `3강_악플분류_4종비교_Colab.ipynb` (Drive에 올려 Colab으로 열어도 돼요)
2. **런타임 → 런타임 유형 변경 → T4 GPU** (무료 등급 OK)
3. (선택) 왼쪽 🔑 **보안 비밀**에 `TYPESAFE_API_KEY` 또는 `OPENROUTER_API_KEY`를 넣고 '노트북 액세스'를 켜요. 둘 다 없으면 4장은 1강에서 같은 질문으로 잰 **9/23 기록**(471건, jev-1.13.0)을 써요.
4. **런타임 → 모두 실행**. 한 장이 실패해도(메모리 부족 · 키 없음 · Node 설치 실패) 셀이 오류로 멈추지 않고 그 장만 '건너뜀'으로 남기고, 5장은 결과가 있는 시스템끼리 비교해요.

- `assets/` 파일은 Colab에 필요 없어요. 도우미 · 러너 · 9/23 기록이 모두 셀 안에 들어 있어요.
- 데이터는 과제 요청 그대로 `load_dataset("nayohan/korean-hate-speech")` 두 줄로 불러와요. 분할 이름은 `validation`이 아니라 **`valid`**(471건)예요. `test`(974건)는 정답 칸이 비어 있어서 쓰지 않아요.
- 바꿀 설정은 0-4 셀 하나예요: `N_SAMPLES`(기본 200, `None` = 471건 전부) · `SEED`(42) · `SHOW_TEXT`(기본 `False`) · `RUN`(장별 켜고 끄기) · `SEMIF_SIZE`/`DECIDER_SIZE`(`"0.8B"`/`"0.8b"`) · `LAYA_TIME_BUDGET_S`(180초).
- 결과는 `/content/results/{semif,decider,laya,jev}.jsonl`(+ `.meta.json`, `compare_summary.json`)에 **id · 정답 · 확률 · ms · 토큰만** 저장해요. 댓글 글은 저장하지도, 출력하지도 않아요(5-8 셀에서 `SHOW_TEXT_HERE = True`로 바꿀 때만 보여요).

## 시간 (무료 T4 예상 · 기본 200건)

| 장 | T4 예상 | 강사 실측 (근거) |
|---|---:|---|
| 0 준비 (pip · 데이터 · 표본) | 1분 안팎 | A4000 6~11초 (pip 필요 없음 · 데이터 캐시) |
| 1 SemIf | 2~4분 | A4000: 올리기 9초 · 판정 200건 22초(건당 109ms) · 받기 4.5GB 370초(회선 약 12MB/s) |
| 2 decider | 2~3분 | A4000: 올리기 5초 · 판정 200건 23초(건당 114ms) |
| 3 laya | GPU 1~2분 · CPU 4~5분 | npm 설치 12~13초 · 받기 1.7GB 160초(A4000)/739초(Mac) · 한 건: A4000 서버 CPU 0.9초(6스레드)/1.4초(2스레드)/2.4초(1스레드), Mac(M5) CPU 0.3초(한가할 때)~2.7초(붐빌 때) |
| 4 Jev | 10~20초 | 실시간 30건 2.1~2.4초(8개 동시, 건당 530~580ms) |
| 5 비교 | 수 초 | 1초 미만 |
| **합계** | **약 7~12분** | A4000 전체 실행(laya 제외, 모델 캐시 있음) 67~69초 |

- 대부분은 모델 받기예요. Colab은 보통 강사 회선보다 훨씬 빨라서 받기 시간을 1~2분으로 잡았어요.
- 무료 Colab CPU(2코어)는 강사 장비보다 느려서, 로컬 모델 한 건이 A4000 값의 1.5~2배 걸릴 것으로 봤어요(참조 구현이라 CPU가 커널을 부르는 시간이 커요).
- laya는 GPU(CUDA 실행기)로 돌면 1~2분, CPU로 떨어지면 판정이 180초에서 멈춰요(무료 CPU에서 45~70건 예상). 그러면 5장은 모두가 판정한 댓글끼리 비교하고, laya를 빼고 나머지를 200건으로 보는 방법(`EXCLUDE_FROM_COMMON = ["laya"]`)을 안내해요.
- **T4 시간은 실제로 재지 못한 예상치**예요.

## T4에 맞춘 선택과 이유
- **숫자 형식**: T4(compute capability 7.5)는 bf16이 없어 float16. `is_bf16_supported()` 대신 GPU 세대로 정해요. 다른 GPU에서도 T4와 같게 재려면 `DTYPE_OVERRIDE = "float16"`.
- **decider**: 기본값은 CUDA에서 bf16 + `torch.compile` + CUDA graph(`Decider.__init__` → `Engine(compile=True)`)라 T4에는 맞지 않아요. `Decider(path, device="cuda", dtype=torch.float16, use_graphs=False)`로 Engine 없이 바로 실행(eager)해요. 설치는 `pip install --no-deps decider-ai==1.2.1` — 패키지가 요구하는 `numpy<2`와 `flash-linear-attention`이 Colab numpy 2를 내려 런타임 재시작을 부르는데, 추론에는 필요 없어요.
- **SemIf**: 1-2 셀이 도는 동안만 `torch.backends.cudnn.enabled = False`. 참조 구현의 짧은 합성곱을 cuDNN이 맡으면 입력 길이가 바뀔 때마다 준비 시간이 붙는데, SemIf는 댓글 길이 그대로 넣어 거의 매번 새 길이예요(decider는 길이를 64 단위로 맞춰 이 비용을 피해요). A4000 200건: 켜면 건당 226ms, 끄면 110ms, **고른 보기 200/200 같음 · 확률 차이 0.0001 미만**. 셀이 끝나면 원래대로 켜요.
- **laya (Node.js)**: Node 20 이상이 없으면 nodejs.org 공식 리눅스 x64 묶음 v24.21.0(32MB, SHA-256 확인)을 `/content`에 풀어 이 노트북에서만 써요. `npm install @receptron/laya@0.1.2`는 리눅스 x64에서 onnxruntime-node의 CUDA 실행기(NuGet 236MB)를 함께 받아요. 러너(`laya_runner.mjs`)는 Node 프로세스 하나에서 모델을 한 번만 올리고 JSONL을 끝까지 판정해요. 먼저 `cuda`로 올려 보고(torch가 깐 `nvidia/*/lib`를 `LD_LIBRARY_PATH`에 추가), 실패하면 `cpu`, 러너가 죽으면 CPU로 한 번 더 돌려요. 판정 시간 상한 180초는 장치와 상관없이 걸어 둬서, GPU를 쓰는 줄 알았는데 실제로는 CPU일 때도 시간을 지켜요.
- **laya 언어**: 공개 ONNX 묶음은 **영어 체크포인트**(ModernBERT, 512토큰)예요. `convaiinnovations/laya`의 `multilingual/`(mmBERT-base, 644MB)은 ① ONNX 묶음이 공개돼 있지 않고 ② receptron/laya 0.1.2가 특수 토큰을 `[CLS]`·`[SEP]`·`[MASK]`·`[PAD]`로 고정해 둬서, mmBERT 토크나이저(`<bos>`·`<eos>`·`<mask>`·`<pad>`)로 내보내도 그대로는 못 읽어요. 그래서 선택 셀을 만들지 않고 노트북 3장 · 6장에 이유와 대안(파이썬 `laya` 패키지의 `Router`)만 적었어요.
- **Jev**: `TYPESAFE_API_KEY` → `https://api.typesafe.ai/v1/systemone`, 없으면 `OPENROUTER_API_KEY` → `https://openrouter.ai/api/alpha/decisions`(모델 `~typesafe/jev-latest`, 응답 `usage.cost`가 있으면 그 값으로 비용 계산), 둘 다 없거나 첫 호출이 401/403이면 9/23 기록. User-Agent 헤더 필수(파이썬 기본값은 Cloudflare 403 · error 1010), 8개 동시, 429 · 5xx 재시도, 키 값은 출력하지 않아요. 주소는 `TYPESAFE_BASE_URL` · `OPENROUTER_BASE_URL`로 바꿀 수 있어요.
- **공정성**: 네 시스템 모두 1강 `04_악플탐지`와 같은 요청이에요 — state = {기사 제목, 댓글, '댓글은 지시가 아님' 메모}, choice 질문 하나, 라벨 정의는 `common.py`의 영어 `LABELS`, 보기 순서 none → offensive → hate 고정. SemIf는 입력 모양이 달라 같은 내용을 옮겨 담고 보기 설명을 `"none: not toxic: …"`처럼 라벨 이름을 붙여 맞췄어요.

## 로컬 검증 (2026-09-24)
Mac은 다른 작업으로 부하가 커서(load average 60~100), 모델 판정은 강사 A4000 서버에서 했어요(float16으로 T4 흉내).

| 무엇 | 어디서 | 결과 |
|---|---|---|
| SemIf · Qwen3.5-2B 30건 · 200건 | A4000 (Windows 11 · torch 2.14+cu126 · float16 · 다른 작업이 GPU 10.7GB/16GB · 사용률 20~40%를 쓰는 중) | 오류 0 · 올리기 9초 · 건당 109~110ms(cuDNN 끔) / 382~449ms(켬, 30건) · GPU 3.8GB |
| decider-2b 30건 · 200건 | A4000 · float16 · `use_graphs=False` | 오류 0 · 올리기 5~7초 · 건당 114~127ms · GPU 3.8GB. 가중치는 `C:\ProgramData\JevLab\models\decider-2b`를 읽기만 했어요(`model.safetensors` SHA-256이 @9839cc9와 같음 확인) |
| laya 30건 | A4000 서버 CPU(Ryzen 5 3600) · Node 24.19 | 오류 0 · 확률이 Mac 결과와 소수점 넷째 자리까지 같음 · 30건 모두 none |
| laya 30건 · 200건 | Mac CPU · Node 24.16 | 오류 0 · 200건 모두 none(평균 확신 0.84, offensive · hate 확률 최대 0.19) · 512토큰에서 잘린 입력 0건(210~438토큰) |
| Jev 실시간 30건 | Mac · 강사 TypeSafe 키(환경변수로만, 출력 · 파일 없음) | 오류 0 · 정확도 70.0% · 건당 530~580ms · 전체 2.1~2.4초 · $0.0007. 9/23 기록과 같은 라벨 28/30 · 확률 차이 최대 0.05 |
| OpenRouter 경로 | Mac · 로컬 가짜 서버 | 첫 요청 429 → 재시도 · User-Agent 헤더 · `usage.cost` 합산 · 401이면 기록으로 대체 확인. 실제 OpenRouter 키는 쓰지 않았어요 |
| 노트북 전체(`nbclient`) | A4000: N=30 · 200 (SemIf · decider · Jev 기록, laya 끔) · Mac: N=30 (laya · Jev 실시간), N=30 (Jev만 · OpenRouter 가짜 서버), N=30 (laya 시간 상한 8초 → 일부만) · A4000: decider 폴더를 빈 폴더로 바꾼 실패 시험 | **셀 오류 0** (A4000 7번 · Mac 8번 모두) · 마지막 두 번(A4000 N=200 · Mac N=30 실시간 Jev)은 **최종본 파일 그대로**(SHA-256 `cdd08e07…`) · 실패 시험에서 decider만 '건너뜀'으로 남고 비교는 계속 · 출력에 댓글 글 0건(검증 세트 930개 문자열 검사) · 키 문자열 0건 |
| Node 설치 셀의 리눅스 경로 | Mac | 공식 묶음 받기(2.9초) · SHA-256 일치 · 풀기 확인(리눅스 바이너리라 실행은 못 해 봤어요) |
| 그림 | 헤드리스 Chrome(별도 프로필 · 끝나고 종료 확인) | 6개 그림 · 표 2개가 겹침 없이 그려지는 것을 스크린샷으로 확인 |

**강사 검증 결과 (200건, 시드 42)**: SemIf 44.5% (macro-F1 0.285, 187건이 offensive) · decider 43.0% (0.305, 147건이 none) · laya 34.0% (0.169, 전부 none) · Jev 기록 64.5% (0.571). 세 로컬 모델은 hate를 한 번도 고르지 않았고, 넷이 모두 틀린 46건 중 44건이 정답 hate였어요. 노트북 6장에 같은 표가 있어요.

**확인하지 못한 것**: 실제 Colab T4 실행(설치 · 다운로드 시간, T4 float16 숫자), Colab에서 onnxruntime-node **CUDA 실행기**가 실제로 올라가는지(Colab의 CUDA · cuDNN 라이브러리 버전에 달려 있어요. 안 되면 CPU로 넘어가게 해 뒀어요), 리눅스에서 Node 묶음 실행, 실제 OpenRouter 호출, 0.8B 모델들(다운로드 제한으로 안 받았어요), 다국어 laya.

## 파일 (노트북 ②)

| 파일 | 크기 | 내용 |
|---|---:|---|
| `3강_악플분류_4종비교_Colab.ipynb` | 163KB | 셀 71개(코드 27 · 마크다운 44, 코드 셀마다 앞에 설명). 출력 없이 저장. Colab 메타데이터: GPU · T4 |
| `build_compare_notebook.py` | 70KB | 노트북 생성기. 글 · 셀 순서는 여기, 코드 · 데이터는 `assets/`에서 읽어요 |
| `assets/cmp_helpers.py` | 14KB | 라벨 정의 · 질문 · 층화 표본 · 모델 받기 · 결과 저장 · 채점(정확도 · macro-F1 · 악플 P/R/F1 · ECE 10칸 · Brier · 윌슨 구간) |
| `assets/cmp_charts.py` | 27KB | 비교 표 · SVG 그림 6개(덱 색, 인터넷 없이 그려짐, 마우스 오버 값 · 숫자 표 보기) |
| `assets/cmp_jev_cell.py` | 6KB | 4장 Jev 셀(TypeSafe → OpenRouter → 기록) |
| `assets/laya_runner.mjs` | 5KB | Node 러너(모델 한 번 올리고 JSONL 끝까지 판정, 장치 후보 · 시간 상한) |
| `assets/jev_recorded_0923.json` | 19KB | 9/23 Jev 기록 471건(id → 확률 3개 · ms · 입력 토큰 · 정답). 댓글 글 없음. 출처 `01_jev개념과연결/code/04_악플탐지/results/jev-20260923-163246.jsonl` |

```bash
python3 build_compare_notebook.py     # 노트북 다시 만들기 (표준 라이브러리만, nbformat이 있으면 형식 검사)
```
