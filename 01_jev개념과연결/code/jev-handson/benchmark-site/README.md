# RouteLab

한국어 악성 댓글 100개를 동일한 영어 분류 기준으로 처리해 일반 LLM(`agy -p`)과 JEV typed decision의 속도 및 품질을 비교하는 로컬 벤치마크 사이트입니다.

## 실행

```powershell
npm install
npm run sample
npm start
```

브라우저에서 `http://127.0.0.1:4173`을 엽니다.

OpenRouter 키는 다음 순서로 읽습니다.

1. `OPENROUTER_API_KEY` 환경 변수
2. 프로젝트 상위 폴더의 `env.txt`
3. 이 폴더의 `env.txt`

API 키는 브라우저로 전송하지 않습니다. AGY는 로컬에 설치된 `agy` 명령을 사용하며 기본 비교 모델은 `gemini-3.8-flash-low`입니다.

## 라우팅

- `none` → `allow`
- `offensive` → `review`
- `hate` → `block`

샘플은 `nayohan/korean-hate-speech` train split 전체에서 고정 시드로 섞은 뒤 `hate` 34개, `offensive` 33개, `none` 33개를 선택합니다. 원문의 댓글, 기사 제목 및 라벨은 수정하지 않습니다.
