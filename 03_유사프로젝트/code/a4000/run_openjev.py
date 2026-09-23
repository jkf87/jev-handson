"""A4000에서 이미 돌고 있는 OpenJev 서비스(Qwen3.5-4B, 옵션 logit 직접 판독, :8040 /decide)에 2강 라우팅 40건을 넣는다.

OpenJev의 /decide는 질문 1개씩 받는다. 그래서 메시지 하나당 route·target·confirm 세 번 호출한다.
Jev는 세 질문을 한 번에 받는다는 점이 비교 포인트다.

실행 (워커, 표준 라이브러리만):  C:\\Python313\\python.exe run_openjev.py routing_bodies.jsonl out_openjev.jsonl
"""
import json
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8040/decide"


def call(row):
    req = urllib.request.Request(URL, data=json.dumps(row).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body, (time.perf_counter() - t0) * 1000


def rows_for(item):
    """Jev 요청 본문 하나를 OpenJev 행 3개로 바꾼다 (같은 정의·같은 상태 텍스트)."""
    body = item["body"]
    state = json.dumps(body["state"], ensure_ascii=False)
    q = body["questions"]
    out = []
    for name in ("route", "target"):
        crit = q[name]["criteria"]
        out.append((name, {"id": f"{item['id']}-{name}", "state": state, "question": q[name]["instructions"],
                           "options": [{"id": k, "description": v or k} for k, v in crit.items()]}))
    out.append(("confirm", {"id": f"{item['id']}-confirm", "state": state, "question": q["confirm"]["instructions"],
                            "options": [{"id": "yes", "description": "yes, a person must confirm first"},
                                        {"id": "no", "description": "no, it is safe to do without confirmation"}]}))
    return out


src, dst = sys.argv[1], sys.argv[2]
items = [json.loads(line) for line in open(src, encoding="utf-8") if line.strip()]
health = json.loads(urllib.request.urlopen("http://127.0.0.1:8040/health", timeout=10).read().decode("utf-8"))
with open(dst, "w", encoding="utf-8") as out:
    out.write(json.dumps({"meta": {"health": health}}, ensure_ascii=False) + "\n")
    for item in items:
        rec = {"id": item["id"], "answers": {}, "ms": {}}
        for name, row in rows_for(item):
            resp, ms = call(row)
            rec["answers"][name] = {"option_ids": resp.get("option_ids"), "probabilities": resp.get("probabilities"),
                                    "forward_seconds": resp.get("forward_seconds"), "service_ms": resp.get("service_ms")}
            rec["ms"][name] = round(ms, 1)
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
print("DONE", len(items))
