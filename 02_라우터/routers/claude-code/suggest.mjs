// 스킬 라우터 본체. docs.typesafe.ai/cookbooks/skill_suggestion 의 2요청 구조를 옮기고,
// 로스터가 누구의 것이든(몇 개든) 돌도록 넓혔다.
//
//   요청 1 (wide)    로스터 전체를 Choice로 랭킹 + "스킬이 필요한 턴인가" Noul 3개(게이트)
//                    후보가 240개를 넘으면 200개 안팎의 조로 나눠 Choice 여러 개로 묻는다(Jev Choice는 선택지 2~255개).
//                    한 요청에 조 4개까지, 넘치면 요청을 더 보낸다(동시에).
//   결선 (pool)      조가 둘 이상이면 조마다 상위 3개를 모아 Choice 한 번 더. 조마다 확률 합이 1이라 조끼리 직접 비교할 수 없어서다.
//   요청 2 (rerank)  상위 3개만 전체 설명·본문 발췌로 다시 Choice + 후보별 "정말 이 일을 하는가" Noul
// 어느 단계든 빈손으로 돌아올 수 있다. 최종 제안은 스킬 이름 최대 1개.
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createJev, JsonCache, keyFileFromArgs} from './jev.mjs';
import {loadRoster, parseAgents, defaultCacheDir} from './skills.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));

export const SHORTLIST = 3;          // 2차로 넘기는 후보 수
export const EXCERPT_CHARS = 700;    // 2차에서 후보마다 붙이는 SKILL.md 본문 길이
export const GATE_THRESHOLD = 0.30;  // 게이트 Noul 3개 평균이 이 밑이면 아무것도 제안하지 않음
export const FITS_THRESHOLD = 0.30;  // 2차 fits Noul 최대값이 이 밑이면 후보 전체 기각
// 위 두 문턱값은 쿡북 값 그대로다. evaluate.mjs --replay 로 내 데이터에 맞춰 조정한다.
export const WIDE_MAX = 240;         // 이보다 많으면 조로 나눈다(Choice 상한 255에 여유)
export const BATCH_SIZE = 200;
export const BATCHES_PER_REQUEST = 4;
export const POOL_PER_BATCH = 3;
export const NONE_KEY = '(해당 없음)'; // 후보가 하나뿐인 Choice에만 넣는 빠져나갈 문(Choice는 선택지 2개 이상)

export const CHOICE_INSTRUCTIONS =
  "Which of these skills, if any, is the right one to load to help with the user's latest request? " +
  'The request may be written in Korean; the skill descriptions mix Korean and English.';

export const GATE_QUESTIONS = {
  acts_on_user_system: "Is the assistant being asked to act on the user's files, accounts, devices, or online services, rather than only to explain or advise?",
  would_follow_documented_procedure: 'Would a careful expert answering this consult a specific documented procedure or set of commands, rather than answering from general understanding?',
  prose_suffices: "Could a knowledgeable generalist fully satisfy this request in prose, with no tools, no documentation, and no access to the user's files or accounts?",
};
export const INVERTED = new Set(['prose_suffices']); // yes가 "스킬 불필요" 쪽을 가리키는 질문

export const RERANK_INSTRUCTIONS =
  "Exactly one of these skills is the right one to load for the user's latest request. Which one? " +
  'Read what each actually does, not just its name.';

export function buildState(request, recentContext = '') {
  return {request, recent_context: recentContext};
}

// 로스터를 조로 나눈다. 조 크기는 고르게(예: 450개 → 150·150·150)
export function planBatches(skills, {wideMax = WIDE_MAX, batchSize = BATCH_SIZE} = {}) {
  if (skills.length <= wideMax) return [skills];
  const k = Math.ceil(skills.length / batchSize);
  const size = Math.ceil(skills.length / k);
  return Array.from({length: k}, (_, i) => skills.slice(i * size, (i + 1) * size));
}

function choiceOver(skills, instructions, describe = (s) => s.description) {
  const criteria = Object.fromEntries(skills.map((s) => [s.key, describe(s)]));
  if (skills.length === 1) criteria[NONE_KEY] = 'None of the listed skills fits the request.';
  return {type: 'choice', instructions, criteria};
}

export function wideRequests(roster, {batchesPerRequest = BATCHES_PER_REQUEST, ...plan} = {}) {
  const batches = planBatches(roster.skills, plan);
  const requests = [];
  for (let r = 0; r * batchesPerRequest < batches.length; r++) {
    const questions = {};
    batches.slice(r * batchesPerRequest, (r + 1) * batchesPerRequest)
      .forEach((b, i) => { questions[`which::${r * batchesPerRequest + i}`] = choiceOver(b, CHOICE_INSTRUCTIONS); });
    if (r === 0) for (const [key, text] of Object.entries(GATE_QUESTIONS)) questions[`gate::${key}`] = {type: 'noul', instructions: text};
    requests.push(questions);
  }
  return {batches, requests};
}

