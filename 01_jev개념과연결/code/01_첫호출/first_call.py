#!/usr/bin/env python3
"""첫 호출 파이썬 버전 (표준 라이브러리만). 1강 프롬프트 ①의 예제 답안.

    python3 01_첫호출/first_call.py [요청본문.json]      # 기본 bodies/01_세가지질문.json

키는 TYPESAFE_API_KEY 환경변수 → 이 폴더나 상위 폴더의 .env 순서로 찾고, 화면에 찍지 않는다.
TYPESAFE_BASE_URL을 바꾸면 3강의 로컬 호환 서버로 같은 요청을 보낸다.
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def api_key() -> str:
    if os.environ.get("TYPESAFE_API_KEY"):
        return os.environ["TYPESAFE_API_KEY"]
    for env in (Path.cwd() / ".env", HERE / ".env", HERE.parent / ".env"):
        if env.is_file():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("TYPESAFE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("\"'")
    sys.exit("TYPESAFE_API_KEY가 없습니다. .env에 넣거나 export 하세요 (console.typesafe.ai/keys)")


body_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "bodies/01_세가지질문.json"
body = json.loads(body_path.read_text(encoding="utf-8"))
body.setdefault("model", "jev-latest")                     # model이 빠지면 HTTP 422

base = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai").rstrip("/")
req = urllib.request.Request(f"{base}/v1/systemone", data=json.dumps(body).encode("utf-8"),
                             headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json",
                                      # 파이썬 기본 User-Agent(Python-urllib)는 Cloudflare가 403(error 1010)으로 막는다
                                      "User-Agent": "jev-lecture-first-call/1.0"})
t0 = time.perf_counter()
with urllib.request.urlopen(req, timeout=15) as res:
    resp = json.load(res)
ms = round((time.perf_counter() - t0) * 1000)

tokens = resp.get("usage", {}).get("input_tokens", 0)
print(f"model {resp.get('model')} · {ms}ms · 입력 {tokens}토큰 (≈ ${tokens * 0.042 / 1e6:.7f})")
for name, a in resp["answers"].items():
    if a.get("type") == "noul":
        print(f"  {name:8} noul   P(예) = {a['noul']}")
    elif a.get("type") == "choice":
        print(f"  {name:8} choice {a['choice']} ({a['probabilities'][a['choice']]}) · 전체 {a['probabilities']}")
    else:
        print(f"  {name:8} score  {a.get('score')} (confidence {a.get('confidence')})")
