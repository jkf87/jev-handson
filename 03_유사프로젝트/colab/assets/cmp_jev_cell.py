# 4장 Jev 셀(노트북에 그대로 들어가요). 키 → 주소를 골라 같은 질문을 보내고, 키가 없으면 9/23 기록을 써요.
import json, os, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

TYPESAFE_URL = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai").rstrip("/") + "/v1/systemone"
OPENROUTER_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api").rstrip("/") + "/alpha/decisions"
PRICE_PER_TOKEN = 0.042 / 1e6          # 입력 100만 토큰당 $0.042, 출력은 무료
USER_AGENT = "jev-lecture-colab-cmp4/1.0"   # 파이썬 기본 User-Agent(Python-urllib)는 Cloudflare 403(error 1010)에 막혀요
JEV_WORKERS = 8                        # 동시에 보내는 요청 수(1강 코드와 같아요)


def secret(name):
    """Colab 🔑 보안 비밀 → 환경변수 순서로 찾아요. 값은 절대 출력하지 않아요."""
    try:
        from google.colab import userdata
        value = userdata.get(name)
        if value:
            return value.strip()
    except Exception:          # Colab 밖이거나, 보안 비밀이 없거나, 노트북 액세스를 안 켠 경우
        pass
    return (os.environ.get(name) or "").strip() or None


def post_json(url, body, key, tries=4):
    """POST 한 번(429 · 5xx · 연결 오류는 조금 쉬었다 다시). 반환: (응답 JSON, 걸린 ms)"""
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": USER_AGENT})
    for attempt in range(tries):
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.load(res), (time.perf_counter() - t0) * 1000
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(min(8.0, 1.5 * 2 ** attempt))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < tries - 1:
                time.sleep(1.0 + attempt)
                continue
            raise


def ask_jev(item, url, key, model):
    body = {"model": model, "state": make_state(item), "questions": QUESTIONS}   # ← 요청은 이게 전부예요
    out, ms = post_json(url, body, key)
    answer = out["answers"][QID]
    usage = out.get("usage", {})
    return result_row(item, answer["probabilities"], ms, usage.get("input_tokens", 0),
                      model=out.get("model"), cost=usage.get("cost"))


def run_jev_live(url, key, model):
    first = ask_jev(SAMPLE[0], url, key, model)            # 한 건 먼저: 키가 틀렸으면 여기서 바로 멈춰요
    t0 = time.perf_counter()

    def safe(item):
        try:
            return ask_jev(item, url, key, model)
        except Exception as e:
            return {"id": item["id"], "gold": item["gold"], "error": f"{type(e).__name__}: {str(e)[:120]}"}

    with ThreadPoolExecutor(JEV_WORKERS) as pool:
        rest = list(pool.map(safe, SAMPLE[1:]))
    return [first] + rest, time.perf_counter() - t0


def jev_from_record():
    rec = JEV_RECORDED["rows"]
    rows = []
    for item in SAMPLE:
        p_none, p_off, p_hate, ms, tokens, gold = rec[item["id"]]
        assert gold == item["gold"], "기록과 데이터 순서가 달라요"        # 기록의 정답 = 지금 데이터의 정답인지 확인
        rows.append(result_row(item, {"none": p_none, "offensive": p_off, "hate": p_hate}, ms, tokens,
                               model=JEV_RECORDED["model"]))
    return rows


ts_key, or_key = secret("TYPESAFE_API_KEY"), secret("OPENROUTER_API_KEY")
if not RUN["jev"]:
    mark_skipped("jev", "RUN['jev'] = False")
    print("RUN['jev'] = False라 건너뛰어요.")
else:
    clear_skip("jev")
    rows = run_s = None
    if ts_key or or_key:
        where, url, key, model = (("TypeSafe API", TYPESAFE_URL, ts_key, "jev-latest") if ts_key else
                                  ("OpenRouter", OPENROUTER_URL, or_key, "~typesafe/jev-latest"))
        print(f"{where}로 {len(SAMPLE)}건을 보내요 (동시 {JEV_WORKERS}개) · 키 값은 출력하지 않아요")
        try:
            rows, run_s = run_jev_live(url, key, model)
            source = f"{where} 실시간 호출"
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:160]
            print(f"HTTP {e.code}: {detail}")
            if e.code in (401, 403):
                print("→ 키가 틀렸거나 요청이 막혔어요. 키를 확인하고, User-Agent 헤더를 지우지 마세요.")
        except Exception as e:
            print(f"호출 실패: {type(e).__name__}: {str(e)[:160]}")
        if rows is None:
            print("→ 9/23 기록으로 대신해요.\n")
    if rows is None:
        if not (ts_key or or_key):
            print("TYPESAFE_API_KEY · OPENROUTER_API_KEY가 없어서, 1강에서 같은 질문으로 잰 9/23 기록을 불러와요.")
        rows, source = jev_from_record(), f"기록 ({JEV_RECORDED['measured_at']}, {JEV_RECORDED['model']})"
    ok = [r for r in rows if "probs" in r]
    tokens = sum(r.get("input_tokens", 0) for r in ok)
    or_cost = [r["cost"] for r in ok if r.get("cost") is not None]
    cost = sum(or_cost) if or_cost else tokens * PRICE_PER_TOKEN
    models = sorted({r.get("model") for r in ok if r.get("model")})
    save_results("jev", rows, {"model": ", ".join(models) or "jev", "source": source, "device": "API (TypeSafe 서버)",
                               "run_s": round(run_s, 2) if run_s else None, "workers": JEV_WORKERS if run_s else None,
                               "input_tokens": tokens, "cost_usd": cost, "size": "비공개"})
    m = evaluate(ok)
    errors = len(rows) - len(ok)
    print(f"Jev · {source} · {len(ok)}건" + (f" (실패 {errors})" if errors else ""))
    print(f"  3분류 정확도 {m['accuracy']:.1%} · macro-F1 {m['macro_f1']:.3f} · 악플 F1 {m['toxic_f1']:.3f}")
    print(f"  요청 한 건 평균 {m['ms_mean']:.0f}ms" + (f" · 전체 {run_s:.1f}초(동시 {JEV_WORKERS}개)" if run_s else " (기록)")
          + f" · 입력 {tokens:,}토큰 ≈ ${cost:.4f} (1,000건 ≈ ${cost / max(len(ok), 1) * 1000:.3f})")
