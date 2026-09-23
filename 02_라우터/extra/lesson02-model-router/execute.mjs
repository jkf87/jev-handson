// 선택된 모델을 실제 CLI(claude -p / codex exec)로 실행하는 어댑터.
// 모델·추론 강도는 cliPlan이 정한 값을 그대로 쓰고, 여기서는 실행 제한만 더한다. 오류나 REVIEW에서 다른 모델로 대체하지 않는다.
// 키 값은 읽지도 전달하지도 않는다. 두 CLI 모두 기존 로그인을 쓴다.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {selectModel, cliPlan, loadCatalog, loadTasks, judge, policyFromArgs, DEFAULT_POLICY} from './router.mjs';

// Codex: 사용자 설정·도구·플러그인 전부 끄고 승인 정책 never. (lesson02-model-score-router에서 실행 검증된 목록)
const CODEX_RESTRICTIONS = ['--ignore-user-config', '--ephemeral', '-c', 'approval_policy="never"', '-c', 'web_search="disabled"',
  ...['shell_tool', 'unified_exec', 'apps', 'plugins', 'hooks', 'memories', 'multi_agent', 'browser_use', 'browser_use_external', 'computer_use', 'image_generation', 'view_image', 'code_mode', 'code_mode_host', 'workspace_dependencies'].flatMap(f => ['--disable', f]),
  '--enable', 'skip_host_skill_discovery'];
// Claude: --tools ""(도구 전부 비활성)·--setting-sources ""·--strict-mcp-config·--disable-slash-commands는 cliPlan에 이미 들어 있다.

export function executionPrompt(task) {
  return ['제공된 요청과 맥락만 사용해 한국어로 답하세요. 파일 읽기/쓰기, 명령 실행, 네트워크 요청, 외부 도구 호출은 하지 마세요.',
    '코드 수정 요청이면 수정된 함수와 테스트 코드를 답변에 제시하세요. 실제로 실행하지 않은 테스트를 통과했다고 말하지 마세요.',
    '다음 JSON의 request가 수행할 요청이고 context는 참고 자료입니다.', JSON.stringify({request: task.request, context: task.context ?? ''})].join('\n');
}

export function restrictedInvocation(plan) {
  if (plan.provider === 'codex') return {program: plan.program, args: [...plan.args.slice(0, -1), ...CODEX_RESTRICTIONS, '-'], stdin: plan.stdin, cwd: undefined};
  return {program: plan.program, args: plan.args, stdin: plan.stdin, cwd: plan.cwd};
}

export function childEnvironment(env = process.env) {
  // API 키 값은 검사·복사·출력·보존하지 않는다. 자식 프로세스에도 넘기지 않는다.
  // USER: claude CLI가 macOS 키체인에서 구독 로그인을 찾을 때 필요하다(없으면 "Not logged in").
  // LOGNAME은 넣지 않는다. 2026-09-23 실측에서 USER+LOGNAME 조합은 2회 모두 로그인 실패, USER만은 2회 모두 성공했다.
  return Object.fromEntries(['PATH', 'HOME', 'USER', 'CODEX_HOME', 'TMPDIR', 'LANG', 'LC_ALL'].filter(k => env[k] !== undefined).map(k => [k, env[k]]));
}

// 상위 모델이 높은 추론 강도로 설계 검토를 하면 4분을 넘기기도 한다(2026-09-23 opus-5 complex_design). 기본 10분.
export function runProcess(invocation, {timeoutMs = 600000} = {}) {
  return new Promise(resolve => {
    const started = Date.now();
    const child = spawn(invocation.program, invocation.args, {shell: false, cwd: invocation.cwd, env: childEnvironment(), stdio: ['pipe', 'pipe', 'pipe']});
    let stdout = '', stderr = '', timedOut = false, outputLimit = false, spawnError = null;
    const timer = setTimeout(() => { timedOut = true; child.kill('SIGTERM'); }, timeoutMs);
    const killTimer = setTimeout(() => child.kill('SIGKILL'), timeoutMs + 2000);
    const collect = (which, chunk) => { if (which === 'out') stdout += chunk; else stderr += chunk; if (stdout.length + stderr.length > 2_000_000) { outputLimit = true; child.kill('SIGKILL'); } };
    child.stdout.on('data', c => collect('out', c));
    child.stderr.on('data', c => collect('err', c));
    child.stdin.on('error', () => {});
    child.on('error', e => { spawnError = e.code ?? 'spawn_error'; });
    child.on('close', (exitCode, signal) => { clearTimeout(timer); clearTimeout(killTimer); resolve({stdout, stderr, exitCode, signal, timedOut, outputLimit, spawnError, elapsedMs: Date.now() - started}); });
    child.stdin.end(invocation.stdin);
  });
}

