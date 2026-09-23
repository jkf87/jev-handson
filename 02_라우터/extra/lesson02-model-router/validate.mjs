// 실행 결과를 모델 답변과 독립적으로 검사한다. 모델이 "통과했다"고 말한 것은 근거로 쓰지 않는다.
//   copy          : 정답 문장이 답변에 그대로 들어 있는가
//   summary       : 결정 3건·담당자가 남고 잡담(점심)이 빠졌는가
//   standard_code : 답변의 첫 JS 코드 블록에서 mean을 추출해 우리가 쓴 독립 테스트를 돌린다
//   complex_design, refactor_module : 요구 항목 키워드 포함 여부만 본다(내용 검토, 실제 시스템 테스트 아님 → passed=null)
// 사용: node validate.mjs <execution-디렉터리> [...]
import fs from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';

export const CHECKS = {
  copy(text) {
    const target = '내일 오전 열 시에 회의가 있습니다. 준비 자료는 메일로 보내 주세요.';
    const alt = '내일 오전 10시에 회의가 있습니다. 준비 자료는 메일로 보내 주세요.';
    const ok = text.includes(target) || text.includes(alt);
    return {kind: 'exact_text', passed: ok, checks: [{name: 'corrected_sentence_present', passed: ok}]};
  },
  summary(text) {
    const checks = [
      {name: 'landing_5_lectures', passed: /5강/.test(text)},
      {name: 'payment_deferred', passed: /이월|다음 스프린트/.test(text)},
      {name: 'rehearsal_and_deadline', passed: /10월\s*3일/.test(text) && /9월\s*30일/.test(text)},
      {name: 'owners_named', passed: /준구/.test(text) && /민수/.test(text)},
      {name: 'chatter_dropped', passed: !/점심/.test(text)},
      {name: 'three_items', passed: (text.match(/^\s*(\d+\.|[-*])\s+/gm) ?? []).length === 3}
    ];
    return {kind: 'content_rules', passed: checks.every(c => c.passed), checks};
  },
  standard_code(text) {
    const block = [...text.matchAll(/```(?:javascript|js)\n([\s\S]*?)```/g)].map(m => m[1]).find(b => /function\s+mean\s*\(|const\s+mean\s*=/.test(b));
    if (!block) return {kind: 'independent_tests', passed: false, checks: [{name: 'mean_function_found', passed: false}]};
    const ctx = {};
    vm.runInNewContext(block + '\nthis.mean = mean;', ctx, {timeout: 1000});
    const mean = ctx.mean;
    const cases = [
      ['empty_returns_null', () => mean([]) === null],
      ['single', () => mean([5]) === 5],
      ['basic', () => mean([1, 2, 3]) === 2],
      ['negatives', () => mean([-4, 2]) === -1],
      ['fraction', () => mean([1, 2]) === 1.5],
      ['decimals', () => Math.abs(mean([0.1, 0.2]) - 0.15) < 1e-12],
      ['large', () => mean([1e6, 3e6]) === 2e6],
      ['input_not_mutated', () => { const xs = [3, 1, 2]; mean(xs); return xs.join() === '3,1,2'; }],
      ['original_behavior_kept', () => { const orig = xs => xs.reduce((a, b) => a + b, 0) / xs.length; return [[1], [2, 4], [-1, -2, -3], [0.5, 1.5]].every(xs => mean(xs) === orig(xs)); }]
    ];
    const checks = cases.map(([name, fn]) => { try { return {name, passed: fn() === true}; } catch (e) { return {name, passed: false, error: e.message}; } });
    return {kind: 'independent_tests', passed: checks.every(c => c.passed), checks};
  },
  complex_design(text) {
    const checks = [['network_retry', /재시도|retry/i], ['webhook_order', /웹훅|webhook/i], ['db_transaction', /트랜잭션|transaction/i], ['counterexample', /반례/], ['idempotency', /멱등|idempot/i], ['zero_downtime', /무중단|zero.?downtime/i]]
      .map(([name, re]) => ({name, passed: re.test(text)}));
    return {kind: 'coverage_only', passed: null, coverage: checks.filter(c => c.passed).length / checks.length, checks, note: '요구 항목 언급 여부만 확인. 설계의 정확성·실제 시스템 안전성은 검증하지 않음.'};
  },
  refactor_module(text) {
    const checks = [['controller', /컨트롤러|controller/i], ['service', /서비스|service/i], ['repository', /저장소|리포지토리|repository/i], ['integration_test_plan', /통합 테스트|integration test/i], ['circular_dependency', /순환/], ['transaction_boundary', /트랜잭션/]]
      .map(([name, re]) => ({name, passed: re.test(text)}));
    return {kind: 'coverage_only', passed: null, coverage: checks.filter(c => c.passed).length / checks.length, checks, note: '요구 항목 언급 여부만 확인. 실제 파일이 없으므로 동작 보존은 검증하지 않음.'};
  }
};

export async function validateRun(dir) {
  const manifest = JSON.parse(await fs.readFile(path.join(dir, 'manifest.json'), 'utf8'));
  const out = [];
  for (const rec of manifest.records) {
    const resultFile = path.join(dir, rec.result);
    const result = JSON.parse(await fs.readFile(resultFile, 'utf8'));
    let validation;
    if (result.execution.status !== 'COMPLETED') validation = {status: 'NOT_RUN', passed: null, reason: 'execution_failed'};
    else if (!CHECKS[rec.taskId]) validation = {status: 'NOT_RUN', passed: null, reason: 'no_check_for_task'};
    else validation = {status: 'RUN', ...CHECKS[rec.taskId](result.execution.response), modelSelfReportedTestsAreEvidence: false};
    result.validation = validation;
    await fs.writeFile(resultFile, JSON.stringify(result, null, 2) + '\n');
    out.push({taskId: rec.taskId, selected: rec.selected, passed: validation.passed, coverage: validation.coverage, failed: (validation.checks ?? []).filter(c => !c.passed).map(c => c.name)});
  }
  return out;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const dirs = process.argv.slice(2);
  for (const d of dirs) for (const row of await validateRun(path.resolve(d))) console.log(JSON.stringify({run: path.basename(d), ...row}));
}
