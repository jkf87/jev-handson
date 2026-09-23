// Jev의 답(확률)을 행동으로 바꾸는 코드. 모델은 확률만 주고, 무엇을 할지는 여기서 정한다.
import { ROUTES, WORKERS } from './questions.mjs';

// 강의용 시작값. 보편적인 최적값이 아니다. 내 데이터로 바꿔 가며 자동 처리율·오류를 함께 본다.
export const DEFAULT_POLICY = {
  minRouteP: 0.6,     // route 최고 확률이 이보다 낮으면 사용자에게 되묻는다
  minTargetP: 0.6,    // task인데 담당자 확률이 이보다 낮으면 되묻는다
  confirmAt: 0.5,     // confirm(P(yes))이 이 이상이면 실행 전에 확인을 받는다
  minSpamP: 0.8,      // spam으로 차단하려면 이만큼은 확실해야 한다
  riskFirst: false,   // true면 task에서 위험(confirm)을 담당자 판단보다 먼저 본다 → 실습 2B
};

// 응답 형식 검사: 후보 밖의 답, 합이 1이 아닌 분포, 숫자가 아닌 확률은 모두 무효로 본다.
export function readChoice(answer, keys) {
  if (!answer || typeof answer.choice !== 'string' || !keys.includes(answer.choice)) return null;
  const ps = answer.probabilities;
  if (!ps || typeof ps !== 'object') return null;
  const values = keys.map((k) => ps[k]);
  if (values.some((p) => !Number.isFinite(p) || p < 0 || p > 1)) return null;
  if (Math.abs(values.reduce((a, b) => a + b, 0) - 1) > 0.02) return null;
  return { choice: answer.choice, p: ps[answer.choice], probabilities: ps };
}

export function readNoul(answer) {
  const p = answer?.noul;
  return Number.isFinite(p) && p >= 0 && p <= 1 ? p : null;
}

// answers → { action, target, reason }
//   action: reply(대화로 답함) | dispatch(작업을 담당자에게 넘김) | confirm(넘기기 전 확인) | clarify(되묻기) | block(차단) | review(사람 검토)
export function decide(answers, policy = DEFAULT_POLICY) {
  const route = readChoice(answers?.route, Object.keys(ROUTES));
  if (!route) return { action: 'review', reason: 'invalid_route' };
  if (route.p < policy.minRouteP) return { action: 'clarify', reason: 'uncertain_route', route };

  if (route.choice === 'spam') {
    return route.p >= policy.minSpamP ? { action: 'block', reason: 'spam', route } : { action: 'review', reason: 'maybe_spam', route };
  }
  if (route.choice === 'chat') return { action: 'reply', reason: 'chat', route };
  if (route.choice === 'unclear') return { action: 'clarify', reason: 'unclear', route };

  // route === 'task'
  const target = readChoice(answers?.target, [...Object.keys(WORKERS), 'none']);
  const confirmP = readNoul(answers?.confirm);
  if (!target) return { action: 'review', reason: 'invalid_target', route };
  if (confirmP === null) return { action: 'review', reason: 'invalid_confirm', route, targetAnswer: target };
  const workerKnown = target.choice !== 'none' && target.p >= policy.minTargetP;
  if (policy.riskFirst && confirmP >= policy.confirmAt) {
    return { action: 'confirm', reason: 'risky', route, target: workerKnown ? target.choice : null, confirmP };
  }
  if (!workerKnown) return { action: 'clarify', reason: 'which_worker', route, targetAnswer: target, confirmP };
  if (confirmP >= policy.confirmAt) return { action: 'confirm', reason: 'risky', route, target: target.choice, confirmP };
  return { action: 'dispatch', reason: 'task', route, target: target.choice, confirmP };
}

// 정답 라벨(data/messages.jsonl)에서 기대 행동을 만든다. 평가할 때만 쓴다.
export function expectedAction(row) {
  if (row.route === 'chat') return 'reply';
  if (row.route === 'spam') return 'block';
  if (row.route === 'unclear') return 'clarify';
  return row.confirm ? 'confirm' : `dispatch:${row.target}`;
}

export function actionKey(decision) {
  return decision.action === 'dispatch' ? `dispatch:${decision.target}` : decision.action;
}
