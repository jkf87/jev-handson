"""3강 Colab 노트북 생성기.

    python3 build_notebook.py            # → 3강_Jev닮은모델_Colab.ipynb

노트북 글(마크다운)과 셀 순서는 이 파일에, 코드·데이터·영상은 assets/에 있어요.
- assets/nb_visuals.py, nb_explain.py, widget_template.html → 도우미 셀에 그대로 넣어요
- assets/cases.json, precomputed.json, widget_fallback.json → '미리 잰 숫자' 셀에 넣어요
- assets/clip*.mp4 → 영상 셀의 '미리 실행된 출력'으로 넣어요(base64 <video>)
표준 라이브러리만 써요. nbformat이 설치돼 있으면 마지막에 형식 검사도 해요.
"""
import base64
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
A = HERE / "assets"
OUT = HERE / "3강_Jev닮은모델_Colab.ipynb"

cells = []


def _src(text):
    text = text.strip("\n") + "\n"
    lines = text.splitlines(True)
    lines[-1] = lines[-1].rstrip("\n")
    return lines


def md(cid, text):
    cells.append({"cell_type": "markdown", "id": cid, "metadata": {}, "source": _src(text)})


def code(cid, text, form=False, outputs=None):
    meta = {"cellView": "form"} if form else {}
    cells.append({"cell_type": "code", "id": cid, "metadata": meta, "execution_count": None,
                  "outputs": outputs or [], "source": _src(text)})


def raw_block(text, what):
    if "'''" in text:
        raise ValueError(f"{what}에 ''' 가 있어 파이썬 문자열로 넣을 수 없어요")
    if text.endswith("\\"):
        raise ValueError(f"{what}이 역슬래시로 끝나요")
    return text


def video_output(name, caption):
    b64 = base64.b64encode((A / name).read_bytes()).decode()
    page = ('<figure style="margin:0;max-width:960px"><video controls playsinline preload="metadata" '
            'style="width:100%;border:1px solid #D6DED9;border-radius:10px" '
            f'src="data:video/mp4;base64,{b64}"></video>'
            '<figcaption style="font-family:\'Noto Sans KR\',\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;'
            f'font-size:12.5px;color:#5E6E68">{html.escape(caption)}</figcaption></figure>')
    return [{"output_type": "display_data", "metadata": {},
             "data": {"text/html": _src(page), "text/plain": ["<IPython.core.display.HTML object>"]}}]


def rows_literal(rows):
    out = ["ROWS = ["]
    for r in rows:
        out.append("    {")
        out.append(f'        "id": {json.dumps(r["id"], ensure_ascii=False)},')
        out.append(f'        "state": {json.dumps(r["state"], ensure_ascii=False)},')
        out.append(f'        "question": {json.dumps(r["question"], ensure_ascii=False)},')
        out.append('        "options": [')
        for o in r["options"]:
            out.append(f'            {{"id": {json.dumps(o["id"], ensure_ascii=False)}, "description": {json.dumps(o["description"], ensure_ascii=False)}}},')
        out.append("        ],")
        out.append("    },")
    out.append("]")
    return "\n".join(out)


def row_literal(name, r):
    lines = [f"{name} = {{",
             f'    "id": {json.dumps(r["id"], ensure_ascii=False)},',
             f'    "state": {json.dumps(r["state"], ensure_ascii=False)},',
             f'    "question": {json.dumps(r["question"], ensure_ascii=False)},',
             '    "options": [']
    for o in r["options"]:
        lines.append(f'        {{"id": {json.dumps(o["id"], ensure_ascii=False)}, "description": {json.dumps(o["description"], ensure_ascii=False)}}},')
    lines += ["    ],", "}"]
    return "\n".join(lines)


def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


# ── 재료 읽기 ──
visuals = (A / "nb_visuals.py").read_text(encoding="utf-8")
explain = (A / "nb_explain.py").read_text(encoding="utf-8")
template = raw_block((A / "widget_template.html").read_text(encoding="utf-8"), "widget_template.html")
cases = json.loads((A / "cases.json").read_text(encoding="utf-8"))
pre = json.loads((A / "precomputed.json").read_text(encoding="utf-8"))
fb_all = json.loads((A / "widget_fallback.json").read_text(encoding="utf-8"))
fallback = {k: fb_all[k] for k in ("_note", "machine", "metadata", "load_seconds", "results", "shared_demo")}
MAC = fb_all["results"]
SD = fb_all["shared_demo"]
vague_perm = {tuple(p["order"]): p["probs"] for p in MAC["route-vague"]["perms"]}
main_at_a = vague_perm[("main", "a4000")]["main"]
main_at_b = vague_perm[("a4000", "main")]["main"]

# ═════════════════════════════ 0. 표지 ═════════════════════════════
md("s00-title", """
# 3강 실습 · Jev를 닮은 오픈 모델, 판단 한 번 뜯어보기

**Jev**(TypeSafe)는 글을 쓰지 않는 AI예요. *상황(state) + 질문 + 보기*를 주면 문장 대신 **보기마다 확률**을 돌려줘요.
3강에서는 이걸 따라 만든 오픈소스들을 봤죠. 이 노트북에서는 그중 **SemIf**(구 openjev · Qwen3.5-4B)를 무료 Colab T4에서 직접 돌리고, 판단 한 번이 어떤 계산으로 나오는지 한 단계씩 열어 봐요.

> Jev 내부 방식은 공개되지 않았어요. 여기서 뜯어보는 건 **Jev를 흉내 낸 오픈 모델(SemIf)** 의 방식이에요.

### 목차와 시간
| 장 | 하는 일 | 기본 실행 | T4 예상 시간 |
|---|---|:---:|---:|
| 0 | 준비: 도우미·미리 잰 숫자 불러오기 | ✅ | 수 초 |
| 1 | 원리 한눈에 — 영상 ① | 영상은 이미 들어 있어요 | – |
| 2 | GPU 확인 · SemIf 설치 · `hf download`로 모델 받기 | ✅ | 3~7분 (약 9.3GB) |
| 3 | 모델 올리기 (T4는 float16) | ✅ | 1~2분 |
| 4 | 한 케이스 뜯어보기 — 영상 ③ + 7단계 위젯 | ✅ | 20~60초 |
| 5 | 강의 5케이스 판정 + 강사 A4000과 비교 | ✅ | 수 초 |
| 6 | 왜 빠른가 — 영상 ② + 미리 잰 속도 + 가벼운 실측 | ✅ | 10~30초 |
| 7 | 정확도와 보정 — API vs 로컬 40건 (미리 잰 값) | ✅ | 즉시 |
| 8 | 내 질문 만들어 보기 | ✅ | 수 초 |
| 9 | (선택) TypeSafe Jev API와 나란히 | 키가 있을 때만 | 수 초 |
| 10 | (선택) Jev-Omni — 80GB GPU 전용 | 파일 목록·검증 기록만 | 수 초 |
| 11 | 정리 | | |

T4 시간은 **예상치**예요(강사 Mac에서 같은 코드를 돌린 시간과 Colab 다운로드 속도로 어림했어요). 대부분은 2장의 모델 다운로드예요.

### 무거운 실험은 미리 잰 결과로 봐요
예전 노트북의 마지막 예제(14B 모델 비교 + llama.cpp를 CUDA로 직접 빌드)는 T4에서 한참 걸렸어요. 이 노트북은 그때 **이미 잰 결과(JSON)** 를 불러와 그림만 그려요. 직접 다시 재고 싶은 분을 위한 안내는 6장 끝에 있어요.

### 시작하기
1. 메뉴 **런타임 → 런타임 유형 변경 → T4 GPU** (무료 등급으로 충분해요)
2. 위에서부터 차례로 실행해요(**런타임 → 모두 실행**도 돼요).
3. GPU가 없으면 자동으로 **'미리 잰 숫자'(precomputed) 모드**가 돼요. 모델은 건너뛰고 그림만 그려서 1분 안에 끝나요.

> 🎬 **영상 3개는 셀 출력으로 미리 넣어 뒀어요.** 실행하지 않아도 보여요. 영상 셀을 다시 실행하면(모두 실행 포함) 공개 저장소 [jkf87/jev-handson](https://github.com/jkf87/jev-handson)에서 영상을 받아 와서 다시 보여 줘요. 인터넷이 안 되면 안내 문구가 나오는데, 노트북을 새로 열면 저장된 영상이 다시 보여요.
""")

