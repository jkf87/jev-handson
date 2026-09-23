# 이 프로젝트의 판단 규칙

- 사용자에게 객관식·예/아니오 질문을 하기 전에 jev-judgment 스킬(Protocol 1)로 이미 답이 정해졌는지 먼저 확인한다.
- 파일 삭제·덮어쓰기, git reset/push --force, 외부 전송 명령은 실행 전에 jev-judgment Protocol 2로 판정받는다.
- 명령이 실패하면 재시도 전에 Protocol 3으로 실패 종류와 비밀값 노출 여부를 확인한다.
- Jev 판정이 행동을 바꿨으면 확률과 함께 한 줄로 알린다. 호출이 실패하면 Jev 없이 원래대로 판단한다.
(스킬은 권고, 훅은 강제다. 삭제·전송 같은 위험 명령은 .claude/settings.json의 PreToolUse 훅이 매번 막는다.)
