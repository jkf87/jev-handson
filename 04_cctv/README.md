# 04 · CCTV 영상을 보고 상태 판단하기 (OneJev)

동영상을 받는 오픈 System One 판단 모델 [OneJev](https://github.com/OmniJev/OneJev)(Apache-2.0)에 CCTV 영상 8초 묶음을 보내고, 글 대신 보기마다 확률을 받아요. 노트북은 저장소 맨 위 `04_CCTV상태판단.ipynb`예요(Colab T4 · OneJev-0.8B · GPU가 없으면 아래 기록으로 재생).

| 파일 | 내용 |
|---|---|
| `scene_examples.json` | 장면 세 가지(쓰러짐 · 다툼 · 물건 방치)의 대표 프레임과 정답 박스(CAVIAR XML 좌표) |
| `gt.json` | 13클립 정답 시간축(초). 싸움 · 가방 방치는 CAVIAR XML 라벨, 쓰러짐 구간은 강사가 눈으로 붙인 값 |
| `results/cctv-0.8B.json` | 2026-10-12 RTX A4000 · OneJev-0.8B float16 · 13클립 전체(클립 판단 + 8초 창 194개) |
| `results/cctv-4B.json` | 같은 날 OneJev-4B · 클립 판단 13개 + 4클립 시간축(4초 간격). GPU를 다른 프로그램과 나눠 써서 지연은 참고만 |
| `cctv_run.py` · `serve_and_run.py` | 강사가 쓴 실행 코드(`qev serve --multimodal` 뒤 판단) |
| `make_figs.py` · `timeline_wide.png` | 시간축 그림 · 알람 규칙 비교 |

실측 요약(0.8B): 쓰러짐 0.5 이상 두 번 연속 → 쓰러짐 3/3 잡고 헛알람 5/10, 0.9 이상 두 번 연속 → 2/3 잡고 헛알람 0/10. 클립 전체 상황 분류는 0.8B 2/13 · 4B 3/13(대부분 "지나감"으로 답함, 가방 방치는 둘 다 못 잡음). 8장 묶음 판단 한 번 0.8B 약 2.4초(A4000).

**데이터 출처**: EC Funded CAVIAR project/IST 2001 37540, http://homepages.inf.ed.ac.uk/rbf/CAVIAR/ (CC BY-SA). 배우가 연출한 건물 로비 영상이에요. 노트북은 원본 사이트에서 클립을 직접 받아요(이 저장소에 영상은 없어요).

실제 학교 CCTV는 개인영상정보예요. 수업 · 연구에 쓰려면 목적 외 이용 제한, 비식별, IRB를 먼저 확인하세요.