export const wideQuestions = (roster, opts) => wideRequests(roster, opts).requests[0];

const rank = (probs) => Object.entries(probs ?? {}).filter(([k]) => k !== NONE_KEY).sort((a, b) => b[1] - a[1]);

// 요청 1의 답(들)을 읽는다. 조가 하나면 바로 순위, 둘 이상이면 결선에 올릴 후보(pool)를 돌려준다.
export function readWide(answersList) {
  const all = Object.assign({}, ...[].concat(answersList));
  const batchKeys = Object.keys(all).filter((k) => k.startsWith('which::')).sort((a, b) => Number(a.slice(7)) - Number(b.slice(7)));
  const perBatch = batchKeys.map((k) => rank(all[k].probabilities));
  const values = {};
  for (const [key, a] of Object.entries(all)) if (key.startsWith('gate::')) values[key.slice(6)] = a.noul;
  const oriented = Object.entries(values).map(([k, v]) => (INVERTED.has(k) ? 1 - v : v));
  const gate = oriented.length ? oriented.reduce((a, b) => a + b, 0) / oriented.length : 0;
  if (perBatch.length <= 1) return {ranked: (perBatch[0] ?? []).slice(0, 12), gate, values, batches: perBatch.length, pool: null};
  const pool = [...new Set(perBatch.flatMap((r) => r.slice(0, POOL_PER_BATCH).map(([k]) => k)))];
  return {ranked: null, gate, values, batches: perBatch.length, pool};
}

export function poolQuestions(roster, keys) {
  const byKey = new Map(roster.skills.map((s) => [s.key, s]));
  return {which: choiceOver(keys.map((k) => byKey.get(k)).filter(Boolean), CHOICE_INSTRUCTIONS)};
}

// 요청이 막히면(403 방화벽 등) 본문 발췌를 빼고 설명만으로 한 번 더 묻는다
export async function callWithFallback(jev, state, questions, fallback) {
  try { return await jev.call({state, questions}); }
  catch (e) {
    if (!fallback || !/jev_http_(403|413|400)/.test(e.message)) throw e;
    const r = await jev.call({state, questions: fallback()});
    return {...r, degraded: e.message.slice(0, 14)};
  }
}

export function rerankQuestions(roster, keys, excerpt = EXCERPT_CHARS) {
  const byKey = new Map(roster.skills.map((s) => [s.key, s]));
  const cands = keys.map((k) => byKey.get(k)).filter(Boolean);
  const questions = {};
  if (cands.length >= 2) {
    questions.which = {type: 'choice', instructions: RERANK_INSTRUCTIONS,
      criteria: Object.fromEntries(cands.map((s) => [s.key, excerpt > 0 && s.body ? `${s.description_full} — ${s.body.slice(0, excerpt)}` : s.description_full]))};
  }
  for (const s of cands) {
    questions[`fits::${s.key}`] = {type: 'noul',
      instructions: `Does the skill '${s.key}' do the specific thing the user's request asks for? It is described as: ${s.description_full}`};
  }
  return questions;
}

export function readRerank(answers, keys = []) {
  const fits = {};
  for (const [key, a] of Object.entries(answers)) if (key.startsWith('fits::')) fits[key.slice(6)] = a.noul;
  return {
    winner: answers.which?.choice ?? keys[0] ?? null,
    probabilities: answers.which?.probabilities ?? (keys[0] ? {[keys[0]]: 1} : {}),
    confidence: answers.which?.confidence ?? null,
    fits,
  };
}

// 두 요청의 결과를 정책으로 묶는 순수 함수. 문턱값만 바꿔 API 재호출 없이 재계산할 수 있다.
export function decide(wide, rerank, {gateThreshold = GATE_THRESHOLD, fitsThreshold = FITS_THRESHOLD} = {}) {
  if (wide.gate < gateThreshold) return {suggestion: [], reason: 'gate_below_threshold'};
  if (!rerank || !Object.keys(rerank.fits ?? {}).length) return {suggestion: [], reason: 'rerank_missing'};
  const best = Math.max(...Object.values(rerank.fits));
  if (best < fitsThreshold) return {suggestion: [], reason: 'nothing_fits'};
  return {suggestion: [rerank.winner], reason: 'winner'};
}

const stat = (stage, r) => ({stage, model: r.model, usage: r.usage, seconds: r.seconds, cached: r.cached});

export async function suggest(request, roster, jev, policy = {}) {
  if (!roster.skills.length) {
    return {request, shortlist: [], wide: {gate: 0, ranked: [], values: {}, batches: 0}, rerank: null, suggestion: [], reason: 'empty_roster', calls: []};
  }
  try {
    return await suggestInner(request, roster, jev, policy);
  } catch (e) {
    // 호출 실패는 "제안 없음"으로 끝낸다(훅이 대화를 멈추지 않게). 이유는 결과에 남긴다.
    return {request, shortlist: [], wide: {gate: 0, ranked: [], values: {}, batches: 0}, rerank: null, suggestion: [],
      reason: `api_error:${String(e.message).slice(0, 40)}`, calls: []};
  }
}

