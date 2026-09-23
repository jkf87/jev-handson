import {ACTIONS} from './questions.mjs';
export function validChoice(a, keys) {
  if (!a || a.type !== 'choice' || !keys.includes(a.choice)) return false;
  if (!Number.isFinite(a.confidence) || a.confidence < 0 || a.confidence > 1) return false;
  const p = a.probabilities;
  if (!p || typeof p !== 'object' || Object.keys(p).length !== keys.length) return false;
  if (keys.some(k => !Object.hasOwn(p,k) || !Number.isFinite(p[k]) || p[k] < 0 || p[k] > 1)) return false;
  if (Math.abs(keys.reduce((sum,k)=>sum+p[k],0)-1)>1e-6) return false;
  return p[a.choice] >= Math.max(...Object.values(p))-1e-6;
}
export function selectRoute(answers, projects, threshold=0.8) {
  if (!Number.isFinite(threshold) || threshold < 0 || threshold > 1) throw new Error('Invalid confidence policy');
  const a=answers?.action, t=answers?.target;
  const base={action:a?.choice??null,target:t?.choice??null};
  const result=(route,reason)=>({...base,route,reason});
  if (!validChoice(a,Object.keys(ACTIONS))) return result('ASK','invalid_action_response');
  if (a.confidence<threshold) return result('ASK','uncertain_action');
  if (a.choice==='unsupported') return result('STOP','outside_scope');
  if (a.choice==='clarify') return result('ASK','missing_context');
  if (!validChoice(t,[...Object.keys(projects),'none'])) return result('ASK','invalid_target_response');
  if (t.choice==='none' || t.confidence<threshold) return result('ASK','missing_or_uncertain_target');
  if (!Object.hasOwn(projects,t.choice)) return result('STOP','target_not_allowed');
  return result(a.choice==='generate'?'CODEX':'TOOL',a.choice==='generate'?'generation_needed':'known_read_operation');
}
