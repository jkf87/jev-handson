# 판단 규칙 (Codex)

- 사용자에게 선택지를 묻기 전, 위험 명령(삭제·force push·외부 전송) 전, 명령 실패 후에는
  `.agents/skills/jev-judgment/SKILL.md`의 프로토콜대로 `python3 .agents/skills/jev-judgment/scripts/jev.py`를 먼저 호출한다.
- API 키는 jev.py가 환경변수 TYPESAFE_API_KEY → 없으면 저장소의 `.env` 순서로 알아서 찾는다. 환경변수를 지우거나 바꾸지 말고 그대로 실행한다.
- Jev 판정이 Protocol 2 임계값을 넘으면 실행하지 말고 값과 함께 사용자에게 확인을 받는다. 호출 자체가 실패하면 위험 명령은 실행하지 말고 사용자에게 확인을 받는다.