async function suggestInner(request, roster, jev, policy) {
  const state = buildState(request);
  const {requests} = wideRequests(roster, policy);
  const first = await Promise.all(requests.map((questions) => jev.call({state, questions})));
  const calls = first.map((r, i) => stat(requests.length > 1 ? `wide#${i}` : 'wide', r));
  const wide = readWide(first.map((r) => r.answers));
  if (wide.pool) {
    const r = await jev.call({state, questions: poolQuestions(roster, wide.pool)});
    wide.ranked = rank(r.answers.which.probabilities).slice(0, 12);
    calls.push(stat('pool', r));
  }
  const shortlist = wide.ranked.slice(0, SHORTLIST).map(([k]) => k);
  let rerank = null;
  // alwaysRerank: 평가 때만 켠다. 게이트 아래 요청도 2차 응답을 저장해 두면 문턱값을 API 없이 다시 훑을 수 있다.
  if (shortlist.length && (policy.alwaysRerank || wide.gate >= (policy.gateThreshold ?? GATE_THRESHOLD))) {
    const r = await callWithFallback(jev, state, rerankQuestions(roster, shortlist), () => rerankQuestions(roster, shortlist, 0));
    rerank = readRerank(r.answers, shortlist);
    calls.push({...stat('rerank', r), ...(r.degraded ? {degraded: r.degraded} : {})});
  }
  return {request, shortlist, wide, rerank, ...decide(wide, rerank, policy), calls};
}

export function suggestionBlock(names) {
  const body = names.length
    ? `Relevant to the current request: ${names.join(', ')}. Ignore this if it does not fit what the user actually asked for.`
    : 'No skill in the roster appears relevant to this request.';
  return `<skill_relevance>\n${body}\n</skill_relevance>`;
}

// 명령행 공통: 어떤 스킬로 로스터를 만들지
//   --agent all|claude|codex|openclaw|shared (쉼표로 여러 개)  --dir <폴더>(여러 번)  --demo(강의 데모 스킬만)
//   --no-dedupe(합치기 끔: 중복 후보가 확률을 쪼개는 걸 보여 줄 때)  --refresh(캐시 무시)
export function rosterOptions(args, {defaultAgent = 'all'} = {}) {
  const val = (flag) => { const i = args.indexOf(flag); return i >= 0 ? args[i + 1] : undefined; };
  const dirs = args.flatMap((a, i) => (a === '--dir' ? [args[i + 1]] : []));
  const demo = args.includes('--demo');
  return {
    agents: demo ? [] : parseAgents(val('--agent') ?? process.env.SKILL_ROUTER_AGENTS ?? defaultAgent),
    dirs: demo ? [path.join(HERE, 'demo', 'skills'), ...dirs] : dirs,
    dedupe: !args.includes('--no-dedupe'),
    refresh: args.includes('--refresh'),
  };
}

export const FLAGS_WITH_VALUE = new Set(['--key-file', '--agent', '--dir', '--gate', '--fits', '--requests', '--n', '--out', '--k']);
export const positional = (args) => args.filter((a, i) => !a.startsWith('--') && !FLAGS_WITH_VALUE.has(args[i - 1]));

export async function openJev(args = [], {cacheDir = defaultCacheDir()} = {}) {
  const cache = await new JsonCache(path.join(cacheDir, 'json_cache.json')).load();
  return createJev({keyFile: keyFileFromArgs(args), cache});
}

if (fileURLToPath(import.meta.url) === path.resolve(process.argv[1] || '')) {
  const args = process.argv.slice(2);
  const request = positional(args).join(' ');
  if (!request) {
    console.error('사용법: node suggest.mjs [--agent all|claude|codex|openclaw|shared] [--dir 폴더] [--demo] [--key-file .env] "요청 문장"');
    process.exit(2);
  }
  const roster = await loadRoster(rosterOptions(args));
  if (!roster.count) console.error('스킬을 하나도 못 찾았어요. node roster.mjs 로 어디를 찾았는지 보거나, --demo 로 강의 데모 스킬을 쓰세요.');
  const result = await suggest(request, roster, await openJev(args));
  console.log(JSON.stringify({
    request, roster: {count: roster.count, batches: result.wide.batches, cache: roster.cache},
    gate: Number(result.wide.gate.toFixed(3)), gateValues: result.wide.values,
    top3: (result.wide.ranked ?? []).slice(0, 3).map(([n, p]) => ({name: n, p: Number(p.toFixed(3))})),
    fits: result.rerank ? Object.fromEntries(Object.entries(result.rerank.fits).map(([k, v]) => [k, Number(v.toFixed(3))])) : null,
    rerankWinner: result.rerank?.winner ?? null, suggestion: result.suggestion, reason: result.reason,
    calls: result.calls,
  }, null, 2));
  console.log(suggestionBlock(result.suggestion));
}