function diagnose(text) {
  const d = [];
  if (/Operation not permitted|Permission denied|Read-only file system/i.test(text)) d.push('filesystem_permission_denied');
  if (/dns|resolve host|connection|network|sending request|stream disconnected|ECONN/i.test(text)) d.push('connection_failed');
  if (/unauthorized|authentication|401|not logged in|Invalid API key|OAuth|please run \/login/i.test(text)) d.push('authentication_failed');
  if (/model .* (not found|does not exist|unavailable)|invalid model/i.test(text)) d.push('model_unavailable');
  if (/usage limit|rate limit|quota|purchase more credits/i.test(text)) d.push('usage_limit');
  return d;
}

export function summarizeCodex(pr, selected) {
  const events = []; let malformed = 0;
  for (const line of pr.stdout.split('\n').filter(Boolean)) try { events.push(JSON.parse(line)); } catch { malformed++; }
  const responses = events.filter(e => e.type === 'item.completed' && e.item?.type === 'agent_message').map(e => e.item.text).filter(t => typeof t === 'string');
  const usage = events.findLast(e => e.type === 'turn.completed')?.usage ?? null;
  const reportedModels = [...new Set(events.flatMap(e => [e.model, e.model_id, e.item?.model]).filter(x => typeof x === 'string'))];
  const reasons = [];
  if (pr.spawnError) reasons.push('spawn_failed');
  if (pr.timedOut) reasons.push('timeout');
  if (pr.outputLimit) reasons.push('output_limit');
  if (pr.exitCode !== 0) reasons.push('nonzero_exit');
  if (events.some(e => e.type === 'turn.failed' || e.type === 'error')) reasons.push('codex_error_event');
  if (malformed) reasons.push('invalid_jsonl');
  if (reportedModels.some(id => id !== selected.id)) reasons.push('reported_model_mismatch');
  if (events.some(e => e.item && ['command_execution', 'mcp_tool_call', 'web_search', 'file_change'].includes(e.item.type))) reasons.push('unexpected_tool_use');
  if (!events.some(e => e.type === 'turn.completed')) reasons.push('missing_turn_completed');
  if (!responses.length) reasons.push('missing_response');
  return {status: reasons.length ? 'ERROR' : 'COMPLETED', reasons, diagnostics: diagnose(pr.stderr + events.filter(e => ['error', 'turn.failed'].includes(e.type)).map(e => e.type === 'error' ? String(e.message) : String(e.error?.message)).join('\n')),
    exitCode: pr.exitCode, elapsedMs: pr.elapsedMs, requestedModel: selected.id, requestedEffort: selected.effort, reportedModels,
    modelVerification: reportedModels.length ? 'event_metadata' : 'CLI arguments only; server model/effort not exposed in JSONL',
    usage, costUsd: null, response: responses.join('\n\n'), stderrOmitted: true};
}

export function summarizeClaude(pr, selected) {
  let out = null;
  try { out = JSON.parse(pr.stdout); } catch { /* 아래에서 invalid_json */ }
  const reasons = [];
  if (pr.spawnError) reasons.push('spawn_failed');
  if (pr.timedOut) reasons.push('timeout');
  if (pr.outputLimit) reasons.push('output_limit');
  if (pr.exitCode !== 0) reasons.push('nonzero_exit');
  if (!out) reasons.push('invalid_json');
  const reportedModels = out ? Object.values(out.modelUsage ?? {}).map(m => m.canonicalModel).filter(Boolean) : [];
  if (out?.is_error) reasons.push('claude_error_result');
  if (out && out.subtype && out.subtype !== 'success') reasons.push(`subtype_${out.subtype}`);
  if (reportedModels.length && reportedModels.some(id => id !== selected.id)) reasons.push('reported_model_mismatch');
  if (out && (out.num_turns ?? 1) > 1) reasons.push('unexpected_multi_turn');
  if (out?.permission_denials?.length) reasons.push('unexpected_tool_use');
  if (out && typeof out.result !== 'string' || out?.result === '') reasons.push('missing_response');
  return {status: reasons.length ? 'ERROR' : 'COMPLETED', reasons, diagnostics: diagnose(pr.stderr + (out?.is_error ? String(out.result) : '')),
    exitCode: pr.exitCode, elapsedMs: pr.elapsedMs, requestedModel: selected.id, requestedEffort: selected.effort, reportedModels,
    modelVerification: reportedModels.length ? 'modelUsage.canonicalModel' : 'CLI arguments only',
    usage: out?.usage ?? null, costUsd: out?.total_cost_usd ?? null, durationApiMs: out?.duration_api_ms ?? null, response: out?.result ?? '', stderrOmitted: true};
}

export async function executeSelection(selection, task, cwd, {runner = runProcess, timeoutMs} = {}) {
  const plan = cliPlan(selection, cwd, executionPrompt(task));
  if (!plan) return {plan: null, invocation: null, execution: {status: 'SKIPPED', reason: selection.reason}, validation: {status: 'NOT_RUN', passed: null, reason: 'no_selected_model'}};
  const invocation = restrictedInvocation(plan);
  const pr = await runner(invocation, {timeoutMs});
  const execution = (plan.provider === 'codex' ? summarizeCodex : summarizeClaude)(pr, selection.selected);
  return {plan, invocation, execution, validation: {status: 'NOT_RUN', passed: null, reason: execution.status === 'COMPLETED' ? 'no_independent_task_test' : 'execution_failed', modelSelfReportedTestsAreEvidence: false}};
}

