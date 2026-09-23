# 로컬 판단 모델 서버 자리 (3강 실습 ② · 프롬프트 ③)

Jev와 같은 `/v1/systemone` 형식을 받는 로컬 모델 [decider](https://pypi.org/project/decider-ai/)를 이 폴더에 띄웁니다.
가상환경(`.venv-decider/`)과 서버 기록(`*.log`)은 여기 생기지만 배포본·저장소에는 넣지 않습니다.

```bash
cd 03_유사프로젝트/code/local
uv venv .venv-decider --python 3.12
uv pip install --python .venv-decider/bin/python "decider-ai[serve,metal]==1.1.2"   # Mac이 아니면 [serve]
DECIDER_MODEL=Mapika/decider-2b .venv-decider/bin/uvicorn decider.serve:app --host 127.0.0.1 --port 8000
```

- 첫 실행 때 모델 가중치(몇 GB)를 받습니다. 첫 호출은 워밍업으로 15초 넘게 걸릴 수 있어요.
- 확인: `curl localhost:8000/health` → `{"ok":true,"model":"Mapika/decider-2b","device":"mps"}`
- 쓰는 쪽은 주소만 바꿉니다: `TYPESAFE_BASE_URL=http://127.0.0.1:8000` (키 불필요)
- 다 쓰면 서버를 꺼 두세요(`lsof -iTCP:8000`으로 확인).
