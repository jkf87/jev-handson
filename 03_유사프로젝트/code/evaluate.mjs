#!/usr/bin/env node
// 3강 실습: 같은 40건을 API(Jev)와 로컬(decider·OpenJev·로컬 LLM) 엔진에 넣은 결과를 '같은 정책 코드'로 채점한다.
// 정책·정답은 2강 코드(../../02_라우터/code)를 그대로 쓴다. 엔진만 바뀌고 판단→행동 규칙은 같다.
//   node evaluate.mjs            # evidence/api-vs-local/ 의 기록을 읽어 표를 만든다
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { decide, expectedAction, actionKey } from '../../02_라우터/code/lib/policy.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const EV = path.join(HERE, '..', 'evidence', 'api-vs-local');
const R2 = path.join(HERE, '..', '..', '02_라우터', 'code', 'results');
const gold = Object.fromEntries(fs.readFileSync(path.join(HERE, 'data/routing_bodies.jsonl'), 'utf8').trim().split('\n')
  .map((l) => JSON.parse(l)).map((r) => [r.id, r.gold]));

const readJsonl = (f) => fs.readFileSync(f, 'utf8').trim().split('\n').map((l) => JSON.parse(l));
const latest = (dir, prefix) => fs.existsSync(dir) ? fs.readdirSync(dir).filter((f) => f.startsWith(prefix)).sort().pop() : undefined;

// OpenJev의 배열 응답을 Jev 답 모양으로 바꾼다.
function fromOpenjev(a) {
  const dist = (q) => Object.fromEntries(q.option_ids.map((id, i) => [id, q.probabilities[i]]));
  const top = (d) => Object.entries(d).sort((x, y) => y[1] - x[1])[0][0];
  const route = dist(a.route), target = dist(a.target), confirm = dist(a.confirm);
  return { route: { choice: top(route), probabilities: route }, target: { choice: top(target), probabilities: target }, confirm: { noul: confirm.yes } };
}

const engines = [];

// 1) Jev API — 2강에서 저장한 기록
const jevFile = latest(R2, 'router-jev-');
if (jevFile) {
  const j = JSON.parse(fs.readFileSync(path.join(R2, jevFile), 'utf8'));
  engines.push({ name: 'Jev API (TypeSafe)', where: '클라우드', model: j.model, costPer1M: 0.042,
    rows: j.results.map((r) => ({ id: r.id, answers: r.decision.answers, ms: r.decision.latencyMs, inTok: r.decision.usage?.input_tokens })) });
}
// 2) decider-2b — A4000 CUDA (같은 /v1/systemone 형식)
if (fs.existsSync(path.join(EV, 'out_decider.jsonl'))) {
  const rows = readJsonl(path.join(EV, 'out_decider.jsonl')).filter((r) => r.id);
  engines.push({ name: 'decider-2b (A4000 CUDA)', where: '내 GPU 서버', model: rows[0].resp.model, costPer1M: 0,
    rows: rows.map((r) => ({ id: r.id, answers: r.resp.answers, ms: r.ms, inTok: r.resp.usage?.input_tokens })) });
}
// 3) decider-2b — Mac MPS (router.mjs를 TYPESAFE_BASE_URL만 바꿔 실행한 기록)
const macFile = latest(EV, 'router-decider-mac-');
if (macFile) {
  const j = JSON.parse(fs.readFileSync(path.join(EV, macFile), 'utf8'));
  engines.push({ name: 'decider-2b (Mac MPS)', where: '내 노트북', model: j.model, costPer1M: 0,
    rows: j.results.map((r) => ({ id: r.id, answers: r.decision.answers, ms: r.decision.latencyMs, inTok: r.decision.usage?.input_tokens })) });
}
// 4) OpenJev(SemIf 계열) Qwen3.5-4B — A4000, 질문 3개를 따로 호출
if (fs.existsSync(path.join(EV, 'out_openjev.jsonl'))) {
  const rows = readJsonl(path.join(EV, 'out_openjev.jsonl')).filter((r) => r.id);
  engines.push({ name: 'OpenJev Qwen3.5-4B (A4000)', where: '내 GPU 서버', model: 'Qwen/Qwen3.5-4B direct readout', costPer1M: 0,
    rows: rows.map((r) => ({ id: r.id, answers: fromOpenjev(r.answers), ms: r.ms.route + r.ms.target + r.ms.confirm })) });
}

// 5) 로컬 LLM(생성 방식): 2강 compare.mjs의 Ollama 기록. 확률이 없어 JSON 라벨을 같은 행동으로 바꾼 결과다.
const olFile = latest(R2, 'compare-ollama_');
if (olFile) {
  const j = JSON.parse(fs.readFileSync(path.join(R2, olFile), 'utf8'));
  engines.push({ name: 'Qwen3.5-4B 생성(JSON) (Mac Ollama)', where: '내 노트북', model: j.summary.model, costPer1M: 0, precomputed: true,
    rows: j.out.map((o) => ({ id: o.id, got: o.got, routeGot: o.routeGot, ms: o.latencyMs })) });
}

function pct(xs, p) { const s = xs.filter(Number.isFinite).sort((a, b) => a - b); return s.length ? Math.round(s[Math.min(s.length - 1, Math.floor(p * s.length))]) : null; }

const table = [];
const perItem = {};
for (const e of engines) {
  let ok = 0, routeOk = 0;
  for (const r of e.rows) {
    const g = gold[r.id];
    const want = expectedAction(g);
    const got = e.precomputed ? r.got : actionKey(decide(r.answers));
    if (want === got) ok++;
    if ((e.precomputed ? r.routeGot : r.answers?.route?.choice) === g.route) routeOk++;
    (perItem[r.id] ||= { id: r.id, expected: want })[e.name] = got;
  }
  const n = e.rows.length;
  const tok = e.rows.reduce((s, r) => s + (r.inTok || 0), 0);
  table.push({ engine: e.name, where: e.where, model: e.model, n, actionAcc: ok / n, routeAcc: routeOk / n,
    p50ms: pct(e.rows.map((r) => r.ms), 0.5), p95ms: pct(e.rows.map((r) => r.ms), 0.95),
    costPer1k: e.costPer1M ? (tok / n) * 1000 * e.costPer1M / 1e6 : 0 });
}

const lines = ['| 엔진 | 어디서 | 행동 일치 | route 일치 | 지연 p50 | p95 | 1,000건 비용 |', '|---|---|---:|---:|---:|---:|---:|'];
for (const t of table) lines.push(`| ${t.engine} | ${t.where} | ${(t.actionAcc * 100).toFixed(1)}% | ${(t.routeAcc * 100).toFixed(1)}% | ${t.p50ms}ms | ${t.p95ms}ms | $${t.costPer1k.toFixed(4)} |`);
const md = lines.join('\n');
console.log(md);
const disagree = Object.values(perItem).filter((x) => new Set(engines.map((e) => x[e.name])).size > 1);
console.log(`\n엔진끼리 행동이 갈린 메시지 ${disagree.length}/40`);
fs.writeFileSync(path.join(EV, 'summary.md'), md + '\n');
fs.writeFileSync(path.join(EV, 'summary.json'), JSON.stringify({ table, perItem }, null, 1));
