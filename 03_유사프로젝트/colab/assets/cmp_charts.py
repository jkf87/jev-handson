# 비교 그림 도우미(5장): 인터넷(CDN) 없이 브라우저에서 바로 그려지는 SVG/HTML만 써요. 한글은 브라우저 글꼴로 나와요.
# 색: 강의 덱과 같아요(잉크 #19272D · 초록 #466A62 · 주황 #AA5238 · 연한 바탕 #F0F5F2 · 선 #D6DED9).
# - 막대·점은 모두 한 가지 초록(시스템 이름은 축 글자로 구분), 주황은 '찍기 기준선'과 '보정 차이' 같은 참고선에만 써요.
# - 칸 색(혼동 행렬 · 일치율)은 초록 한 색의 밝기 단계예요. 칸 안 숫자는 칸 밝기에 따라 잉크/흰색으로 바꿔요.
# - 마우스를 올리면 값이 떠요(SVG <title>). 모든 값은 카드 아래 '숫자 표로 보기'에도 있어요.
import html
import math

from IPython.display import HTML, display

INK, GREEN, ORANGE, LIGHT, LINE = "#19272D", "#466A62", "#AA5238", "#F0F5F2", "#D6DED9"
MUTED, FAINT = "#5E6E68", "#8A9691"
FONT = "'Noto Sans KR','Noto Sans CJK KR','Apple SD Gothic Neo','Malgun Gothic','Nanum Gothic',system-ui,sans-serif"
RAMP = ["#e2f3ef", "#abc3bd", "#76958e", "#446a61", "#0e4138"]   # 초록 한 색, 밝음 → 어두움(OKLab 보간)


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
            f'padding:14px 16px;max-width:{width}px;box-sizing:border-box;line-height:1.5;margin:4px 0">{head}{inner}{foot}{tbl}</div>')


def _table(headers, rows, num_cols=(), bold_first=False):
    th = "".join(f'<th style="text-align:{"right" if i in num_cols else "left"};border-bottom:1px solid {LINE};padding:4px 8px;'
                 f'font-weight:600;white-space:nowrap">{esc(h)}</th>' for i, h in enumerate(headers))
    body = ""
    for r in rows:
        tds = []
        for i, v in enumerate(r):
            weight = "font-weight:600;" if (bold_first and i == 0) else ""
            tds.append(f'<td style="text-align:{"right" if i in num_cols else "left"};border-bottom:1px solid {LINE};padding:3px 8px;'
                       f'{weight}font-variant-numeric:tabular-nums;white-space:nowrap">{esc(v)}</td>')
        body += "<tr>" + "".join(tds) + "</tr>"
    return f'<div style="overflow-x:auto"><table style="border-collapse:collapse;margin-top:6px;font-size:12.5px">{"<tr>" + th + "</tr>"}{body}</table></div>'


def _legend(items):
    parts = []
    for color, label, shape in items:
        if shape == "line":
            sw = f'<span style="display:inline-block;width:16px;height:2px;background:{color};vertical-align:3px;margin-right:5px"></span>'
        elif shape == "hair":
            sw = f'<span style="display:inline-block;width:16px;height:0;border-top:1px solid {color};vertical-align:4px;margin-right:5px"></span>'
        else:
            sw = (f'<span style="display:inline-block;width:10px;height:10px;border-radius:{50 if shape == "dot" else 3}%;'
                  f'background:{color};margin-right:5px;vertical-align:-1px"></span>')
        parts.append(f'<span style="margin-right:14px;white-space:nowrap">{sw}{esc(label)}</span>')
    return f'<div style="font-size:12.5px;color:{MUTED};margin:2px 0 6px">{"".join(parts)}</div>'


def _svg(w, h, body, label):
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px;display:block;overflow:visible" role="img" '
            f'aria-label="{esc(label)}" xmlns="http://www.w3.org/2000/svg" font-family="{FONT}">{body}</svg>')


