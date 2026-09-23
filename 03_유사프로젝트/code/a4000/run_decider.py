"""A4000(CUDA)에서 decider-2b로 2강 라우팅 40건을 판정한다. Jev와 같은 state/questions를 그대로 넣는다.

실행 (워커):  set TORCH_COMPILE_DISABLE=1 & set DECIDER_COMPILE=0 & set DECIDER_FP8=0
             C:\\ProgramData\\JevLab\\decider_venv\\Scripts\\python.exe run_decider.py routing_bodies.jsonl out_decider.jsonl
"""
import json
import sys
import time

from decider.infer import Decider

MODEL = "C:/ProgramData/JevLab/models/decider-2b"

src, dst = sys.argv[1], sys.argv[2]
rows = [json.loads(line) for line in open(src, encoding="utf-8") if line.strip()]

t0 = time.perf_counter()
d = Decider(MODEL)
load_s = time.perf_counter() - t0

# 첫 호출은 커널 준비 시간이 섞이므로 따로 잰다
t0 = time.perf_counter()
d.system_one(rows[0]["body"]["state"], rows[0]["body"]["questions"])
warm_ms = (time.perf_counter() - t0) * 1000

with open(dst, "w", encoding="utf-8") as out:
    out.write(json.dumps({"meta": {"model": MODEL, "load_s": round(load_s, 2), "first_call_ms": round(warm_ms, 1)}}) + "\n")
    for r in rows:
        t0 = time.perf_counter()
        ans = d.system_one(r["body"]["state"], r["body"]["questions"])
        ms = (time.perf_counter() - t0) * 1000
        out.write(json.dumps({"id": r["id"], "ms": round(ms, 1), "resp": ans}, ensure_ascii=False, default=float) + "\n")
print("DONE", len(rows), "load_s", round(load_s, 1), "first_call_ms", round(warm_ms))
