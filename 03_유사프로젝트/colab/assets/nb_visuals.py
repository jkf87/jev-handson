# 그림 도우미: 인터넷(CDN) 없이 브라우저에서 바로 그려지는 SVG/HTML만 써요. 한글은 브라우저 글꼴로 나와요.
import base64
import html
import json
import math
import uuid
from pathlib import Path

from IPython.display import HTML, display

INK, GREEN, ORANGE, LIGHT, LINE = "#19272D", "#466A62", "#AA5238", "#F0F5F2", "#D6DED9"
MUTED, FAINT, GRAY = "#5E6E68", "#8A9691", "#B7C2BD"
FONT = "'Noto Sans KR','Noto Sans CJK KR','Apple SD Gothic Neo','Malgun Gothic','Nanum Gothic',system-ui,sans-serif"  # HTML style="..." 안에 들어가니 작은따옴표만 써요
QWEN_VOCAB = 248320  # Qwen/Qwen3.5-4B @851bf6e config.json의 vocab_size
CASE_TITLES = {
    "route-gpu": "GPU 서버 요청 → 어느 세션?",
    "route-vague": "목적지 없는 요청 → 어느 세션?",
    "classify-fail": "로그 없는 실패 → 원인은?",
    "route-mail": "메일 확인 요청 → 어느 세션?",
    "gate-danger": "요약만 부탁했는데 전체 삭제? → 진행?",
    "my-test": "내 질문: 환불 메일 → 어느 팀?",
}
PRESET_KO = {
    "code_security": "코드 보안 · 28필드",
    "fintech_fraud": "결제 사기 · 28필드",
    "support_triage": "고객 문의 분류 · 28필드",
    "high_cardinality_255": "관세 분류(후보 255개) · 4필드",
}
ENGINE_KO = {
    "Jev API (TypeSafe)": "Jev API (클라우드)",
    "decider-2b (A4000 CUDA)": "decider-2b · A4000",
    "decider-2b (Mac MPS)": "decider-2b · Mac",
    "OpenJev Qwen3.5-4B (A4000)": "OpenJev(SemIf) 4B · A4000",
    "Qwen3.5-4B 생성(JSON) (Mac Ollama)": "Qwen3.5-4B JSON 생성 · Mac",
}


def esc(s):
    return html.escape(str(s))


def _card(inner, title=None, sub=None, note=None, table=None, width=760):
    head = ""
    if title:
        head += f'<div style="font-size:16px;font-weight:700;margin-bottom:2px">{esc(title)}</div>'
    if sub:
        head += f'<div style="font-size:12.5px;color:{MUTED};margin-bottom:8px">{sub}</div>'
    foot = f'<div style="font-size:12.5px;color:{MUTED};margin-top:8px;line-height:1.6">{note}</div>' if note else ""
    tbl = ""
    if table:
        tbl = (f'<details style="margin-top:8px;font-size:12.5px"><summary style="cursor:pointer;color:{MUTED}">숫자 표로 보기</summary>'
               f'{table}</details>')
    return (f'<div style="font-family:{FONT};color:{INK};background:#fff;border:1px solid {LINE};border-radius:12px;'
            f'padding:14px 16px;max-width:{width}px;box-sizing:border-box;line-height:1.5">{head}{inner}{foot}{tbl}</div>')


def _table(headers, rows, num_cols=()):
    th = "".join(f'<th style="text-align:{"right" if i in num_cols else "left"};border-bottom:1px solid {LINE};padding:4px 8px">{esc(h)}</th>'
                 for i, h in enumerate(headers))
    body = ""
    for r in rows:
        body += "<tr>" + "".join(
            f'<td style="text-align:{"right" if i in num_cols else "left"};border-bottom:1px solid {LINE};padding:3px 8px;font-variant-numeric:tabular-nums">{esc(v)}</td>'
            for i, v in enumerate(r)) + "</tr>"
    return f'<table style="border-collapse:collapse;margin-top:6px">{"<tr>" + th + "</tr>"}{body}</table>'


def _legend(items):
    parts = []
    for color, label, shape in items:
        if shape == "x":
            sw = f'<span style="color:{color};font-weight:700;margin-right:4px">✕</span>'
        elif shape == "line":
            sw = f'<span style="display:inline-block;width:14px;height:2px;background:{color};vertical-align:3px;margin-right:4px"></span>'
        else:
            sw = f'<span style="display:inline-block;width:11px;height:11px;border-radius:{50 if shape == "dot" else 3}%;background:{color};margin-right:4px;vertical-align:-1px"></span>'
        parts.append(f'<span style="margin-right:14px">{sw}{esc(label)}</span>')
    return f'<div style="font-size:12.5px;color:{MUTED};margin:2px 0 6px">{"".join(parts)}</div>'


def _svg(w, h, body, label):
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px;display:block" role="img" '
            f'aria-label="{esc(label)}" xmlns="http://www.w3.org/2000/svg" font-family="{FONT}">{body}</svg>')


def _bar(x, y, w, h, color, title=None):
    """끝만 4px 둥근 막대(바닥 쪽은 각지게)."""
    w = max(w, 0)
    r = min(4, w / 2, h / 2)
    if w < 5:
        d = f"M{x:.1f},{y:.1f} h{w:.1f} v{h:.1f} h{-w:.1f} z"
    else:
        d = (f"M{x:.1f},{y:.1f} h{w - r:.1f} a{r},{r} 0 0 1 {r},{r} v{h - 2 * r:.1f} "
             f"a{r},{r} 0 0 1 {-r},{r} h{-(w - r):.1f} z")
    t = f"<title>{esc(title)}</title>" if title else ""
    return f'<path d="{d}" fill="{color}">{t}</path>'


