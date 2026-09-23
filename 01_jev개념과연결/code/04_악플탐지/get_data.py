#!/usr/bin/env python3
"""korean-hate-speech(BEEP!) 검증 세트 471건을 받아 data/valid.jsonl로 저장한다. 파이썬 표준 라이브러리만 쓴다.

    python3 get_data.py

- 출처: Hugging Face nayohan/korean-hate-speech (원본 kocohub/korean-hate-speech, Moon et al. 2020), CC BY-SA 4.0
- 뉴스 기사 제목 + 그 기사에 달린 댓글 + 사람이 붙인 정답(hate: none · offensive · hate)
- test 세트는 정답이 공개돼 있지 않아서 valid(471건)로 채점한다
- 주의: 실제 악플이 들어 있는 데이터입니다
"""
import json
import urllib.request
from collections import Counter
from pathlib import Path

URL = "https://datasets-server.huggingface.co/rows?dataset=nayohan/korean-hate-speech&config=default&split=valid&offset={}&length=100"
OUT = Path(__file__).parent / "data" / "valid.jsonl"


def fetch(offset):
    # 파이썬 기본 User-Agent는 일부 서버가 막는다(1강 첫 호출에서 겪은 403과 같은 이유)
    req = urllib.request.Request(URL.format(offset), headers={"User-Agent": "jev-lecture-hate-speech/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    rows, offset = [], 0
    while True:
        page = fetch(offset)
        rows += [r["row"] for r in page["rows"]]
        offset += 100
        if offset >= page["num_rows_total"]:
            break
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for i, r in enumerate(rows, 1):
            f.write(json.dumps({"id": f"v{i:03d}", "news_title": r["news_title"], "comment": r["comments"],
                                "hate": r["hate"], "bias": r["bias"]}, ensure_ascii=False) + "\n")
    print(f"{len(rows)}건 → {OUT}")
    print("정답 분포:", dict(Counter(r["hate"] for r in rows)))


if __name__ == "__main__":
    main()
