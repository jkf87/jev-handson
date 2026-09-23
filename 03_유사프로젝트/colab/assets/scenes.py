"""3강 노트북용 짧은 설명 영상 3개 (Manim Community 0.21).

렌더 (1280x720, 30fps):
    manim -qm --disable_caching scenes.py GenerateVsRead SharedPrefix LogitsToProbs

숫자 출처
- GenerateVsRead: route-vague 케이스, A4000 실측 로짓 A 24.0 · B 24.5 → 0.38/0.62
  (~/jev/lecture-code/3강-오픈소스/openjev/results_a4000.jsonl).
  JSON 토큰 조각은 Qwen3.5-4B 토크나이저로 '{"choice": "main"}'을 실제로 자른 결과(assets/widget_fallback.json).
- SharedPrefix: llama.cpp parallel-decision, Qwen2.5-1.5B GGUF, 28필드 프리셋 3종
  (~/jev특강/output/parallel-decision-rlcd-20260922/README.md, timings.csv, summary.json).
- LogitsToProbs: classify-fail 케이스, A4000 실측 로짓 22.25 · 20.125 · 20.0 · 25.875.
"""
import math

from manim import (BOLD, DOWN, LEFT, RIGHT, UP, UL, WHITE, Arrow, Create, Dot, FadeIn, FadeOut,
                   Indicate, Line, MoveAlongPath, Rectangle, ReplacementTransform, RoundedRectangle, Scene,
                   Text, Transform, ValueTracker, VGroup, Write, always_redraw, config, rate_functions)

config.background_color = WHITE

INK, GREEN, ORANGE, LIGHT, LINE = "#19272D", "#466A62", "#AA5238", "#F0F5F2", "#D6DED9"
MUTED = "#5E6E68"
FONT, MONO = "Noto Sans CJK KR", "Menlo"


def T(text, size=26, color=INK, bold=False, font=FONT):
    # 작은 글씨를 그대로 그리면 Pango 자간이 틀어져요("JS ON"). 4배로 그린 뒤 줄여요.
    return Text(text, font=font, font_size=size * 4, color=color,
                weight=BOLD if bold else "NORMAL").scale(0.25)


def card(w, h, fill=LIGHT, stroke=LINE, width=2):
    return RoundedRectangle(corner_radius=0.14, width=w, height=h, fill_color=fill, fill_opacity=1,
                            stroke_color=stroke, stroke_width=width)


def softmax(values, temp=1.0):
    m = max(v / temp for v in values)
    e = [math.exp(v / temp - m) for v in values]
    s = sum(e)
    return [x / s for x in e]


def title(scene, main, sub):
    t = T(main, 34, INK, True).to_corner(UL, buff=0.45)
    s = T(sub, 19, GREEN).next_to(t, DOWN, aligned_edge=LEFT, buff=0.14)
    scene.play(FadeIn(t, shift=0.2 * DOWN), FadeIn(s), run_time=1.0)
    return VGroup(t, s)


def model_box(label, color=GREEN):
    box = card(1.7, 1.05, fill="#FFFFFF", stroke=color, width=3)
    txt = T(label, 22, color, True).move_to(box)
    return VGroup(box, txt)


def pass_through(scene, box, color, run_time=0.8):
    """모델 상자를 신호 하나가 지나가는 모습(= forward 1번)."""
    path = Line(box.get_left() + 0.05 * RIGHT, box.get_right() + 0.05 * LEFT)
    dot = Dot(color=color, radius=0.09).move_to(path.get_start())
    scene.add(dot)
    scene.play(MoveAlongPath(dot, path), box[0].animate.set_fill(color, opacity=0.18),
               run_time=run_time, rate_func=rate_functions.ease_in_out_sine)
    scene.play(box[0].animate.set_fill("#FFFFFF", opacity=1), FadeOut(dot), run_time=0.2)