# ═════════════════════════════ 0. 준비 ═════════════════════════════
md("s00-prep", """
## 0. 준비: 도우미 불러오기

아래 세 셀(①②③)은 이 노트북이 쓰는 **도구와 숫자**를 메모리에 올려요. GPU도 인터넷도 필요 없고 몇 초면 끝나요. Colab에서는 코드가 접혀 있어요(펼쳐 읽어도 돼요).

- **① 그림 도우미**: 영상 다시 보기, 7단계 위젯, 차트 함수. 차트는 인터넷(CDN) 없이 브라우저에서 바로 그려지는 SVG예요.
- **② 판정 뜯어보기 도우미**: SemIf 원본 함수 `score()`로 판정하면서, 위젯에 보여 줄 중간값(토큰·층별 점수·보기 순서 바꾸기)을 함께 모아요.
- **③ 미리 잰 숫자**: 강사 A4000·Mac, 예전 Colab T4(14B) 실험에서 이미 잰 결과예요. 묶음마다 `source`에 원본 파일 경로가 있어요.

먼저 **① 그림 도우미**예요. 위젯 HTML 원본(`WIDGET_TEMPLATE`)과 차트 함수가 들어 있어요.
""")
code("s00-helpers-visual", "#@title 🔧 ① 그림 도우미 (영상 · 위젯 · 차트)\n" + visuals.rstrip("\n")
     + "\n\n\nWIDGET_TEMPLATE = r'''" + template + "'''\nprint('그림 도우미 준비 완료')", form=True)
md("s00-explain-md", """
**② 판정 뜯어보기 도우미**예요. `explain_case()`는 SemIf `score()`를 그대로 부르고, 위젯에 필요한 토큰·층별 점수·보기 순서 바꾸기 결과를 더 모아요. `run_shared_demo()`는 6장의 공유 모드 실측이에요. 모델은 3장에서 올려요.
""")
code("s00-helpers-explain", "#@title 🔧 ② 판정 뜯어보기 도우미 (SemIf 방식 그대로)\n" + explain.rstrip("\n")
     + "\n\n\nprint('판정 뜯어보기 도우미 준비 완료')", form=True)
data_code = (
    "#@title 📦 ③ 미리 잰 숫자 불러오기 (출처는 각 묶음의 source)\n"
    "import json\n\n"
    "# 강의 5케이스 입력 + 강사 A4000 기록(results_a4000.jsonl) + 8장 예시 질문\n"
    f"CASES = json.loads(r'''{raw_block(compact(cases), 'cases')}''')\n"
    "# 6·7·10장 차트용: 병렬 판단 속도(Mac·A4000), 14B Colab T4, API vs 로컬 40건, Jev-Omni 검증 기록\n"
    f"PRE = json.loads(r'''{raw_block(compact(pre), 'precomputed')}''')\n"
    "# GPU가 없을 때 쓰는 값: 강사 Mac(M5, MPS, bfloat16)에서 assets/measure_local.py로 잰 위젯 데이터\n"
    f"FALLBACK = json.loads(r'''{raw_block(compact(fallback), 'fallback')}''')\n\n"
    "print(f\"강의 케이스 {len(CASES['rows'])}개 + A4000 기록 · 위젯용 Mac 측정 {len(FALLBACK['results'])}케이스 · \"\n"
    "      f\"병렬 판단 속도 {len(PRE['parallel_decision']['rows'])}줄 · 14B T4 {len(PRE['colab14b']['rows'])}가지 · \"\n"
    "      f\"API vs 로컬 {len(PRE['api_vs_local']['table'])}엔진 · Jev-Omni 검증 {len(PRE['jev_omni']['verification_cases'])}건\")\n"
)
md("s00-data-md", """
**③ 미리 잰 숫자**예요. 강의 케이스와 A4000 기록(`CASES`), 차트용 숫자(`PRE`), GPU가 없을 때 쓸 위젯 숫자(`FALLBACK`)를 불러와요. 출력 한 줄에 무엇을 불러왔는지 나와요.
""")
code("s00-data", data_code, form=True)

# ═════════════════════════════ 1. 원리 ═════════════════════════════
md("s01-idea", """
## 1. 원리 한눈에: 글로 답하기 vs 점수 읽기

보통 LLM에게 "어느 세션으로 보낼까?"를 물으면 `{"choice": "main"}` 같은 **글을 토큰 하나씩** 써요. 토큰 하나마다 모델을 한 번씩 통과해야 하고, 코드는 그 글을 다시 읽어서 if 문으로 바꿔요.

SemIf 같은 Jev 닮은 모델은 글을 쓰지 않아요. 보기마다 글자(A, B, …)를 붙여 프롬프트에 넣고, 모델을 **딱 한 번** 통과시킨 뒤 '다음에 올 토큰' 점수 중 **보기 글자 점수만** 읽어요. 그 점수를 softmax로 바꾸면 보기별 확률이 돼요.

아래 영상 ①(27초)은 같은 질문(강의의 `route-vague` 케이스)을 두 방식으로 처리하는 모습이에요. 점수 24.0 · 24.5는 강사 A4000에서 잰 실제 값이에요.
""")
code("s01-clip", '#@title 🎬 영상 ① 글로 답하기 vs 점수 읽기 (27초) — 실행하지 않아도 돼요\n'
     'show_clip("clip1_generate_vs_read.mp4", "영상 ① · Manim으로 그림 · 숫자: route-vague, 강사 A4000 실측")',
     form=True, outputs=video_output("clip1_generate_vs_read.mp4", "영상 ① · Manim으로 그림 · 숫자: route-vague, 강사 A4000 실측"))
md("s01-read", """
**영상 읽는 법**
- **통과 횟수**: 생성 방식은 답 토큰 수만큼(여기선 7번) 모델을 통과하고, 점수 읽기는 1번이에요. 속도 차이는 여기서 나와요(6장).
- **보기 밖 답이 없어요**: 정해 둔 보기 글자 중에서만 고르니 형식이 깨지지 않아요.
- **0.62의 뜻**: 'main이 맞을 확률 62%'가 아니라 **보기끼리 비교한 점수**예요. 보정은 7장에서 봐요.
- JSON 조각(`{"`, `choice`, `":` …)은 Qwen3.5-4B 토크나이저로 실제로 자른 결과예요.
""")

