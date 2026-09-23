# Codex(또는 Claude Code)에 순서대로 붙여 넣을 프롬프트

이 폴더(`02_라우터/routers/codex`)에서 에이전트를 켜고 위에서부터 하나씩 붙여 넣습니다. `.env`는 사람이 직접 편집합니다(키를 채팅에 붙여 넣지 않기).

## 1. 이해하기 (API 호출 없음)
```
이 폴더의 README.md, questions.mjs, judge.mjs, policy.mjs, handlers.mjs, service.mjs를 읽고
TOOL / CODEX / ASK / STOP 네 경로가 각각 언제 나오는지, mock과 live 모드가 어떻게 다른지 표로 설명해 줘.
아직 API 호출이나 codex exec 실행은 하지 말고, npm test로 로컬 분기만 확인해 줘.
```

## 2. 실제 Jev로 판단 보기 (Codex 실행은 끔)
```
.env의 키 값은 읽거나 출력하지 마. JEV_MODE=live, CODEX_MODE=dry-run으로 npm start를 띄우고,
node cli.mjs --all과 새 문장 두 개("문서 프로젝트에 어떤 파일들이 있어?", "앱 코드에 테스트를 어떻게 붙이면 좋을지 설명해줘")를 보내
judgmentSource·model·action·target·route·reason을 표로 보여 줘. 끝나면 서버를 꺼 줘.
```

## 3. 후보 설명 고치기
```
기대와 다른 경로가 나온 사례가 있으면, 정답을 코드에 박아 넣지 말고 원인을 먼저 나눠 줘:
state 부족, 후보 설명 겹침, 낮은 confidence, 정책 코드, 서비스 오류 중 어디인지.
후보 설명(config/projects.json의 description, questions.mjs의 ACTIONS)을 최소한으로 고친 뒤 같은 사례를 다시 보내 비교해 줘.
```

## 4. 내 프로젝트 추가
```
config/projects.json에 추가할 프로젝트의 별칭, 설명, 경로를 먼저 나에게 물어봐.
설명에는 내가 그 프로젝트를 부르는 이름을 넣고, Jev에는 별칭과 설명만 보내. 경로는 서버의 허용 목록에서만 읽어.
config/cases.json에 새 프로젝트를 가리키는 문장과 대상을 빼먹은 문장을 추가하고 npm test와 실제 Jev로 다시 확인해 줘.
```

## 5. 필요한 요청만 Codex에 넘기기
```
handlers.mjs에서 CODEX 경로에만 codex exec가 있는지 확인해 줘. 읽기 전용(-s read-only)과 검증된 프로젝트 경로(-C),
요청은 stdin으로 넘기는지도 확인해. TOOL / ASK / STOP에서는 실행 어댑터를 부르지 않는 시험을 유지해.
나는 CODEX_MODE=live로 바꿔서 "앱 프로젝트의 코드를 읽고 오류 원인과 수정안을 설명해줘" 하나만 실행할 거야. 그 명령을 알려 줘.
```

## 6. 잘못된 라우팅 고치기
```
내가 보내는 오분류 사례를 정답으로 하드코딩하지 마. 원인을 나누고, 최소 변경 뒤 이전 사례를 모두 다시 검증해.
Codex를 불렀는지뿐 아니라 사용자의 원래 요청이 끝났는지도 확인해 줘.
```

## 처음부터 직접 만들기 (도전)
```
TypeSafe 공식 API 문서(https://docs.typesafe.ai/llms-full.txt)를 보고 Node.js 로컬 라우터를 만들어 줘.
입력은 message와 context, action과 target Choice를 한 요청에 보낸다. TOOL(등록된 파일 목록/README 원문), CODEX(설명·분석),
ASK(정보 부족/판단 오류), STOP(지원 밖)으로 나눈다. 프로젝트 경로는 서버의 허용 목록에서만 고른다.
기본은 JEV_MODE=mock, CODEX_MODE=dry-run. CODEX는 codex exec 읽기 전용으로, 사용자 문장은 쉘 문자열이 아니라 stdin으로 넘긴다.
네 경로를 검증하는 시험을 만들고, README에 준비 → 모의 실행 → 실제 Jev → Codex 실행 순서를 적어 줘.
```
