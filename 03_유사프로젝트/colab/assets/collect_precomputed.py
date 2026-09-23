"""노트북 6·7·10장이 읽는 '미리 잰 숫자'를 원본 기록에서 모아 precomputed.json으로 저장해요.

    python3 collect_precomputed.py [--fp16 /path/to/dtype_float16.json] [--omni-dir /path/to/jev-omni-small-files]

숫자는 모두 아래 원본 파일에서 그대로 읽어요(손으로 옮겨 적지 않음). 각 묶음의 "source"에 경로를 남겨요.
Jev-Omni는 Hugging Face에서 받은 작은 파일(README.md, unified/verification_unified.json)과
HfApi 파일 목록(메타데이터만)을 써요. 가중치는 받지 않아요.
"""
import argparse
import csv
import json
import time
from pathlib import Path

HOME = Path.home()
PD = HOME / "jev특강/output/parallel-decision-rlcd-20260922"
COLAB14 = HOME / "Downloads/20260922-043237-7fa17c (1)"
F3 = HOME / "jev특강/final/03_유사프로젝트"
F2 = HOME / "jev특강/final/02_라우터"
HERE = Path(__file__).resolve().parent


def rel(p):
    return "~/" + str(Path(p).relative_to(HOME))


def parallel_decision():
    summary = json.loads((PD / "summary.json").read_text())
    rows = []
    for r in summary:
        rows.append({
            "device": r["device"], "project": r["project"], "preset": r["preset"], "fields": r["fields"],
            "parallel_ms": r["warm_median_ms"], "parallel_min_ms": r["warm_min_ms"], "parallel_max_ms": r["warm_max_ms"],
            "json_ms": r["naive_ms"], "speedup": r["speedup"],
            "parallel_schema_valid": r["parallel_valid"], "json_schema_valid": r["naive_valid"],
            "json_missing_fields": len((r.get("naive_validation") or {}).get("missing", [])),
        })
    dense = json.loads((PD / "dense9b-a4000/summary.json").read_text())
    extra = []
    for key, label in (("qwen1p5b", "Qwen2.5 1.5B"), ("qwen9b", "Qwen3.5 9B")):
        a, s = dense[f"{key}-results"], dense[f"{key}-structured-results"]
        extra.append({"model": label, "parallel_ms": a["parallel_ms"], "json_ms": a["naive_ms"],
                      "schema_json_ms": s["naive_structured_ms"],
                      "parallel_exact": a["parallel_exact"], "json_exact": a["naive_exact"], "cases": a["total_cases"]})
    return {
        "source": [rel(PD / "summary.json"), rel(PD / "timings.csv"), rel(PD / "README.md"), rel(PD / "dense9b-a4000/summary.json")],
        "setup": "llama.cpp parallel-decision(14d04e7) · 같은 Qwen2.5-1.5B-Instruct GGUF Q4_K_M, Mac M5(Metal) / RTX A4000(CUDA). "
                 "RLCD는 장치마다 모델 빌드가 달라요(Mac MLX 4bit / A4000 PyTorch BF16). 일반 JSON은 프롬프트로만 요청(형식 강제 아님).",
        "timing": "첫 호출 뒤 3회 중앙값(ms). 모델 로딩 제외.",
        "rows": rows,
        "a4000_small_accuracy": extra,
        "a4000_small_accuracy_note": "문의 8건 × 3필드를 모두 맞혀야 정답. 28필드 속도 프리셋에는 정답 라벨이 없어요.",
    }


def colab14b():
    j = json.loads((COLAB14 / "visualization/comparison_all.json").read_text())
    return {"source": [rel(COLAB14 / "visualization/comparison_all.json"), rel(COLAB14 / "results.json")],
            "gpu": j["gpu"], "model": j["model"], "chunk_size": j["chunk_size"], "rows": j["rows"], "caveats": j["caveats"],
            "notebook": "Colab_Local_16GB_Qwen14B.ipynb (14B NF4/FP16, 선택 llama.cpp CUDA 빌드)"}