# ═════════════════════════════ 2. GPU · 설치 · 다운로드 ═════════════════════════════
md("s02-gpu", """
## 2. GPU 확인 · 설치 · 모델 받기

### 2-1. GPU 확인과 실행 모드
어떤 장비에서 돌리는지 확인하고, 모델을 올릴 숫자 형식(dtype)을 정해요.
- **T4는 bfloat16을 하드웨어로 못 해서 float16**을 써요. 파이토치가 T4에서도 bf16을 '지원'한다고 답할 때가 있는데, 흉내 내는 방식이라 느려요. 그래서 GPU 세대(compute capability 8 이상인지)로 정해요.
- 강사 A4000은 bfloat16이었어요. 확률이 소수점 아래에서 조금 다를 수 있지만, 고르는 보기는 같아야 해요.
- GPU가 없으면 **precomputed(미리 잰 숫자) 모드**가 돼요. `FORCE_PRECOMPUTED = True`로 바꾸면 GPU가 있어도 이 모드로 돌아요.
""")
code("s02-mode", '''
import os, sys, shutil, subprocess, time

IN_COLAB = "google.colab" in sys.modules
FORCE_PRECOMPUTED = os.environ.get("JEV3_PRECOMPUTED") == "1"   # True로 바꾸면 모델 없이 미리 잰 숫자만 써요

try:
    import torch
    HAS_CUDA = torch.cuda.is_available()
    HAS_MPS = (not HAS_CUDA) and torch.backends.mps.is_available()
except ImportError:
    HAS_CUDA = HAS_MPS = False

if FORCE_PRECOMPUTED or not (HAS_CUDA or HAS_MPS):
    MODE, DTYPE, GPU_NAME = "precomputed", None, None
elif HAS_CUDA:
    MODE = "cuda"
    major, minor = torch.cuda.get_device_capability()
    DTYPE = "bfloat16" if major >= 8 else "float16"      # T4 = 7.5 → float16
    GPU_NAME = torch.cuda.get_device_name()
    total_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f"GPU {GPU_NAME} · 메모리 {total_gb:.1f}GB · compute capability {major}.{minor}")
else:
    MODE, DTYPE, GPU_NAME = "mps", "bfloat16", "Apple GPU (MPS)"   # 강사 Mac 같은 Apple Silicon

print(f"모드: {MODE}" + (f" · dtype {DTYPE}" if DTYPE else " · 모델 없이 미리 잰 숫자로 그려요"))
if MODE == "cuda":
    !nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv
''')
md("s02-mode-read", """
**읽는 법**: `모드: cuda`, `Tesla T4`, 메모리 약 15GB가 보이면 준비 끝이에요. `모드: precomputed`가 보이면 GPU가 없는 런타임이에요 — 그림은 다 볼 수 있고, 모델을 직접 돌리는 셀만 미리 잰 숫자로 대신해요.
""")
md("s02-install", """
### 2-2. SemIf 설치 (커밋 고정)
SemIf는 openjev에서 이름이 바뀐 저장소예요(`TheoLeeCJ/SemIf`). 저장소가 계속 바뀌니 **강의 때 쓴 커밋 `1f2dea3`으로 고정**해서 받아요(그 커밋만 얕게 받아서 몇 초면 돼요).
- `pip install --no-deps -e`: 저장소가 적어 둔 torch 2.10을 새로 깔지 않고, **Colab에 이미 있는 CUDA용 torch를 그대로** 써요.
- 나머지(transformers 5.17 등)는 SemIf가 고정한 버전으로 맞춰요. 30초~1분쯤 걸리고, 다른 패키지와 버전이 안 맞는다는 경고는 무시해도 돼요.
""")
code("s02-install-code", '''
SEMIF_REPO = "https://github.com/TheoLeeCJ/SemIf.git"
SEMIF_COMMIT = "1f2dea3e25379f9dfc98cb83c324f00ab5deda37"   # 2026-09-22, 강의·A4000 실측과 같은 코드

def run(cmd):
    subprocess.run(cmd, check=True)

if MODE == "precomputed":
    print("precomputed 모드라 설치를 건너뛰어요.")
elif IN_COLAB:
    if not os.path.isdir("SemIf/.git"):
        run(["git", "init", "-q", "SemIf"])
        run(["git", "-C", "SemIf", "remote", "add", "origin", SEMIF_REPO])
        run(["git", "-C", "SemIf", "fetch", "-q", "--depth", "1", "origin", SEMIF_COMMIT])
        run(["git", "-C", "SemIf", "checkout", "-q", "--detach", "FETCH_HEAD"])
    head = subprocess.check_output(["git", "-C", "SemIf", "rev-parse", "HEAD"], text=True).strip()
    assert head == SEMIF_COMMIT, f"SemIf 커밋이 달라요: {head}"
    run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "-e", "./SemIf"])
    run([sys.executable, "-m", "pip", "install", "-q", "transformers==5.17.0", "accelerate==1.12.0",
         "huggingface-hub==1.31.0", "tokenizers==0.23.2", "safetensors==0.8.0"])
    sys.path.insert(0, os.path.abspath("SemIf/src"))   # 런타임 재시작 없이 바로 import
else:
    # Colab 밖(예: 강사 Mac): SemIf를 미리 설치했거나 SEMIF_SRC=/path/to/SemIf/src 로 알려 주세요
    if os.environ.get("SEMIF_SRC"):
        sys.path.insert(0, os.environ["SEMIF_SRC"])

if MODE != "precomputed":
    import semif_phase1, transformers
    print(f"SemIf {semif_phase1.__version__} · transformers {transformers.__version__} · torch {torch.__version__}")
''')
md("s02-hf", """
### 2-3. `hf download`로 필요한 파일만 받기
`hf`는 Hugging Face 공식 명령줄 도구예요(`huggingface_hub` 패키지에 들어 있어요). 모델 저장소에는 README·라이선스·이미지 전처리 설정도 있는데, 우리는 **글자 판단에 필요한 9개 파일만** 받아요.
- `--revision 851bf6e…`: A4000 실측과 **같은 커밋**으로 고정해요.
- `--include`: 받을 파일 모양(가중치 `*.safetensors`, 설정 `*.json`, 채팅 틀 `*.jinja`, `merges.txt`). `--exclude`로 이미지 전처리 설정은 빼요.
- 먼저 `--dry-run`으로 **무엇을 얼마나 받을지**만 보고, 다음 셀에서 진짜로 받아요.
- 받은 파일은 Hugging Face 캐시(`~/.cache/huggingface/hub`)에 들어가고, 3장의 `from_pretrained`가 그대로 찾아 써요. 공개 모델이라 로그인(`hf auth`)은 필요 없어요.
""")
code("s02-hf-dry", '''
MODEL = "Qwen/Qwen3.5-4B"
REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"   # 강사 A4000 실측과 같은 커밋
HF_ARGS = (f'{MODEL} --revision {REVISION} --include "*.safetensors" --include "*.json" '
           f'--include "*.jinja" --include "merges.txt" --exclude "*preprocessor_config.json"')

print("$ hf download " + HF_ARGS + " --dry-run")
if shutil.which("hf"):
    !hf download {HF_ARGS} --dry-run
else:
    print("hf 명령이 없어요. 2-2 설치 셀(pip install huggingface-hub)을 먼저 실행해 주세요.")
''')
md("s02-hf-dry-read", """
**읽는 법**: 파일 9개, 합계 약 9.3GB예요. 대부분이 `model.safetensors-0000X-of-00002` 두 조각(5.3GB + 4.0GB)이고, 이미 받은 파일은 '받을 것'에 들어가지 않아요.

다음 셀이 **진짜로 받아요**(precomputed 모드면 건너뛰어요). Colab에서는 보통 몇 분 걸리고, 진행 막대가 보여요. 중간에 끊겨도 다시 실행하면 이어 받아요.
""")
code("s02-hf-get", '''
if MODE == "precomputed":
    print("precomputed 모드라 모델을 받지 않아요.")
else:
    t0 = time.time()
    !hf download {HF_ARGS}
    print(f"받기 끝 · {time.time() - t0:.0f}초")
''')

# ═════════════════════════════ 3. 모델 로드 ═════════════════════════════
md("s03-load", """
## 3. 모델 올리기

SemIf의 `load_causal_model()`로 올려요. 강사 A4000 상주 서비스(`openjev_service.py`)가 쓰던 바로 그 함수예요.
- 모델 이름과 **40자리 커밋**을 함께 줘야 해요. 안 주면 SemIf가 거절해요(재현성을 위해서예요).
- Qwen3.5-4B는 원래 이미지도 보는 모델이라, SemIf는 **글자 부분(`Qwen3_5ForCausalLM`)만** 꺼내 올려요.
- T4에서는 1~2분, GPU 메모리는 9GB쯤 써요.
""")
code("s03-load-code", '''
model = tokenizer = metadata = None
if MODE == "precomputed":
    print("precomputed 모드라 모델을 올리지 않아요. 4장부터는 미리 잰 숫자로 그려요.")
else:
    if MODE == "mps":
        os.environ["HF_DEACTIVATE_ASYNC_LOAD"] = "1"   # Mac(MPS): 가중치를 여러 스레드로 올리면 멈춰서 한 줄로 올려요
    from semif_phase1.core import load_causal_model
    from semif_phase1.direct import score
    t0 = time.time()
    model, tokenizer, metadata = load_causal_model(MODEL, REVISION, device=MODE, dtype=DTYPE)
    msg = f"로드 완료 {time.time() - t0:.0f}초 · {metadata['dtype']} · {metadata['device']}"
    if MODE == "cuda":
        msg += f" · GPU 메모리 {torch.cuda.memory_allocated() / 1e9:.1f}GB"
    print(msg)
''')
md("s03-read", """
**읽는 법**: `로드 완료 … float16 · cuda:0 · GPU 메모리 …GB`가 나오면 성공이에요. `causal_conv1d`·`flash-linear-attention`이 없어 느린 참조 구현을 쓴다는 경고가 나올 수 있어요. Qwen3.5의 선형 어텐션 층을 빠르게 해 주는 커널이 없다는 뜻이고, 결과는 같아요(조금 느릴 뿐).
""")

