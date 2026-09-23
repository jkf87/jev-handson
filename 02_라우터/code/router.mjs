#!/usr/bin/env node
// 메시지와 작업을 나누는 라우터 (Jev 한 번 호출 = 질문 3개).
//   node router.mjs "내일 9시에 회의 알림 걸어 줘"     # 메시지 하나
//   node router.mjs --all                               # data/messages.jsonl 40건 + 정확도
//   node router.mjs --all --policy '{"minRouteP":0.8}'   # 정책만 바꿔 보기
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildRequest } from './lib/questions.mjs';
import { callJev, jevConfig } from './lib/jev.mjs';
import { decide, DEFAULT_POLICY, expectedAction, actionKey } from './lib/policy.mjs';
export { decide };

const HERE = path.dirname(fileURLToPath(import.meta.url));

export async function route(message, { policy = DEFAULT_POLICY, cfg = jevConfig() } = {}) {
  const body = buildRequest(message);
  try {
    const resp = await callJev(body, cfg);
    return { ...decide(resp.answers, policy), answers: resp.answers, usage: resp.usage, model: resp.model, latencyMs: resp.latencyMs };
  } catch (err) {
    // API 실패는 '판단 불확실'과 다르다. 자동 실행하지 않고 사람 검토로 보낸다.
    return { action: 'review', reason: `api_error:${err.kind || 'error'}`, error: String(err.message).slice(0, 200) };
  }
}

const ICON = { reply: '💬 대화로 답함', dispatch: '🛠  작업 넘김', confirm: '⚠️  실행 전 확인', clarify: '❓ 되묻기', block: '⛔ 차단', review: '👀 사람 검토' };

function summarize(d) {
  const r = d.route ? `${d.route.choice} ${d.route.p?.toFixed(2)}` : '-';
  const t = d.answers?.target ? `${d.answers.target.choice} ${d.answers.target.probabilities?.[d.answers.target.choice]?.toFixed(2)}` : '-';
  const c = d.answers?.confirm?.noul;
  return `${ICON[d.action] || d.action}${d.target ? ` → ${d.target}` : ''}   [route ${r} | target ${t} | confirm ${c ?? '-'}]  ${d.latencyMs ?? '-'}ms`;
}

async function main() {
  const args = process.argv.slice(2);
  const pIdx = args.indexOf('--policy');
  const policy = pIdx >= 0 ? { ...DEFAULT_POLICY, ...JSON.parse(args[pIdx + 1]) } : DEFAULT_POLICY;
  if (!args.includes('--all')) {
    const message = args.filter((a, i) => !a.startsWith('--') && (pIdx < 0 || i !== pIdx + 1)).join(' ');
    if (!message) { console.error('사용법: node router.mjs "메시지" | --all'); process.exit(2); }
    const d = await route(message, { policy });
    console.log(summarize(d));
    if (args.includes('--json')) console.log(JSON.stringify(d, null, 2));
    return;
  }
  const rows = fs.readFileSync(path.join(HERE, 'data/messages.jsonl'), 'utf8').trim().split('\n').map((l) => JSON.parse(l));
  // --replay <기록.json>: API를 다시 부르지 않고, 저장된 Jev 답에 정책만 다시 적용한다 (모델과 코드의 분리)
  const rIdx = args.indexOf('--replay');
  const saved = rIdx >= 0 ? JSON.parse(fs.readFileSync(args[rIdx + 1], 'utf8')).results : null;
  const results = [];
  for (const row of rows) {
    let d;
    if (saved) {
      const prev = saved.find((s) => s.id === row.id)?.decision;
      d = prev?.answers ? { ...decide(prev.answers, policy), answers: prev.answers, usage: prev.usage, model: prev.model, latencyMs: prev.latencyMs } : { action: 'review', reason: 'no_saved_answer' };
    } else {
      d = await route(row.text, { policy });
    }
    const want = expectedAction(row), got = actionKey(d);
    results.push({ id: row.id, text: row.text, expected: want, got, ok: want === got, decision: d });
    console.log(`${want === got ? '✓' : '✗'} ${row.id} ${summarize(d)}\n     ${row.text.slice(0, 60)}${want === got ? '' : `   (정답: ${want})`}`);
  }
  const ok = results.filter((r) => r.ok).length;
  const lat = results.map((r) => r.decision.latencyMs).filter(Number.isFinite).sort((a, b) => a - b);
  const q = (p) => lat[Math.min(lat.length - 1, Math.floor(p * lat.length))];
  const tokens = results.reduce((s, r) => s + (r.decision.usage?.input_tokens || 0), 0);
  console.log(`\n행동 일치 ${ok}/${rows.length}  ·  지연 p50 ${q(0.5)}ms p95 ${q(0.95)}ms  ·  입력 토큰 합 ${tokens} (≈ $${(tokens * 0.042 / 1e6).toFixed(6)})`);
  if (saved) return;  // 재생은 기록을 새로 남기지 않는다
  // ROUTER_TAG·ROUTER_RESULTS_DIR로 기록 위치를 바꿀 수 있다 (3강: 같은 코드로 로컬 엔진 결과를 따로 저장)
  const tag = process.env.ROUTER_TAG || 'jev';
  const dir = process.env.ROUTER_RESULTS_DIR || path.join(HERE, 'results');
  const out = path.join(dir, `router-${tag}-${new Date().toISOString().replace(/[:.]/g, '-')}.json`);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, JSON.stringify({ policy, model: results[0]?.decision.model, results }, null, 1));
  console.log(`기록: ${path.relative(process.cwd(), out)}`);
}

if (fileURLToPath(import.meta.url) === path.resolve(process.argv[1] || '')) main();
