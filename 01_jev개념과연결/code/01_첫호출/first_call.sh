#!/bin/bash
# 가장 짧은 Jev 호출: curl 한 번. 키는 환경변수로만 넘긴다(화면·파일에 적지 않기).
#   export TYPESAFE_API_KEY=...   (또는 code/.env)
#   ./first_call.sh [bodies/01_세가지질문.json]
set -e
cd "$(dirname "$0")"
# 키: 환경변수 → 이 폴더 .env → 상위 폴더(code/) .env 순서
for f in .env ../.env; do [ -z "$TYPESAFE_API_KEY" ] && [ -f "$f" ] && export $(grep -E '^TYPESAFE_API_KEY=' "$f" | xargs); done
[ -z "$TYPESAFE_API_KEY" ] && { echo "TYPESAFE_API_KEY가 없습니다. console.typesafe.ai/keys 에서 발급 → export TYPESAFE_API_KEY=..."; exit 1; }
BODY=${1:-bodies/01_세가지질문.json}
curl -sS https://api.typesafe.ai/v1/systemone \
  -H "Authorization: Bearer $TYPESAFE_API_KEY" \
  -H "Content-Type: application/json" \
  -d @"$BODY" -w '\n[http %{http_code}, %{time_total}s]\n'