# ═════════════════════════════ 4. 뜯어보기 ═════════════════════════════
md("s04-cases", """
## 4. 한 케이스 뜯어보기 (Transformer Explainer처럼)

먼저 강의에서 쓴 케이스 5개를 정의해요. 한 케이스 = `state`(상황) + `question`(질문) + `options`(보기). Jev의 **CHOICE** 질문과 같은 모양이에요. 강사 A4000 상주 서비스에 보냈던 입력 그대로예요.
""")
code("s04-rows", rows_literal(cases["rows"]) + "\n\n# 8장에서 쓸 예시 질문(한국어) — 위젯에도 같이 넣어요\n"
     + row_literal("MY_ROW_EXAMPLE", cases["my_row"]) + "\n\n"
     + 'A4000 = CASES["a4000"]   # 강사 A4000(bfloat16) 기록: 보기별 확률 · 점수 · 프롬프트 지문\n'
     + 'print(f"케이스 {len(ROWS)}개: " + ", ".join(r["id"] for r in ROWS))')
md("s04-clip3", """
### 4-1. 영상 ③: 점수가 확률이 되는 길 (26초)
위젯의 ⑤·⑥단계를 먼저 영상으로 봐요. `classify-fail` 케이스의 A4000 실측 점수(22.25 · 20.125 · 20.0 · 25.875)가 softmax를 거쳐 0.026 · 0.003 · 0.003 · 0.968이 되는 과정과, 온도 T를 바꾸면 무엇이 달라지는지 보여 줘요.
""")
code("s04-clip", '#@title 🎬 영상 ③ 점수(logit) → 확률, 그리고 온도 (26초) — 실행하지 않아도 돼요\n'
     'show_clip("clip3_logits_to_probs.mp4", "영상 ③ · Manim으로 그림 · 숫자: classify-fail, 강사 A4000 실측")',
     form=True, outputs=video_output("clip3_logits_to_probs.mp4", "영상 ③ · Manim으로 그림 · 숫자: classify-fail, 강사 A4000 실측"))
md("s04-clip-read", """
**영상 읽는 법**: 가장 큰 값을 빼도 막대 모양은 그대로예요. 확률은 **점수의 차이**로만 정해져요. 온도 T는 1등을 바꾸지 않고, 확률이 얼마나 뾰족한지만 바꿔요.
""")
md("s04-widget", f"""
### 4-2. 7단계 위젯
아래 셀은 케이스 6개(강의 5개 + 8장 예시)를 **SemIf 원본 `score()`** 로 판정하면서 중간값을 모아 위젯으로 그려요. 보기 순서를 바꾼 판정까지 합쳐 40번 넘게 돌려요.

| 단계 | 보여 주는 것 | 해 볼 것 |
|---|---|---|
| ① 입력 | state · question · options | 위쪽 버튼으로 케이스 바꾸기 |
| ② 프롬프트 조립 | SemIf가 만든 채팅 프롬프트 전문(역할별 색) | 보기 id가 프롬프트에 **없다**는 점 |
| ③ 토큰 | 토큰 조각과 번호 | 마우스를 올려 id 보기 · 마지막 토큰(주황 테두리) |
| ④ 모델 1번 통과 | 32층 구조와 층마다 읽어 본 보기 확률 | 층을 지나며 선이 어떻게 움직이는지 |
| ⑤ 글자 점수 | 전체 어휘 상위 10개와 보기 글자 점수 | 보기 글자에 모인 확률 |
| ⑥ 확률 | softmax · 온도 T 슬라이더 · 보기 순서 바꾸기 | T 끌어 보기 · 순서 바꾸기 켜기 |
| ⑦ 코드의 판단 | 기준 τ 슬라이더와 if 문 | τ를 옮겨 행동이 바뀌는지 |

- **GPU 모드**: 방금 이 런타임에서 잰 숫자로 그려요.
- **precomputed 모드**: 강사 Mac(M5, MPS, bfloat16)에서 같은 코드로 잰 숫자로 그려요. 5케이스 모두 A4000과 **프롬프트 지문(SHA-256)이 같고 고른 보기도 같았어요**.
- **단순화한 곳**: ④의 층별 선은 '로짓 렌즈'라는 **분석용 근사**예요(SemIf는 맨 끝 층만 읽어요). ⑥의 온도와 ⑦의 기준은 SemIf 판정에는 없는 **내 코드 쪽 손잡이**예요.
- 위젯은 인터넷 없이 동작해요(외부 스크립트·글꼴을 받지 않아요). 키보드 ←/→로도 단계를 옮길 수 있어요.
""")
code("s04-widget-code", '''
CASE_ORDER = [r["id"] for r in ROWS] + [MY_ROW_EXAMPLE["id"]]
if MODE == "precomputed":
    EXPLAIN = [FALLBACK["results"][k] for k in CASE_ORDER]
    SOURCE = f"숫자: 강사 Mac(M5) · MPS · bfloat16 미리 잰 값 ({EXPLAIN[0]['measured_at']})"
    DEVICE = "Mac MPS · bfloat16"
else:
    score(model, tokenizer, ROWS[0], metadata)            # 첫 호출은 GPU 준비(워밍업) — 버려요
    t0 = time.time()
    EXPLAIN = [explain_case(model, tokenizer, row, metadata) for row in ROWS + [MY_ROW_EXAMPLE]]
    n_perm = sum(len(e["perms"]) for e in EXPLAIN)
    print(f"케이스 {len(EXPLAIN)}개 + 보기 순서 바꾼 판정 {n_perm}번 · {time.time() - t0:.1f}초")
    SOURCE = f"숫자: 방금 이 런타임에서 잰 값 ({GPU_NAME} · {DTYPE})"
    DEVICE = f"{GPU_NAME} · {DTYPE}"
show_explainer(EXPLAIN, SOURCE, DEVICE, refs=A4000)
''')
md("s04-widget-read", f"""
**읽는 법 — 이것부터 눌러 보세요** (숫자는 강사 Mac 기준이에요. T4에서는 소수점이 조금 달라요)
1. `목적지 없는 요청` → **④**: 초록 선(main)이 층마다 오르내리다 마지막에 {MAC['route-vague']['probabilities'][1]:.2f}로 끝나요. 근거가 없는 질문이라 모델도 갈팡질팡해요. 다른 케이스는 20층대에서 답이 굳어요.
2. 같은 케이스 → **⑥ → 보기 순서 바꿔 보기**: 순서만 바꿨는데 main이 **A 자리일 때 {main_at_a:.2f}, B 자리일 때 {main_at_b:.2f}**예요. 작은 모델은 자리(글자)에 쏠려요. 보기 순서도 입력의 일부예요.
3. **⑦**: 기준 0.70이면 '되묻기', 0.55로 내리면 'main으로 진행'. 같은 확률이라도 행동은 코드가 정해요.
4. `요약만 부탁했는데 전체 삭제?` → **⑥**: ask {MAC['gate-danger']['probabilities'][1]:.3f}. 순서를 바꿔도 거의 그대로예요 — 분명한 질문은 흔들리지 않아요.
""")

