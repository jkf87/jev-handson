"""악플 탐지 실습 공통: 데이터 읽기, 라벨 정의, 채점. 파이썬 표준 라이브러리만 쓴다."""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "valid.jsonl"
RESULTS = HERE / "results"

# korean-hate-speech(BEEP!) 주석 지침을 줄여 옮긴 정의. Jev의 후보 설명과 LLM의 시스템 프롬프트가 같은 문장을 쓴다(공정한 비교).
# 지시문은 영어로 쓰고 댓글은 한국어 그대로 넣는다(TypeSafe 문서: 영어가 주 학습 언어).
LABELS = {
    "none": "not toxic: neutral, positive, or civil criticism with no insult",
    "offensive": "offensive but not hate speech: rude, insulting, aggressive, sarcastic, cynical, or disrespectful toward the target or bystanders",
    "hate": "hate speech: explicit hatred toward a person or group because of gender, sexual orientation, age, appearance, "
            "social status, religion, military service, disease or disability, ethnicity, or national origin; "
            "or a severe insult, humiliation, sexual harassment, or derogation of a person or group",
}
TOXIC = ("offensive", "hate")   # 악플 = 공격적 발언 + 혐오 발언


def load(limit=None):
    rows = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
    if limit and limit < len(rows):
        # 앞에서부터 자르지 않고 파일 전체에서 고르게 뽑는다(정답 분포가 한쪽으로 치우치지 않게)
        n = len(rows)
        rows = [rows[int((k + 0.5) * n / limit)] for k in range(limit)]
    return rows


def api_key(required=True):
    """TYPESAFE_API_KEY 환경변수 → 실행 폴더 .env → 이 폴더·상위 폴더 .env. 값은 화면에 찍지 않는다."""
    if os.environ.get("TYPESAFE_API_KEY"):
        return os.environ["TYPESAFE_API_KEY"]
    for env in (Path.cwd() / ".env", HERE / ".env", HERE.parent / ".env"):
        if env.is_file():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("TYPESAFE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("\"'")
    if required:
        sys.exit("TYPESAFE_API_KEY가 없습니다. code/.env에 넣거나 export 하세요 (console.typesafe.ai/keys)")
    return ""


def save(prefix, rows):
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path


def latest(prefix):
    files = sorted(RESULTS.glob(f"{prefix}-*.jsonl"))
    return files[-1] if files else None


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def scores(pairs):
    """pairs: (정답이 악플인가, 숨겼나) 목록 → 정밀도·재현율·F1·정확도. '악플'을 양성으로 본다."""
    tp = sum(g and p for g, p in pairs)
    fp = sum((not g) and p for g, p in pairs)
    fn = sum(g and (not p) for g, p in pairs)
    acc = sum(g == p for g, p in pairs) / len(pairs) if pairs else 0
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    return {"precision": prec, "recall": rec, "f1": f1, "accuracy": acc, "hidden": tp + fp, "n": len(pairs)}
