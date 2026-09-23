"""jev-ultrafast로 구글 항공권 편도 검색을 실제로 돌리고 기록을 남긴다 (예약·선택은 하지 않는다).

jev-ultrafast 저장소 안에서 실행한다:
  cd <jev-ultrafast>
  BU_NAME=jevlecture BU_CDP_URL=http://127.0.0.1:9333 uv run --env-file .env python <이 파일> --show --origin Seoul --destination Jeju --date 2026-10-20 --out <폴더>

- 먼저 임시 프로필 Chrome을 띄운다(start_chrome.sh). BU_NAME을 꼭 따로 줘야 한다:
  기본 데몬(default)은 평소 쓰는 Chrome에 붙어 있을 수 있고, 그러면 BU_CDP_URL이 무시된다.
- 글자 입력(TYPE_TEXT)만 작은 LLM이 쓴다: TEXT_MODEL_BASE_URL / TEXT_MODEL / TEXT_MODEL_API_KEY (.env)
  로컬 Ollama 예) TEXT_MODEL_BASE_URL=http://127.0.0.1:11434/v1  TEXT_MODEL=qwen3.5:4b  TEXT_MODEL_API_KEY=ollama
"""
import argparse
import base64
import datetime as dt
import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jev_ultrafast.model as ultrafast_model
from jev_ultrafast import Agent

# 로컬 Ollama의 Qwen3.5는 OpenAI 호환 주소에서 생각 모드가 기본으로 켜져 한참 걸린다.
# TEXT_MODEL_REASONING_EFFORT=none 이면 글자 도우미 호출에만 reasoning_effort를 붙인다 (원본 저장소는 수정하지 않음).
_post_json = ultrafast_model.post_json


def _post_json_with_effort(url, key, body):
    effort = os.environ.get("TEXT_MODEL_REASONING_EFFORT")
    base = os.environ.get("TEXT_MODEL_BASE_URL", "")
    if base and url.startswith(base.rstrip("/")):
        if effort:
            body = {k: v for k, v in body.items() if k != "reasoning"} | {"reasoning_effort": effort}
        # 원본은 맥락을 json.dumps 기본값(ensure_ascii=True)으로 보내 한글이 \uXXXX로 바뀐다. 작은 모델은 이걸 잘 못 읽는다.
        msgs = []
        for m in body.get("messages", []):
            try:
                m = {**m, "content": json.dumps(json.loads(m["content"]), ensure_ascii=False)}
            except (ValueError, TypeError, KeyError):
                pass
            msgs.append(m)
        body = {**body, "messages": msgs}
        if os.environ.get("TEXT_MODEL_TEMPERATURE"):
            body["temperature"] = float(os.environ["TEXT_MODEL_TEMPERATURE"])  # 로컬 모델은 0으로 두면 같은 입력에 같은 값을 쓴다
        result = _post_json(url, key, body)
        content = (result.get("choices") or [{}])[0].get("message", {}).get("content")
        print(f"   [text helper] {content!r}", flush=True)
        return result
    return _post_json(url, key, body)


ultrafast_model.post_json = _post_json_with_effort


def ensure_isolated_browser():
    """에이전트가 '어느 Chrome'을 조종하는지 먼저 확인한다.

    browser-harness의 기본 데몬(default)은 평소 쓰는 Chrome(원격 디버깅 9222)에 이미 붙어 있을 수 있고,
    그 경우 BU_CDP_URL을 줘도 기존 데몬을 그대로 쓴다(2026-09-23 실제로 겪음).
    그래서 BU_NAME을 따로 주고, 데몬이 cdp 모드(=BU_CDP_URL의 임시 Chrome)인지 확인한 뒤에만 시작한다.
    """
    from browser_harness import admin
    if not os.environ.get("BU_CDP_URL") or admin.NAME == "default":
        raise SystemExit("임시 Chrome 전용으로 실행하세요: BU_NAME=jevlecture BU_CDP_URL=http://127.0.0.1:9333 ...")
    admin.ensure_daemon()
    kind = admin.daemon_browser_kind()
    if kind != "cdp":
        raise SystemExit(f"데몬 '{admin.NAME}'이 {kind} 모드입니다. 임시 Chrome에 붙지 않았으니 멈춥니다.")
    print(f"[browser] daemon={admin.NAME} mode={kind} target={os.environ['BU_CDP_URL']}", flush=True)

