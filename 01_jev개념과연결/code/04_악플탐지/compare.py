#!/usr/bin/env python3
"""두 출력 비교: LLM으로 거른 결과와 Jev로 거른 결과를 같은 댓글끼리 맞춰 본다.

    python3 compare.py                         # results/의 가장 최근 jev-*.jsonl · llm-*.jsonl
    python3 compare.py --jev <기록> --llm <기록>

보여 주는 것: 정확도·정밀도·재현율·지연·비용, 두 결과가 갈린 댓글, Jev 기준(임계값)을 바꾸면 달라지는 것(API 재호출 없음)
결과: results/compare.md
"""
import argparse
from pathlib import Path

from common import RESULTS, TOXIC, latest, load, median, read_jsonl, scores

PRICE_PER_TOKEN = 0.042 / 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jev")
    ap.add_argument("--llm")
    ap.add_argument("--threshold", type=float, default=0.5)
    args = ap.parse_args()
    jev_path = Path(args.jev) if args.jev else latest("jev")
    llm_path = Path(args.llm) if args.llm else latest("llm")
    if not jev_path or not llm_path:
        raise SystemExit("results/에 jev-*.jsonl과 llm-*.jsonl이 모두 있어야 합니다 (jev_filter.py, llm_filter.py 먼저)")
    jev = {r["id"]: r for r in read_jsonl(jev_path) if "error" not in r}
    llm = {r["id"]: r for r in read_jsonl(llm_path) if r.get("pred")}
    ids = [i for i in jev if i in llm]
    if not ids:
        raise SystemExit("두 기록에 같은 댓글이 없습니다. jev_filter.py와 llm_filter.py를 같은 --limit으로 돌리세요")
    text = {r["id"]: r for r in load()}
    t = args.threshold
    lines = [f"# 악플 거르기: LLM vs Jev ({len(ids)}건 · 같은 댓글 · 같은 정의)", "",
             f"- Jev: `{jev_path.name}` · LLM: `{llm_path.name}`",
             f"- 악플 = offensive + hate (정답은 사람이 붙인 라벨). Jev는 악플 확률 {t} 이상이면 숨김, LLM은 라벨이 악플이면 숨김", ""]

    def row(name, rs, hide, three, ms, cost_per_1k):
        s = scores([(r["gold"] in TOXIC, hide(r)) for r in rs])
        return f"| {name} | {three:.1%} | {s['precision']:.1%} | {s['recall']:.1%} | {s['f1']:.3f} | {ms}ms | ${cost_per_1k:.3f} |"

    J = [jev[i] for i in ids]
    L = [llm[i] for i in ids]
    j_cost = sum(r["input_tokens"] for r in J) * PRICE_PER_TOKEN / len(J) * 1000
    l_cost = sum(r.get("cost_usd") or 0 for r in L) / len(L) * 1000
    lines += ["| 방법 | 3분류 정확도 | 악플 정밀도 | 악플 재현율 | F1 | 지연 중앙값 | 1,000건 비용 |", "|---|---:|---:|---:|---:|---:|---:|",
              row(f"Jev ({J[0].get('model')})", J, lambda r: r["p_toxic"] >= t, sum(r["pred"] == r["gold"] for r in J) / len(J), median([r["ms"] for r in J]), j_cost),
              row(f"LLM ({L[0].get('model')})", L, lambda r: r["pred"] in TOXIC, sum(r["pred"] == r["gold"] for r in L) / len(L), median([r.get("ms") for r in L]), l_cost),
              "", "- 정밀도: 숨긴 것 중 진짜 악플 비율(정상 댓글을 잘못 숨기면 떨어짐) · 재현율: 진짜 악플 중 숨긴 비율(놓치면 떨어짐)",
              f"- LLM 비용은 claude CLI가 보고한 정가 기준. Jev는 입력 토큰 × $0.042/100만", ""]

    # 두 출력이 갈린 댓글
    only_j = [i for i in ids if jev[i]["p_toxic"] >= t and llm[i]["pred"] not in TOXIC]
    only_l = [i for i in ids if jev[i]["p_toxic"] < t and llm[i]["pred"] in TOXIC]
    both = sum(1 for i in ids if jev[i]["p_toxic"] >= t and llm[i]["pred"] in TOXIC)
    lines += ["## 두 출력 맞춰 보기", "",
              f"- 둘 다 숨김 {both} · 둘 다 둠 {len(ids) - both - len(only_j) - len(only_l)} · **Jev만 숨김 {len(only_j)}** · **LLM만 숨김 {len(only_l)}** (일치 {1 - (len(only_j) + len(only_l)) / len(ids):.1%})",
              f"- Jev만 숨긴 {len(only_j)}건 중 정답이 악플: {sum(jev[i]['gold'] in TOXIC for i in only_j)}건 · LLM만 숨긴 {len(only_l)}건 중 정답이 악플: {sum(llm[i]['gold'] in TOXIC for i in only_l)}건",
              "", "| 갈린 댓글(앞 40자) | 정답 | Jev 악플 확률 | LLM 라벨 |", "|---|---|---:|---|"]
    for i in (only_j + only_l)[:8]:
        c = text[i]["comment"].replace("|", "/").replace("\n", " ")
        lines.append(f"| {c[:40]}{'…' if len(c) > 40 else ''} | {jev[i]['gold']} | {jev[i]['p_toxic']:.2f} | {llm[i]['pred']} |")

    # 기준 바꾸기: Jev는 확률이 있어서 API를 다시 부르지 않고 기준만 바꿔 다시 채점할 수 있다
    lines += ["", "## Jev 기준(임계값) 바꾸기 — API 재호출 없이", "", "| 악플 확률 기준 | 숨김 | 정밀도 | 재현율 | F1 |", "|---:|---:|---:|---:|---:|"]
    for th in (0.3, 0.5, 0.7, 0.9):
        s = scores([(r["gold"] in TOXIC, r["p_toxic"] >= th) for r in J])
        lines.append(f"| {th} | {s['hidden']} | {s['precision']:.1%} | {s['recall']:.1%} | {s['f1']:.3f} |")
    lines += ["", "- 기준을 올리면 정상 댓글을 덜 숨기고(정밀도↑) 악플을 더 놓친다(재현율↓). LLM 라벨로는 이 조절을 할 수 없다."]
    out = RESULTS / "compare.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n→ {out.relative_to(out.parent.parent)}")


if __name__ == "__main__":
    main()
