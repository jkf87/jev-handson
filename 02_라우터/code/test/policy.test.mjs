// 키·네트워크 없이 도는 테스트: 정책(확률→행동)과 LLM 답 파싱만 검사한다.
import test from 'node:test';
import assert from 'node:assert/strict';
import { decide, readChoice, expectedAction, actionKey, DEFAULT_POLICY } from '../lib/policy.mjs';
import { parseLabels, decideFromLabels } from '../lib/llm.mjs';
import { buildRequest } from '../lib/questions.mjs';

const dist = (choice, p, keys) => ({ choice, probabilities: Object.fromEntries(keys.map((k) => [k, k === choice ? p : (1 - p) / (keys.length - 1)])) });
const R = ['chat', 'task', 'unclear', 'spam'];
const T = ['codex', 'claude_code', 'scheduler', 'gpu_worker', 'none'];

test('요청 본문: 질문 3개, 판단 대상은 state 안에', () => {
  const b = buildRequest('내일 9시 알림');
  assert.deepEqual(Object.keys(b.questions), ['route', 'target', 'confirm']);
  assert.equal(b.state.message, '내일 9시 알림');
  assert.ok(b.questions.target.criteria.none, 'no-match 후보(none)가 반드시 있어야 한다');
  assert.throws(() => buildRequest(''));
});

test('chat → reply, spam(확실) → block, spam(애매) → review', () => {
  assert.equal(decide({ route: dist('chat', 0.99, R) }).action, 'reply');
  assert.equal(decide({ route: dist('spam', 0.95, R) }).action, 'block');
  assert.equal(decide({ route: dist('spam', 0.7, R) }).action, 'review');
});

test('route가 애매하면 되묻기', () => {
  assert.equal(decide({ route: dist('task', 0.55, R) }).reason, 'uncertain_route');
});

test('task: 담당자 확실 + 위험 낮음 → dispatch', () => {
  const d = decide({ route: dist('task', 0.9, R), target: dist('codex', 0.9, T), confirm: { noul: 0.1 } });
  assert.equal(actionKey(d), 'dispatch:codex');
});

test('task: 위험 높음 → confirm', () => {
  const d = decide({ route: dist('task', 0.9, R), target: dist('codex', 0.9, T), confirm: { noul: 0.9 } });
  assert.equal(d.action, 'confirm');
});

test('riskFirst: 담당자가 애매해도 위험하면 먼저 확인 (m24 운영 DB 삭제 사례)', () => {
  const answers = { route: dist('task', 0.8, R), target: dist('none', 0.54, T), confirm: { noul: 0.96 } };
  assert.equal(decide(answers).action, 'clarify');
  assert.equal(decide(answers, { ...DEFAULT_POLICY, riskFirst: true }).action, 'confirm');
});

test('형식이 깨진 답은 실행하지 않고 review', () => {
  assert.equal(decide({ route: { choice: 'deploy', probabilities: { deploy: 1 } } }).action, 'review');
  assert.equal(readChoice({ choice: 'chat', probabilities: { chat: 0.7, task: 0.7, unclear: 0, spam: 0 } }, R), null, '합이 1이 아니면 무효');
});

test('LLM 답 파싱: 코드펜스·앞뒤 말이 붙어도 JSON만 꺼낸다', () => {
  const p = parseLabels('```json\n{"route":"task","target":"codex","confirm":false}\n```');
  assert.ok(p.ok && p.fenced);
  assert.equal(actionKey(decideFromLabels(p)), 'dispatch:codex');
  assert.equal(parseLabels('작업입니다').ok, false);
  assert.equal(parseLabels('{"route":"deploy"}').error, 'bad_route');
});

test('정답 라벨 → 기대 행동', () => {
  assert.equal(expectedAction({ route: 'task', target: 'scheduler', confirm: false }), 'dispatch:scheduler');
  assert.equal(expectedAction({ route: 'task', target: 'codex', confirm: true }), 'confirm');
});
