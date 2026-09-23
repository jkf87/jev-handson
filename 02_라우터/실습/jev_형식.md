# Jev 요청·응답 형식 (에이전트 참고용)

2026-09-23 실측 기준(jev-1.13.0). 공식 문서: https://docs.typesafe.ai (전체 텍스트 https://docs.typesafe.ai/llms-full.txt)

## 요청
`POST https://api.typesafe.ai/v1/systemone`
헤더: `Authorization: Bearer $TYPESAFE_API_KEY`, `Content-Type: application/json`
(파이썬 urllib는 기본 User-Agent가 403으로 막히므로 User-Agent 헤더를 직접 넣는다. Node fetch·curl은 그대로 통과)

```json
{
  "model": "jev-latest",
  "state": { "message": "…판단에 필요한 사실만…" },
  "questions": {
    "urgent": { "type": "noul", "instructions": "Does `message` need a reply today?" },
    "team": {
      "type": "choice",
      "instructions": "Which team should handle `message`?",
      "criteria": { "billing": "charges, refunds", "technical": "bugs, API errors", "none": "none of the above" }
    },
    "impact": {
      "type": "score",
      "instructions": "How badly is the customer blocked?",
      "criteria": ["no impact", "a workaround exists", "work is blocked"]
    }
  }
}
```
- `model`은 필수(빠지면 HTTP 422).
- 질문 세 개는 같은 `state`를 보고 병렬로 답한다. 서로의 답은 보지 못한다.
- choice에는 딱 맞는 게 없을 때 고를 후보(none·ask_user 등)를 넣는다.
- 지시문(instructions)은 영어, state 안의 데이터는 한국어여도 된다.

## 응답
```json
{
  "model": "jev-1.13.0",
  "answers": {
    "urgent": { "type": "noul", "noul": 0.85 },
    "team": { "type": "choice", "choice": "technical", "confidence": 0.99,
              "probabilities": { "billing": 0.0, "technical": 1.0, "none": 0.0 } },
    "impact": { "type": "score", "score": 2.0, "confidence": 1.0,
                "probabilities": { "0": 0.0, "1": 0.0, "2": 1.0 } }
  },
  "usage": { "input_tokens": 512, "output_tokens": 75 }
}
```
- noul: 예일 확률. choice: 고른 후보 + 후보별 확률(합 1). score: 단계 기대값(0부터) + confidence.
- 가격: 입력 100만 토큰당 $0.042, 출력 무료.
