"""jev-ultrafast로 네이버 항공권(flight.naver.com) 국내선 편도 검색을 돌린다. 예약·선택은 하지 않는다.

사이트별 스크립트는 없다. 같은 에이전트에 목표 문장만 주고, 마지막 페이지는 코드로 따로 확인한다.
  cd <jev-ultrafast>
  BU_NAME=jevlecture BU_CDP_URL=http://127.0.0.1:9333 uv run --env-file .env python <이 파일> --show --mobile --viewport 430x932 --out <폴더>
"""
import argparse
import base64
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import run_flights  # noqa: F401  (Ollama용 reasoning_effort 패치를 함께 적용)
from jev_ultrafast import Agent

URL = "https://flight.naver.com/"


def verify(page, origin_code, dest_code, ymd):
    """최종 URL과 화면 글자로 검색 결과 페이지인지 확인한다."""
    url, text = page["url"], page.get("text", "")
    checks = {
        "results_url": "flight.naver.com/flights/domestic/" in url,
        "route": bool(re.search(rf"{origin_code}[^/]*-{dest_code}", url)) or (origin_code in url and dest_code in url),
        "date": ymd in url,
        "one_way": url.count("-") <= 3 and "roundtrip" not in url.lower(),
        "results_visible": bool(re.search(r"\d{1,3}(,\d{3})+\s*원", text)),
    }
    return {"passed": all(checks.values()), "checks": checks, "url": url}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="artifacts/naver/run")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--date", default="2026-10-20",
                    help="네이버 달력은 안쪽 스크롤 상자라서 첫 화면(이번 달)에 보이는 날짜만 고를 수 있다")
    ap.add_argument("--mobile", action="store_true",
                    help="모바일 화면으로 연다(요소가 적고 덜 움직인다). Chrome을 --user-agent=<아이폰 UA>로 띄워 두면 첫 요청부터 모바일 페이지를 받는다")
    ap.add_argument("--viewport", default="1280x1500",
                    help="에이전트 탭의 화면 크기. 요소 표는 화면 안의 요소만 담는다. 세로가 780px이면 달력 첫 줄만 보인다")
    ap.add_argument("--no-date-labels", action="store_true",
                    help="날짜 버튼 이름 보강을 끈다(끄면 '20'처럼 숫자만 남아 몇 월인지 알 수 없다)")
    ap.add_argument("--done-min-p", type=float, default=0.6,
                    help="DONE 확률이 이보다 낮으면 끝내지 않고 WAIT로 바꾼다(1차 모바일 실행: 결과 로딩 중 DONE p=0.36으로 조기 종료)")
    ap.add_argument("--settle-ms", type=int, default=300, help="관찰 직전 DOM 변화가 이만큼 멈출 때까지 기다린다(0이면 끔)")
    ap.add_argument("--settle-max-ms", type=int, default=3000)
    ap.add_argument("--fill-wait", type=float, default=0.8,
                    help="글자 입력 뒤 기다릴 초. 네이버 자동완성은 약 0.6초 뒤에 뜬다(원본은 최대 0.2초만 기다림)")
    ap.add_argument("--keep-covered", action="store_true",
                    help="팝업 등에 가려 지금 누를 수 없는 요소도 요소 표에 남긴다(기본은 뺀다)")
    args = ap.parse_args()
    from jev_ultrafast.browser import Browser
    if not args.no_date_labels:
        # 네이버 달력 버튼에는 접근성 이름이 없다. 관찰 직전에 '2026년 10월 20일' 같은 aria-label을 붙인다.
        # 에이전트 코드는 그대로 두고, 화면 쪽 이름만 보강하는 '어댑터'다 (사이트 전용 보정임을 밝혀 둔다).
        LABEL_DAYS = r"""(() => {
          const heads=[...document.querySelectorAll('*')].filter(e=>e.children.length===0 && /^\d{4}\.\d{2}\.$/.test((e.textContent||'').trim()));
          for (const b of document.querySelectorAll('td.day button')) {
            let head=null; for (const h of heads) if (h.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING) head=h;
            const m=head && (head.textContent||'').trim().match(/^(\d{4})\.(\d{2})\.$/);
            const day=(b.querySelector('b')?.textContent||'').trim();
            if (m && /^\d{1,2}$/.test(day)) b.setAttribute('aria-label', `${m[1]}년 ${+m[2]}월 ${day}일`);
          }
        })()"""
        _observe = Browser.observe

        def observe_with_labels(self, screenshot=True):
            try:
                self.evaluate(LABEL_DAYS)
            except Exception:
                pass
            return _observe(self, screenshot=screenshot)

        Browser.observe = observe_with_labels
    # smart if: Jev는 확률을 주고, 끝낼지 말지는 코드가 정한다.
    import jev_ultrafast.agent as A
    _choose = A.choose

    def choose_with_done_gate(page, goal, history):
        d = _choose(page, goal, history)
        p_done = d.get("operation_probabilities", {}).get("DONE", 0)
        if d["choice"] == "DONE" and p_done < args.done_min_p and any(a["id"] == "wait" for a in page["actions"]):
            print(f"   [gate] DONE p={p_done:.2f} < {args.done_min_p} → WAIT", flush=True)
            d = {**d, "choice": "wait", "operation": "WAIT", "gated_from_done": p_done,
                 "probabilities": {"wait": d.get("operation_probabilities", {}).get("WAIT", 0.0)}}
        return d

    A.choose = choose_with_done_gate
    import jev_ultrafast.model as M
    _post = M.post_json

    def post_retry_once(url, key, body):
        try:
            return _post(url, key, body)
        except RuntimeError:
            time.sleep(0.5)
            return _post(url, key, body)  # 일시 오류(5xx·연결 끊김)만 한 번 더. 두 번째 실패는 그대로 멈춘다

    M.post_json = post_retry_once
    # 화면이 계속 바뀌는 사이트(배너 회전·최저가 비동기 표시)에서는 '판단→클릭' 사이에 화면이 바뀌어
    # 안전장치가 클릭을 취소한다. 동작 뒤 DOM 변화가 0.4초 멈출 때까지(최대 3초) 기다렸다가 다음 관찰을 한다. 사이트 전용이 아닌 일반 보정.
    SETTLE = """new Promise(res => { const t0=Date.now(); let timer;
      const done=()=>{ mo.disconnect(); res(Date.now()-t0); };
      const mo=new MutationObserver(()=>{ clearTimeout(timer); timer=setTimeout(done, Date.now()-t0>%d ? 0 : %d); });
      mo.observe(document.body,{subtree:true,childList:true,characterData:true});
      timer=setTimeout(done,%d); })"""
    _act = Browser.act

    def act_then_settle(self, action, page, text=None):
        result = _act(self, action, page, text=text)
        if action.get("kind") == "fill" and args.fill_wait > 0:
            time.sleep(args.fill_wait)
        return result

    Browser.act = act_then_settle
    _observe2 = Browser.observe

    def settle_then_observe(self, screenshot=True):
        if args.settle_ms > 0:
            try:
                self.call("Runtime.evaluate", expression=SETTLE % (args.settle_max_ms, args.settle_ms, args.settle_ms),
                          awaitPromise=True, returnByValue=True)
            except Exception:
                pass
        return _observe2(self, screenshot=screenshot)

    Browser.observe = settle_then_observe
    if not args.keep_covered:
        # 새 프로필로 열면 전체 화면 이벤트 팝업(투명 레이어)이 폼을 덮는다. Jev는 화면을 보지 않고 요소 표만 보므로
        # 뒤의 '도착지'를 계속 고르고, 클릭 직전 검사(browser.act의 elementFromPoint)가 매번 취소한다(판단 120회·실행 0회).
        # 그 검사와 같은 기준으로, 지금 누를 수 없는 요소는 요소 표에서 뺀다. 사이트 전용이 아닌 일반 보정.
        COVERED = """(nodes => nodes.filter(n => {
          const e=window.__jevFast?.nodes.get(n); if (!e) return false;
          const r=e.getBoundingClientRect(), x=r.x+r.width/2, y=r.y+r.height/2;
          if (!r.width || !r.height || x<0 || y<0 || x>=innerWidth || y>=innerHeight) return false;
          return !e.contains(document.elementFromPoint(x,y));
        }))(%s)"""
        _observe3 = Browser.observe

        def observe_clickable_only(self, screenshot=True):
            page = _observe3(self, screenshot=screenshot)
            nodes = [a["node"] for a in page["actions"] if type(a.get("node")) is int]
            try:
                covered = set(self.evaluate(COVERED % json.dumps(nodes)) or [])
            except Exception:
                return page
            if covered:
                page["actions"] = [a for a in page["actions"] if a.get("node") not in covered]
            return page

        Browser.observe = observe_clickable_only
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # 목표에 한글 화면 이름(편도·도착지)을 함께 적는다. 영어 'one-way'만 쓰면 Jev가 '편도'와 '다구간' 사이에서 흔들렸다(1차 실행).
    import datetime as dt
    day = dt.date.fromisoformat(args.date)
    goal = ("On Naver Flights, the origin is already set to 서울 (Seoul). Set the destination (도착지) to 제주 (Jeju), "
            f"choose one-way (편도), departure date {day.strftime('%B')} {day.day}, {day.year} "
            f"({day.year}년 {day.month}월 {day.day}일), one adult, then search (검색). "
            "Stop when the list of flights with prices is visible. Do not select, reserve, or pay for any flight.")
    run_flights.ensure_isolated_browser()
    # 사이트 데이터는 지우지 않는다. 매번 새 임시 프로필(start_chrome.sh --fresh)로 시작하는 게 안전하다.
    steps, started = [], time.perf_counter()
    agent = Agent(URL, goal, record_dir=(out / "frames") if args.record else None)
    if args.viewport:
        w, h = (int(v) for v in args.viewport.split("x"))
        agent.browser.call("Emulation.setDeviceMetricsOverride", width=w, height=h,
                           deviceScaleFactor=2 if args.mobile else 1, mobile=args.mobile)
    if args.show:
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
        snap["verification"] = verify(snap["page"], "SEL", "CJU", args.date.replace("-", ""))
        snap["goal"] = goal
        snap["wall_seconds"] = round(time.perf_counter() - started, 2)
        (out / "state.json").write_text(json.dumps(snap, indent=2, ensure_ascii=False))
        (out / "steps.json").write_text(json.dumps(steps, indent=2, ensure_ascii=False))
        try:
            shot = agent.browser.call("Page.captureScreenshot", format="png")
            (out / "final.png").write_bytes(base64.b64decode(shot["data"]))
        except Exception as exc:
            print("screenshot failed:", exc)
    print(json.dumps(snap["verification"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
