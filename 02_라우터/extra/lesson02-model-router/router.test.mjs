import test from 'node:test';
import assert from 'node:assert/strict';
import {buildRequest, validScore, selectModel, cliPlan, LEVELS} from './router.mjs';
import {summarizeClaude, summarizeCodex, restrictedInvocation, executionPrompt, forcedSelection, childEnvironment} from './execute.mjs';
import {CHECKS} from './validate.mjs';

const models = [
  {provider: 'codex', id: 'gpt-cheap', effort: 'high', description: 'c', aai_score: 30, input_usd_per_million: 0.2, output_usd_per_million: 1.2, available_in_local_catalog: true},
  {provider: 'claude', id: 'claude-mid', effort: 'high', description: 'm', aai_score: 38, input_usd_per_million: 2, output_usd_per_million: 10, available_in_local_catalog: true},
  {provider: 'claude', id: 'claude-top', effort: 'high', description: 't', aai_score: 51, input_usd_per_million: 5, output_usd_per_million: 25, available_in_local_catalog: true}
];
const score = (p0, p1, p2, p3) => ({type: 'score', score: p1 + 2 * p2 + 3 * p3, probabilities: {0: p0, 1: p1, 2: p2, 3: p3}, confidence: 0.8, legend: {}});

test('one score question per task × candidate, provider in state', () => {
  const r = buildRequest([{id: 'a', request: 'x'}, {id: 'b', request: 'y'}], models);
  assert.equal(Object.keys(r.questions).length, 6);
  assert.equal(r.questions.t1_m2.criteria, LEVELS);
  assert.equal(r.state.candidates[1].provider, 'claude');
});

test('validScore rejects a mismatch between score and probabilities', () => {
  assert.ok(validScore(score(0, 0, 0.5, 0.5)));
  assert.ok(!validScore({...score(0, 0, 0.5, 0.5), score: 1.0}));
  // 실측 응답(t1_m6): 반올림된 확률의 평균 2.83, score 2.86 → 허용
  assert.ok(validScore({type: 'score', score: 2.86, confidence: 0.86, probabilities: {0: 0.01, 1: 0.01, 2: 0.12, 3: 0.86}}));
  assert.ok(!validScore({type: 'score', score: 2, probabilities: {0: 0, 1: 0, 2: 1}, confidence: 1}));
});

test('selectModel: cheapest sufficient candidate; provider filter changes the answer', () => {
  const answers = {t0_m0: score(0.3, 0.1, 0.4, 0.2), t0_m1: score(0, 0.05, 0.4, 0.55), t0_m2: score(0, 0, 0.2, 0.8)};
  assert.equal(selectModel(answers, models).selected.id, 'claude-mid'); // gpt-cheap은 부족 질량 0.4로 탈락
  assert.equal(selectModel(answers, models, 0, {provider: 'codex'}).status, 'REVIEW');
  assert.equal(selectModel(answers, models, 0, {provider: 'claude', minScore: 2.7}).selected.id, 'claude-top');
});

test('selectModel: a broken in-scope answer forces REVIEW, out-of-scope broken answer does not', () => {
  const answers = {t0_m0: {type: 'score', score: 9}, t0_m1: score(0, 0, 0.3, 0.7), t0_m2: score(0, 0, 0.2, 0.8)};
  assert.equal(selectModel(answers, models).status, 'REVIEW');
  assert.equal(selectModel(answers, models, 0, {provider: 'claude'}).selected.id, 'claude-mid');
});

test('cliPlan: claude gets -p/--tools "" without --bare and codex gets exec read-only; stdin carries the prompt', () => {
  const sel = (id, provider) => ({status: 'PLANNED', selected: {id, provider, effort: 'high'}});
  const c = cliPlan(sel('claude-mid', 'claude'), '/tmp/x', 'PROMPT');
  assert.deepEqual(c.args.slice(0, 10), ['-p', '--model', 'claude-mid', '--effort', 'high', '--output-format', 'json', '--tools', '', '--setting-sources']);
  assert.ok(!c.args.includes('--bare')); // --bare는 키체인 로그인을 끊는다
  assert.equal(c.stdin, 'PROMPT');
  const x = cliPlan(sel('gpt-cheap', 'codex'), '/tmp/x', 'PROMPT');
  assert.deepEqual(x.args.slice(0, 6), ['exec', '-m', 'gpt-cheap', '-c', 'model_reasoning_effort="high"', '-s']);
  assert.equal(cliPlan({status: 'REVIEW', selected: null}, '/tmp/x', 'P'), null);
  const inv = restrictedInvocation(x);
  assert.ok(inv.args.includes('--ignore-user-config') && inv.args.at(-1) === '-');
  assert.doesNotMatch(executionPrompt({request: 'r'}), /API|key/i);
});