class GenerateVsRead(Scene):
    def construct(self):
        title(self, "① 글로 답하기 vs 점수 읽기", "같은 질문을 두 방식으로 · 무엇을 출력하느냐의 차이")

        # 입력 카드
        inp = card(3.9, 3.7).move_to([-4.95, -0.55, 0])
        lines = VGroup(
            T("입력", 22, GREEN, True),
            T("상황", 17, MUTED), T("'just handle this for me'", 17, INK, font=MONO), T("(어디로 보낼지 안 적힘)", 16, MUTED),
            T("질문", 17, MUTED), T("어느 세션이 처리할까요?", 18),
            T("보기", 17, MUTED), T("A  a4000 · GPU 실험", 18), T("B  main · 일반 대화", 18),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.09)
        if lines.width > inp.width - 0.45:
            lines.scale_to_fit_width(inp.width - 0.45)
        lines.move_to(inp)
        self.play(FadeIn(inp), FadeIn(lines, lag_ratio=0.05), run_time=1.2)
        self.wait(1.0)

        # 두 갈래
        y1, y2 = 1.25, -2.05
        lab1 = T("일반 LLM · JSON을 한 토큰씩 생성", 19, ORANGE, True).move_to([1.6, y1 + 1.0, 0])
        lab2 = T("Jev 닮은 모델 · 보기 점수를 한 번에 읽기", 19, GREEN, True).move_to([1.6, y2 + 1.35, 0])
        box1 = model_box("LLM", ORANGE).move_to([-1.75, y1, 0])
        box2 = model_box("같은 LLM", GREEN).move_to([-1.75, y2, 0])
        a1 = Arrow(inp.get_right() + 0.4 * UP, box1.get_left(), buff=0.12, color=LINE, stroke_width=4)
        a2 = Arrow(inp.get_right() + 0.4 * DOWN, box2.get_left(), buff=0.12, color=LINE, stroke_width=4)
        c1 = ValueTracker(0)
        c2 = ValueTracker(0)
        cnt1 = always_redraw(lambda: T(f"통과 {int(round(c1.get_value()))}번", 18, ORANGE).next_to(box1, DOWN, buff=0.12))
        cnt2 = always_redraw(lambda: T(f"통과 {int(round(c2.get_value()))}번", 18, GREEN).next_to(box2, DOWN, buff=0.12))
        self.play(FadeIn(lab1), FadeIn(lab2), Create(a1), Create(a2), FadeIn(box1), FadeIn(box2),
                  FadeIn(cnt1), FadeIn(cnt2), run_time=1.2)

        # 첫 통과는 둘 다 같아요(입력 전체를 한 번 읽기)
        dots = []
        for box, color in ((box1, ORANGE), (box2, GREEN)):
            path = Line(box.get_left() + 0.05 * RIGHT, box.get_right() + 0.05 * LEFT)
            d = Dot(color=color, radius=0.09).move_to(path.get_start())
            dots.append((d, path))
        self.add(*[d for d, _ in dots])
        self.play(*[MoveAlongPath(d, p) for d, p in dots],
                  box1[0].animate.set_fill(ORANGE, opacity=0.18), box2[0].animate.set_fill(GREEN, opacity=0.18),
                  run_time=1.1)
        self.play(*[FadeOut(d) for d, _ in dots], box1[0].animate.set_fill("#FFFFFF", opacity=1),
                  box2[0].animate.set_fill("#FFFFFF", opacity=1), c1.animate.set_value(1), c2.animate.set_value(1),
                  run_time=0.3)

        # 아래 갈래: 마지막 자리에서 A/B 점수만 읽기 → softmax
        x0 = -0.35
        logits = [24.0, 24.5]
        probs = softmax(logits)
        bars, labels = VGroup(), VGroup()
        for i, (name, z) in enumerate(zip(["A", "B"], logits)):
            h = (z - 22.0) * 0.36
            bar = Rectangle(width=0.55, height=h, fill_color=LINE, fill_opacity=1, stroke_width=0)
            bar.move_to([x0 + 0.95 + i * 0.95, y2 - 0.45 + h / 2, 0])
            bars.add(bar)
            labels.add(T(f"{name} {z:.1f}", 16, INK).next_to(bar, DOWN, buff=0.08))
        read = T("마지막 자리의 A·B 점수", 16, MUTED).next_to(bars, UP, buff=0.14)
        self.play(FadeIn(bars, shift=0.2 * UP), FadeIn(labels), FadeIn(read), run_time=0.9)
        sm = Arrow([x0 + 2.55, y2 + 0.05, 0], [x0 + 3.55, y2 + 0.05, 0], buff=0, color=GREEN, stroke_width=4)
        smt = T("softmax", 16, GREEN, font=MONO).next_to(sm, UP, buff=0.06)
        pbars, plabels = VGroup(), VGroup()
        for i, (name, oid, p) in enumerate(zip(["A", "B"], ["a4000", "main"], probs)):
            w = 2.1 * p
            bar = Rectangle(width=max(w, 0.02), height=0.36, fill_color=GREEN if i == 1 else LINE,
                            fill_opacity=1, stroke_width=0)
            bar.move_to([x0 + 3.8 + w / 2, y2 + 0.35 - i * 0.55, 0])
            pbars.add(bar)
            plabels.add(T(f"{oid} {p:.2f}", 17, INK, i == 1).next_to(bar, RIGHT, buff=0.1))
        self.play(Create(sm), FadeIn(smt), run_time=0.5)
        self.play(*[FadeIn(b, shift=0.2 * RIGHT) for b in pbars], FadeIn(plabels), run_time=0.8)
        done2 = T("끝 · 보기 밖 답은 나올 수 없어요", 17, GREEN, True).move_to([x0 + 4.9, y2 - 0.75, 0])
        self.play(FadeIn(done2), run_time=0.5)
        self.wait(1.2)

        # 위 갈래: 토큰마다 한 번씩 통과 (Qwen3.5-4B 토크나이저로 자른 실제 조각)
        pieces = ['{"', 'choice', '":', ' "', 'main', '"}', '<끝>']
        chips = VGroup()
        cursor = [x0 + 0.2, y1 + 0.1, 0]
        for k, piece in enumerate(pieces):
            if k:
                pass_through(self, box1, ORANGE, run_time=0.62)
                self.play(c1.animate.set_value(k + 1), run_time=0.12)
            shown = piece.replace(" ", "␣")
            chip_t = T(shown, 18, INK, font=MONO if piece != '<끝>' else FONT)
            chip_b = card(chip_t.width + 0.26, 0.5, fill="#FBEDE7", stroke=ORANGE, width=2)
            chip = VGroup(chip_b, chip_t)
            chip_t.move_to(chip_b)
            if chips:
                chip.next_to(chips, RIGHT, buff=0.08)
            else:
                chip.move_to(cursor, aligned_edge=LEFT)
            chips.add(chip)
            self.play(FadeIn(chip, shift=0.15 * RIGHT), run_time=0.3)
        parse = T("→ 코드가 JSON을 다시 읽어 main 을 꺼내요", 17, ORANGE).next_to(chips, DOWN, aligned_edge=LEFT, buff=0.22)
        self.play(FadeIn(parse), run_time=0.6)
        self.wait(2.0)

        # 정리: 두 갈래를 지우고 요약만 남겨요
        self.play(FadeOut(VGroup(chips, parse, bars, labels, read, sm, smt, pbars, plabels, done2, a1, a2,
                                 box1, box2, lab1, lab2)), FadeOut(cnt1), FadeOut(cnt2), run_time=0.8)
        summary = card(8.4, 1.9, fill="#FFFFFF", stroke=INK, width=2).move_to([2.35, -0.45, 0])
        s1 = T("점수 읽기: 통과 1번 · 정해 둔 보기 중에서만 고름", 21, GREEN, True)
        s2 = T("JSON 생성: 답 토큰 수만큼 통과 · 형식이 깨질 수도 있음", 21, ORANGE, True)
        s3 = T("단, 이 0.62는 '보기끼리 비교한 점수'예요. 보정은 따로 봐요", 17, MUTED)
        sg = VGroup(s1, s2, s3).arrange(DOWN, aligned_edge=LEFT, buff=0.12).move_to(summary)
        self.play(FadeIn(summary), FadeIn(sg, lag_ratio=0.2), run_time=1.2)
        self.wait(5.0)


