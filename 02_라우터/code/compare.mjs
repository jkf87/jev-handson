#!/usr/bin/env node
// 같은 40건을 여러 '라우터 두뇌'에 넣고 정확도·형식 오류·지연·비용을 비교한다.
//   node compare.mjs --engines jev,claude-cli:haiku,claude-cli:sonnet,ollama:qwen3.5:4b
//   node compare.mjs --engines jev --jev-from results/router-jev-XXXX.json   # Jev는 저장된 기록 사용
//   node compare.mjs --engines jev,claude-cli:haiku --limit 10               # 40건 중 고르게 10건만(맛보기, 약 2분)
//   node compare.mjs --report                                               # results/compare-*.json 모아 표로
// 키(TYPESAFE_API_KEY)는 실행 폴더의 .env 또는 환경변수에서 읽는다. .env가 있는 폴더에서 실행할 것.
// 엔진별 원시 기록은 results/compare-<엔진>-<시각>.json 에 남는다.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { route } from './router.mjs';
import { expectedAction, actionKey } from './lib/policy.mjs';
import { callLlm, parseLabels, decideFromLabels } from './lib/llm.mjs';
import { jevConfig } from './lib/jev.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PRICES = JSON.parse(fs.readFileSync(path.join(HERE, 'prices.json'), 'utf8')).models;
const ALL_ROWS = fs.readFileSync(path.join(HERE, 'data/messages.jsonl'), 'utf8').trim().split('\n').map((l) => JSON.parse(l));
let rows = ALL_ROWS;
// --limit N: 40건에서 고르게 N건 (10건이면 대화 3 · 작업 4(확인 2) · 되묻기 2 · 스팸 1)
function sample(all, n) {
  if (!n || n >= all.length) return all;
  return [...new Set([...Array(n)].map((_, k) => Math.min(all.length - 1, Math.floor((k + 0.9) * all.length / n))))].map((i) => all[i]);
}

function priceFor(model) {
  const key = Object.keys(PRICES).find((k) => model && model.startsWith(k));
  return key ? PRICES[key] : null;
}

async function runJev(jevFrom) {
  const saved = jevFrom ? JSON.parse(fs.readFileSync(jevFrom, 'utf8')).results : null;
  const out = [];
  for (const row of rows) {
    const d = saved ? saved.find((s) => s.id === row.id).decision : await route(row.text);
    const inTok = d.usage?.input_tokens || 0, outTok = d.usage?.output_tokens || 0;
    out.push({ id: row.id, expected: expectedAction(row), got: actionKey(d), routeGot: d.route?.choice ?? null,
      formatError: d.reason?.startsWith('invalid') || false, latencyMs: d.latencyMs, inputTokens: inTok, outputTokens: outTok,
      costUsd: inTok * PRICES['jev-1.13.0'].input / 1e6, model: d.model, raw: d.answers });
  }
  return out;
}

async function runLlm(engine) {
  const out = [];
  for (const row of rows) {
    let r, parsed, d, error = null;
    try {
      r = await callLlm(engine, row.text);
      parsed = parseLabels(r.text);
      d = decideFromLabels(parsed);
    } catch (e) {
      error = String(e.message).slice(0, 200);
      parsed = { ok: false, error: 'call_failed' };
      d = { action: 'review', reason: 'call_failed' };
    }
    const p = r ? priceFor(r.model) : null;
    const listCost = p ? (r.inputTokens * p.input + r.outputTokens * p.output) / 1e6 : null;
    out.push({ id: row.id, expected: expectedAction(row), got: actionKey(d), routeGot: parsed.labels?.route ?? null,
      formatError: !parsed.ok, fenced: parsed.fenced || false, latencyMs: r?.latencyMs, apiMs: r?.apiMs,
      inputTokens: r?.inputTokens || 0, outputTokens: r?.outputTokens || 0, thinkingTokens: r?.thinkingTokens || 0,
      costUsd: r?.costUsd ?? listCost ?? 0, costFromPrices: listCost, costBasis: r?.costBasis, model: r?.model, text: r?.text, error });
    process.stdout.write(d.action === 'review' ? 'x' : (actionKey(d) === expectedAction(row) ? '.' : '!'));
  }
  process.stdout.write('\n');
  return out;
}

