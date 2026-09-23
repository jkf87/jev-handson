// 라벨 붙인 요청으로 라우터 자체의 오류율 두 가지를 잰다(쿡북 Step 5의 지표 정의를 따름).
//   wrong suggestion   : 스킬이 있는 요청 중 제안이 정답이 아닌 비율(아무것도 제안 안 한 것도 오답)
//   needless suggestion: 스킬이 없는 요청 중 무엇이든 제안한 비율
// 쿡북과 달리 에이전트를 실제로 돌려 로드 여부를 세지는 않는다. 라우터 단독 성능이다.
//
//   node evaluate.mjs --demo                          # 강의 데모 스킬 + demo/requests.json (누구나 같은 결과)
//   node evaluate.mjs --requests my_requests.json     # 내 스킬 + 내가 라벨 붙인 요청 (--agent 로 범위 지정)
//   node evaluate.mjs --replay --gate 0.2 --fits 0.5  # 마지막 결과로 문턱값만 다시 계산(API 호출 없음)
// 결과는 ~/.cache/jev-skill-router/eval-*.json. --demo --save-evidence 면 evidence/demo-eval.json 에도 남긴다.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {suggest, decide, openJev, rosterOptions, GATE_THRESHOLD, FITS_THRESHOLD} from './suggest.mjs';
import {loadRoster, defaultCacheDir} from './skills.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));

export function score(rows) {
  const scored = rows.filter((r) => !r.skipped);
  const covered = scored.filter((r) => r.gold.length);
  const uncovered = scored.filter((r) => !r.gold.length);
  const wrong = covered.filter((r) => !r.gold.includes(r.suggestion[0]));
  const needless = uncovered.filter((r) => r.suggestion.length);
  return {
    covered: covered.length, uncovered: uncovered.length, skipped: rows.length - scored.length,
    wrong_suggestion: covered.length ? wrong.length / covered.length : null,
    needless_suggestion: uncovered.length ? needless.length / uncovered.length : null,
    wrong: wrong.map((r) => ({id: r.id, gold: r.gold, got: r.suggestion, top1: r.top3?.[0]?.name, reason: r.reason})),
    needless: needless.map((r) => ({id: r.id, got: r.suggestion, gate: r.gate})),
  };
}

export function policyFromArgs(args) {
  // 문턱값은 0~1 숫자만 받는다. 잘못 들어가면(NaN) 모든 비교가 거짓이 돼 전부 제안하는 조용한 사고가 난다.
  const num = (flag, fallback) => {
    const at = args.indexOf(flag);
    if (at < 0) return fallback;
    const v = Number(args[at + 1]);
    if (!Number.isFinite(v) || v < 0 || v > 1) throw new Error(`${flag} 값은 0~1 사이 숫자여야 해요: ${args[at + 1]}`);
    return v;
  };
  return {gateThreshold: num('--gate', GATE_THRESHOLD), fitsThreshold: num('--fits', FITS_THRESHOLD)};
}

// 정답 이름을 로스터 키로 맞춘다. 별칭으로 적어도 되고, 로스터에 없으면 그 줄은 건너뛴다(내 스킬 목록은 사람마다 다르다).
export function resolveGold(requests, roster) {
  const index = new Map();
  for (const s of roster.skills) for (const n of [s.key, s.name, ...(s.aliases ?? [])]) if (!index.has(n)) index.set(n, s.key);
  return requests.map((r) => {
    const want = r.gold ?? [];
    const gold = want.map((g) => index.get(g) ?? null);
    const missing = want.filter((g, i) => gold[i] === null);
    return missing.length && missing.length === want.length
      ? {...r, gold: [], skipped: true, missing}
      : {...r, gold: gold.filter(Boolean), missing};
  });
}

const val = (args, flag) => { const i = args.indexOf(flag); return i >= 0 ? args[i + 1] : undefined; };

