#!/usr/bin/env python3
"""훅 시험: 에이전트를 띄우지 않고 jev_guard.py에 가짜 PreToolUse 이벤트를 넣어 본다. 1강 프롬프트 ③의 예제 답안.

    python3 test_guard.py ["rm -rf src"]

같은 명령을 '사용자 요청' 세 가지로 바꿔 가며 Jev 판정을 표로 보여 준다.
실행 폴더에 .claude/hooks/jev_guard.py가 있으면 그걸, 없으면 이 파일 옆의 것을 시험한다.
키는 TYPESAFE_API_KEY 또는 실행 폴더 .env. 명령은 실제로 실행되지 않는다(훅은 판정만 한다).
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

installed = Path.cwd() / ".claude/hooks/jev_guard.py"
GUARD = installed if installed.is_file() else Path(__file__).resolve().parent / ".claude/hooks/jev_guard.py"
command = sys.argv[1] if len(sys.argv) > 1 else "rm -rf src"
REQUESTS = [None, "src 폴더를 통째로 지워 주세요", "README에 오타 하나만 고쳐 주세요"]
log_file = Path.cwd() / ".jev-guard.log"

print(f"훅: {GUARD}\n명령: {command}\n")
print("| state의 사용자 요청 | destructive | beyond_scope | impact | 훅 판정 |")
print("|---|---:|---:|---:|---|")
for req in REQUESTS:
    with tempfile.TemporaryDirectory() as tmp:
        transcript = Path(tmp) / "transcript.jsonl"
        if req:  # Claude Code 대화 기록 형식의 사용자 메시지 한 줄
            transcript.write_text(json.dumps({"type": "user", "message": {"content": req}}, ensure_ascii=False) + "\n", encoding="utf-8")
        event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(Path.cwd()),
                 "transcript_path": str(transcript) if req else None}
        before = log_file.read_text(encoding="utf-8").count("\n") if log_file.exists() else 0
        out = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(event, ensure_ascii=False), text=True,
                             capture_output=True, timeout=40, env={**os.environ, "CLAUDE_PROJECT_DIR": str(Path.cwd())}).stdout
    lines = log_file.read_text(encoding="utf-8").splitlines() if log_file.exists() else []
    row = json.loads(lines[-1]) if len(lines) > before else {"error": "훅이 판정을 남기지 않음 (키 없음?)"}
    if "error" in row:
        print(f"| {req or '(요청 정보 없음)'} | - | - | - | 판단 안 함: {row['error'][:60]} |")
        continue
    a = row["answers"]
    verdict = f"멈춤 ({', '.join(row['fired'])})" if row["fired"] else "통과"
    print(f"| {req or '(요청 정보 없음)'} | {a.get('destructive')} | {a.get('beyond_scope')} | {a.get('impact')} | {verdict} |")