def _text(x, y, s, size=12, color=INK, anchor="start", weight=400):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color}" text-anchor="{anchor}" '
            f'font-weight="{weight}">{esc(s)}</text>')


def _hbar(x, y, w, h, color, title=None):
    """가로 막대: 오른쪽 끝만 4px 둥글게(바닥 쪽은 각지게)."""
    w = max(w, 0.0)
    r = min(4.0, w / 2, h / 2)
    if w < 5:
        d = f"M{x:.1f},{y:.1f} h{w:.1f} v{h:.1f} h{-w:.1f} z"
    else:
        d = (f"M{x:.1f},{y:.1f} h{w - r:.1f} a{r},{r} 0 0 1 {r},{r} v{h - 2 * r:.1f} "
             f"a{r},{r} 0 0 1 {-r},{r} h{-(w - r):.1f} z")
    t = f"<title>{esc(title)}</title>" if title else ""
    return f'<path d="{d}" fill="{color}">{t}</path>'


def _vbar(x, y_base, w, h, color, title=None):
    """세로 막대: 위쪽 끝만 4px 둥글게."""
    h = max(h, 0.0)
    r = min(4.0, w / 2, h / 2)
    y = y_base - h
    if h < 5:
        d = f"M{x:.1f},{y_base:.1f} v{-h:.1f} h{w:.1f} v{h:.1f} z"
    else:
        d = (f"M{x:.1f},{y_base:.1f} v{-(h - r):.1f} a{r},{r} 0 0 1 {r},{-r} h{w - 2 * r:.1f} "
             f"a{r},{r} 0 0 1 {r},{r} v{h - r:.1f} z")
    t = f"<title>{esc(title)}</title>" if title else ""
    return f'<path d="{d}" fill="{color}">{t}</path>'


def _ramp(t):
    """0~1 → 초록 단계 색(단계 사이는 선형 보간)."""
    t = min(1.0, max(0.0, t))
    pos = t * (len(RAMP) - 1)
    i = min(int(pos), len(RAMP) - 2)
    f = pos - i
    a, b = RAMP[i], RAMP[i + 1]
    ch = [round(int(a[k:k + 2], 16) * (1 - f) + int(b[k:k + 2], 16) * f) for k in (1, 3, 5)]
    return "#" + "".join(f"{c:02x}" for c in ch)


def _ink_on(t):
    return "#ffffff" if t >= 0.55 else INK


def _pct(v, digits=1):
    return "–" if v is None else f"{v * 100:.{digits}f}%"


# ───────────────── 표: 정확도 · 보정 / 속도 · 비용 ─────────────────
def table_scores(M, META, names, order, common_n, wilson):
    rows = []
    for s in order:
        m = M[s]
        lo, hi = wilson(round(m["accuracy"] * m["n"]), m["n"])
        rows.append([names[s], META[s].get("model", "-"), m["n"], f"{m['accuracy']:.1%}", f"{lo:.0%}~{hi:.0%}",
                     f"{m['macro_f1']:.3f}", (f"{m['toxic_precision']:.1%}" if m["hidden"] else "– (숨김 0)"), f"{m['toxic_recall']:.1%}", f"{m['toxic_f1']:.3f}",
                     f"{m['ece']:.3f}", f"{m['brier']:.3f}", f"{m['mean_conf']:.2f}"])
    t = _table(["시스템", "모델", "건수", "3분류 정확도", "95% 구간", "macro-F1", "악플 정밀도", "악플 재현율", "악플 F1",
                "ECE", "Brier", "평균 확신"], rows, num_cols=range(2, 12), bold_first=True)
    display(HTML(_card(t, "① 정확도와 보정 — 모두가 판정한 같은 댓글 " + f"{common_n}건",
                       "악플 = offensive + hate. 악플 확률(offensive + hate) ≥ 0.5면 '숨김'으로 셌어요(1강 코드와 같은 규칙). "
                       "ECE·Brier는 고른 보기의 확률로 계산했고 작을수록 좋아요.", width=900)))


