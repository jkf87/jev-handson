# 2강 실습: Claude Code·Codex 공용 모델 라우터

"이 일을 끝내는 데 어느 모델이면 충분한가?"를 Jev에 묻고, 충분한 후보 중 가장 싼 모델로 `claude -p` 또는 `codex exec`를 실행합니다. [lesson02-model-score-router](../lesson02-model-score-router/)(Codex 전용)의 Score 설계를 그대로 잇고, Claude 모델 4개를 같은 표에 올렸습니다.

## 구조

```text
요청 + 후보 9개 (codex 5 + claude 4, 각자 AAI 점수·단가·설명)
                    │
                    ▼  Jev: 요청 × 후보마다 Score 1개 (0~3, "상위 모델 없이 맡길 만한가")
          코드: score ≥ 2.3 이고 부족 수준(0·1) 확률 ≤ 0.2 인가?
             ├─ 응답 깨짐 / 통과 후보 없음 → REVIEW (억지로 최고 모델을 고르지 않음)
             └─ 통과 후보 중 단가 최저 → PLANNED
                    │
                    ▼  execute.mjs: 선택 모델을 해당 CLI로 읽기 전용 실행
                    ▼  validate.mjs: 모델 답변과 독립적인 검사
```

- **판단은 Jev, 정책은 코드.** 문턱값·제공사 필터·가격 정렬을 바꿔도 Jev를 다시 부르지 않습니다(응답은 `evidence/json_cache.json`).
- `--provider claude|codex|any`로 한쪽 CLI만 쓰게 할 수 있습니다.
- 가격은 입력·출력 각 1,000토큰을 가정한 공개 API 단가 비교값입니다. 구독 사용량 차감이 아닙니다.

## 후보와 근거 (`models.json`)

| 후보 | AAI | 입력/출력 $/1M | AAI 측정 조건 |
|---|---:|---:|---|
| gpt-5.6-luna | 32 | 0.2 / 1.2 | high |
| gpt-5.6-terra | 34 | 2 / 12 | high |
| gpt-5.5 | 37 | 5 / 30 | high |
| gpt-5.6-sol | 42 | 4 / 20 | high |
| gpt-6-astra | 51 | 10 / 50 | high |
| claude-haiku-4-5 | 17 | 1 / 5 | reasoning |
| claude-sonnet-5 | 38 | 2 / 10 | max effort |
| claude-opus-5 | 51 | 5 / 25 | max effort |
| claude-fable-5-1 | 53 | 10 / 50 | max effort, default fallback |

Codex 행은 2026-09-22 기존 실습 값, Claude 행은 2026-09-23 artificialanalysis.ai 모델 페이지에서 읽은 값입니다. **두 계열의 AAI 측정 조건이 달라** 같은 잣대의 비교가 아닙니다. 이 사실을 Jev에게도 `state.evidence_scope`와 후보별 `aai_effort`로 알려줍니다.

## 실행

```sh
node --test router.test.mjs
node router.mjs --live --key-file /path/to/.env                  # Jev 판정 (tasks.json × 9후보, 요청 1개)
node router.mjs --live --provider claude --key-file /path/to/.env # 캐시 응답으로 Claude만 재선택
node router.mjs --live --request "이 함수 이름 바꿔줘" --key-file /path/to/.env
node execute.mjs --provider claude --key-file /path/to/.env      # 실행 계획 미리보기
node execute.mjs --execute --provider claude --task copy --key-file /path/to/.env
node execute.mjs --execute --task standard_code --force claude/claude-haiku-4-5 --key-file /path/to/.env  # 비교 실행
node validate.mjs evidence/execution-XXXX
```

실행 격리:

- **Claude:** `--tools ""`, `--setting-sources ""`, `--strict-mcp-config`, `--disable-slash-commands`, `--no-session-persistence`.
- **Codex:** 사용자 설정·도구·플러그인을 끄고 승인 정책을 never로 둡니다.
- **공통:** 임시 폴더에서 실행하고, 자식 프로세스에는 API 키를 넘기지 않습니다. 두 CLI 모두 기존 로그인을 씁니다.

## 이번 실측 (2026-09-23, jev-1.13.0)

Jev 요청 1개에 Score 45개(5작업 × 9후보)를 묶었습니다. 입력 18,450토큰(약 $0.0008), 1.3초가 걸렸습니다.

| 작업 | luna | terra | 5.5 | sol | astra | haiku | sonnet | opus | fable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| copy (맞춤법) | 2.93 | 2.98 | 2.98 | 2.98 | 2.98 | 2.86 | 2.96 | 2.98 | 2.98 |
| standard_code (평균 함수) | 2.65 | 2.82 | 2.86 | 2.87 | 2.92 | 1.97 | 2.86 | 2.94 | 2.95 |
| complex_design (중복 결제) | 0.86 | 1.13 | 1.60 | 1.63 | 2.55 | 0.50 | 1.91 | 2.79 | 2.87 |
| summary (회의록) | 2.91 | 2.97 | 2.96 | 2.95 | 2.96 | 2.74 | 2.96 | 2.96 | 2.97 |
| refactor_module (계층 분리) | 1.16 | 1.48 | 1.82 | 1.80 | 2.45 | 0.47 | 1.97 | 2.74 | 2.75 |