class SharedPrefix(Scene):
    def construct(self):
        title(self, "② 왜 빠른가: 공통 앞부분은 한 번, 질문은 나란히", "문의 1건에서 필드 28개를 판단 · llama.cpp parallel-decision 방식")

        # 긴 상황(state)
        st = card(2.7, 3.9).move_to([-5.45, -0.35, 0])
        head = T("문의 1건 (긴 상황)", 18, INK, True).next_to(st.get_top(), DOWN, buff=0.2)
        fake = VGroup(*[Rectangle(width=w, height=0.1, fill_color=LINE, fill_opacity=1, stroke_width=0)
                        for w in [2.2, 2.0, 2.25, 1.6, 2.1, 2.2, 1.8, 2.0, 1.4, 2.15, 1.9, 2.2, 1.7]])
        fake.arrange(DOWN, aligned_edge=LEFT, buff=0.14).next_to(head, DOWN, buff=0.22)
        self.play(FadeIn(st), FadeIn(head), FadeIn(fake, lag_ratio=0.05), run_time=1.1)

        model = model_box("LLM", GREEN).move_to([-2.55, 0.9, 0])
        a = Arrow(st.get_right() + 1.25 * UP, model.get_left(), buff=0.1, color=LINE, stroke_width=4)
        self.play(Create(a), FadeIn(model), run_time=0.6)
        pass_through(self, model, GREEN, run_time=1.0)
        cache = card(1.9, 0.72, fill="#E3ECE8", stroke=GREEN, width=2).move_to([-2.55, -0.55, 0])
        ctext = T("문맥 캐시", 18, GREEN, True).move_to(cache)
        once = T("앞부분 계산은 딱 1번", 16, GREEN).next_to(cache, DOWN, buff=0.1)
        self.play(FadeIn(cache, shift=0.2 * DOWN), FadeIn(ctext), FadeIn(once), run_time=0.8)
        self.wait(1.0)

        # 필드별 짧은 뒷부분을 나란히 (실제 A4000 결과 값)
        fields = [("감정", "매우 부정"), ("심각도", "SEV 0"), ("담당 부서", "인프라 SRE"),
                  ("SLA 위반 위험", "예"), ("환불 권고", "예"), ("보안 사고", "예")]
        branches, lines_ = VGroup(), VGroup()
        for i, (name, value) in enumerate(fields):
            y = 1.75 - i * 0.56
            c = card(3.35, 0.5, fill="#FFFFFF", stroke=LINE).move_to([0.95, y, 0])
            n = T(name, 16, INK).move_to(c).align_to(c, LEFT).shift(0.15 * RIGHT)
            v = T(value, 16, GREEN, True).move_to(c).align_to(c, RIGHT).shift(0.15 * LEFT)
            branches.add(VGroup(c, n, v))
            lines_.add(Line(cache.get_right(), c.get_left(), color=LINE, stroke_width=2))
        more = T("… 필드 28개", 16, MUTED).next_to(branches, DOWN, buff=0.12)
        self.play(*[Create(l) for l in lines_], run_time=0.6)
        self.play(*[FadeIn(b, shift=0.15 * RIGHT) for b in branches], FadeIn(more), run_time=0.9)
        par = T("질문+보기(짧은 뒷부분)만 나란히 계산", 17, GREEN, True).next_to(branches, UP, buff=0.18)
        self.play(FadeIn(par), *[Indicate(b[2], color=GREEN, scale_factor=1.12) for b in branches], run_time=1.0)
        self.wait(1.6)

        # 비교: JSON 생성은 필드를 차례로 한 글자씩
        rib = card(6.9, 1.35, fill="#FFFFFF", stroke=ORANGE).move_to([3.4, -2.75, 0])
        rl = T("JSON 생성: 필드 28개를 차례로 한 토큰씩", 17, ORANGE, True).next_to(rib.get_top(), DOWN, buff=0.12).align_to(rib, LEFT).shift(0.2 * RIGHT)
        js = '{"sentiment": "VERY_NEGATIVE", "severity_tier": "SEV_0_CRITICAL", "primary_department": ...'
        full = T(js, 14, INK, font=MONO)
        full.scale_to_fit_width(6.4).next_to(rl, DOWN, buff=0.16).align_to(rl, LEFT)
        self.play(FadeIn(rib), FadeIn(rl), run_time=0.5)
        self.play(Write(full), run_time=3.2, rate_func=rate_functions.linear)
        miss = T("이 실행에서는 필드 2개가 빠졌어요 (assigned_agent_tier · ticket_priority)", 14, ORANGE)
        miss.next_to(full, DOWN, buff=0.1).align_to(full, LEFT)
        self.play(FadeIn(miss), run_time=0.5)
        self.wait(1.8)

        # 실측 숫자
        box = card(6.4, 2.05, fill="#FFFFFF", stroke=INK, width=2).move_to([3.55, 0.55, 0])
        h = T("실측 (같은 Qwen2.5-1.5B GGUF · 28필드 프리셋 3종)", 17, INK, True)
        r1 = T("RTX A4000   병렬 판단 95~126ms   ·   JSON 2.1~2.3초", 17, INK)
        r2 = T("Mac M5      병렬 판단 0.41~0.61초 ·   JSON 6.5~7.5초", 17, INK)
        r3 = T("→ 12~22배 빠름. 단, 빠르다고 다 맞는 건 아니에요", 17, GREEN, True)
        g = VGroup(h, r1, r2, r3).arrange(DOWN, aligned_edge=LEFT, buff=0.13).move_to(box)
        self.play(FadeOut(branches), FadeOut(lines_), FadeOut(more), FadeOut(par), run_time=0.5)
        self.play(FadeIn(box), FadeIn(g, lag_ratio=0.15), run_time=1.1)
        self.wait(5.0)