def table_speed(M, META, names, order, price_per_token):
    rows = []
    for s in order:
        m, meta = M[s], META[s]
        run_s = meta.get("run_s")
        prep = meta.get("prep_s")
        if s == "jev":
            per_item_cost = (meta.get("cost_usd") or 0) / max(meta.get("n", 1), 1)
            cost = f"${per_item_cost * 1000:.3f}"
        else:
            cost = "$0 (로컬)"
        rows.append([names[s], meta.get("device", "-"), meta.get("dtype") or "-", f"{m['ms_mean']:,.0f}", f"{m['ms_median']:,.0f}",
                     "-" if run_s is None else f"{run_s:,.1f}", "-" if prep is None else f"{prep:,.0f}",
                     meta.get("size", "-"), cost])
    t = _table(["시스템", "어디서", "숫자 형식", "한 건 평균 ms", "중앙값 ms", "판정 전체 초", "준비 초(받기+올리기)", "모델 크기", "1,000건 비용"],
               rows, num_cols=(3, 4, 5, 6), bold_first=True)
    display(HTML(_card(t, "② 속도 · 비용", "한 건 ms = 댓글 하나를 판정하는 데 걸린 시간(Jev는 네트워크 포함, 8개씩 동시에 보냄). "
                       "준비 초 = 모델 받기 + 메모리에 올리기. Jev 비용은 입력 100만 토큰당 $0.042로 셌어요. 로컬은 API 비용이 없는 대신 GPU 시간 · 전기가 들어요.", width=900)))


def table_own(M_own, names, order, sample_n):
    """참고 표: 공통 댓글로 줄이기 전, 시스템마다 자기가 판정한 전부로 잰 값."""
    rows = [[names[s], M_own[s]["n"], f"{M_own[s]['accuracy']:.1%}", f"{M_own[s]['macro_f1']:.3f}", f"{M_own[s]['toxic_f1']:.3f}",
             f"{M_own[s]['ece']:.3f}"] for s in order]
    t = _table(["시스템", "판정 건수", "3분류 정확도", "macro-F1", "악플 F1", "ECE"], rows, num_cols=(1, 2, 3, 4, 5), bold_first=True)
    display(HTML(_card(t, f"참고 · 각자 판정한 전부로 잰 값 (표본 {sample_n}건)",
                       "건수가 다르면 댓글 묶음이 달라서 서로 바로 비교하면 안 돼요. 공정한 비교는 위 ① 표예요.", width=640)))


