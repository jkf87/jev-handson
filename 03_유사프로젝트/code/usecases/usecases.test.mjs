// 키 없이 도는 시험: node --test usecases/usecases.test.mjs  (폴더만 주면 Node 24에서 실패)
import test from 'node:test';
import assert from 'node:assert/strict';
import * as pick from './pick_element.mjs';
import * as game from './game_move.mjs';
import * as robot from './robot_action.mjs';

const choice = (c, p, keys) => ({ type: 'choice', choice: c, probabilities: Object.fromEntries(keys.map((k) => [k, k === c ? p : (1 - p) / (keys.length - 1)])) });
const noul = (p) => ({ type: 'noul', noul: p });

test('컴퓨터 유즈: 요소 표가 선택지가 되고, 되돌릴 수 없으면 확인을 받는다', () => {
  const keys = [...pick.SCREEN.map((e) => e.id), 'none'];
  const body = pick.buildRequest(pick.SCENARIOS[0]);
  assert.deepEqual(Object.keys(body.questions.element.criteria), keys);
  assert.equal(pick.decide({ element: choice('e5', 0.95, keys), irreversible: noul(0.1) }).key, 'click:e5');
  assert.equal(pick.decide({ element: choice('e6', 0.9, keys), irreversible: noul(0.7) }).key, 'confirm:e6');
  assert.equal(pick.decide({ element: choice('none', 0.8, keys), irreversible: noul(0.1) }).key, 'ask');
  assert.equal(pick.decide({ element: choice('e5', 0.5, keys), irreversible: noul(0.1) }).reason, 'uncertain');
  assert.equal(pick.decide({ element: { choice: 'e99' }, irreversible: noul(0.1) }).reason, 'invalid_answer');
});

test('게임: 둘 수 있는 칸만 선택지, 규칙 봇은 이기기 → 막기 순서', () => {
  const b = game.parse(['XX.', 'OO.', '...']);
  assert.deepEqual(Object.keys(game.buildRequest({ rows: ['XX.', 'OO.', '...'] }).questions.move.criteria), ['c3', 'c6', 'c7', 'c8', 'c9']);
  assert.equal(game.winningCell(b, 'X'), 2);
  assert.equal(game.ruleMove(b, 'O', 'X'), 5);            // O는 자기 승리(6번 칸)가 먼저
  assert.equal(game.ruleMove(game.parse(['OO.', 'X..', '..X']), 'X', 'O'), 2);   // X는 막기
  assert.equal(game.winner(game.parse(['XXX', 'OO.', '...'])), 'X');
  assert.equal(game.winner(game.parse(['XOX', 'XOO', 'OXX'])), 'draw');
  const sc = { rows: ['XX.', 'OO.', '...'] };
  assert.equal(game.decide({ move: choice('c3', 0.6, ['c3', 'c6', 'c7', 'c8', 'c9']) }, sc).key, 'play:c3');
  assert.equal(game.decide({ move: choice('c1', 0.9, ['c1', 'c3']) }, sc).key, 'fallback');     // 이미 찬 칸
  assert.equal(game.decide({ move: choice('c6', 0.3, ['c3', 'c6', 'c7', 'c8', 'c9']) }, sc).reason, 'uncertain');
});

test('로봇: 안전 규칙은 코드가 모델보다 먼저', () => {
  const keys = Object.keys(robot.ACTIONS);
  assert.equal(robot.decide({ action: choice('grasp', 0.8, keys), unsafe: noul(0.05) }).key, 'send:grasp');
  assert.equal(robot.decide({ action: choice('move_forward', 0.9, keys), unsafe: noul(0.5) }).reason, 'safety_override');
  assert.equal(robot.decide({ action: choice('grasp', 0.9, keys), unsafe: noul(0.5) }).key, 'send:grasp');    // 제자리에서 집기는 움직임이 아님
  assert.equal(robot.decide({ action: choice('turn_left', 0.5, keys), unsafe: noul(0) }).reason, 'uncertain');
  assert.equal(robot.decide({ action: choice('stop', 0.9, keys), unsafe: noul(0.9) }).key, 'stop');
  assert.equal(robot.decide({}).reason, 'invalid_answer');
});
