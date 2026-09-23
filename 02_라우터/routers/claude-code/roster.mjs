// 내 컴퓨터에 깔린 스킬로 로스터를 만들고, 어디서 몇 개를 찾았는지 보여 준다.
//   node roster.mjs                       # 모든 에이전트(claude·codex·openclaw·shared)에서 찾기
//   node roster.mjs --agent claude        # Claude Code 스킬만 (훅은 이 설정을 씀)
//   node roster.mjs --dir ./my-skills     # 폴더 추가
//   node roster.mjs --demo                # 강의 데모 스킬(demo/skills)만
//   node roster.mjs --list                # 후보 이름·출처까지 출력 (화면 녹화 때는 빼기)
// 로스터는 ~/.cache/jev-skill-router 에 캐시한다. 스킬을 깔거나 지우면 다음 실행 때 저절로 다시 만든다.
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {loadRoster} from './skills.mjs';
import {rosterOptions, planBatches, WIDE_MAX, BATCH_SIZE} from './suggest.mjs';

export {parseSkillMd, loadRoster, buildRoster} from './skills.mjs';

if (fileURLToPath(import.meta.url) === path.resolve(process.argv[1] || '')) {
  const args = process.argv.slice(2);
  const roster = await loadRoster(rosterOptions(args));
  const batches = planBatches(roster.skills);
  const summary = {
    count: roster.count,
    found_files: roster.found,
    merged_duplicates: roster.merged_duplicates,
    description_missing: roster.description_missing,
    skipped: roster.skipped.length,
    choice_plan: batches.length > 1
      ? `${roster.count}개 > ${WIDE_MAX} → Choice ${batches.length}개(조당 ${batches.map((b) => b.length).join('·')}) + 결선 1번`
      : `Choice 1개(${roster.count}개)`,
    sources: roster.sources,
    cache: roster.cache,
  };
  if (args.includes('--json')) console.log(JSON.stringify({...summary, cacheFile: roster.cacheFile}, null, 2));
  else {
    console.log(`스킬 ${roster.count}개 (SKILL.md ${roster.found}개, 중복 ${roster.merged_duplicates}개 합침, 설명 없음 ${roster.description_missing}개, 읽기 실패 ${roster.skipped.length}개)`);
    console.log(`Choice 계획: ${summary.choice_plan}  ·  조 크기 기준 ${BATCH_SIZE}`);
    for (const s of roster.sources) console.log(`  ${s.agent.padEnd(8)} ${s.scope.padEnd(24)} ${String(s.count).padStart(4)}  ${s.root}`);
    if (!roster.count) console.log('\n스킬을 못 찾았어요. --dir 로 폴더를 알려 주거나, --demo 로 강의 데모 스킬을 쓰세요.');
    console.log(`캐시: ${roster.cache}`);
  }
  if (args.includes('--list')) {
    for (const s of roster.skills) {
      const extra = [s.agents.join('+'), s.aliases.length ? `별칭 ${s.aliases.join(',')}` : '', s.description_missing ? '설명없음' : ''].filter(Boolean).join(' · ');
      console.log(`${s.key.padEnd(34)} ${extra.padEnd(22)} ${s.description.slice(0, 70)}`);
    }
  }
}