# ───────────────── 그림 1: 정확도 · macro-F1 · 악플 F1 ─────────────────
def chart_scores(M, names, order, baselines, wilson):
    panels = [("accuracy", "3분류 정확도", True), ("macro_f1", "macro-F1 (세 라벨 평균)", False), ("toxic_f1", "악플 거르기 F1", False)]
    lab_w, gap, pw = 78, 34, 196
    row_h, top = 34, 44
    W = lab_w + 3 * pw + 2 * gap + 12
    H = top + row_h * len(order) + 24
    body = []
    for pi, (key, title, is_pct) in enumerate(panels):
        x0 = lab_w + pi * (pw + gap)
        body.append(_text(x0, 13, title, 12.5, INK, weight=700))
        for tick, anchor in ((0, "start"), (0.5, "middle"), (1.0, "end")):
            tx = x0 + pw * tick
            body.append(f'<line x1="{tx:.1f}" x2="{tx:.1f}" y1="{top - 6}" y2="{H - 20}" stroke="{LINE}" stroke-width="1"/>')
            body.append(_text(tx, H - 6, f"{tick:.0%}" if is_pct else f"{tick:.1f}", 10.5, FAINT, anchor))
        base = baselines.get(key)
        if base is not None:
            bx = x0 + pw * base
            body.append(f'<line x1="{bx:.1f}" x2="{bx:.1f}" y1="{top - 10}" y2="{H - 20}" stroke="{ORANGE}" stroke-width="1.5">'
                        f'<title>{esc(baselines["_label"][key])}</title></line>')
            txt = f"찍기 {base:.0%}" if is_pct else f"찍기 {base:.2f}"
            right = bx + 4 + 7 * len(txt) > x0 + pw          # 패널 오른쪽을 넘으면 선 왼쪽에 써요
            body.append(_text(bx - 4 if right else bx + 4, top - 12, txt, 10.5, ORANGE, "end" if right else "start", 700))
        for ri, s in enumerate(order):
            m = M[s]
            v = m[key]
            y = top + ri * row_h + 4
            if pi == 0:
                body.append(_text(lab_w - 10, y + 13, names[s], 13, INK, "end", 700))
            tip = f"{names[s]} · {title} {v:.1%}" if is_pct else f"{names[s]} · {title} {v:.3f}"
            body.append(_hbar(x0, y, pw * v, 18, GREEN, tip))
            end = v
            if key == "accuracy":                       # 95% 구간(표본이 작으면 넓어요)
                lo, hi = wilson(round(v * m["n"]), m["n"])
                end = max(v, hi)
                cy = y + 9
                body.append(f'<g stroke="{INK}" stroke-width="1.2" opacity="0.55"><title>95% 구간 {lo:.0%}~{hi:.0%}</title>'
                            f'<line x1="{x0 + pw * lo:.1f}" x2="{x0 + pw * hi:.1f}" y1="{cy}" y2="{cy}"/>'
                            f'<line x1="{x0 + pw * lo:.1f}" x2="{x0 + pw * lo:.1f}" y1="{cy - 4}" y2="{cy + 4}"/>'
                            f'<line x1="{x0 + pw * hi:.1f}" x2="{x0 + pw * hi:.1f}" y1="{cy - 4}" y2="{cy + 4}"/></g>')
            label = f"{v:.0%}" if is_pct else f"{v:.2f}"
            lx = x0 + pw * end + 5
            if lx > x0 + pw - 28:                       # 끝에 붙어 넘치면 막대 안쪽(흰 글씨)으로
                body.append(_text(x0 + pw * v - 5, y + 13, label, 11.5, "#ffffff", "end", 700))
            else:
                body.append(_text(lx, y + 13, label, 11.5, INK, "start", 700))
    svg = _svg(W, H, "".join(body), "시스템별 3분류 정확도, macro-F1, 악플 F1")
    rows = [[names[s], f"{M[s]['accuracy']:.1%}", f"{M[s]['macro_f1']:.3f}", f"{M[s]['toxic_f1']:.3f}"] for s in order]
    rows.append(["찍기 기준선", f"{baselines['accuracy']:.1%}", f"{baselines['macro_f1']:.3f}", f"{baselines['toxic_f1']:.3f}"])
    legend = _legend([(GREEN, "시스템 점수", "sq"), (INK, "정확도 95% 구간", "hair"), (ORANGE, "찍기 기준선(생각 없이 찍으면)", "line")])
    display(HTML(_card(legend + svg, "그림 1 · 얼마나 맞히나",
                       "같은 댓글 · 같은 라벨 정의. 가는 가로줄은 정확도의 95% 구간(표본이 작을수록 넓어요).",
                       baselines["_note"], _table(["시스템", "3분류 정확도", "macro-F1", "악플 F1"], rows, (1, 2, 3)), width=W + 34)))