URL = "https://www.google.com/travel/flights?hl=en"


def verify(page, origin, destination, date):
    """모델이 DONE이라고 한 것과 별개로, 최종 페이지를 코드로 다시 확인한다."""
    parsed = urlparse(page["url"])
    encoded = parse_qs(parsed.query).get("tfs", [""])[0]
    try:
        date_in_url = date.encode() in base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except ValueError:
        date_in_url = False
    values = {a["label"].strip(): (a.get("value") or "") for a in page["actions"]}
    flights = [a["label"] for a in page["actions"] if "Select flight" in a["label"]]
    day = dt.date.fromisoformat(date)
    long_day = f"{day.strftime('%A')}, {day.strftime('%B')} {day.day}"
    checks = {
        "search_page": parsed.hostname == "www.google.com" and parsed.path == "/travel/flights/search",
        "one_way": values.get("Change ticket type. One way") == "One way",
        "origin": origin.lower() in values.get("Where from?", "").lower(),
        "destination": destination.lower() in values.get("Where to?", "").lower(),
        "date": date_in_url,
        "results": bool(flights) and all(long_day in f for f in flights),
    }
    return {"passed": all(checks.values()), "checks": checks, "visible_flights": flights[:10], "flight_count": len(flights)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", default="Seoul")
    ap.add_argument("--destination", default="Jeju")
    ap.add_argument("--date", default="2026-10-20")
    ap.add_argument("--out", default="artifacts/flights/run")
    ap.add_argument("--show", action="store_true", help="에이전트가 쓰는 탭을 화면 앞으로 가져온다")
    ap.add_argument("--record", action="store_true", help="단계마다 화면을 jpg로 남긴다(관찰에 스크린샷이 붙어 조금 느려진다)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    day = dt.date.fromisoformat(args.date)
    goal = (f"Find one-way flights from {args.origin} to {args.destination} on {day.strftime('%B')} {day.day}, {day.year}, "
            "for one adult in economy. Stop when matching flight options are visible. Do not select or book a flight.")
    ensure_isolated_browser()
    steps = []
    started = time.perf_counter()
    agent = Agent(URL, goal, record_dir=(out / "frames") if args.record else None)
    if args.show:
        # jev-ultrafast는 뒤쪽 탭에서 일한다. 강의 화면용으로 그 탭을 앞으로 가져온다(동작에는 영향 없음).
        from browser_harness.helpers import cdp
        cdp("Target.activateTarget", targetId=agent.browser.target)
    try:
        for state in agent.run():
            last = state["history"][-1] if state["history"] else {}
            steps.append({"elapsed_ms": state["elapsed_ms"], "status": state["status"], "operation": last.get("operation"),
                          "action": last.get("action"), "probability": last.get("probability"), "jev_ms": last.get("latency_ms"),
                          "text": last.get("text"), "text_ms": last.get("text_latency_ms")})
            print(state["elapsed_ms"], state["status"], last.get("operation", ""), (last.get("action") or "")[:50],
                  last.get("text") or "", flush=True)
    finally:
        snap = agent.snapshot()
        snap["verification"] = verify(snap["page"], args.origin, args.destination, args.date)
        snap["goal"] = goal
        snap["wall_seconds"] = round(time.perf_counter() - started, 2)
        (out / "state.json").write_text(json.dumps(snap, indent=2, ensure_ascii=False))
        (out / "steps.json").write_text(json.dumps(steps, indent=2, ensure_ascii=False))
        try:
            shot = agent.browser.call("Page.captureScreenshot", format="png")
            (out / "final.png").write_bytes(base64.b64decode(shot["data"]))
        except Exception as exc:  # 스크린샷은 기록용이다. 실패해도 결과 판정에는 영향이 없다
            print("screenshot failed:", exc)
        agent.close()
    print(json.dumps(snap["verification"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