function summarize(engine, out) {
  const n = out.length;
  const lat = out.map((o) => o.latencyMs).filter(Number.isFinite).sort((a, b) => a - b);
  const q = (p) => lat.length ? lat[Math.min(lat.length - 1, Math.floor(p * lat.length))] : null;
  const sum = (k) => out.reduce((s, o) => s + (o[k] || 0), 0);
  const routeOk = out.filter((o) => rows.find((r) => r.id === o.id).route === o.routeGot).length;
  return {
    engine, model: out.find((o) => o.model)?.model, n,
    actionAcc: out.filter((o) => o.got === o.expected).length / n,
    routeAcc: routeOk / n,
    formatErrors: out.filter((o) => o.formatError).length,
    fenced: out.filter((o) => o.fenced).length,
    p50ms: q(0.5), p95ms: q(0.95),
    avgInputTokens: Math.round(sum('inputTokens') / n), avgOutputTokens: Math.round(sum('outputTokens') / n),
    totalCostUsd: sum('costUsd'), costPer1kUsd: (sum('costUsd') / n) * 1000,
  };
}

function report() {
  const files = fs.readdirSync(path.join(HERE, 'results')).filter((f) => f.startsWith('compare-') && f.endsWith('.json'));
  const latest = {};
  for (const f of files.sort()) { const j = JSON.parse(fs.readFileSync(path.join(HERE, 'results', f), 'utf8')); latest[j.summary.engine] = j.summary; }
  const lines = ['| 엔진 | 모델 | 건수 | 행동 일치 | route 일치 | 형식 오류 | 지연 p50 | p95 | 평균 입력/출력 토큰 | 1,000건 비용 |', '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|'];
  for (const s of Object.values(latest).sort((a, b) => a.costPer1kUsd - b.costPer1kUsd)) {
    lines.push(`| ${s.engine} | ${s.model ?? ''} | ${s.n} | ${(s.actionAcc * 100).toFixed(1)}% | ${(s.routeAcc * 100).toFixed(1)}% | ${s.formatErrors}${s.fenced ? ` (펜스 ${s.fenced})` : ''} | ${s.p50ms}ms | ${s.p95ms}ms | ${s.avgInputTokens}/${s.avgOutputTokens} | $${s.costPer1kUsd.toFixed(4)} |`);
  }
  const md = lines.join('\n');
  fs.writeFileSync(path.join(HERE, 'results', 'compare-summary.md'), md + '\n');
  console.log(md);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--report')) return report();
  const eIdx = args.indexOf('--engines');
  const engines = (eIdx >= 0 ? args[eIdx + 1] : 'jev').split(',');
  const jIdx = args.indexOf('--jev-from');
  const lIdx = args.indexOf('--limit');
  rows = sample(ALL_ROWS, lIdx >= 0 ? Number(args[lIdx + 1]) : 0);
  if (rows.length < ALL_ROWS.length) console.log(`${ALL_ROWS.length}건 중 ${rows.length}건: ${rows.map((r) => r.id).join(' ')}`);
  // 키 없이 Jev를 돌리면 40건이 전부 api_error로 채점된다 → 시작 전에 멈춘다
  if (engines.includes('jev') && jIdx < 0 && !jevConfig().apiKey && jevConfig().baseUrl.includes('api.typesafe.ai')) {
    console.error(`TYPESAFE_API_KEY가 없습니다. 키가 든 .env가 있는 폴더에서 실행하세요(지금 폴더: ${process.cwd()}).`);
    process.exit(2);
  }
  for (const engine of engines) {
    console.log(`▶ ${engine}`);
    const out = engine === 'jev' ? await runJev(jIdx >= 0 ? args[jIdx + 1] : null) : await runLlm(engine);
    const summary = summarize(engine, out);
    console.log(JSON.stringify(summary));
    const file = path.join(HERE, 'results', `compare-${engine.replace(/[:/]/g, '_')}-${new Date().toISOString().replace(/[:.]/g, '-')}.json`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, JSON.stringify({ summary, out }, null, 1));
  }
  report();
}

main();