test('summarizeClaude: verifies the reported model and flags tool use or errors', () => {
  const ok = {stdout: JSON.stringify({type: 'result', subtype: 'success', is_error: false, result: '답', num_turns: 1, total_cost_usd: 0.01, usage: {input_tokens: 1}, modelUsage: {'claude-mid-20260101': {canonicalModel: 'claude-mid'}}, permission_denials: []}), stderr: '', exitCode: 0, elapsedMs: 5};
  const s = summarizeClaude(ok, {id: 'claude-mid', effort: 'high'});
  assert.equal(s.status, 'COMPLETED');
  assert.deepEqual(s.reportedModels, ['claude-mid']);
  const wrong = summarizeClaude({...ok, stdout: ok.stdout.replace('"canonicalModel":"claude-mid"', '"canonicalModel":"claude-other"')}, {id: 'claude-mid'});
  assert.ok(wrong.reasons.includes('reported_model_mismatch'));
  const denied = summarizeClaude({...ok, stdout: ok.stdout.replace('"permission_denials":[]', '"permission_denials":[{"tool_name":"Bash"}]')}, {id: 'claude-mid'});
  assert.ok(denied.reasons.includes('unexpected_tool_use'));
  assert.ok(summarizeClaude({stdout: 'not json', stderr: 'Invalid API key', exitCode: 1, elapsedMs: 1}, {id: 'x'}).diagnostics.includes('authentication_failed'));
});

test('summarizeCodex: JSONL events → response and model check', () => {
  const lines = [{type: 'item.completed', item: {type: 'agent_message', text: '답'}}, {type: 'turn.completed', usage: {input_tokens: 3}}].map(e => JSON.stringify(e)).join('\n');
  const s = summarizeCodex({stdout: lines, stderr: '', exitCode: 0, elapsedMs: 5}, {id: 'gpt-cheap', effort: 'high'});
  assert.equal(s.status, 'COMPLETED');
  assert.equal(s.response, '답');
  assert.ok(summarizeCodex({stdout: '', stderr: '', exitCode: 1, elapsedMs: 1}, {id: 'gpt-cheap'}).reasons.includes('missing_response'));
});

test('forcedSelection keeps the router pick on record and rejects unknown ids', () => {
  const answers = {t0_m0: score(0, 0, 0, 1), t0_m1: score(0, 0, 0, 1), t0_m2: score(0, 0, 0, 1)};
  const f = forcedSelection(selectModel(answers, models), 'claude/claude-top');
  assert.equal(f.selected.id, 'claude-top');
  assert.equal(f.routerSelected, 'codex/gpt-cheap');
  assert.ok(f.forced);
  assert.throws(() => forcedSelection(selectModel(answers, models), 'claude/nope'), /unknown_forced_model/);
});

test('child env passes USER (keychain login) but never LOGNAME or API keys', () => {
  const env = childEnvironment({PATH: '/bin', HOME: '/h', USER: 'u', LOGNAME: 'u', TYPESAFE_API_KEY: 'x', ANTHROPIC_API_KEY: 'y'});
  assert.deepEqual(Object.keys(env).sort(), ['HOME', 'PATH', 'USER']);
});

test('validators: independent checks, not the model self-report', () => {
  assert.equal(CHECKS.copy('**내일 오전 열 시에 회의가 있습니다. 준비 자료는 메일로 보내 주세요.**').passed, true);
  assert.equal(CHECKS.copy('내일 오전 열시에 회의가 있습니다.').passed, false);
  const good = '```javascript\nfunction mean(xs) { if (xs.length === 0) return null; return xs.reduce((a,b)=>a+b,0)/xs.length; }\n```\nAll tests passed';
  assert.equal(CHECKS.standard_code(good).passed, true);
  const bad = '```js\nfunction mean(xs) { return xs.length ? xs.reduce((a,b)=>a+b,0)/xs.length : 0; }\n```\nAll tests passed';
  assert.equal(CHECKS.standard_code(bad).passed, false); // 모델이 통과했다고 써도 빈 배열 0 반환은 실패
  assert.equal(CHECKS.summary('1. 5강 확정 - 준구\n2. 결제 다음 스프린트 이월 - 민수\n3. 10월 3일 리허설, 9월 30일 공유 - 준구').passed, true);
  assert.equal(CHECKS.complex_design('재시도 웹훅').passed, null);
});
