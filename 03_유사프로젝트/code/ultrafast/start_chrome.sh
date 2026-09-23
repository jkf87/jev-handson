#!/bin/bash
# 강의용 임시 Chrome을 따로 띄운다. 평소 쓰는 Chrome 프로필·로그인과 분리된 빈 프로필이다.
#   ./start_chrome.sh            # 데스크톱 화면
#   ./start_chrome.sh --mobile   # 아이폰 UA (네이버 항공권은 모바일 화면이 덜 움직여 에이전트가 잘 된다)
# 이후 실행할 때는 항상  BU_NAME=jevlecture BU_CDP_URL=http://127.0.0.1:9333  을 붙인다.
PROFILE="${TMPDIR:-/tmp}/jevlecture-chrome-$(date +%s)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ARGS=(--remote-debugging-port=9333 --user-data-dir="$PROFILE" --no-first-run --no-default-browser-check --lang=ko-KR)
if [ "$1" == "--mobile" ]; then
  ARGS+=(--window-size=460,1000 "--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
else
  ARGS+=(--window-size=1400,1000)
fi
pkill -f "remote-debugging-port=9333" 2>/dev/null; sleep 1
"$CHROME" "${ARGS[@]}" about:blank >/dev/null 2>&1 &
sleep 3
curl -s http://127.0.0.1:9333/json/version | grep -E '"Browser"|User-Agent'
echo "profile: $PROFILE"