# ═════════════════════════════ 5. 5케이스 ═════════════════════════════
md("s05", """
## 5. 강의 5케이스 판정 + 강사 A4000과 비교

이번엔 위젯 없이, 실제 코드에서 쓰는 모양 그대로 판정해요. `decide(row)`는 SemIf의 `validate_row()`로 입력을 검사하고 `score()`로 보기별 확률을 받아요. 강사 A4000(bfloat16) 기록과 나란히 놓아요.
""")
code("s05-code", '''
if MODE != "precomputed":
    from semif_phase1.core import validate_row

    def decide(row):
        validate_row(row)
        return score(model, tokenizer, row, metadata)
else:
    def decide(row):
        r = FALLBACK["results"].get(row["id"])
        if r is None or r["row"] != row:
            raise RuntimeError("precomputed 모드에서는 미리 잰 케이스만 볼 수 있어요. GPU 런타임에서 다시 실행해 주세요.")
        return r
    print("(precomputed 모드: 아래 '이번' 숫자와 ms는 강사 Mac · MPS · bfloat16 기록이에요)\\n")

NOW = {}
for row in ROWS:
    r = decide(row)
    NOW[row["id"]] = r
    probs = dict(zip(r["option_ids"], r["probabilities"]))
    ref = dict(zip(A4000[row["id"]]["option_ids"], A4000[row["id"]]["probabilities"]))
    pick, ref_pick = max(probs, key=probs.get), max(ref, key=ref.get)
    print(f"[{row['id']}] {row['question']}")
    for k in probs:
        print(f"   {k:<10} 이번 {probs[k]:.3f}   A4000 {ref[k]:.3f}")
    same = "✓ 같음" if pick == ref_pick else "✗ 다름"
    print(f"   → 선택 {pick} ({r['forward_seconds'] * 1000:.0f}ms) | A4000 {ref_pick}  {same}\\n")

chart_cases(NOW, A4000, "이번 실행" if MODE != "precomputed" else "강사 Mac (bfloat16)")
''')
md("s05-read", f"""
**읽는 법**
- `✓ 같음`이 5개 모두 나오면 성공이에요. T4(float16)와 A4000(bfloat16)은 숫자 형식이 달라 소수점 둘째 자리쯤 달라질 수 있어요. 강사 Mac(bfloat16)에서는 `route-vague`의 차이가 가장 컸고, 그래도 {abs(MAC['route-vague']['probabilities'][0] - cases['a4000']['route-vague']['probabilities'][0]):.2f} 정도였어요(a4000 {MAC['route-vague']['probabilities'][0]:.3f} vs {cases['a4000']['route-vague']['probabilities'][0]:.3f}).
- `route-vague`처럼 근거가 없는 질문에서 확률이 한쪽으로 쏠리지 않으면 정상이에요. 강의에서 본 TypeSafe Jev는 같은 질문에 main 0.84였어요.
- ms는 한 번 판정(생성 없이 1번 통과) 시간이에요. 강사 A4000 기록은 첫 호출 뒤 0.10~0.13초였어요. 첫 호출은 GPU 준비 때문에 느려서 한 번 버리고 시작해요.
""")

# ═════════════════════════════ 6. 속도 ═════════════════════════════
md("s06", """
## 6. 왜 빠른가: 공통 앞부분은 한 번, 질문은 나란히

판단을 여러 개 할 때 속도를 가르는 건 **같은 상황(state)을 몇 번 읽느냐**예요.
- 문의 1건에 물을 게 28개면, 생성 방식은 28개 필드를 **한 토큰씩 차례로** 써요.
- 병렬 판단은 긴 상황을 **한 번만** 계산해 문맥 캐시(KV 캐시)에 두고, 질문+보기처럼 짧은 뒷부분만 **나란히** 계산해요. SemIf에는 `score_shared()`로, llama.cpp에는 `parallel-decision` 포크로 들어 있어요.

영상 ②(22초)는 이 구조와 강사 장비의 실측 숫자를 보여 줘요.
""")
code("s06-clip", '#@title 🎬 영상 ② 공통 앞부분은 한 번, 질문은 나란히 (22초) — 실행하지 않아도 돼요\n'
     'show_clip("clip2_shared_prefix.mp4", "영상 ② · Manim으로 그림 · 숫자: llama.cpp parallel-decision, 강사 Mac M5 · RTX A4000 실측")',
     form=True, outputs=video_output("clip2_shared_prefix.mp4", "영상 ② · Manim으로 그림 · 숫자: llama.cpp parallel-decision, 강사 Mac M5 · RTX A4000 실측"))
md("s06-clip-read", """
**영상 읽는 법**: 초록 칸(질문+보기)은 서로 기다리지 않고 한꺼번에 계산돼요. 아래 주황 띠(JSON 생성)는 필드를 한 줄로 써 내려가다 이 실행에선 필드 2개를 빠뜨렸어요. 숫자는 같은 1.5B 모델 파일로 Mac과 A4000에서 잰 값이에요.
""")
md("s06-1", """
### 6-1. 미리 잰 결과 ①: 병렬 판단 vs JSON 생성 (Mac M5 · RTX A4000)
2026-09-22에 강사가 llama.cpp `parallel-decision` 포크로 잰 기록이에요. 같은 Qwen2.5-1.5B GGUF 파일을 두 장비에서 돌렸어요. 모델을 다시 돌리지 않고 기록(JSON)만 읽어 그려요.
""")
code("s06-1-code", 'chart_parallel(PRE["parallel_decision"])')
md("s06-1-read", """
**읽는 법**: 초록 점(병렬 판단)과 주황 점(JSON 생성) 사이 거리가 배율이에요. 가로축이 로그 눈금이라 눈금 한 칸이 약 3배예요. A4000은 필드 28개를 0.1초 안팎에, Mac도 0.4~0.6초에 끝냈어요. 그림 아래 설명에 **빠르다고 다 맞는 건 아니라는** 작은 정답 테스트 결과도 있어요(1.5B 6/8 · 9B 8/8).
""")
md("s06-2", """
### 6-2. 미리 잰 결과 ②: 14B 모델을 Colab T4에서 (예전 무거운 노트북)
예전 노트북(`Colab_Local_16GB_Qwen14B.ipynb`)이 오래 걸린 이유가 이 실험이에요. Qwen2.5-14B 원본(약 30GB)을 받아 4비트로 올리고, SemIf·RLCD·JSON 생성을 반복해 재고, 선택으로 GGUF(약 9GB)를 받아 llama.cpp를 T4용 CUDA로 직접 빌드했어요. 그 결과 파일(`comparison_all.json`)을 그대로 그려요.

> 여기서 **RLCD**는 공개 데모 코드(`harshatheg/Qwen-2.5-1B-RLCD`)의 병렬 읽기 구현이에요. TypeSafe가 Jev 학습에 썼다고 밝힌 RLCD(보정된 결정 학습, 비공개)와 이름만 같고, 학습은 하지 않아요.
""")
code("s06-2-code", 'chart_colab14b(PRE["colab14b"])')
md("s06-2-read", f"""
**읽는 법**: 같은 T4, 같은 8건 정답(8/8)인데 시간은 1.4초~44초로 벌어져요. 판단 방식(초록)이 생성(주황)보다 빠른 건 두 엔진 모두 같지만, **엔진 차이(llama.cpp vs PyTorch)가 방식 차이보다 더 커요.** PyTorch 쪽은 T4 메모리에 맞추려고 질문을 2개씩 끊어(chunk=2) 매번 문맥을 다시 계산했고, 캐시를 한 번만 쓰는 llama.cpp 병렬 판단은 {pre['colab14b']['rows'][0]['median_seconds'] / pre['colab14b']['rows'][3]['median_seconds']:.0f}배 빨랐어요.
""")
md("s06-3", f"""
### 6-3. 가볍게 직접 재 보기: 같은 상황 × 질문 8개
무거운 실험 대신, 방금 올린 4B 모델로 SemIf의 두 함수를 비교해요. 고객 문의 1건(장애 신고 + 로그 몇 줄)에 질문 8개(심각도 · 담당 팀 · 이탈 위험 · 환불 · 법무 검토 · 상태 페이지 · 전화 · 원인)를 던져요.
- **따로 8번**: `score()`를 8번 — 매번 상황부터 다시 읽어요.
- **앞부분 공유**: `score_shared()` 1번 — 상황을 한 번 읽고 캐시를 나눠 써요.

GPU 모드에서는 여기서 직접 재고(두 번 재서 빠른 쪽), precomputed 모드에서는 강사 Mac 기록을 보여 줘요.
""")
code("s06-3-code", '''
if MODE == "precomputed":
    SHARED, WHERE = FALLBACK["shared_demo"], "강사 Mac(M5) · MPS · bfloat16 기록"
else:
    try:
        t0 = time.time()
        SHARED = run_shared_demo(model, tokenizer, metadata)
        WHERE = f"방금 이 런타임 ({GPU_NAME} · {DTYPE}) · 셀 전체 {time.time() - t0:.0f}초"
    except Exception as e:   # 공유 캐시 경로가 이 환경에서 안 되면 Mac 기록으로 대신 보여 줘요
        print(f"공유 모드 실행 실패({type(e).__name__}: {str(e)[:120]}) → 강사 Mac 기록을 보여 줘요")
        SHARED, WHERE = FALLBACK["shared_demo"], "강사 Mac(M5) · MPS · bfloat16 기록"
chart_shared_demo(SHARED, WHERE)
''')
md("s06-3-read", f"""
**읽는 법**: 강사 Mac(MPS)에서는 따로 8번 {SD['direct_seconds']:.2f}초 vs 공유 {SD['shared_seconds']:.2f}초({SD['direct_seconds'] / SD['shared_seconds']:.1f}배)였고, 모델이 읽은 토큰은 {SD['direct_tokens']:,}개 vs {SD['shared_tokens']:,}개였어요. CUDA에서는 SemIf가 뒷부분 8개를 **한 번에(batch)** 계산해서 차이가 달라질 수 있어요. 고른 답은 같아야 하고, 확률은 소수점 아래가 조금 다를 수 있어요.

""")
md("s06-4", """
### 6-4. 미리 잰 결과 ③: 강사 A4000에서 SemIf 따로 vs 공유 vs RLCD
6-3과 같은 비교를 강사 A4000(NF4 4비트)에서 필드 28개로 한 기록이에요. 모델을 한 번만 올리고 세 방식이 같은 가중치를 썼어요. 정답은 따로 만든 문의 8건으로 쟀어요.
""")
code("s06-4-code", 'chart_semif_a4000(PRE["semif_a4000"])')
md("s06-4-read", """
**읽는 법**: 초록(공유)과 주황(따로)의 차이가 6-3에서 본 '상황을 한 번만 읽는' 효과예요. 회색 RLCD는 더 빠르지만 작은 1.5B에서 더 많이 틀렸어요. **속도는 구현이, 정확도는 모델과 질문 모양이** 크게 좌우해요.

**더 해 보기: 14B·llama.cpp를 직접 다시 재고 싶다면 (선택 · 무거움)**
- 노트북: 강사 자료 `parallel-decision-rlcd-20260922/colab-large-models/Colab_Local_16GB_Qwen14B.ipynb`
- 필요한 것: T4 16GB, 디스크 여유 약 38GiB, 다운로드 약 39GB(14B 원본 + GGUF), T4용 llama.cpp CUDA 빌드(`RUN_LLAMA_CPP=True`일 때만)
- 이 노트북의 6-2 그림은 그 노트북이 T4에서 남긴 결과 파일을 그대로 쓴 거예요.
""")

