#!/usr/bin/env node
// 2강 프롬프트 ②③의 예제 답안: 40건 채점 → 기록 저장 → 기록으로 정책만 바꿔 재채점(API 재호출 없음).
//   node mini/eval.mjs                                          # 40건 호출·채점, results/mini-<시각>.json 저장
//   node mini/eval.mjs --replay results/<기록>.json --policy '{"riskFirst":true}'
// 완성본 기록(results/router-jev-*.json)도 재생할 수 있다 → 키가 없어도 채점 실습 가능.
import fs from 'node:fs';
import { buildRequest, askJev, decide, POLICY } from './router.mjs';

const rows = fs.readFileSync(new URL('../data/messages.jsonl', import.meta.url), 'utf8').trim().split('\n').map((l) => JSON.parse(l));
const arg = (k) => { const i = process.argv.indexOf(k); return i > 1 ? process.argv[i + 1] : null; };
const policy = { ...POLICY, ...JSON.parse(arg('--policy') || '{}') };

let saved = null;
if (arg('--replay')) {
  const raw = JSON.parse(fs.readFileSync(arg('--replay'), 'utf8'));
  saved = raw.results ? raw.results.map((x) => ({ id: x.id, ...x.decision })) : raw;   // 완성본 형식도 받는다
}

// 정답 라벨 → 기대 행동
const expected = (r) => (r.route === 'chat' ? 'reply' : r.route === 'spam' ? 'block' : r.route === 'unclear' ? 'clarify'
  : r.confirm ? 'confirm' : `dispatch:${r.target}`);
const key = (d) => (d.action === 'dispatch' ? `dispatch:${d.target}` : d.action);

const log = [];
let ok = 0;
for (const r of rows) {
  const resp = saved ? saved.find((s) => s.id === r.id) : { id: r.id, ...(await askJev(buildRequest(r.text))) };
  const got = key(decide(resp.answers, policy)), want = expected(r);
  if (got === want) ok++;
  else console.log(`✗ ${r.id} ${r.text.slice(0, 36)} → ${got} (정답 ${want})  route ${resp.answers.route.choice} ${resp.answers.route.probabilities[resp.answers.route.choice]} · confirm ${resp.answers.confirm.noul}`);
  log.push({ id: r.id, model: resp.model, answers: resp.answers, usage: resp.usage, latencyMs: resp.latencyMs });
}
const lat = log.map((x) => x.latencyMs).filter(Number.isFinite).sort((a, b) => a - b);
console.log(`\n행동 일치 ${ok}/${rows.length} · 지연 중앙값 ${lat[lat.length >> 1]}ms · 정책 ${JSON.stringify(policy)}`);
if (!saved) {
  fs.mkdirSync('results', { recursive: true });
  const file = `results/mini-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
  fs.writeFileSync(file, JSON.stringify(log, null, 1));
  console.log(`기록: ${file}`);
}
