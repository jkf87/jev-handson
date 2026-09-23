// Claude Code UserPromptSubmit 훅. 사용자 프롬프트를 받아 스킬 제안 한 줄을 추가 컨텍스트로 돌려준다.
// 로스터 자체는 건드리지 않으므로 시스템 프롬프트 캐시가 유지된다(쿡북의 suggestion_block 자리).
// - 로스터: 이 사람 컴퓨터의 Claude Code 스킬(SKILL_ROUTER_AGENTS로 바꿈). 스킬을 깔거나 지우면 다음 프롬프트에서 저절로 다시 만든다.
// - 어떤 오류든 조용히 exit 0 — 라우터가 죽어도 대화는 멈추지 않는다(fail-open).
// - 기록은 ~/.cache/jev-skill-router/hook.log (프롬프트 앞 120자가 남으니 강의 폴더에 두지 않는다).
import fs from 'node:fs/promises';
import path from 'node:path';
import {suggest, suggestionBlock, openJev} from './suggest.mjs';
import {loadRoster, parseAgents, defaultCacheDir} from './skills.mjs';

const MIN_CHARS = 8; // 너무 짧은 프롬프트("응", "ㅇㅇ")에는 판정하지 않는다.
const LOG = path.join(defaultCacheDir(), 'hook.log');

async function log(row) {
  try {
    await fs.mkdir(path.dirname(LOG), {recursive: true});
    await fs.appendFile(LOG, JSON.stringify({at: new Date().toISOString(), ...row}) + '\n');
  } catch { /* 로그도 못 쓰면 그냥 조용히 */ }
}

async function main() {
  const raw = await new Promise((resolve) => { let b = ''; process.stdin.on('data', (c) => (b += c)); process.stdin.on('end', () => resolve(b)); });
  const input = JSON.parse(raw || '{}');
  const prompt = String(input.prompt ?? '').trim();
  if (prompt.length < MIN_CHARS || prompt.startsWith('/')) return;
  const dirs = (process.env.SKILL_ROUTER_DIRS ?? '').split(path.delimiter).filter(Boolean);
  const roster = await loadRoster({agents: parseAgents(process.env.SKILL_ROUTER_AGENTS ?? 'claude'), dirs, cwd: input.cwd || process.cwd()});
  if (!roster.count) return;
  const jev = await openJev(process.argv.slice(2));
  // 문턱값은 코드 기본값(쿡북 0.30/0.30)을 쓰고, 환경변수로 바꿀 수 있다.
  const policy = {};
  const unit = (v) => { const n = Number(v); return v !== undefined && v !== '' && Number.isFinite(n) && n >= 0 && n <= 1 ? n : undefined; };
  if (unit(process.env.SKILL_ROUTER_GATE) !== undefined) policy.gateThreshold = unit(process.env.SKILL_ROUTER_GATE);   // 잘못된 값은 무시(기본값)
  if (unit(process.env.SKILL_ROUTER_FITS) !== undefined) policy.fitsThreshold = unit(process.env.SKILL_ROUTER_FITS);
  const result = await suggest(prompt, roster, jev, policy);
  await log({prompt: prompt.slice(0, 120), roster: roster.count, gate: Number(result.wide.gate.toFixed(3)), top3: (result.wide.ranked ?? []).slice(0, 3), suggestion: result.suggestion, reason: result.reason});
  process.stdout.write(JSON.stringify({hookSpecificOutput: {hookEventName: 'UserPromptSubmit', additionalContext: suggestionBlock(result.suggestion)}}));
}

main().catch((e) => log({error: String(e.message).slice(0, 200)}));