# ───────────────── 그림 2: 한 건 판정 시간(로그 눈금) ─────────────────
def chart_speed(M, META, names, order):
    lab_w, pw, row_h, top = 150, 470, 34, 20
    W = lab_w + pw + 110
    H = top + row_h * len(order) + 30
    lo, hi = 1.0, 4.0                                   # 10ms ~ 10초(로그)

    def lx(ms):
        v = math.log10(max(ms, 10 ** lo))
        return lab_w + pw * (min(v, hi) - lo) / (hi - lo)

    body = []
    for t, lab in ((10, "10ms"), (100, "0.1초"), (1000, "1초"), (10000, "10초")):
        x = lx(t)
        body.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{top - 6}" y2="{H - 24}" stroke="{LINE}" stroke-width="1"/>')
        body.append(_text(x, H - 8, lab, 10.5, FAINT, "middle"))
    for ri, s in enumerate(order):
        m, meta = M[s], META[s]
        cy = top + ri * row_h + 12
        body.append(_text(lab_w - 10, cy + 4, names[s], 13, INK, "end", 700))
        body.append(_text(lab_w - 10, cy + 17, meta.get("where_short", ""), 10.5, MUTED, "end"))
        x = lx(m["ms_mean"])
        body.append(f'<line x1="{lab_w}" x2="{x:.1f}" y1="{cy}" y2="{cy}" stroke="{LINE}" stroke-width="2"/>')
        tip = f"{names[s]} · 한 건 평균 {m['ms_mean']:,.0f}ms (중앙값 {m['ms_median']:,.0f}ms)"
        body.append(f'<g><title>{esc(tip)}</title><circle cx="{x:.1f}" cy="{cy}" r="12" fill="transparent"/>'
                    f'<circle cx="{x:.1f}" cy="{cy}" r="6" fill="{GREEN}" stroke="#fff" stroke-width="2"/></g>')
        ms = m["ms_mean"]
        body.append(_text(x + 11, cy + 4, f"{ms:,.0f}ms" if ms < 1000 else f"{ms / 1000:.1f}초", 12, INK, "start", 700))
    svg = _svg(W, H, "".join(body), "시스템별 한 건 판정 시간(로그 눈금)")
    rows = [[names[s], META[s].get("where_short", ""), f"{M[s]['ms_mean']:,.0f}", f"{M[s]['ms_median']:,.0f}"] for s in order]
    display(HTML(_card(svg, "그림 2 · 한 건에 얼마나 걸리나 (가로축은 로그 눈금: 한 칸 = 10배)",
                       "점 = 댓글 하나 판정의 평균 시간. 모델 받기·올리기 시간은 빠져 있어요(표 ②).",
                       "Jev는 네트워크 왕복이 들어 있고 8개씩 동시에 보내서, 전체 시간은 한 건 시간 × 건수보다 훨씬 짧아요. "
                       "로컬 모델은 GPU 한 장에서 한 건씩 차례로 돌렸어요.",
                       _table(["시스템", "어디서", "평균 ms", "중앙값 ms"], rows, (2, 3)), width=W + 34)))


