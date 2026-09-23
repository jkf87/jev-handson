"""노트북의 '미리 잰 값(fallback)'을 만드는 스크립트 — 강사 Mac(Apple M5, MPS)에서 실행.

    HF_HUB_OFFLINE=1 HF_DEACTIVATE_ASYNC_LOAD=1 python measure_local.py --dtype bfloat16 --explain --shared --out widget_fallback.json
    HF_HUB_OFFLINE=1 HF_DEACTIVATE_ASYNC_LOAD=1 python measure_local.py --dtype float16 --out dtype_float16.json

HF_DEACTIVATE_ASYNC_LOAD=1: Mac(MPS)에서 transformers 5.17의 병렬 가중치 로딩이 Metal 커널 캐시와 부딪혀
세그폴트(139)가 나서, 로딩을 한 줄로 돌려요. CUDA(Colab)에서는 필요 없어요.

- 모델: Qwen/Qwen3.5-4B @ 851bf6e (A4000 실측과 같은 커밋), SemIf 1f2dea3의 load_causal_model/score 그대로.
- --explain 이면 nb_explain.explain_case()로 위젯 데이터(토큰·층별 점수·순서 바꾸기)까지 저장해요.
"""
import argparse
import json
import platform
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

MODEL = "Qwen/Qwen3.5-4B"
REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float16", "float32"])
    ap.add_argument("--device", default="mps")
    ap.add_argument("--explain", action="store_true")
    ap.add_argument("--shared", action="store_true", help="6장 공유 모드 비교(질문 8개)도 재요")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import torch
    from semif_phase1.core import load_causal_model
    from semif_phase1.direct import score
    from nb_explain import explain_case, run_shared_demo

    cases = json.loads((HERE / "cases.json").read_text())
    rows = cases["rows"] + [cases["my_row"]]

    t0 = time.time()
    model, tokenizer, metadata = load_causal_model(MODEL, REVISION, device=args.device, dtype=args.dtype)
    load_s = time.time() - t0
    score(model, tokenizer, rows[0], metadata)  # 워밍업(버림)

    results = {}
    for row in rows:
        if args.explain:
            results[row["id"]] = explain_case(model, tokenizer, row, metadata)
        else:
            r = score(model, tokenizer, row, metadata)
            results[row["id"]] = {k: r[k] for k in ("option_ids", "probabilities", "option_logits",
                                                     "input_tokens", "forward_seconds", "prompt_sha256")}
    # 강의 예시 JSON 답의 실제 토큰 조각(영상 ①에 사용)
    samples = {}
    for text in ['{"choice": "main"}', '{"session": "main", "confidence": 0.62}']:
        ids = tokenizer.encode(text, add_special_tokens=False)
        samples[text] = [tokenizer.decode([i]) for i in ids]
    shared_demo = run_shared_demo(model, tokenizer, metadata) if args.shared else None
    out = {
        "_note": "강사 Mac에서 잰 값. Colab T4(float16)와 소수점 아래가 다를 수 있어요.",
        "machine": {"platform": platform.platform(), "machine": platform.machine(),
                    "python": platform.python_version(), "device": args.device, "dtype": args.dtype,
                    "torch": torch.__version__},
        "metadata": metadata,
        "load_seconds": load_s,
        "json_answer_tokens": samples,
        "results": results,
        "shared_demo": shared_demo,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    ref = cases["a4000"]
    for rid, r in results.items():
        a = ref.get(rid)
        same_prompt = (a and a["prompt_sha256"] == r["prompt_sha256"])
        probs = " ".join(f"{o}={p:.4f}" for o, p in zip(r["option_ids"], r["probabilities"]))
        extra = ""
        if a:
            delta = max(abs(p - q) for p, q in zip(r["probabilities"], a["probabilities"]))
            pick = r["option_ids"][max(range(len(r["probabilities"])), key=r["probabilities"].__getitem__)]
            apick = a["option_ids"][max(range(len(a["probabilities"])), key=a["probabilities"].__getitem__)]
            extra = f" | A4000 pick={apick} same_pick={pick == apick} max|Δp|={delta:.4f} same_prompt={same_prompt}"
        print(f"[{rid}] {probs} fwd={r['forward_seconds']*1000:.0f}ms tok={r['input_tokens']}{extra}")
    print(f"load {load_s:.1f}s")
    if shared_demo:
        d = shared_demo
        print(f"shared demo: direct {d['direct_seconds']:.2f}s ({d['direct_tokens']} tok) vs shared {d['shared_seconds']:.2f}s "
              f"({d['shared_tokens']} tok, prefix {d['prefix_tokens']}) picks {d['same_picks']}/{d['questions']} "
              f"max|dp| {d['max_prob_diff']:.4f} {d['serving_config']}")


if __name__ == "__main__":
    main()