| 작업 | any | claude만 | codex만 |
|---|---|---|---|
| copy | gpt-5.6-luna | claude-haiku-4-5 | gpt-5.6-luna |
| standard_code | gpt-5.6-luna | claude-sonnet-5 | gpt-5.6-luna |
| complex_design | claude-opus-5 | claude-opus-5 | gpt-6-astra |
| summary | gpt-5.6-luna | claude-haiku-4-5 | gpt-5.6-luna |
| refactor_module | claude-opus-5 | claude-opus-5 | gpt-6-astra |

### 실제 실행과 독립 검사 (Claude만)

| 작업 | 실행 모델 | 시간 | 목록가 환산 | 독립 검사 |
|---|---|---:|---:|---|
| copy | haiku-4-5 | 8.4초 | $0.017 | 정답 문장 포함 PASS |
| summary | haiku-4-5 | 7.0초 | $0.016 | 규칙 6개 PASS (결정 3건·담당자·잡담 제외) |
| standard_code | sonnet-5 | 5.6초 | $0.028 | 추출한 함수로 독립 테스트 9개 PASS |
| complex_design | opus-5 | 187초 | $0.332 | 요구 항목 6/6 언급. 설계의 옳고 그름은 검증 안 함 (passed=null) |
| refactor_module | opus-5 | 98초 | $0.244 | 요구 항목 6/6 언급. 실제 파일이 없어 동작 보존 검증 안 함 (passed=null) |
| **비교:** standard_code | haiku-4-5 (**라우터가 탈락시킨 모델**) | 21초 | $0.018 | 독립 테스트 9개 **PASS** |

목록가 환산은 `claude -p`가 보고한 `total_cost_usd`이며, 구독 로그인에서는 실제 청구액이 아닙니다.

### 수업에서 짚을 장면

**1. 라우터가 보수적이었던 사례.** 평균 함수 작업에서 Haiku는 1.97로 탈락했고 Sonnet이 선택됐습니다. 그런데 Haiku로 강제 실행해도 독립 테스트 9개를 모두 통과했습니다. Jev는 후보 설명과 AAI 점수를 근거로 판단합니다. Haiku의 AAI 17이 Luna(32)보다 한참 낮으니 같은 작업에 1.97 대 2.65가 나온 것으로 보입니다. **Score는 실행 전 예상 적합도일 뿐 실행 결과가 아닙니다.** 이 한 건으로 문턱을 내릴 근거는 없지만, "탈락 모델도 돌려보고 기준을 고친다"는 루프를 보여주기에 좋은 장면입니다.

**2. 같은 요청, 다른 제공사.** 복잡한 설계에서 any 선택은 claude-opus-5($5/$25)였습니다. Codex만 허용하면 gpt-6-astra($10/$50)가 됩니다. 제공사를 한쪽으로 고정하면 이렇게 비용 구조가 달라집니다.

**3. AAI 순위가 그대로 보존되지 않는다.** Sonnet 5(AAI 38)가 설계 작업에서 1.91을 받아 GPT-5.5(37, 1.60)와 Sol(42, 1.63)보다 높았습니다. Jev는 AAI를 사전 근거로 쓰지만 모델 설명과 작업 내용을 함께 읽습니다.

**4. 검증 코드도 틀릴 수 있다.** 처음 판정에서 Sonnet의 standard_code 응답이 "깨진 응답"으로 분류돼 전체가 REVIEW로 떨어졌습니다. 원인은 모델이 아니라 검사 코드였습니다. Jev 확률은 소수 둘째 자리로 반올림돼 오므로 가중 평균이 `score`와 최대 0.03까지 어긋날 수 있는데, 허용 오차를 0.025로 잡아뒀습니다. 지금은 0.035입니다.

## 실행 중 막혔던 것 (기록 보존)

| 기록 | 원인 | 조치 |
|---|---|---|
| `execution-nT1zrQ` (codex/luna) | Codex 계정 사용 한도 소진. 2026-09-26 17:33에 풀림 | `usage_limit` 진단 추가. 한도가 풀리면 `--provider codex`로 재실행 |
| `execution-Aotga4`, `execution-QeeC9J` (claude) | `--bare`는 키체인을 읽지 않아 구독 로그인이 끊김 → "Not logged in" | `--bare` 대신 개별 격리 플래그 사용 |
| (같은 증상) | 자식 환경에서 `USER`를 뺌 | `USER`만 전달. `USER`와 `LOGNAME`을 함께 넘기면 2회 모두 로그인 실패, `USER`만 넘기면 2회 모두 성공해 `LOGNAME`은 넘기지 않음 |

**Codex 쪽 실제 실행은 이번에 하지 못했습니다.** Codex 판정(Score)과 실행 계획은 만들어지지만, 실행 성공은 기존 실습(`lesson02-model-score-router/evidence/execution-G4plzX`, 2026-09-22)의 기록이 마지막입니다.

## 다음에 확인할 것

- Codex 한도가 풀린 뒤 codex/luna로 copy·summary·standard_code 실행과 검사
- 탈락 후보 강제 실행을 작업마다 한 번씩 돌려, 문턱 2.3이 너무 높은지 판단
- 설계형 작업(complex_design, refactor_module)에 대한 채점 기준(루브릭 판정자)
- 후보 이름을 가리거나 순서를 바꿨을 때 Score 변화