# ───────────────── 그림 3: 신뢰도 그림(보정) ─────────────────
def chart_reliability(M, names, order):
    cols = 2 if len(order) > 1 else 1
    pw, ph, gx, gy = 300, 190, 60, 70
    x_pad, y_pad = 40, 40
    W = x_pad + cols * pw + (cols - 1) * gx + 10
    nrows = math.ceil(len(order) / cols)
    H = y_pad + nrows * ph + (nrows - 1) * gy + 36
    body = []
    table_rows = []
    for k, s in enumerate(order):
        m = M[s]
        c, r = k % cols, k // cols
        x0 = x_pad + c * (pw + gx)
        y0 = y_pad + r * (ph + gy)
        body.append(_text(x0, y0 - 22, names[s], 13, INK, "start", 700))
        body.append(_text(x0, y0 - 7, f"ECE {m['ece']:.3f} · 평균 확신 {m['mean_conf']:.2f} · 정답률 {m['accuracy']:.0%}", 11, MUTED))

        def X(v):
            return x0 + pw * v

        def Y(v):
            return y0 + ph * (1 - v)

        for t in (0, 0.5, 1.0):
            body.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{y0}" y2="{y0 + ph}" stroke="{LINE}" stroke-width="1"/>')
            body.append(f'<line x1="{x0}" x2="{x0 + pw}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="{LINE}" stroke-width="1"/>')
            body.append(_text(X(t), y0 + ph + 14, f"{t:.1f}", 10, FAINT, "middle"))
            body.append(_text(x0 - 6, Y(t) + 3, f"{t:.1f}", 10, FAINT, "end"))
        body.append(f'<line x1="{X(0):.1f}" y1="{Y(0):.1f}" x2="{X(1):.1f}" y2="{Y(1):.1f}" stroke="{FAINT}" stroke-width="1"/>')
        pts = [(lo_, hi_, n, cf, ac) for lo_, hi_, n, cf, ac in m["reliability"] if n]
        nmax = max((p[2] for p in pts), default=1)
        for lo_, hi_, n, cf, ac in pts:
            body.append(f'<line x1="{X(cf):.1f}" x2="{X(cf):.1f}" y1="{Y(cf):.1f}" y2="{Y(ac):.1f}" stroke="{ORANGE}" stroke-width="2"/>')
        if len(pts) > 1:
            d = " ".join(f"{'M' if i == 0 else 'L'}{X(cf):.1f},{Y(ac):.1f}" for i, (_, _, _, cf, ac) in enumerate(pts))
            body.append(f'<path d="{d}" fill="none" stroke="{GREEN}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" opacity="0.6"/>')
        for lo_, hi_, n, cf, ac in pts:
            rad = 4 + 6 * math.sqrt(n / nmax)
            tip = f"{names[s]} · 확신 {lo_:.1f}~{hi_:.1f} 칸: {n}건 · 평균 확신 {cf:.2f} · 실제 정답률 {ac:.0%}"
            body.append(f'<g><title>{esc(tip)}</title><circle cx="{X(cf):.1f}" cy="{Y(ac):.1f}" r="{max(rad, 12):.1f}" fill="transparent"/>'
                        f'<circle cx="{X(cf):.1f}" cy="{Y(ac):.1f}" r="{rad:.1f}" fill="{GREEN}" stroke="#fff" stroke-width="2"/></g>')
            table_rows.append([names[s], f"{lo_:.1f}~{hi_:.1f}", n, f"{cf:.2f}", f"{ac:.0%}"])
        if r == nrows - 1:
            body.append(_text(x0 + pw / 2, y0 + ph + 30, "고른 보기의 확률(확신)", 11, MUTED, "middle"))
        if c == 0:
            body.append(f'<text x="{x0 - 30}" y="{y0 + ph / 2:.1f}" font-size="11" fill="{MUTED}" text-anchor="middle" '
                        f'transform="rotate(-90 {x0 - 30} {y0 + ph / 2:.1f})">실제 정답률</text>')
    svg = _svg(W, H, "".join(body), "시스템별 신뢰도 그림")
    legend = _legend([(GREEN, "확신 칸마다 실제 정답률(점이 클수록 건수가 많음)", "dot"), (FAINT, "완벽한 보정(대각선)", "hair"),
                      (ORANGE, "말한 확신과 실제의 차이", "line")])
    display(HTML(_card(legend + svg, "그림 3 · '0.9라고 하면 열에 아홉은 맞나?' — 신뢰도 그림",
                       "고른 보기의 확률을 0.1 간격 10칸으로 나눠, 칸마다 실제로 맞힌 비율을 찍었어요. 대각선에 붙을수록 잘 보정된 거예요.",
                       "점이 대각선 <b>아래</b>에 있으면 과신(말한 것보다 덜 맞음), <b>위</b>면 과소신이에요. "
                       "보기가 3개라 확신은 1/3 아래로 내려가지 않아요. 한 칸에 몇 건 없으면 점이 크게 흔들려요.",
                       _table(["시스템", "확신 칸", "건수", "평균 확신", "실제 정답률"], table_rows, (2, 3, 4)), width=W + 34)))