// --force <provider/id>: 라우터 선택을 무시하고 지정 후보로 실행한다. "라우터가 탈락시킨 모델이 정말 못 하는가"를
// 확인하는 비교 실행 전용이며, 기록에 forced:true와 원래 선택을 함께 남긴다.
export function forcedSelection(selection, spec) {
  const c = selection.candidates.find(x => `${x.provider}/${x.id}` === spec);
  if (!c) throw new Error('unknown_forced_model');
  return {...selection, status: 'PLANNED', reason: 'forced_for_comparison', forced: true, routerSelected: selection.selected ? `${selection.selected.provider}/${selection.selected.id}` : null, selected: c};
}

export async function main(args) {
  const live = args.includes('--execute');
  const taskAt = args.indexOf('--task'), taskId = taskAt < 0 ? null : args[taskAt + 1];
  const forceAt = args.indexOf('--force'), force = forceAt < 0 ? null : args[forceAt + 1];
  const timeoutAt = args.indexOf('--timeout'), timeoutMs = timeoutAt < 0 ? undefined : Number(args[timeoutAt + 1]) * 1000;
  const catalog = await loadCatalog();
  const tasks = await loadTasks(args);
  const policy = policyFromArgs(args);
  const selectedTasks = tasks.map((task, i) => ({task, i})).filter(({task}) => !taskId || task.id === taskId);
  if (!selectedTasks.length) throw new Error('unknown_task_id');
  // Jev 판정: 저장된 응답이 있으면 캐시에서, 없으면 1회 호출. --execute가 아니어도 판정은 필요하다.
  const {result} = await judge(tasks, catalog, args);
  if (!live) {
    console.log(JSON.stringify({mode: 'preview', jevCached: result.cached, jevModel: result.model, plans: selectedTasks.map(({task, i}) => {
      const sel = selectModel(result.answers, catalog.models, i, policy);
      return {taskId: task.id, status: sel.status, selected: sel.selected ? `${sel.selected.provider}/${sel.selected.id}` : null, plan: cliPlan(sel, '<isolated temporary directory>', executionPrompt(task))};
    })}, null, 2));
    return;
  }
  const runDir = await fs.mkdtemp(new URL('evidence/execution-', import.meta.url));
  const manifest = {at: new Date().toISOString(), jevModel: result.model, jevCached: result.cached, policy: {...DEFAULT_POLICY, ...policy}, records: []};
  for (const {task, i} of selectedTasks) { // 직렬 실행: 한도·실패·비용을 작업별로 귀속시킨다.
    const cwd = await fs.mkdtemp(path.join(os.tmpdir(), 'jev-model-router-readonly-'));
    await fs.writeFile(path.join(cwd, 'AGENTS.md'), 'Use only the supplied request. Do not read files, secrets or environment variables. Do not use tools or write files. Return the requested answer only. Do not claim tests ran.\n');
    const routed = selectModel(result.answers, catalog.models, i, policy);
    const selection = force ? forcedSelection(routed, force) : routed;
    const record = await executeSelection(selection, task, cwd, {timeoutMs});
    const stem = `task-${task.id}`;
    await fs.writeFile(path.join(runDir, stem + '.result.json'), JSON.stringify({task, selection, plan: record.plan, invocation: record.invocation, execution: record.execution, validation: record.validation}, null, 2) + '\n');
    // 실패한 실행의 출력(예: "Not logged in")을 모델 답변처럼 저장하지 않는다. 원인은 result.json의 reasons/diagnostics에 있다.
    if (record.execution.status === 'COMPLETED' && record.execution.response) await fs.writeFile(path.join(runDir, stem + '.response.md'), record.execution.response + '\n');
    manifest.records.push({taskId: task.id, selected: selection.selected ? `${selection.selected.provider}/${selection.selected.id}` : null, forced: !!selection.forced, routerSelected: selection.routerSelected ?? null, result: stem + '.result.json', executionStatus: record.execution.status});
    if (record.execution.status === 'ERROR') process.exitCode = 1;
    await fs.writeFile(path.join(runDir, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
    console.log(JSON.stringify({taskId: task.id, selected: manifest.records.at(-1).selected, execution: record.execution.status, reasons: record.execution.reasons, diagnostics: record.execution.diagnostics, elapsedMs: record.execution.elapsedMs, costUsd: record.execution.costUsd, runDir: path.basename(runDir)}));
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main(process.argv.slice(2)).catch(e => { console.error('execution_adapter_failed: ' + e.message); process.exitCode = 1; });