# ═════════════════════════════ 7. 정확도와 보정 ═════════════════════════════
md("s07", """
## 7. 정확도와 보정: 빠른 것 ≠ 맞는 것 ≠ 믿을 수 있는 것

3강 실습 ②(API vs 로컬)와 같은 기록이에요. 2강 라우터 메시지 40건을 엔진만 바꿔 돌리고, **같은 정책 코드**로 행동(답장 · 작업 넘기기 · 되묻기 · 확인 · 차단)을 정해 채점했어요. 모델을 다시 돌리지 않아요.
""")
code("s07-code", 'chart_api_vs_local(PRE["api_vs_local"])')
md("s07-read", """
**읽는 법**
- Jev API와 Qwen3.5-4B JSON 생성이 92.5%로 같지만, 지연은 0.25초 vs 4.2초예요.
- decider-2b는 A4000에서 0.21초로 가장 빠르지만 72.5%, OpenJev(SemIf 4B)는 67.5%예요. 로컬 판단 모델은 **공짜·빠름 대신 정확도를 조금 내줘요**.
- 같은 decider-2b라도 Mac에서는 1.9초예요. 장비가 속도를 크게 바꿔요.
""")
md("s07-cal", """
### 7-1. 보정 맛보기: "0.95라고 했으면 정말 맞았나?"
1강에서 본 **보정(calibration)** 을 떠올려 봐요. 모델이 0.8이라고 한 경우를 모으면 실제로 80%쯤 맞아야 잘 보정된 거예요(신뢰도 그림 · ECE).

SemIf는 결과마다 `"probability_status": "conditional option score; uncalibrated as decision confidence"`라고 스스로 적어요. **보기끼리 비교한 점수**이고, '맞을 확률'로 맞춰진 값이 아니라는 뜻이에요. 40건 중 route 질문(잡담 · 작업 · 애매함 · 스팸) 하나만 골라, 고른 답의 확률과 정답 여부를 점으로 찍어 봐요.
""")
code("s07-cal-code", 'chart_calibration(PRE["api_vs_local"])')
md("s07-cal-read", """
**읽는 법**
- 좋은 모습은 틀린 답(✕)이 왼쪽(낮은 확률)에 모이고, 평균 확신(세로선)이 정답률과 비슷한 거예요. Jev는 40건 중 1건만 틀렸고, 그때 확률도 0.53으로 낮았어요.
- OpenJev(SemIf 4B)는 정답률 77.5%인데 평균 확신이 0.85로 **조금 과신**하고, 틀린 9건 중 3건에 0.9 넘게 확신했어요. 이런 숫자에 '0.9 이상이면 자동 실행' 같은 기준을 걸면 사고가 나요.
- decider-2b는 정답률 77.5%에 평균 확신 0.77로 거의 같고, 틀린 답은 모두 0.74 아래였어요. 지도학습에 온도 보정까지 한 모델의 모습이에요.
- 40건은 신뢰도 그림을 그리기엔 적어요. 내 서비스에 쓰려면 내 데이터 수백 건으로 재고, 필요하면 온도(4장 ⑥)를 맞춰요. SemIf 저장소에도 작업별 온도 보정 기능이 있어요.
""")
md("s07-rlcr", """
### 7-2. 같은 가중치, 출력 방식만 다르게: RLCR 생성 vs RLCD 읽기
1강에서 본 **RLCR**은 추론 끝에 확신도를 글로 쓰도록 학습한 방식이에요. 강사 A4000에서 RLCR로 학습된 7B 모델 하나를 두 방식으로 돌려 봤어요. ① 원래대로 추론·답·확신도를 글로 쓰기 ② 같은 모델에 6장의 RLCD 데모 코드로 보기 점수만 읽기. 이미 잰 기록이라 모델은 돌리지 않아요.
""")
code("s07-rlcr-code", 'chart_rlcr_rlcd(PRE["rlcr_vs_rlcd"])')
md("s07-rlcr-read", """
**읽는 법**: 점수 읽기는 수십 배 빠르지만, 틀린 두 건에 0.96 · 0.83이라는 높은 확률을 붙였어요. 같은 문의에서 글로 쓴 RLCR은 맞혔고 확신도는 0.7 · 0.8이었어요. 빠른 판단을 쓸 때는 **확률을 그대로 믿지 말고 내 데이터로 보정을 재는 일**이 따라와야 해요. TypeSafe가 Jev를 '보정된 결정'이 되도록 따로 학습했다고 강조하는 이유이기도 해요.
""")