def semif_a4000():
    rows = list(csv.DictReader(open(PD / "semif-a4000/comparison.csv", encoding="utf-8-sig")))
    for r in rows:
        for k in ("median_ms", "min_ms", "max_ms", "peak_allocated_mib"):
            r[k] = float(r[k])
        for k in ("correct_cases", "correct_fields"):
            r[k] = int(r[k])
    return {"source": [rel(PD / "semif-a4000/comparison.csv"), rel(PD / "semif-a4000/README.md")],
            "setup": "RTX A4000, NF4/FP16, 같은 프로세스·같은 가중치, 28항목 속도 + 문의 8건 정답", "rows": rows}


def rlcr_vs_rlcd():
    base = PD / "rlcr-vs-rlcd-a4000"
    s = json.loads((base / "summary.json").read_text())["same_weights_comparison"]
    preds = list(csv.DictReader(open(base / "predictions.csv", encoding="utf-8-sig")))
    wrong = []
    for r in preds:
        if r["mode"] == "rlcd" and r["correct"] == "False":
            twin = next(x for x in preds if x["mode"] == "rlcr" and x["case"] == r["case"] and x["field"] == r["field"])
            wrong.append({"case": r["case"], "field": r["field"], "expected": r["expected"],
                          "rlcd_prediction": r["prediction"], "rlcd_confidence": float(r["confidence"]),
                          "rlcr_prediction": twin["prediction"], "rlcr_confidence": float(twin["confidence"])})
    return {"source": [rel(base / "summary.json"), rel(base / "predictions.csv"), rel(base / "README.md")],
            "setup": "같은 RLCR 7B 가중치(NF4/FP16), 문의 8건 × 3필드, RTX A4000",
            "rlcr": {k: s["rlcr"][k] for k in ("field_correct", "field_total", "case_correct", "case_total", "median_case_ms")},
            "rlcd": {k: s["rlcd"][k] for k in ("field_correct", "field_total", "case_correct", "case_total", "median_case_ms")},
            "rlcd_wrong": wrong}


def api_vs_local():
    s = json.loads((F3 / "evidence/api-vs-local/summary.json").read_text())
    gold = {}
    for line in open(F3 / "code/data/routing_bodies.jsonl", encoding="utf-8"):
        r = json.loads(line)
        gold[r["id"]] = r["gold"]["route"]

    def item(rid, probs):
        choice = max(probs, key=probs.get)
        return [round(probs[choice], 4), choice == gold[rid]]

    cal = {}
    jev = json.loads(next((F2 / "code/results").glob("router-jev-*.json")).read_text())
    cal["Jev API (TypeSafe)"] = [item(r["id"], r["decision"]["answers"]["route"]["probabilities"]) for r in jev["results"]]
    dec = [json.loads(l) for l in open(F3 / "evidence/api-vs-local/out_decider.jsonl") if l.strip()]
    cal["decider-2b (A4000 CUDA)"] = [item(r["id"], r["resp"]["answers"]["route"]["probabilities"]) for r in dec if "id" in r]
    mac = json.loads(next((F3 / "evidence/api-vs-local").glob("router-decider-mac-*.json")).read_text())
    cal["decider-2b (Mac MPS)"] = [item(r["id"], r["decision"]["answers"]["route"]["probabilities"]) for r in mac["results"]]
    oj = [json.loads(l) for l in open(F3 / "evidence/api-vs-local/out_openjev.jsonl") if l.strip()]
    cal["OpenJev Qwen3.5-4B (A4000)"] = [item(r["id"], dict(zip(r["answers"]["route"]["option_ids"], r["answers"]["route"]["probabilities"])))
                                        for r in oj if "id" in r]
    return {"source": [rel(F3 / "evidence/api-vs-local/summary.json"), rel(F3 / "evidence/api-vs-local/summary.md"),
                       rel(F3 / "code/evaluate.mjs"), rel(F3 / "code/data/routing_bodies.jsonl"),
                       rel(next((F2 / "code/results").glob("router-jev-*.json"))),
                       rel(F3 / "evidence/api-vs-local/out_decider.jsonl"), rel(F3 / "evidence/api-vs-local/out_openjev.jsonl")],
            "setup": "2강 라우터 메시지 40건, 같은 정책 코드(policy.mjs)로 채점. 행동 일치 = 정책이 고른 행동이 정답과 같은 비율",
            "table": s["table"],
            "route_calibration": cal,
            "route_calibration_note": "route 질문(chat/task/unclear/spam) 하나만: [고른 답의 확률, 정답 여부]. 40건이라 참고용"}


