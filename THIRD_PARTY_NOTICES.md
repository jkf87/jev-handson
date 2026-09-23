# 제3자 코드 고지

## jev-judgment (MIT)

- 파일: `01_jev개념과연결/code/01_첫호출/jev.py` — 원본 그대로(수정 없음)
- 출처: https://github.com/HyunjunJeon/jev-judgment `skills/jev-judgment/scripts/jev.py` (커밋 f6056e7)
- 1강에서 설치하는 커뮤니티 스킬의 스크립트를, 스킬 설치 전에도 첫 호출을 해 볼 수 있게 함께 둡니다.

```text
MIT License

Copyright (c) 2026 HyunjunJeon

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## korean-hate-speech (CC BY-SA 4.0)

- 파일: `01_jev개념과연결/code/04_악플탐지/data/valid.jsonl` — 검증 세트 471건을 JSON Lines로 옮긴 것(열 이름만 바꿈)
- 파일: `01_jev개념과연결/code/jev-handson/benchmark-site/data/sample-100.json` — train에서 고정 시드로 뽑은 100건(hate 34 · offensive 33 · none 33, 1강 녹화 때 에이전트가 만든 표본)
- 출처: https://huggingface.co/datasets/nayohan/korean-hate-speech · 원본 https://github.com/kocohub/korean-hate-speech
- 논문: Jihyung Moon, Won Ik Cho, Junbum Lee. BEEP! Korean Corpus of Online News Comments for Toxic Speech Detection. SocialNLP 2020
- 라이선스: Creative Commons Attribution-ShareAlike 4.0 International (https://creativecommons.org/licenses/by-sa/4.0/) — 이 파일도 같은 라이선스를 따릅니다
- 실제 악플(욕설·혐오 표현)이 들어 있습니다

## 참고한 문서

- `02_라우터/routers/claude-code/`는 TypeSafe 문서의 [Skill suggestion 쿡북](https://docs.typesafe.ai/cookbooks/skill_suggestion) 구조(2요청 · 게이트 · 재검증)를 Node로 옮긴 것입니다. 코드는 새로 썼고, 게이트 질문 문구는 쿡북을 따랐습니다.
- `03_유사프로젝트/code/ultrafast/`는 [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast)를 따로 받아서 그 안에서 실행하는 스크립트입니다(원본 저장소는 여기 들어 있지 않고, 그 라이선스를 따릅니다).