# ═════════════════════════════ 8. 내 질문 ═════════════════════════════
md("s08", """
## 8. 내 질문 만들어 보기

`state`, `question`, `options`만 바꿔서 실행해 보세요.
- 보기는 2~16개, `id`는 서로 달라야 해요. 보기 id는 모델에 보이지 않아요 — **설명(`description`)이 판단 재료**예요.
- 애매할 때 빠져나갈 보기(예: '판단 불가 — 사람에게 묻기')를 하나 넣어 두면 좋아요(`classify-fail`의 `unknown`처럼).
- 한국어도 돼요. 아래 예시는 한국어 메일이에요.
- precomputed 모드에서는 예시 그대로일 때만 미리 잰 결과를 보여 줘요. 새 질문은 GPU가 있어야 판정할 수 있어요.
""")
code("s08-code", row_literal("my_row", cases["my_row"]) + '''

try:
    r = decide(my_row)
    for k, p in zip(r["option_ids"], r["probabilities"]):
        print(f"{k:<10} {p:.3f}  " + "█" * round(p * 30))
    print(f"\\n{r['input_tokens']}토큰 · 한 번 통과 {r['forward_seconds'] * 1000:.0f}ms")
except RuntimeError as e:
    print(e)
''')
md("s08-widget-md", """
(선택) 아래 셀은 내 질문도 4장의 7단계 위젯으로 열어 봐요. 보기 순서를 바꾼 판정까지 돌려서, 보기가 3개면 판정을 7번 더 해요(T4에서 수 초~10초).
""")
code("s08-widget", '''
#@title (선택) 내 질문도 7단계 위젯으로 보기 — 보기 순서 바꾸기까지 돌려요
if MODE == "precomputed":
    if my_row == FALLBACK["results"]["my-test"]["row"]:
        show_explainer([FALLBACK["results"]["my-test"]], "숫자: 강사 Mac(M5) · MPS · bfloat16 미리 잰 값", "Mac MPS · bfloat16", default_case="my-test")
    else:
        print("새 질문은 GPU 런타임에서 볼 수 있어요.")
else:
    mine = explain_case(model, tokenizer, my_row, metadata)
    show_explainer([mine], f"숫자: 방금 이 런타임에서 잰 값 ({GPU_NAME} · {DTYPE})", f"{GPU_NAME} · {DTYPE}", default_case=my_row["id"])
''', form=True)
md("s08-read", """
**해 볼 것**: ① 보기 순서를 바꿔 다시 돌려 보기 ② `refund` 설명을 모호하게 바꿔 보기('고객 담당') ③ 빠져나갈 보기 추가하기. 확률이 어떻게 흔들리는지 보면, **보기 설명이 곧 판단 기준**이라는 게 느껴져요.
""")

# ═════════════════════════════ 9. API ═════════════════════════════
md("s09", """
## 9. (선택) TypeSafe Jev API와 나란히

API 키가 있으면 같은 질문을 진짜 Jev에도 보내 비교해요. 키가 없으면 이 셀은 안내만 하고 넘어가요.
1. 왼쪽 🔑 **보안 비밀(Secrets)** 에 `TYPESAFE_API_KEY`를 추가하고 '노트북 액세스'를 켜요. **키를 코드에 붙여 넣지 마세요.** 셀은 키 값을 화면에 찍지 않아요.
2. 비용: 입력 100만 토큰당 $0.042이에요. 2강 라우터 40건 전체가 약 $0.0014였어요.
3. TypeSafe는 2026-09-22부터 신규 가입을 잠시 멈췄어요(기존 계정은 사용 가능).
4. 파이썬 기본 User-Agent(`Python-urllib`)로 부르면 Cloudflare가 **HTTP 403(error 1010)** 으로 막아요. 1강에서 겪은 그 문제라 헤더에 User-Agent를 넣었어요.
""")
code("s09-code", '''
import json, urllib.request, urllib.error

# 2강 코드와 같은 규칙: 주소는 TYPESAFE_BASE_URL(기본 https://api.typesafe.ai)로 바꿀 수 있어요
BASE_URL = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai").rstrip("/")

def get_key():
    try:
        from google.colab import userdata
        return userdata.get("TYPESAFE_API_KEY")
    except Exception:          # Colab 밖이거나, 보안 비밀이 없거나, 액세스를 안 켠 경우
        return os.environ.get("TYPESAFE_API_KEY")

def jev_api(row, key, model="jev-latest"):
    body = {"model": model, "state": row["state"],
            "questions": {"q": {"type": "choice", "instructions": row["question"],
                                "criteria": {o["id"]: o["description"] for o in row["options"]}}}}
    req = urllib.request.Request(f"{BASE_URL}/v1/systemone", data=json.dumps(body).encode("utf-8"),
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                                          "User-Agent": "jev-lecture-colab/1.0"})   # 없으면 403 (error 1010)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=20) as resp:
        out = json.load(resp)
    return out, (time.perf_counter() - t0) * 1000

KEY = get_key()   # 값은 출력하지 않아요
if not KEY:
    print("TYPESAFE_API_KEY가 없어서 건너뛰어요. (왼쪽 🔑 보안 비밀에 추가하고 노트북 액세스를 켠 뒤 다시 실행)")
else:
    for row in ROWS + [my_row]:
        try:
            out, ms = jev_api(row, KEY)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:160]
            print(f"[{row['id']}] HTTP {e.code}: {detail}")
            if e.code in (401, 403):
                print("   → 키가 틀렸거나 요청이 막혔어요. 키를 확인하고, User-Agent 헤더를 지우지 마세요.")
                break
            continue
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"[{row['id']}] 연결 실패: {e}")
            break
        api_probs = out["answers"]["q"]["probabilities"]
        try:
            local = dict(zip(*[decide(row)[k] for k in ("option_ids", "probabilities")]))
        except RuntimeError:
            local = {}
        tokens = out.get("usage", {}).get("input_tokens", 0)
        print(f"[{row['id']}] Jev {out.get('model')} · {ms:.0f}ms · 입력 {tokens}토큰(≈ ${tokens * 0.042 / 1e6:.6f})")
        for o in row["options"]:
            k = o["id"]
            loc = f"{local[k]:.3f}" if k in local else "  -  "
            print(f"   {k:<10} Jev {api_probs.get(k, 0):.3f}   SemIf {loc}")
''')
md("s09-read", """
**읽는 법**: 두 엔진이 같은 보기를 고르는지, 확률이 얼마나 다른지 보세요. Jev는 보정까지 학습했다고 밝힌 모델(RLCD, 방법은 비공개)이라 애매한 질문에서 숫자가 다르게 나올 수 있어요. 강의에서는 `route-vague`에 Jev가 main 0.84를 줬어요.
""")