def _text(x, y, s, size=12, color=INK, anchor="start", weight=400):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color}" text-anchor="{anchor}" '
            f'font-weight="{weight}">{esc(s)}</text>')


# ─────────────────────────── 영상 ───────────────────────────
CLIP_DIRS = [Path("assets"), Path("colab/assets"), Path("/content/assets")]
# 셀을 다시 실행했는데 옆에 assets/가 없으면(Colab에서 노트북만 연 경우) 공개 저장소에서 받아 와요
CLIP_REPO_RAW = "https://raw.githubusercontent.com/jkf87/jev-handson/main/"
CLIP_REPO_DIR = "03_유사프로젝트/colab/assets/"


def _clip_bytes(name):
    for d in CLIP_DIRS:
        p = d / name
        if p.exists():
            return p.read_bytes()
    try:
        import urllib.parse
        import urllib.request
        req = urllib.request.Request(CLIP_REPO_RAW + urllib.parse.quote(CLIP_REPO_DIR + name),
                                     headers={"User-Agent": "jev-lecture-colab/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
        if data[4:8] == b"ftyp":   # MP4가 맞는지(파일 머리 확인)
            return data
    except Exception:
        pass
    return None


def show_clip(name, caption=""):
    """영상 다시 보기: 옆의 assets/ → 공개 저장소(jkf87/jev-handson) 순서로 찾아요. 둘 다 없으면 안내만 해요."""
    data = _clip_bytes(name)
    if data:
        b64 = base64.b64encode(data).decode()
        display(HTML(f'<figure style="margin:0;max-width:960px"><video controls playsinline preload="metadata" '
                     f'style="width:100%;border:1px solid {LINE};border-radius:10px" src="data:video/mp4;base64,{b64}"></video>'
                     f'<figcaption style="font-family:{FONT};font-size:12.5px;color:{MUTED}">{esc(caption)}</figcaption></figure>'))
        return
    display(HTML(f'<div style="font-family:{FONT};font-size:13px;color:{MUTED};border:1px dashed {LINE};border-radius:8px;padding:10px 12px;max-width:760px">'
                 f'영상 <code>{esc(name)}</code>을 찾지 못했어요(옆에 assets/ 폴더가 없고, 공개 저장소에서도 받지 못했어요). '
                 f'노트북을 새로 열면 저장된 출력으로 다시 보여요. 영상 파일은 강의 자료의 <code>03_유사프로젝트/colab/assets/</code>에 있어요.</div>'))


# ─────────────────────────── 위젯 ───────────────────────────
WIDGET_TEMPLATE = None  # 노트북에서는 build_notebook.py가 위젯 HTML 원본을 여기에 채워 넣어요


def _case_for_widget(r, ref=None, ref_label=None):
    title = CASE_TITLES.get(r["id"], r["id"])
    if r["id"] not in CASE_TITLES or r["id"] == "my-test":  # 내 질문은 질문 글에서 제목을 만들어요
        q = r["row"]["question"]
        title = "내 질문: " + (q if len(q) <= 22 else q[:21] + "…")
    c = {
        "id": r["id"], "title": title, "row": r["row"], "prompt": r["prompt"],
        "tokens": r["tokens"], "slots": r["slots"], "option_ids": r["option_ids"],
        "logits": [round(v, 4) for v in r["option_logits"]],
        "top": [[t[0], t[1], t[2]] for t in r["top_tokens"]], "mass": r["allowed_mass"],
        "lens": r["lens"], "layer_types": r["layer_types"],
        "perms": [{"order": p["order"], "logits": p["logits"]} for p in r.get("perms", [])],
        "ms": r["forward_seconds"] * 1000, "sha": r["prompt_sha256"],
    }
    if ref:
        c["ref"] = {"label": ref_label, "probs": dict(zip(ref["option_ids"], ref["probabilities"])), "sha": ref.get("prompt_sha256")}
    return c


def show_explainer(results, source_label, device_label, refs=None, ref_label="A4000 기록", default_case="route-vague"):
    """explain_case() 결과 목록을 받아 7단계 위젯을 그려요. refs = {케이스 id: A4000 기록}."""
    display(HTML(explainer_html(results, source_label, device_label, refs, ref_label, default_case)))


def explainer_html(results, source_label, device_label, refs=None, ref_label="A4000 기록", default_case="route-vague"):
    refs = refs or {}
    cases = [_case_for_widget(r, refs.get(r["id"]), ref_label) for r in results]
    data = {"cases": cases, "roles": ROLE_NAMES_KO, "sourceLabel": source_label, "deviceLabel": device_label,
            "defaultCase": default_case if any(c["id"] == default_case for c in cases) else cases[0]["id"],
            "vocabSize": QWEN_VOCAB}
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    static = "자바스크립트가 꺼진 화면이에요. 요약: " + " · ".join(
        f"{c['id']} → {c['option_ids'][max(range(len(c['logits'])), key=c['logits'].__getitem__)]}" for c in cases)
    uid = "jx" + uuid.uuid4().hex[:10]
    return WIDGET_TEMPLATE.replace("__UID__", uid).replace("__STATIC__", esc(static)).replace("__DATA__", payload)


ROLE_NAMES_KO = {
    "template": "채팅 틀(특수 토큰)", "system": "지시문(system)", "json": "JSON 키·기호", "evidence": "상황(state)",
    "criterion": "질문(question)", "letter": "보기 글자", "option": "보기 설명", "gen": "답이 올 자리",
}


# ─────────────────────────── 5장: 강의 5케이스 ───────────────────────────
def chart_cases(now, ref, now_label, ref_label="A4000 기록 (bfloat16)"):
    """now/ref = {케이스 id: {option_ids, probabilities}}. 보기마다 두 막대(이번 실행 / A4000)."""
    W, lab, plot = 760, 230, 430
    rows_svg, y, table = [], 8, []
    for cid, r in now.items():
        a = ref.get(cid)
        if a is None:
            continue
        pick = r["option_ids"][max(range(len(r["probabilities"])), key=r["probabilities"].__getitem__)]
        apick = a["option_ids"][max(range(len(a["probabilities"])), key=a["probabilities"].__getitem__)]
        mark = "✓ 같은 선택" if pick == apick else "✗ 선택이 달라요"
        rows_svg.append(_text(0, y + 12, f"{cid}", 13, INK, weight=700))
        rows_svg.append(_text(W - 4, y + 12, mark, 12, GREEN if pick == apick else ORANGE, "end", 700))
        y += 20
        amap = dict(zip(a["option_ids"], a["probabilities"]))
        for oid, p in zip(r["option_ids"], r["probabilities"]):
            q = amap.get(oid, 0.0)
            rows_svg.append(_text(lab - 8, y + 13, oid, 12.5, INK, "end", 700 if oid == pick else 400))
            rows_svg.append(_bar(lab, y, plot * p, 9, GREEN, f"{cid} · {oid} · {now_label} {p:.3f}"))
            rows_svg.append(_bar(lab, y + 11, plot * q, 9, GRAY, f"{cid} · {oid} · {ref_label} {q:.3f}"))
            rows_svg.append(_text(lab + plot * max(p, q) + 6, y + 14, f"{p:.3f} / {q:.3f}", 11.5, MUTED))
            table.append([cid, oid, f"{p:.4f}", f"{q:.4f}", f"{p - q:+.4f}"])
            y += 26
        y += 10
    for t in (0, 0.5, 1.0):
        rows_svg.insert(0, f'<line x1="{lab + plot * t}" x2="{lab + plot * t}" y1="0" y2="{y - 6}" stroke="{LINE}" stroke-width="1"/>')
        rows_svg.append(_text(lab + plot * t, y + 8, f"{t:.1f}", 11, MUTED, "middle"))
    svg = _svg(W, y + 14, "".join(rows_svg), "강의 5케이스 보기 확률 비교")
    legend = _legend([(GREEN, now_label, "sq"), (GRAY, ref_label, "sq")])
    display(HTML(_card(legend + svg, "강의 5케이스: 이번 실행 vs 강사 A4000",
                       "막대 = 보기별 확률(합 1). 위 막대가 이번 실행, 아래 막대가 A4000 기록이에요. 오른쪽 숫자 = 이번 / A4000.",
                       table=_table(["케이스", "보기", "이번", "A4000", "차이"], table, (2, 3, 4)))))


# ─────────────────────────── 6장: 속도 ───────────────────────────
def _logx(v, lo, hi, x0, w):
    return x0 + w * (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))


def chart_parallel(pd):
    """llama.cpp parallel-decision: 같은 GGUF로 Mac·A4000에서 병렬 판단 vs 일반 JSON 생성 (로그 눈금)."""
    W, lab, x0, pw, lo, hi = 760, 230, 240, 440, 50, 20000
    body, y = [], 6
    ticks = [(100, "0.1초"), (300, "0.3초"), (1000, "1초"), (3000, "3초"), (10000, "10초")]
    rows = [r for r in pd["rows"] if r["project"] == "llama"]
    order = ["support_triage", "code_security", "fintech_fraud", "high_cardinality_255"]
    for dev, dev_ko in (("a4000", "RTX A4000 (CUDA)"), ("mac", "Mac M5 (Metal)")):
        body.append(_text(0, y + 12, dev_ko, 13, INK, weight=700))
        y += 20
        for preset in order:
            r = next(x for x in rows if x["device"] == dev and x["preset"] == preset)
            a, b = _logx(r["parallel_ms"], lo, hi, x0, pw), _logx(r["json_ms"], lo, hi, x0, pw)
            cy = y + 10
            body.append(_text(lab - 8, cy + 4, PRESET_KO[preset], 12.5, INK, "end"))
            body.append(f'<line x1="{a:.1f}" x2="{b:.1f}" y1="{cy}" y2="{cy}" stroke="{GRAY}" stroke-width="2"/>')
            body.append(f'<circle cx="{a:.1f}" cy="{cy}" r="5.5" fill="{GREEN}" stroke="#fff" stroke-width="2"><title>병렬 판단 {r["parallel_ms"]:.0f}ms</title></circle>')
            body.append(f'<circle cx="{b:.1f}" cy="{cy}" r="5.5" fill="{ORANGE}" stroke="#fff" stroke-width="2"><title>JSON 생성 {r["json_ms"]:.0f}ms</title></circle>')
            body.append(_text(b + 10, cy + 4, f"{r['speedup']:.0f}배", 12.5, INK, weight=700))
            y += 24
        y += 8
    for v, t in ticks:
        x = _logx(v, lo, hi, x0, pw)
        body.insert(0, f'<line x1="{x:.1f}" x2="{x:.1f}" y1="0" y2="{y}" stroke="{LINE}" stroke-width="1"/>')
        body.append(_text(x, y + 14, t, 11, MUTED, "middle"))
    svg = _svg(W, y + 22, "".join(body), "병렬 판단과 JSON 생성 지연 비교")
    tbl = _table(["장치", "구현", "프리셋", "필드", "병렬(ms)", "JSON(ms)", "배율", "JSON 형식 통과"],
                 [[r["device"], r["project"], r["preset"], r["fields"], f"{r['parallel_ms']:.0f}", f"{r['json_ms']:.0f}",
                   f"{r['speedup']:.1f}×", "통과" if r["json_schema_valid"] else f"실패(빠진 필드 {r['json_missing_fields']}개)"]
                  for r in pd["rows"]], (3, 4, 5, 6))
    display(HTML(_card(_legend([(GREEN, "병렬 판단 (보기 점수 읽기)", "dot"), (ORANGE, "일반 JSON 생성", "dot")]) + svg,
                       "병렬 판단 vs JSON 생성 — 같은 1.5B 모델, 필드 28개",
                       "llama.cpp parallel-decision · Qwen2.5-1.5B GGUF Q4_K_M(두 장치 같은 파일) · 가로축은 로그 눈금 · 첫 호출 뒤 3회 중앙값",
                       note="그림의 llama.cpp 8줄에서 일반 JSON 생성은 <b>8번 모두 형식 검사를 통과하지 못했어요</b>(필드 누락·없는 값). "
                            "표에는 RLCD 줄도 있어요. RLCD는 장치마다 모델 빌드가 달라(Mac MLX 4bit / A4000 PyTorch BF16) 그림에서 뺐고, 배율은 6~79배예요.<br>"
                            "<b>빠르다고 다 맞는 건 아니에요</b> — 같은 A4000, 정답이 있는 작은 문의 8건: " + " · ".join(
                                f"{a['model']} 병렬 판단 {a['parallel_exact']}/{a['cases']} ({a['parallel_ms']:.0f}ms) vs JSON {a['json_exact']}/{a['cases']} ({a['json_ms'] / 1000:.1f}초)"
                                for a in pd.get("a4000_small_accuracy", [])),
                       table=tbl)))


def chart_colab14b(c14):
    """무거운 노트북(14B, Colab T4)에서 이미 잰 6가지 방식."""
    W, lab, plot = 760, 230, 330
    names = {
        "torch_semif_shared": ("SemIf 병렬 · PyTorch", GREEN), "torch_rlcd_parallel": ("RLCD 병렬 · PyTorch", GREEN),
        "torch_json_generate": ("JSON 생성 · PyTorch", ORANGE), "llama14b_parallel": ("병렬 판단 · llama.cpp", GREEN),
        "llama14b_json": ("JSON 생성 · llama.cpp", ORANGE), "llama14b-structured_json": ("형식 강제 JSON · llama.cpp", ORANGE),
    }
    mx = max(r["median_seconds"] for r in c14["rows"])
    body, y = [], 4
    for r in c14["rows"]:
        name, color = names.get(r["key"], (r["method"], GRAY))
        w = plot * r["median_seconds"] / mx
        acc = f"문의 {r['correct_cases']}/{r['total_cases']} · 필드 {r['correct_fields']}/{r['total_fields']}" if r["correct_cases"] is not None else "정확도 미측정"
        body.append(_text(lab - 8, y + 14, name, 12.5, INK, "end"))
        body.append(_bar(lab, y + 3, w, 16, color, f"{name}: 중앙값 {r['median_seconds']:.2f}초 (최소 {r['min_seconds']:.2f} · 최대 {r['max_seconds']:.2f})"))
        body.append(_text(lab + w + 6, y + 15, f"{r['median_seconds']:.1f}초", 12, INK, weight=700))
        body.append(_text(W - 4, y + 15, acc, 12, MUTED, "end"))
        y += 28
    for t in (0, 10, 20, 30, 40):
        x = lab + plot * t / mx
        body.insert(0, f'<line x1="{x:.1f}" x2="{x:.1f}" y1="0" y2="{y}" stroke="{LINE}" stroke-width="1"/>')
        body.append(_text(x, y + 14, f"{t}초", 11, MUTED, "middle"))
    svg = _svg(W, y + 22, "".join(body), "14B 모델 Colab T4 비교")
    tbl = _table(["방식", "엔진", "양자화", "중앙값(초)", "최소", "최대", "반복", "문의 정답", "스케줄"],
                 [[r["method"], r["engine"], r["quantization"], f"{r['median_seconds']:.2f}", f"{r['min_seconds']:.2f}",
                   f"{r['max_seconds']:.2f}", r["measured_repeats"],
                   f"{r['correct_cases']}/{r['total_cases']}" if r["correct_cases"] is not None else "N/A", r["scheduling"]]
                  for r in c14["rows"]], (3, 4, 5, 6))
    display(HTML(_card(_legend([(GREEN, "보기 점수 읽기(판단)", "sq"), (ORANGE, "글로 생성", "sq")]) + svg,
                       f"무거운 실험 결과: {c14['model']} · {c14['gpu']} (이미 잰 값)",
                       "필드 28개를 끝내는 시간(3회 중앙값). PyTorch 줄은 NF4 4비트 + FP16, 질문 2개씩 묶어 매번 문맥을 새로 계산(chunk=2). llama.cpp 줄은 GGUF Q4_K_M.",
                       note="같은 T4인데 <b>llama.cpp 병렬 판단 1.4초 vs PyTorch SemIf 24초</b>: 차이의 대부분은 방식이 아니라 구현(엔진·캐시 재사용·양자화 커널)이에요. "
                            "양자화·프롬프트·캐시 조건이 서로 달라 줄끼리는 '시스템 비교'로만 읽어 주세요. 문의 8/8은 작은 스모크 테스트예요.",
                       table=tbl)))


def chart_shared_demo(d, where):
    """SemIf score() 8번 vs score_shared() 1번: 시간과 처리한 토큰 수."""
    W, lab, plot = 760, 200, 290
    rows = [("따로 8번 (score)", d["direct_seconds"], d["direct_tokens"], ORANGE),
            ("앞부분 공유 (score_shared)", d["shared_seconds"], d["shared_tokens"], GREEN)]
    mx = max(r[1] for r in rows)
    body, y = [], 4
    for name, sec, tok, color in rows:
        w = plot * sec / mx
        body.append(_text(lab - 8, y + 15, name, 12.5, INK, "end"))
        body.append(_bar(lab, y + 4, w, 16, color, f"{name}: {sec:.2f}초 · 토큰 {tok}개"))
        body.append(_text(lab + w + 6, y + 16, f"{sec:.2f}초 · 모델이 읽은 토큰 {tok:,}개", 12, INK))
        y += 30
    svg = _svg(W, y + 4, "".join(body), "공유 모드 비교")
    speed = d["direct_seconds"] / d["shared_seconds"]
    note = (f"상황 앞부분 {d['prefix_tokens']}토큰을 한 번만 계산하니 읽는 토큰이 <b>{d['direct_tokens'] / d['shared_tokens']:.1f}분의 1</b>, "
            f"시간은 <b>{speed:.1f}배</b> 빨라졌어요. 고른 답은 {d['same_picks']}/{d['questions']} 같고, 확률 차이는 최대 {d['max_prob_diff']:.4f}예요"
            f"(캐시를 나눠 쓰면 소수점 아래가 조금 달라질 수 있어요). 실행 방식: <code>{esc(d.get('serving_config'))}</code>")
    tbl = _table(["질문", "따로", "공유"], [[a["id"], json.dumps(a["direct"]), json.dumps(a["shared"])] for a in d["answers"]])
    display(HTML(_card(svg, f"같은 상황 × 질문 {d['questions']}개 — {where}", "SemIf 원본 함수 두 개를 같은 모델로 돌려 잰 값이에요.", note, tbl)))


def chart_semif_a4000(sa):
    """강사 A4000: 같은 가중치로 SemIf 개별(score) · SemIf 병렬(score_shared) · RLCD 병렬 — 모델별 작은 그림 두 개."""
    names = {"semif_direct": ("SemIf 따로(score)", ORANGE), "semif_shared": ("SemIf 공유(score_shared)", GREEN),
             "rlcd": ("RLCD 병렬", GRAY)}
    models = [("qwen9b", "Qwen3.5 9B"), ("qwen1p5b", "Qwen2.5 1.5B")]
    W, lab, plot = 760, 190, 330
    body, y = [], 4
    for key, title in models:
        rows = [r for r in sa["rows"] if r["model"] == key]
        rows.sort(key=lambda r: ["semif_direct", "semif_shared", "rlcd"].index(r["method"]))
        mx = max(r["median_ms"] for r in rows)
        body.append(_text(0, y + 13, f"{title} · 필드 28개", 13, INK, weight=700))
        y += 20
        for r in rows:
            name, color = names[r["method"]]
            w = plot * r["median_ms"] / mx
            body.append(_text(lab - 8, y + 14, name, 12.5, INK, "end"))
            body.append(_bar(lab, y + 3, w, 15, color, f"{title} · {name}: {r['median_ms'] / 1000:.2f}초"))
            body.append(_text(lab + w + 6, y + 15, f"{r['median_ms'] / 1000:.2f}초", 12, INK, weight=700))
            body.append(_text(W - 4, y + 15, f"문의 {r['correct_cases']}/8 · 필드 {r['correct_fields']}/24", 12, MUTED, "end"))
            y += 24
        y += 10
    svg = _svg(W, y, "".join(body), "A4000 SemIf와 RLCD 비교")
    tbl = _table(["모델", "방식", "중앙값(ms)", "최소", "최대", "문의 정답", "필드 정답", "GPU 할당(MiB)"],
                 [[r["model"], r["method"], f"{r['median_ms']:.0f}", f"{r['min_ms']:.0f}", f"{r['max_ms']:.0f}",
                   r["correct_cases"], r["correct_fields"], f"{r['peak_allocated_mib']:.0f}"] for r in sa["rows"]], (2, 3, 4, 5, 6, 7))
    d9 = {r["method"]: r["median_ms"] for r in sa["rows"] if r["model"] == "qwen9b"}
    d1 = {r["method"]: r["median_ms"] for r in sa["rows"] if r["model"] == "qwen1p5b"}
    display(HTML(_card(_legend([(ORANGE, "질문마다 상황부터 다시", "sq"), (GREEN, "상황은 한 번, 질문은 나란히", "sq"), (GRAY, "다른 구현(RLCD)", "sq")]) + svg,
                       "강사 A4000: 같은 가중치에서 SemIf 따로 vs 공유 vs RLCD (이미 잰 값)",
                       "RTX A4000 · NF4/FP16 · 같은 프로세스에 모델 한 번만 올림 · 28항목 3회 중앙값 · 정답은 별도 문의 8건",
                       note=f"공유(score_shared)가 따로(score)보다 9B {d9['semif_direct'] / d9['semif_shared']:.1f}배, 1.5B {d1['semif_direct'] / d1['semif_shared']:.1f}배 빨랐어요 — 6-3에서 잰 것과 같은 효과예요. "
                            "RLCD는 질문별 뒷부분이 짧아 SemIf보다 2배쯤 빨랐지만, 1.5B에서는 문의 5/8로 SemIf(7/8)보다 덜 맞혔어요.",
                       table=tbl)))


# ─────────────────────────── 7장: 정확도와 보정 ───────────────────────────
def chart_api_vs_local(avl):
    t = avl["table"]
    W, lab = 760, 230
    body, y = [], 4
    half = 230
    body.append(_text(lab, y + 10, "행동 일치 (40건)", 12, MUTED, weight=700))
    body.append(_text(lab + half + 40, y + 10, "지연 중앙값 p50 (로그 눈금 · 점)", 12, MUTED, weight=700))
    y += 18
    for r in t:
        name = ENGINE_KO.get(r["engine"], r["engine"])
        is_gen = "생성" in r["engine"]
        body.append(_text(lab - 8, y + 14, name, 12.5, INK, "end"))
        body.append(_bar(lab, y + 4, half * r["actionAcc"], 14, ORANGE if is_gen else GREEN, f"{name}: 행동 일치 {r['actionAcc']:.1%}"))
        body.append(_text(lab + half * r["actionAcc"] + 5, y + 15, f"{r['actionAcc']:.1%}", 12, INK))
        x1 = lab + half + 40
        lx = _logx(r["p50ms"], 100, 10000, x1, 200)
        # 로그 눈금에서는 막대 길이가 값에 비례하지 않아서 점으로 찍어요
        body.append(f'<line x1="{x1:.1f}" x2="{lx:.1f}" y1="{y + 11}" y2="{y + 11}" stroke="{LINE}" stroke-width="2"/>')
        body.append(f'<circle cx="{lx:.1f}" cy="{y + 11}" r="5.5" fill="{ORANGE if is_gen else GREEN}" stroke="#fff" stroke-width="2"><title>{esc(name)}: p50 {r["p50ms"]}ms</title></circle>')
        body.append(_text(lx + 9, y + 15, f"{r['p50ms']:,}ms", 12, INK))
        y += 26
    x1 = lab + half + 40
    for v, s in ((100, "0.1초"), (1000, "1초"), (10000, "10초")):
        x = _logx(v, 100, 10000, x1, 200)
        body.insert(0, f'<line x1="{x:.1f}" x2="{x:.1f}" y1="18" y2="{y}" stroke="{LINE}" stroke-width="1"/>')
        body.append(_text(x, y + 13, s, 11, MUTED, "middle"))
    for v in (0, 0.5, 1):
        x = lab + half * v
        body.insert(0, f'<line x1="{x:.1f}" x2="{x:.1f}" y1="18" y2="{y}" stroke="{LINE}" stroke-width="1"/>')
        body.append(_text(x, y + 13, f"{v:.0%}", 11, MUTED, "middle"))
    svg = _svg(W, y + 20, "".join(body), "API와 로컬 40건 비교")
    tbl = _table(["엔진", "어디서", "행동 일치", "route 일치", "p50(ms)", "p95(ms)", "1,000건 비용($)"],
                 [[r["engine"], r["where"], f"{r['actionAcc']:.1%}", f"{r['routeAcc']:.1%}", r["p50ms"], r["p95ms"], f"{r['costPer1k']:.4f}"] for r in t],
                 (2, 3, 4, 5, 6))
    display(HTML(_card(_legend([(GREEN, "보기 확률을 주는 엔진", "sq"), (ORANGE, "JSON을 생성하는 LLM", "sq")]) + svg,
                       "API vs 로컬 — 같은 40건 · 같은 정책 코드",
                       "2강 라우터 메시지 40건(잡담·작업·애매함·스팸). 모델 답(route·target·confirm)을 같은 정책 코드로 행동으로 바꿔 정답과 비교했어요.",
                       table=tbl)))


def chart_calibration(avl):
    cal = avl["route_calibration"]
    W, lab, x0, pw = 760, 210, 220, 380
    lo = 0.25
    body, y = [], 4
    for name, items in cal.items():
        n = len(items)
        acc = sum(ok for _, ok in items) / n
        conf = sum(p for p, _ in items) / n
        bad_hi = sum(1 for p, ok in items if not ok and p >= 0.9)
        cy = y + 18
        body.append(_text(lab - 8, cy + 4, ENGINE_KO.get(name, name), 12.5, INK, "end"))
        body.append(f'<line x1="{x0}" x2="{x0 + pw}" y1="{cy}" y2="{cy}" stroke="{LINE}" stroke-width="1"/>')
        for k, (p, ok) in enumerate(sorted(items, key=lambda t: t[0])):
            x = x0 + pw * (max(p, lo) - lo) / (1 - lo)
            jy = cy + ((k % 5) - 2) * 4
            tip = f"{name}: 고른 답 확률 {p:.3f} · {'맞음' if ok else '틀림'}"
            if ok:
                body.append(f'<circle cx="{x:.1f}" cy="{jy:.1f}" r="4" fill="{GREEN}" fill-opacity="0.55" stroke="#fff" stroke-width="1"><title>{esc(tip)}</title></circle>')
            else:
                body.append(f'<g stroke="{ORANGE}" stroke-width="2.4" stroke-linecap="round"><title>{esc(tip)}</title>'
                            f'<line x1="{x - 5:.1f}" y1="{jy - 5:.1f}" x2="{x + 5:.1f}" y2="{jy + 5:.1f}"/><line x1="{x - 5:.1f}" y1="{jy + 5:.1f}" x2="{x + 5:.1f}" y2="{jy - 5:.1f}"/></g>')
        cx = x0 + pw * (conf - lo) / (1 - lo)
        ax = x0 + pw * (acc - lo) / (1 - lo)
        body.append(f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{cy - 15}" y2="{cy + 15}" stroke="{INK}" stroke-width="2"><title>평균 확신 {conf:.2f}</title></line>')
        body.append(_text(x0 + pw + 12, cy - 2, f"정답률 {acc:.1%} · 평균 확신 {conf:.2f}", 12, INK, weight=700))
        body.append(_text(x0 + pw + 12, cy + 14, f"틀렸는데 0.9 이상: {bad_hi}건", 12, ORANGE if bad_hi else MUTED))
        y += 44
    for v in (0.25, 0.5, 0.75, 1.0):
        x = x0 + pw * (v - lo) / (1 - lo)
        body.append(_text(x, y + 12, f"{v:.2f}", 11, MUTED, "middle"))
    body.append(_text(x0 + pw / 2, y + 28, "고른 답에 모델이 붙인 확률", 11.5, MUTED, "middle"))
    svg = _svg(W + 150, y + 34, "".join(body), "route 질문의 확신과 정답 여부")
    display(HTML(_card(_legend([(GREEN, "맞힌 답", "dot"), (ORANGE, "틀린 답", "x"), (INK, "평균 확신(세로선)", "line")]) + svg,
                       "보정 맛보기: 확률이 높으면 정말 맞았나? (route 질문 40건)",
                       "점 하나가 메시지 하나예요. 가로 위치 = 고른 답의 확률. 잘 보정됐다면 평균 확신(세로선)이 정답률과 비슷해야 해요.",
                       note=avl["route_calibration_note"] + ". 1강의 신뢰도 그림(reliability diagram)·ECE를 제대로 그리려면 수백 건이 필요해요.",
                       width=910)))


def chart_rlcr_rlcd(rr):
    """같은 RLCR 7B 가중치: 추론·답·확신도를 글로 쓰기(RLCR) vs 보기 점수 읽기(RLCD)."""
    W, lab = 760, 250
    rows = [("글로 쓰기 (RLCR 원래 방식)", rr["rlcr"], ORANGE),
            ("점수 읽기 (같은 모델 + RLCD)", rr["rlcd"], GREEN)]
    body, y = [], 4
    body.append(_text(lab, y + 10, "필드 정답 (24개)", 12, MUTED, weight=700))
    body.append(_text(lab + 250, y + 10, "문의 1건 시간 (로그 눈금 · 점)", 12, MUTED, weight=700))
    y += 18
    for name, r, color in rows:
        body.append(_text(lab - 8, y + 15, name, 12, INK, "end"))
        w = 200 * r["field_correct"] / r["field_total"]
        body.append(_bar(lab, y + 4, w, 16, color, f"{name}: {r['field_correct']}/{r['field_total']}"))
        body.append(_text(lab + w + 6, y + 16, f"{r['field_correct']}/{r['field_total']}", 12, INK, weight=700))
        x1 = lab + 250
        lx = _logx(r["median_case_ms"], 100, 30000, x1, 200)
        body.append(f'<line x1="{x1:.1f}" x2="{lx:.1f}" y1="{y + 12}" y2="{y + 12}" stroke="{LINE}" stroke-width="2"/>')
        body.append(f'<circle cx="{lx:.1f}" cy="{y + 12}" r="6" fill="{color}" stroke="#fff" stroke-width="2"><title>{esc(name)}: {r["median_case_ms"] / 1000:.3f}초</title></circle>')
        body.append(_text(lx + 10, y + 16, f"{r['median_case_ms'] / 1000:.2f}초", 12, INK, weight=700))
        y += 30
    for v, t in ((100, "0.1초"), (1000, "1초"), (10000, "10초")):
        x = _logx(v, 100, 30000, lab + 250, 200)
        body.insert(0, f'<line x1="{x:.1f}" x2="{x:.1f}" y1="18" y2="{y}" stroke="{LINE}" stroke-width="1"/>')
        body.append(_text(x, y + 13, t, 11, MUTED, "middle"))
    svg = _svg(W, y + 20, "".join(body), "RLCR과 RLCD 비교")
    wrong = "; ".join(f"{w['case']} {w['field']}: 정답 {w['expected']} → RLCD {w['rlcd_prediction']} <b>{w['rlcd_confidence']:.2f}</b> "
                      f"(RLCR은 {w['rlcr_prediction']}, 확신도 {w['rlcr_confidence']:.1f})" for w in rr["rlcd_wrong"])
    ratio = rr["rlcr"]["median_case_ms"] / rr["rlcd"]["median_case_ms"]
    display(HTML(_card(svg, "같은 가중치, 출력 방식만 다르게: RLCR 생성 vs RLCD 읽기 (강사 A4000, 이미 잰 값)",
                       rr["setup"] + " · 문의 1건 = 필드 3개(category · urgent · priority)",
                       note=f"점수 읽기가 {ratio:.0f}배 빨랐지만 필드 2개를 틀렸어요. 틀린 두 건의 확률이 높았다는 게 중요해요: {wrong}. "
                            "<b>높은 softmax 확률이 정답을 보장하지 않아요.</b> 문의 8건짜리 작은 실험이라 보정 우열을 말하기엔 부족해요.",
                       width=760)))


# ─────────────────────────── 10장: Jev-Omni ───────────────────────────
def omni_files_table(omni):
    gb = lambda b: f"{b / 1e9:.1f}GB" if b >= 1e8 else f"{b / 1e6:.1f}MB"
    labels = {"backbone": "backbone/ (FP32 본체, 13조각)", "unified": "unified/ (BF16 합친 모델)", "head.pt": "head.pt (256칸 판단 머리)",
              "assets": "assets/ (그림·데모 영상)", "기타 작은 파일": "토크나이저·설정·코드"}
    rows = [[labels.get(k, k), gb(v)] for k, v in sorted(omni["files_bytes"].items(), key=lambda kv: -kv[1])]
    rows.append(["저장소 전체 (snapshot_download가 받는 양)", gb(omni["repo_total_bytes"])])
    rows.append(["+ google/gemma-4-12B-it (로더가 추가로 받음)", gb(omni["gemma_total_bytes"])])
    rows.append(["합계", gb(omni["repo_total_bytes"] + omni["gemma_total_bytes"])])
    display(HTML(_card(_table(["파일", "크기"], rows, (1,)), "Jev-Omni가 받는 파일 (메타데이터로만 확인)",
                       f"akhilaaa3/Jev-Omni @ {omni['repo_sha'][:7]} · {omni['fetched_at']} 조회 · 가중치는 받지 않았어요",
                       note="공식 로더는 FP32 본체(약 48GB)를 GPU에 통째로 올린 뒤 BF16으로 바꾸고, Gemma 4 12B(약 24GB)를 또 올려요. "
                            "그래서 <b>80GB GPU(A100 80GB·H100)</b>가 필요해요. 무료 T4(15GB)·L4(24GB)·A100 40GB로는 그대로 안 돌아가요.",
                       width=640)))


def chart_omni_verification(omni):
    cases = omni["verification_cases"]
    die, urn = cases[2], cases[3]

    def bars(case, ideal, title):
        W, H, x0, bw, gap, ph = 440, 190, 34, 34, 14, 130
        body = []
        mx = 0.5
        for v in (0, 0.25, 0.5):
            y = 10 + ph * (1 - v / mx)
            body.append(f'<line x1="{x0}" x2="{W - 8}" y1="{y:.1f}" y2="{y:.1f}" stroke="{LINE}" stroke-width="1"/>')
            body.append(_text(x0 - 5, y + 4, f"{v:.2f}", 10.5, MUTED, "end"))
        for i, (o, p) in enumerate(zip(case["options"], case["probabilities"])):
            x = x0 + 10 + i * (bw + gap)
            h = ph * p / mx
            body.append(f'<path d="M{x},{10 + ph} v{-(h - 4):.1f} a4,4 0 0 1 4,-4 h{bw - 8} a4,4 0 0 1 4,4 v{h - 4:.1f} z" fill="{GREEN}"><title>{esc(o)}: {p:.3f}</title></path>')
            body.append(_text(x + bw / 2, 10 + ph - h - 5, f"{p:.2f}", 11, INK, "middle"))
            body.append(_text(x + bw / 2, 10 + ph + 15, o, 11.5, INK, "middle"))
        iy = 10 + ph * (1 - ideal / mx)
        body.append(f'<line x1="{x0}" x2="{W - 8}" y1="{iy:.1f}" y2="{iy:.1f}" stroke="{ORANGE}" stroke-width="2"/>')
        body.append(_text(W - 8, iy - 5, f"공정하면 {ideal:.3f}", 11, ORANGE, "end", 700))
        return f'<div style="flex:1 1 340px"><div style="font-size:13px;font-weight:700">{esc(title)}</div>{_svg(W, H + 12, "".join(body), title)}</div>'

    tiles = ""
    for c, label in ((cases[0], "10시 회의, 지금 9시 — 시작했나?"), (cases[1], "환불 끝, 고객 '해결됐어요' — 해결됐나?")):
        k = max(range(len(c["probabilities"])), key=c["probabilities"].__getitem__)
        tiles += (f'<div style="background:{LIGHT};border-radius:8px;padding:8px 12px;flex:1 1 200px"><div style="font-size:12px;color:{MUTED}">{esc(label)}</div>'
                  f'<div style="font-size:22px;font-weight:700">{esc(c["options"][k])} {c["probabilities"][k]:.4f}</div></div>')
    inner = (f'<div style="display:flex;flex-wrap:wrap;gap:12px">{bars(die, 1 / 6, "주사위 한 번: 몇이 나올까?")}{bars(urn, 0.25, "구슬 4개 중 하나: 무슨 색?")}</div>'
             f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:8px">{tiles}</div>')
    claims = omni["readme_claims"]
    display(HTML(_card(inner, "Jev-Omni 자체 검증 기록 읽기 (우리가 돌린 게 아니에요)",
                       "unified/verification_unified.json의 reference 확률 · 모델 저장소가 스스로 올린 값",
                       note=f"정답이 있는 질문(회의·환불)은 잘 맞히지만, <b>정답이 없는 질문</b>(공정한 주사위·구슬)에서는 확률이 고르게 퍼지지 않아요 — "
                            f"주사위 '6'에 {die['probabilities'][5]:.2f}, '3'에 {die['probabilities'][2]:.2f}. README가 말하는 ECE {claims['decisionbench_medium_ece']:.3f}"
                            f"(DecisionBench Medium)는 '정답이 있는 문제' 기준이라 이런 경우를 보장하지 않아요. 보정은 내 데이터로 다시 재 봐야 해요.",
                       width=780)))