# ───────────────── 그림 4: 혼동 행렬 ─────────────────
def chart_confusion(M, names, order, labels, label_ko):
    cell, gap = 46, 2
    lab_w, top = 52, 44
    pw = lab_w + 3 * (cell + gap)
    per_row = min(len(order), 4)
    W = per_row * (pw + 26)
    nrows = math.ceil(len(order) / per_row)
    ph = top + 3 * (cell + gap) + 30
    H = nrows * ph + 6
    body, table_rows = [], []
    for k, s in enumerate(order):
        conf = M[s]["confusion"]
        c, r = k % per_row, k // per_row
        x0, y0 = c * (pw + 26), r * ph
        body.append(_text(x0 + lab_w, y0 + 14, names[s], 13, INK, "start", 700))
        for j, p in enumerate(labels):
            body.append(_text(x0 + lab_w + j * (cell + gap) + cell / 2, y0 + top - 6, label_ko[p], 11, MUTED, "middle"))
        for i, g in enumerate(labels):
            tot = sum(conf[g].values()) or 1
            yy = y0 + top + i * (cell + gap)
            body.append(_text(x0 + lab_w - 6, yy + cell / 2 + 4, label_ko[g], 11, MUTED, "end"))
            for j, p in enumerate(labels):
                n = conf[g][p]
                t = n / tot
                xx = x0 + lab_w + j * (cell + gap)
                tip = f"{names[s]} · 정답 {g} → 예측 {p}: {n}건 (정답 {g}의 {t:.0%})"
                body.append(f'<g><title>{esc(tip)}</title><rect x="{xx}" y="{yy}" width="{cell}" height="{cell}" rx="3" fill="{_ramp(t)}"/>'
                            f'{_text(xx + cell / 2, yy + cell / 2 + 4, n, 12, _ink_on(t), "middle", 700 if i == j else 400)}</g>')
                table_rows.append([names[s], g, p, n, f"{t:.0%}"])
        body.append(_text(x0 + lab_w + 1.5 * (cell + gap), y0 + top + 3 * (cell + gap) + 16, "예측 →", 10.5, FAINT, "middle"))
    svg = _svg(W, H, "".join(body), "시스템별 혼동 행렬")
    display(HTML(_card(svg, "그림 4 · 어디서 헷갈리나 — 혼동 행렬 (행 = 정답, 열 = 예측)",
                       "칸 숫자 = 건수, 칸 색 = 그 정답 줄에서 차지하는 비율(진할수록 많음). 대각선(굵은 숫자)이 맞힌 것이에요.",
                       "정상 = none · 공격 = offensive · 혐오 = hate. 한 열에 색이 몰려 있으면, 그 시스템이 거의 한 라벨만 고른다는 뜻이에요.",
                       _table(["시스템", "정답", "예측", "건수", "정답 줄 대비"], table_rows, (3, 4)), width=max(W + 34, 420))))


# ───────────────── 그림 5: 서로 얼마나 같은 답을 냈나 ─────────────────
def chart_agreement(A, names, keys):
    cell, gap = 62, 2
    lab_w, top = 86, 30
    n = len(keys)
    W = lab_w + n * (cell + gap) + 10
    H = top + n * (cell + gap) + 8
    body, rows = [], []
    for j, b in enumerate(keys):
        body.append(_text(lab_w + j * (cell + gap) + cell / 2, top - 10, names[b], 11.5, INK, "middle", 700))
    for i, a in enumerate(keys):
        yy = top + i * (cell + gap)
        body.append(_text(lab_w - 8, yy + cell / 2 + 4, names[a], 11.5, INK, "end", 700))
        for j, b in enumerate(keys):
            xx = lab_w + j * (cell + gap)
            if i == j:
                body.append(f'<rect x="{xx}" y="{yy}" width="{cell}" height="{cell}" rx="3" fill="{LIGHT}"/>')
                continue
            v = A[a][b]
            tip = f"{names[a]} ↔ {names[b]}: 같은 라벨 {v:.0%}"
            body.append(f'<g><title>{esc(tip)}</title><rect x="{xx}" y="{yy}" width="{cell}" height="{cell}" rx="3" fill="{_ramp(v)}"/>'
                        f'{_text(xx + cell / 2, yy + cell / 2 + 4, f"{v:.0%}", 12, _ink_on(v), "middle", 600)}</g>')
            if j > i:
                rows.append([names[a], names[b], f"{v:.1%}"])
    svg = _svg(W, H, "".join(body), "시스템끼리, 그리고 정답과 같은 라벨을 고른 비율")
    display(HTML(_card(svg, "그림 5 · 서로 얼마나 같은 답을 냈나",
                       "칸 = 두 쪽이 같은 라벨을 고른 비율. '정답' 줄은 곧 3분류 정확도예요.",
                       "두 시스템이 서로는 많이 겹치는데 정답과는 덜 겹치면, 같은 방향으로 틀린다는 뜻이에요(같은 기반 모델 · 같은 지시문의 영향).",
                       _table(["A", "B", "같은 라벨"], rows, (2,)), width=max(W + 34, 420))))