class LogitsToProbs(Scene):
    def construct(self):
        title(self, "③ 점수(logit) → 확률: softmax와 온도", "classify-fail 케이스 · A4000 실측 점수")
        names = ["A transient", "B code", "C permission", "D unknown"]
        logits = [22.25, 20.125, 20.0, 25.875]
        base_y, x0, gap = -2.35, -4.6, 2.35
        scale = 0.42

        def bars_for(values, color_last=True, fmt="{:.2f}", top=None):
            group = VGroup()
            for i, v in enumerate(values):
                h = max(v, 0.0001) * (top if top else 1)
                bar = Rectangle(width=1.0, height=max(h, 0.02), fill_color=GREEN if (color_last and i == 3) else LINE,
                                fill_opacity=1, stroke_width=0)
                bar.move_to([x0 + i * gap, base_y + bar.height / 2, 0])
                val = T(fmt.format(v), 19, INK, i == 3).next_to(bar, UP, buff=0.08)
                group.add(VGroup(bar, val))
            return group

        labels = VGroup(*[T(n, 18, MUTED).move_to([x0 + i * gap, base_y - 0.32, 0]) for i, n in enumerate(names)])
        step = T("1) 모델이 낸 보기 글자 점수 (logit)", 21, INK, True).move_to([0, 2.0, 0])
        raw = bars_for([z - 18.0 for z in logits], fmt="{:.2f}", top=scale)
        for g, z in zip(raw, logits):
            g[1].become(T(f"{z:.3f}".rstrip("0").rstrip("."), 19, INK).next_to(g[0], UP, buff=0.08))
        base = T("막대 바닥 = 18 (차이가 잘 보이게 잘라 그렸어요)", 16, MUTED).next_to(step, DOWN, buff=0.15)
        self.play(FadeIn(labels), FadeIn(step), FadeIn(base), FadeIn(raw, shift=0.2 * UP), run_time=1.1)
        self.wait(1.6)

        shifted = [z - max(logits) for z in logits]
        step2 = T("2) 가장 큰 값을 빼요 (크기 비교만 남김)", 21, INK, True).move_to(step)
        sh = VGroup()
        for i, (g, v) in enumerate(zip(raw, shifted)):
            t = T(f"{v:+.2f}" if v else "0", 19, INK, i == 3).next_to(g[0], UP, buff=0.08)
            sh.add(t)
        why = T("모두 같은 값을 뺐으니 막대 모양은 그대로예요", 17, MUTED).next_to(step2, DOWN, buff=0.15)
        self.play(ReplacementTransform(step, step2), FadeOut(base), FadeIn(why), *[Transform(g[1], t) for g, t in zip(raw, sh)], run_time=1.0)
        self.wait(2.0)

        ex = [math.exp(v) for v in shifted]
        step3 = T("3) 지수 함수 e^x 로 바꿔요 (모두 양수로)", 21, INK, True).move_to(step)
        exb = bars_for(ex, fmt="{:.3f}", top=3.2)
        self.play(ReplacementTransform(step2, step3), FadeOut(why), ReplacementTransform(raw, exb), run_time=1.1)
        self.wait(1.5)

        probs = softmax(logits)
        step4 = T("4) 합으로 나누면 확률 (합 = 1)", 21, INK, True).move_to(step)
        pb = bars_for(probs, fmt="{:.3f}", top=3.2)
        self.play(ReplacementTransform(step3, step4), ReplacementTransform(exb, pb), run_time=1.1)
        note = T("A4000 기록: 0.026 · 0.003 · 0.003 · 0.968", 17, GREEN).next_to(step4, DOWN, buff=0.15)
        self.play(FadeIn(note), run_time=0.5)
        self.wait(2.0)

        # 온도: 점수를 T로 나눈 뒤 softmax
        temp = ValueTracker(1.0)
        step5 = T("5) 온도 T: 점수를 T로 나누고 softmax", 21, INK, True).move_to(step)

        def live():
            ps = softmax(logits, temp.get_value())
            return bars_for(ps, fmt="{:.2f}", top=3.2)

        live_bars = always_redraw(live)
        tlabel = always_redraw(lambda: T(f"T = {temp.get_value():.2f}", 24, ORANGE, True, font=MONO).move_to([4.6, 1.15, 0]))
        self.play(ReplacementTransform(step4, step5), FadeOut(note), FadeOut(pb), FadeIn(live_bars), FadeIn(tlabel), run_time=0.8)
        self.play(temp.animate.set_value(3.0), run_time=2.4)
        self.wait(0.5)
        self.play(temp.animate.set_value(0.5), run_time=2.4)
        self.wait(0.5)
        self.play(temp.animate.set_value(1.0), run_time=1.4)
        end = card(9.6, 1.05, fill="#FFFFFF", stroke=INK, width=2).move_to([0, 1.95, 0])
        e1 = T("온도는 1등을 바꾸지 않아요. 얼마나 뾰족한지만 바꿔요", 21, INK, True)
        e2 = T("→ 내 데이터로 T를 맞추는 게 1강의 '보정(온도 조절)'", 19, GREEN)
        eg = VGroup(e1, e2).arrange(DOWN, buff=0.1).move_to(end)
        self.play(FadeOut(tlabel), FadeOut(step5), FadeIn(end), FadeIn(eg), run_time=0.9)
        self.wait(4.5)
