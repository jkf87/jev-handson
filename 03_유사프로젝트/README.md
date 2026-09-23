# 3강 · Jev를 닮은 프로젝트들 — jev-ultrafast, API vs 로컬, 활용 사례

- 에이전트에게 시킬 때: [`프롬프트.md`](프롬프트.md) ①~⑥ — `code/`에서 (키: `cp ../../02_라우터/실습/.env code/.env`)
- 직접 칠 때: [`code/README.md`](code/README.md)
- **Colab 노트북**: [`colab/3강_Jev닮은모델_Colab.ipynb`](colab/3강_Jev닮은모델_Colab.ipynb) · [Colab에서 열기](https://colab.research.google.com/github/jkf87/jev-handson/blob/main/03_%EC%9C%A0%EC%82%AC%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8/colab/3%EA%B0%95_Jev%EB%8B%AE%EC%9D%80%EB%AA%A8%EB%8D%B8_Colab.ipynb) — 무료 T4로 openjev(SemIf · Qwen3.5-4B) 판단 한 번을 7단계 위젯으로 뜯어보고, 병렬 판단 · API vs 로컬 · 보정 결과를 차트로 봐요. 무거운 14B · llama.cpp는 미리 잰 값으로, Jev-Omni는 80GB GPU 선택 셀로(`colab/README.md`)

| 폴더 | 내용 |
|---|---|
| `code/ultrafast/` | [jev-ultrafast](https://github.com/browser-use/jev-ultrafast) 실행 스크립트: 임시 Chrome(9333) 띄우기 · 구글 항공권 · 네이버 항공권(모바일, 가려진 요소 빼기 · DONE 확률 게이트) |
| `code/local/` | 로컬 판단 모델 decider 서버 띄우는 자리(Jev와 같은 `/v1/systemone` 형식) |
| `code/a4000/` | GPU 서버(A4000)에서 decider · OpenJev를 돌린 스크립트 |
| `code/evaluate.mjs` · `evidence/api-vs-local/` | 같은 40건을 API와 로컬 엔진에 넣은 결과를 2강 정책으로 채점 |
| `colab/` | Colab 노트북 + 만든 재료: 생성기 `build_notebook.py` · Manim 영상 3개와 소스(`assets/scenes.py`) · 위젯(`widget_template.html`) · 미리 잰 숫자(`precomputed.json`, 묶음마다 출처) |
| `code/usecases/` | 활용 사례 예제 세 개: 화면 요소 표에서 누를 것 · 틱택토 수 · 로봇 다음 행동 (Jev가 고르고 코드가 실행·확인·멈춤) |

9/23 실측 요약: 구글 항공권 11~18초(검증 6/6) · 네이버 모바일 8초대(검증 5/5, 데스크톱은 9번 모두 실패) · API vs 로컬 같은 40건 Jev 92.5% / decider-2b 72.5% / Qwen JSON 생성 92.5%(17배 느림) · 예제 세 개 10건 중 9건.