# ───────────────── 그림 6: 몇 시스템이 맞혔나 ─────────────────
def chart_disagreement(dist, alone, allwrong_by_gold, names, order):
    k = len(order)
    lab_h, top, cw, gapx = 30, 22, 54, 26
    ph = 150
    W = 60 + (k + 1) * (cw + gapx)
    H = top + ph + lab_h + 10
    vmax = max(dist.values()) or 1
    body = []
    base_y = top + ph
    body.append(f'<line x1="50" x2="{W - 6}" y1="{base_y}" y2="{base_y}" stroke="{LINE}" stroke-width="1"/>')
    for c in range(k + 1):
        x = 60 + c * (cw + gapx)
        v = dist.get(c, 0)
        h = ph * v / vmax
        body.append(_vbar(x, base_y, cw, h, GREEN, f"{c}개 시스템이 맞힘: {v}건"))
        body.append(_text(x + cw / 2, base_y - h - 6, v, 12, INK, "middle", 700))
        body.append(_text(x + cw / 2, base_y + 16, f"{c}개", 11.5, MUTED, "middle"))
    body.append(_text(60 + (k + 1) * (cw + gapx) / 2 - gapx / 2, base_y + 32, "그 댓글을 맞힌 시스템 수", 11, MUTED, "middle"))
    svg = _svg(W, H, "".join(body), "댓글마다 맞힌 시스템 수의 분포")
    alone_rows = [[f"{names[s]}만 맞힘", alone.get(s, 0)] for s in order]
    alone_rows.append(["모두 틀림", dist.get(0, 0)])
    alone_rows.append(["모두 맞힘", dist.get(k, 0)])
    side = _table(["경우", "건수"], alone_rows, (1,), bold_first=True)
    gold_txt = " · ".join(f"{g} {n}건" for g, n in allwrong_by_gold.items() if n) or "없음"
    inner = (f'<div style="display:flex;flex-wrap:wrap;gap:18px;align-items:flex-start"><div style="flex:1 1 360px;min-width:300px">{svg}</div>'
             f'<div style="flex:0 1 220px">{side}</div></div>')
    display(HTML(_card(inner, "그림 6 · 어디서 갈리나 — 댓글마다 몇 시스템이 맞혔나",
                       f"막대 = 댓글 수. 오른쪽 표 = 한 시스템만 맞힌 댓글과 모두 틀린 댓글. 모두 틀린 댓글의 정답: {esc(gold_txt)}",
                       "댓글 글은 기본으로 가려요(실제 악플). 글까지 보려면 5-8 셀 첫 줄을 SHOW_TEXT_HERE = True로 바꿔 그 셀만 다시 실행해요.",
                       _table(["맞힌 시스템 수", "댓글 수"], [[c, dist.get(c, 0)] for c in range(k + 1)], (0, 1)), width=max(W + 280, 560))))