async function main(args) {
  const demo = args.includes('--demo');
  const requestsFile = val(args, '--requests') ?? (demo ? path.join(HERE, 'demo', 'requests.json') : path.join(HERE, 'my_requests.json'));
  let raw;
  try { raw = JSON.parse(await fs.readFile(requestsFile, 'utf8')); }
  catch {
    console.error(`요청 파일이 없어요: ${requestsFile}\n  --demo 로 데모 세트를 쓰거나, 내 스킬로 라벨 붙인 요청을 my_requests.json 으로 만드세요(README 참고).`);
    process.exitCode = 2; return;
  }
  const roster = await loadRoster(rosterOptions(args));
  if (roster.count < 1) { console.error('로스터가 비었어요. node roster.mjs 로 확인하세요.'); process.exitCode = 2; return; }
  const requests = resolveGold(raw, roster);
  for (const r of requests.filter((x) => x.missing?.length)) console.warn(`! ${r.id}: 로스터에 없는 정답 ${r.missing.join(', ')}${r.skipped ? ' → 건너뜀' : ''}`);
  const policy = policyFromArgs(args);
  const jev = await openJev(args);
  const rows = [];
  for (const r of requests) {
    if (r.skipped) { rows.push({id: r.id, text: r.text, gold: [], skipped: true, suggestion: [], calls: []}); continue; }
    const s = await suggest(r.text, roster, jev, {...policy, alwaysRerank: true});
    rows.push({
      id: r.id, text: r.text, gold: r.gold,
      gate: Number(s.wide.gate.toFixed(3)), gateValues: s.wide.values,
      top3: (s.wide.ranked ?? []).slice(0, 3).map(([n, p]) => ({name: n, p: Number(p.toFixed(3))})),
      shortlist: s.shortlist,
      fits: s.rerank ? Object.fromEntries(Object.entries(s.rerank.fits).map(([k, v]) => [k, Number(v.toFixed(3))])) : null,
      rerankWinner: s.rerank?.winner ?? null,
      suggestion: s.suggestion, reason: s.reason, calls: s.calls,
    });
    const mark = r.gold.length ? (r.gold.includes(s.suggestion[0]) ? 'OK  ' : 'MISS') : (s.suggestion.length ? 'OVER' : 'OK  ');
    console.log(`${mark}  gate=${s.wide.gate.toFixed(2)}  ${String(s.suggestion[0] ?? '-').padEnd(24)} ${r.text.slice(0, 50)}`);
  }
  const summary = score(rows);
  const allCalls = rows.flatMap((r) => r.calls);
  const liveCalls = allCalls.filter((c) => !c.cached);
  const report = {
    at: new Date().toISOString(), label: demo ? 'demo' : 'mine',
    roster: {count: roster.count, found: roster.found, merged_duplicates: roster.merged_duplicates,
      wide_requests: rows.find((r) => r.calls?.length)?.calls.filter((c) => c.stage.startsWith('wide')).length ?? null},
    policy, jevModels: [...new Set(allCalls.map((c) => c.model).filter(Boolean))],
    liveCalls: liveCalls.length, cachedCalls: allCalls.length - liveCalls.length,
    inputTokens: allCalls.reduce((a, c) => a + (c.usage?.input_tokens ?? 0), 0),
    medianSecondsPerLiveCall: liveCalls.length ? [...liveCalls].sort((a, b) => a.seconds - b.seconds)[Math.floor(liveCalls.length / 2)].seconds : null,
    summary, rows,
  };
  const cacheDir = defaultCacheDir();
  await fs.mkdir(cacheDir, {recursive: true});
  const out = path.join(cacheDir, `eval-${report.label}.json`);
  await fs.writeFile(out, JSON.stringify(report, null, 1) + '\n');
  if (demo && args.includes('--save-evidence')) {
    await fs.mkdir(path.join(HERE, 'evidence'), {recursive: true});
    await fs.writeFile(path.join(HERE, 'evidence', 'demo-eval.json'), JSON.stringify(report, null, 1) + '\n');
  }
  const pct = (v) => (v === null ? '-' : (v * 100).toFixed(1) + '%');
  console.log(`\nwrong suggestion    ${pct(summary.wrong_suggestion)}  (${summary.covered}건)`);
  console.log(`needless suggestion ${pct(summary.needless_suggestion)}  (${summary.uncovered}건)${summary.skipped ? `  · 건너뜀 ${summary.skipped}건` : ''}`);
  console.log(`live calls ${report.liveCalls}, cached ${report.cachedCalls}, input tokens ${report.inputTokens}, jev ${report.jevModels.join('/')}`);
  console.log(`결과: ${out}`);
}

// --replay [파일]: 저장된 응답으로 다른 문턱값을 재계산한다. API 호출 없음.
async function replay(args) {
  const at = args.indexOf('--replay');
  const next = args[at + 1];
  const file = next && !next.startsWith('--') ? next
    : path.join(defaultCacheDir(), `eval-${args.includes('--demo') ? 'demo' : 'mine'}.json`);
  const saved = JSON.parse(await fs.readFile(file, 'utf8'));
  const policy = policyFromArgs(args);
  const rows = saved.rows.map((r) => (r.skipped ? r : {...r, ...decide({gate: r.gate}, r.rerankWinner ? {winner: r.rerankWinner, fits: r.fits} : null, policy)}));
  const s = score(rows);
  console.log(JSON.stringify({policy, wrong_suggestion: s.wrong_suggestion, needless_suggestion: s.needless_suggestion,
    wrong: s.wrong.map((w) => w.id), needless: s.needless.map((n) => n.id)}, null, 2));
}

if (fileURLToPath(import.meta.url) === path.resolve(process.argv[1] || '')) {
  const args = process.argv.slice(2);
  (args.includes('--replay') ? replay(args) : main(args)).catch((e) => { console.error(e.message); process.exitCode = 1; });
}