def readme_claims(path):
    """Jev-Omni README의 자기 보고 수치를 정규식으로 그대로 읽어요(우리가 재현한 값 아님)."""
    import re
    text = Path(path).read_text()

    def grab(pattern, cast=float):
        m = re.search(pattern, text)
        if not m:
            raise ValueError("README 형식이 바뀌었어요: " + pattern)
        return cast(m.group(1))

    return {
        "decisionbench_medium_accuracy": round(grab(r"DecisionBench Medium[^|]*\|\s*\*\*([0-9.]+)%") / 100, 4),
        "decisionbench_medium_ece": grab(r"Medium ECE: \*\*([0-9.]+)\*\*"),
        "jevbench_matched_accuracy": round(grab(r"JevBench[^|]*\|\s*\*\*([0-9.]+)%") / 100, 4),
        "h200_text_ms": grab(r"Warm H200 inference: \*\*([0-9]+) ms\*\*", int),
        "fp32_weights_gb": grab(r"FP32 weights use about ([0-9]+) GB", int),
        "max_options_tested": grab(r"Best supported at \*\*≤([0-9]+) options\*\*", int),
    }


def jev_omni(omni_dir):
    from huggingface_hub import HfApi

    api = HfApi(token=False)
    info = api.model_info("akhilaaa3/Jev-Omni", token=False)
    files = [(f.path, f.size) for f in api.list_repo_tree("akhilaaa3/Jev-Omni", recursive=True, token=False)
             if getattr(f, "size", None) is not None]
    groups = {}
    for path, size in files:
        key = path.split("/")[0] if "/" in path else ("head.pt" if path == "head.pt" else "기타 작은 파일")
        groups[key] = groups.get(key, 0) + size
    gemma = api.model_info("google/gemma-4-12B-it", files_metadata=True, token=False)
    ver = json.loads((Path(omni_dir) / "omni_verification_unified.json").read_text())
    cases = []
    for case, ref in zip(ver["cases"], ver["reference"]):
        cases.append({"state": case["state"], "question": case["question"], "options": case["options"],
                      "probabilities": [round(ref[o], 4) for o in case["options"]]})
    return {
        "source": ["https://huggingface.co/akhilaaa3/Jev-Omni (README.md, unified/verification_unified.json, jev_omni.py, load_model.py)",
                   "HfApi.list_repo_tree / model_info (메타데이터만, 가중치 받지 않음)"],
        "fetched_at": time.strftime("%Y-%m-%d"),
        "repo_sha": info.sha, "license": "apache-2.0", "base_model": "google/gemma-4-12B-it",
        "files_bytes": groups, "repo_total_bytes": sum(s for _, s in files),
        "gemma_total_bytes": sum((s.size or 0) for s in gemma.siblings), "gemma_gated": bool(gemma.gated),
        "readme_claims": readme_claims(Path(omni_dir) / "omni_README.md"),
        "verification_cases": cases,
        "verification_worst_abs_diff": ver.get("worst_abs_diff"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fp16", help="measure_local.py --dtype float16 결과 JSON")
    ap.add_argument("--omni-dir", required=True, help="Jev-Omni 작은 파일을 받아 둔 폴더")
    args = ap.parse_args()
    out = {
        "_about": "노트북이 그리는 미리 잰 숫자. 모든 값은 source에 적힌 파일에서 읽었어요.",
        "_collected_at": time.strftime("%Y-%m-%d %H:%M"),
        "parallel_decision": parallel_decision(),
        "colab14b": colab14b(),
        "semif_a4000": semif_a4000(),
        "rlcr_vs_rlcd": rlcr_vs_rlcd(),
        "api_vs_local": api_vs_local(),
        "jev_omni": jev_omni(args.omni_dir),
    }
    if args.fp16:
        f = json.loads(Path(args.fp16).read_text())
        out["mac_fp16_check"] = {
            "source": "assets/measure_local.py --dtype float16 (강사 Mac M5, MPS, " + f["machine"]["torch"] + ")",
            "results": {k: {"option_ids": v["option_ids"], "probabilities": [round(p, 4) for p in v["probabilities"]]}
                        for k, v in f["results"].items()}}
    (HERE / "precomputed.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("precomputed.json", (HERE / "precomputed.json").stat().st_size, "bytes")


if __name__ == "__main__":
    main()