# ═════════════════════════════ 10. Jev-Omni ═════════════════════════════
omni = pre["jev_omni"]
md("s10", f"""
## 10. (선택 · 80GB GPU 전용) Jev-Omni 살펴보기

[akhilaaa3/Jev-Omni](https://huggingface.co/akhilaaa3/Jev-Omni)는 2026-09에 공개된 **독립 오픈 모델**이에요(TypeSafe와 무관, Apache-2.0).
- Gemma 4 12B IT 위에 **3840 → 256 판단 머리(head)** 를 붙였어요. SemIf처럼 글자 점수를 읽는 대신, 마지막 은닉 상태에서 보기 번호(최대 256개) 중 하나를 고르는 **분류기를 학습**했어요.
- `predict(state, question, options)` → 보기별 확률. 글·이미지·오디오·영상을 받아요.
- **무료 T4에서는 안 돼요.** 공식 로더가 저장소 전체(약 72GB)와 Gemma 4 12B(약 24GB)를 받고, FP32 본체(약 48GB)를 GPU에 통째로 올려요. A100 80GB나 H100이 필요해요(T4 · L4 · A100 40GB로는 그대로 안 돼요).

그래서 여기서는 **돌리지 않고 읽기만** 해요: ① `hf download --dry-run`으로 받을 양 보기 ② 파일 크기 정리(메타데이터만) ③ 모델이 스스로 올린 검증 기록 ④ 공식 빠른 시작 코드(80GB GPU가 아니면 실행을 거절해요).
""")
code("s10-dry", '''
# 받기 전에 크기부터: --dry-run은 목록만 보고 아무것도 받지 않아요
if shutil.which("hf"):
    !hf download akhilaaa3/Jev-Omni --dry-run 2>/dev/null | grep "dry-run"
    !hf download google/gemma-4-12B-it --dry-run 2>/dev/null | grep "dry-run"
else:
    print("hf 명령이 없어요 (pip install huggingface-hub)")
''')
md("s10-files-md", """
받을 양을 폴더별로 묶어 봐요. `HfApi().list_repo_tree()`로 **파일 이름과 크기(메타데이터)만** 읽어요. 인터넷이 안 되면 2026-09-24에 조회한 값을 보여 줘요.
""")
code("s10-files", '''
OMNI = dict(PRE["jev_omni"])   # 미리 조회한 값(2026-09-24)으로 시작해서, 인터넷이 되면 지금 값으로 바꿔요
try:
    from huggingface_hub import HfApi
    api = HfApi(token=False)
    groups = {}
    for f in api.list_repo_tree("akhilaaa3/Jev-Omni", recursive=True):
        if getattr(f, "size", None):
            key = f.path.split("/")[0] if "/" in f.path else ("head.pt" if f.path == "head.pt" else "기타 작은 파일")
            groups[key] = groups.get(key, 0) + f.size
    OMNI.update(files_bytes=groups, repo_total_bytes=sum(groups.values()),
                repo_sha=api.model_info("akhilaaa3/Jev-Omni").sha, fetched_at=time.strftime("%Y-%m-%d"))
except Exception as e:
    print(f"허브에 닿지 않아 미리 조회한 목록을 보여 줘요 ({type(e).__name__})")
omni_files_table(OMNI)
''')
md("s10-files-read", """
**읽는 법**: 2장의 `hf download`처럼 **받기 전에 크기부터** 보는 습관이에요. `backbone/`(FP32, 약 48GB)과 `unified/`(BF16, 약 24GB)가 같은 모델을 두 형식으로 담고 있어서 저장소가 커요. 공식 로더는 둘 다 받아요.
""")
md("s10-ver-md", """
다음은 모델 저장소가 스스로 올린 검증 기록(`unified/verification_unified.json`)의 확률 4건이에요. 우리가 모델을 돌린 게 아니라, 올라온 숫자를 그림으로 읽어요. 1강의 보정 질문('0.9라고 하면 열에 아홉은 맞나?')을 떠올리며 보세요.
""")
code("s10-ver", 'chart_omni_verification(PRE["jev_omni"])')
md("s10-ver-read", f"""
**읽는 법**
- 정답이 분명한 질문(10시 회의인데 지금 9시 → 시작했나? → No {omni['verification_cases'][0]['probabilities'][1]:.4f})은 확신 있게 맞혀요.
- **정답이 없는 질문**이 재밌어요. 공정한 주사위라면 모든 눈이 1/6(0.167)이어야 하는데, '6'에 {omni['verification_cases'][2]['probabilities'][5]:.2f}, '3'에 {omni['verification_cases'][2]['probabilities'][2]:.2f}를 줘요. 구슬 4개도 0.25씩이어야 하는데 파랑 {omni['verification_cases'][3]['probabilities'][0]:.2f} · 초록 {omni['verification_cases'][3]['probabilities'][3]:.2f}로 쏠려요.
- README의 ECE {omni['readme_claims']['decisionbench_medium_ece']:.3f}은 정답이 있는 벤치마크(DecisionBench Medium) 기준이에요. '모른다'를 고르게 표현하는 능력은 따로 봐야 해요. 보정은 결국 **내 데이터로** 재야 해요.
""")
md("s10-run-md", """
마지막 셀은 모델 카드의 **빠른 시작 코드 그대로**예요. GPU 메모리 75GB · 디스크 여유 110GB가 안 되면 실행하지 않고, 조건이 맞아도 `RUN_JEV_OMNI = True`로 바꿔야 돌아요(약 96GB를 받아요). 무료 T4에서는 '건너뛰어요'가 나오면 정상이에요.
""")
code("s10-run", '''
#@title (80GB GPU 전용) Jev-Omni 공식 빠른 시작 — 조건이 안 맞으면 실행하지 않아요
RUN_JEV_OMNI = False     # 80GB GPU에서 직접 돌려 보려면 True (약 96GB를 받아요)
NEED_GPU_GB, NEED_DISK_GB = 75, 110

gpu_gb = torch.cuda.get_device_properties(0).total_memory / 1e9 if MODE == "cuda" else 0.0
disk_gb = shutil.disk_usage(os.path.expanduser("~")).free / 1e9
if gpu_gb < NEED_GPU_GB:
    print(f"건너뛰어요: GPU 메모리 {gpu_gb:.0f}GB < {NEED_GPU_GB}GB. Jev-Omni는 A100 80GB · H100 같은 GPU가 필요해요.")
elif disk_gb < NEED_DISK_GB:
    print(f"건너뛰어요: 디스크 여유 {disk_gb:.0f}GB < {NEED_DISK_GB}GB (저장소 약 72GB + Gemma 4 12B 약 24GB)")
elif not RUN_JEV_OMNI:
    print(f"GPU {gpu_gb:.0f}GB · 디스크 {disk_gb:.0f}GB — 돌릴 수 있어요. RUN_JEV_OMNI = True로 바꾸고 다시 실행하세요.")
else:
    # ↓ 모델 카드(README)의 Quick start 그대로예요 (Apache-2.0)
    !pip install -q -r https://huggingface.co/akhilaaa3/Jev-Omni/resolve/main/requirements.txt
    from huggingface_hub import snapshot_download
    path = snapshot_download("akhilaaa3/Jev-Omni")
    sys.path.insert(0, path)
    from jev_omni import load_jev_omni
    classifier = load_jev_omni()
    result = classifier.predict(
        state="The meeting starts at 10 AM. It is now 9 AM.",
        question="Has the meeting started?",
        options=["Yes", "No"],
    )
    print(result)
''', form=True)

# ═════════════════════════════ 11. 정리 ═════════════════════════════
md("s11", """
## 11. 정리

- **Jev 닮은 판단 = 한 번 통과 + 보기 글자 점수 읽기.** 글을 쓰지 않으니 빠르고, 보기 밖 답이 나오지 않아요. (1 · 4장)
- **빠른 이유는 반복을 줄여서예요.** 답을 쓰는 반복(토큰마다 통과)과 상황을 다시 읽는 반복(질문마다 문맥 계산)을 없앴어요. 같은 장비라도 엔진과 캐시 구현이 속도를 크게 바꿔요. (6장)
- **빠른 것 ≠ 맞는 것 ≠ 믿을 수 있는 것.** 로컬 판단 모델은 정확도를 조금 내주고, 학습하지 않은 SemIf의 숫자는 보기끼리 비교한 점수라 보정이 필요해요. 보기 순서만 바꿔도 흔들려요. (4 · 7장)
- **행동은 코드가 정해요.** 확률에 기준을 걸고, 애매하면 사람에게 묻는 길을 코드로 만들어 두세요. 기준값은 내 데이터로 정해요. (4장 ⑦)

**더 보기**
- SemIf: https://github.com/TheoLeeCJ/SemIf (이 노트북은 커밋 `1f2dea3`으로 고정)
- 3강 슬라이드 「원리 ①~③」 · 프롬프트 ③④(API vs 로컬) · `03_유사프로젝트/evidence/api-vs-local/`
- 1강: 보정 · ECE · 신뢰도 그림
- Jev-Omni: https://huggingface.co/akhilaaa3/Jev-Omni
- 이 노트북의 영상 · 위젯 · 미리 잰 숫자 원본: `03_유사프로젝트/colab/assets/` (`build_notebook.py`로 다시 만들어요)
""")

nb = {
    "nbformat": 4, "nbformat_minor": 5,
    "metadata": {
        "accelerator": "GPU",
        "colab": {"provenance": [], "gpuType": "T4", "toc_visible": True, "name": OUT.name},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
    },
    "cells": cells,
}
OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
size = OUT.stat().st_size
print(f"{OUT.name}: 셀 {len(cells)}개 (코드 {sum(c['cell_type'] == 'code' for c in cells)}) · {size / 1e6:.2f}MB")
try:
    import nbformat
    nbformat.validate(nbformat.read(str(OUT), as_version=4))
    print("nbformat 검사 통과")
except ImportError:
    print("(nbformat이 없어 형식 검사는 건너뛰었어요)")
if size > 12e6:
    sys.exit("노트북이 12MB를 넘어요")
