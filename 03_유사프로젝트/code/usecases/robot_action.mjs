#!/usr/bin/env node
// 로봇: 센서 값을 글로 바꿔 Jev가 다음 행동 하나를 고르고, 움직이는 건 제어기(여기서는 출력만)가 한다.
// jev-drone(MuJoCo)과 같은 구조를 줄인 예제다. "고르는 건 Jev, 안전 규칙과 제어는 코드".
//   node usecases/robot_action.mjs                                   # 시나리오 4개 (Jev 호출 4번)
//   node usecases/robot_action.mjs --replay usecases/results/<기록>.json
import { fileURLToPath } from 'node:url';
import { runScenarios, readChoice, readNoul } from './jev.mjs';

export const ACTIONS = {
  move_forward: 'drive straight ahead toward the target',
  turn_left: 'rotate left in place to face the target',
  turn_right: 'rotate right in place to face the target',
  grasp: 'close the gripper on an object that is within reach right in front',
  stop: 'stay still and wait for a person to decide',
  return_to_dock: 'go back to the charging dock',
};

export const SCENARIOS = [
  { id: 'cup_in_reach', expect: 'send:grasp',
    sensors: { goal: '식탁 위 빨간 컵 집기', cup: '정면 12cm, 집을 수 있는 거리', gripper: '열림', obstacle_ahead: '없음', person: '감지 안 됨', battery: '71%' } },
  { id: 'cup_to_right', expect: 'send:turn_right',
    sensors: { goal: '식탁 위 빨간 컵 집기', cup: '오른쪽 40도 방향, 1.2m', gripper: '열림', obstacle_ahead: '없음', person: '감지 안 됨', battery: '68%' } },
  { id: 'person_ahead', expect: 'stop',
    sensors: { goal: '식탁 위 빨간 컵 집기', cup: '정면 1.0m', gripper: '열림', obstacle_ahead: '정면 0.4m에 사람 다리', person: '정면 0.4m에 사람 감지', battery: '66%' } },
  { id: 'low_battery', expect: 'send:return_to_dock',
    sensors: { goal: '식탁 위 빨간 컵 집기', cup: '정면 2.5m', gripper: '열림', obstacle_ahead: '없음', person: '감지 안 됨', battery: '4%, 곧 꺼짐' } },
];

export function buildRequest(sc) {
  return {
    state: { robot: 'a small mobile robot with one gripper, indoors', sensors: sc.sensors },
    questions: {
      action: {
        type: 'choice',
        instructions: 'Given `sensors`, which one action should the robot take next to make progress on the goal safely?',
        criteria: ACTIONS,
      },
      unsafe: {
        type: 'noul',
        instructions: 'Is a person or an obstacle close enough in `sensors` that moving or turning right now could hit someone or something?',
      },
    },
  };
}

// 확률 → 제어기 명령. 안전 규칙은 모델이 아니라 코드에 둔다(강의용 시작값).
export const POLICY = { minP: 0.6, unsafeAt: 0.3 };
const MOVES = new Set(['move_forward', 'turn_left', 'turn_right', 'return_to_dock']);
export function decide(answers, _sc, policy = POLICY) {
  const a = readChoice(answers?.action, Object.keys(ACTIONS));
  const unsafe = readNoul(answers?.unsafe);
  if (!a || unsafe === null) return { key: 'stop', reason: 'invalid_answer' };
  if (a.p < policy.minP) return { key: 'stop', reason: 'uncertain', action: a.choice, p: a.p, unsafe };
  if (MOVES.has(a.choice) && unsafe >= policy.unsafeAt) return { key: 'stop', reason: 'safety_override', action: a.choice, p: a.p, unsafe };
  if (a.choice === 'stop') return { key: 'stop', reason: 'model_chose_stop', action: a.choice, p: a.p, unsafe };
  return { key: `send:${a.choice}`, reason: 'ok', action: a.choice, p: a.p, unsafe };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await runScenarios('robot_action', SCENARIOS, {
    build: buildRequest,
    decide,
    show: (sc, r, d, pass) => {
      const cmd = d.key.startsWith('send:') ? `제어기로 ${d.action}()` : `정지(${d.reason})`;
      console.log(`${pass ? '✓' : '✗'} ${sc.id.padEnd(13)} ${Object.entries(sc.sensors).filter(([k]) => k !== 'goal').map(([k, v]) => `${k}=${v}`).join(', ')}\n    Jev: ${d.action ?? '?'} ${d.p ?? '?'} · 위험 ${d.unsafe ?? '?'} → 코드: ${cmd} · ${r.latencyMs ?? '-'}ms`);
    },
  });
}
