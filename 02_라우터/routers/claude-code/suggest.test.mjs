// 키 없이 도는 시험: node --test
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {parseSkillMd, firstParagraph, clip, buildRoster, loadRoster, mergeSkills} from './skills.mjs';
import {planBatches, wideRequests, readWide, rerankQuestions, readRerank, decide, suggest, suggestionBlock, NONE_KEY, WIDE_MAX} from './suggest.mjs';
import {score, resolveGold} from './evaluate.mjs';

// ---------------------------------------------------------------- SKILL.md 읽기

test('frontmatter: 블록 스칼라(>, >-, |)와 중첩 매핑 건너뛰기', () => {
  const {frontmatter, body} = parseSkillMd('---\nname: x\ndescription: >\n  first line\n  second line\nmetadata:\n  openclaw:\n    emoji: 1\n---\n# Title\nbody');
  assert.equal(frontmatter.name, 'x');
  assert.equal(frontmatter.description.trim(), 'first line second line');
  assert.equal(frontmatter.metadata, '');
  assert.equal(body.trim(), '# Title\nbody');
  assert.equal(parseSkillMd('---\ndescription: >-\n  a\n  b\n---\n').frontmatter.description.trim(), 'a b');
  assert.equal(parseSkillMd('---\ndescription: |\n  a\n  b\n---\n').frontmatter.description.trim(), 'a\nb');
});

test('frontmatter: 따옴표(콜론·이스케이프·주석)와 여러 줄 평문', () => {
  assert.equal(parseSkillMd('---\ndescription: "PDF: 표 \\"추출\\"" # 주석\n---\n').frontmatter.description, 'PDF: 표 "추출"');
  assert.equal(parseSkillMd("---\ndescription: 'it''s ok'\n---\n").frontmatter.description, "it's ok");
  assert.equal(parseSkillMd('---\ndescription: 첫 줄\n  둘째 줄\n  셋째 줄\nname: y\n---\n').frontmatter.description, '첫 줄 둘째 줄 셋째 줄');
  assert.equal(parseSkillMd('---\ndescription: plain # 주석\n---\n').frontmatter.description, 'plain');
});

test('frontmatter: BOM·CRLF·앞머리 없음', () => {
  const r = parseSkillMd('﻿---\r\nname: z\r\ndescription: 윈도 줄바꿈\r\n---\r\n본문');
  assert.equal(r.frontmatter.description, '윈도 줄바꿈');
  assert.equal(r.body.trim(), '본문');
  assert.deepEqual(parseSkillMd('# 제목만\n본문').frontmatter, {});
});

test('설명이 없으면 본문 첫 문단(제목·코드·주석 건너뜀)', () => {
  assert.equal(firstParagraph('# 제목\n\n<!-- 메모 -->\n```\ncode\n```\n**굵게** 첫 문단 [링크](http://x)\n이어짐\n\n둘째 문단'), '굵게 첫 문단 링크 이어짐');
});

test('clip은 단어 경계에서 자른다', () => {
  assert.equal(clip('가나다 라마바 사아자 차카타', 10), '가나다 라마바…');
  assert.equal(clip('짧음', 10), '짧음');
});

// ---------------------------------------------------------------- 찾기·합치기(가짜 홈 폴더)

async function write(file, text) { await fs.mkdir(path.dirname(file), {recursive: true}); await fs.writeFile(file, text); }
const md = (name, desc, body = '본문') => `---\nname: ${name}\ndescription: ${desc}\n---\n${body}\n`;

async function fakeHome() {
  const home = await fs.mkdtemp(path.join(os.tmpdir(), 'skill-router-home-'));
  const proj = path.join(home, 'proj');
  await write(path.join(home, '.claude/skills/pdf/SKILL.md'), md('pdf', 'PDF 표 추출'));
  await write(path.join(home, '.claude/skills/voice/SKILL.md'), md('voice', '문체 윤문'));
  await fs.symlink(path.join(home, '.claude/skills/voice'), path.join(home, '.claude/skills/voice-alias'));   // 심링크 별칭
  await write(path.join(home, '.claude/skills/no-skill/README.md'), '스킬 아님');
  await write(path.join(home, '.claude/plugins/installed_plugins.json'), JSON.stringify({plugins: {'kit@market': [{installPath: path.join(home, 'plugin-kit')}]}}));
  await write(path.join(home, 'plugin-kit/skills/run/SKILL.md'), md('run', '플러그인 실행'));
  await write(path.join(home, '.codex/skills/pdf/SKILL.md'), md('pdf', '코덱스 쪽 PDF (내용이 다름)'));     // 이름 같고 내용 다름
  await write(path.join(home, '.codex/skills/voice-copy/SKILL.md'), md('voice', '문체 윤문'));             // 복사본(내용 같음)
  await write(path.join(home, '.codex/skills/.system/creator/SKILL.md'), md('creator', '스킬 만들기'));
  await write(path.join(home, '.openclaw/skills/sns/SKILL.md'), md('sns', 'SNS 올리기'));
  await write(path.join(home, '.openclaw/workspace-a/skills/ws/SKILL.md'), md('ws', '워크스페이스 스킬'));
  await write(path.join(home, '.agents/skills/shared/SKILL.md'), md('shared', '공유 폴더 스킬'));
  await write(path.join(proj, '.claude/skills/local/SKILL.md'), md('local', '프로젝트 스킬'));
  await write(path.join(proj, '.agents/skills/proj-codex/SKILL.md'), md('proj-codex', '프로젝트 코덱스 스킬'));
  return {home, proj};
}

test('에이전트별 폴더를 모두 찾고, 심링크·복사본은 합치고, 이름 충돌은 구분한다', async () => {
  const {home, proj} = await fakeHome();
  const env = {};
  const all = await buildRoster({home, cwd: proj, env});
  const keys = all.skills.map((s) => s.key);
  for (const k of ['pdf', 'voice', 'kit:run', 'creator', 'sns', 'ws', 'shared', 'local', 'proj-codex']) assert.ok(keys.includes(k), `없음: ${k} (${keys})`);
  assert.ok(keys.includes('codex:pdf'), '이름 충돌은 에이전트 이름을 붙여 구분');
  const voice = all.skills.find((s) => s.key === 'voice');
  assert.deepEqual(voice.agents.sort(), ['claude', 'codex']);           // 복사본이 합쳐짐
  assert.equal(voice.scopes.length, 2);                                // claude:user(원본·심링크) + codex:user(복사본)
  assert.equal(all.found, 12);
  assert.equal(all.count, 10);                                          // 심링크 1 + 복사본 1 합침
  assert.ok(!keys.includes('no-skill'));
  const claudeOnly = await buildRoster({home, cwd: proj, env, agents: ['claude']});
  assert.deepEqual(claudeOnly.skills.map((s) => s.key).sort(), ['kit:run', 'local', 'pdf', 'voice']);
  const codexHome = await buildRoster({home, cwd: proj, env: {CODEX_HOME: path.join(home, 'nowhere')}, agents: ['codex']});
  assert.deepEqual(codexHome.skills.map((s) => s.key), ['proj-codex']);  // CODEX_HOME을 따른다
  assert.ok(all.skills.every((s) => !s.path.includes(home)), '경로는 ~ 로 가린다');
});

test('캐시: 지문이 같으면 재사용, SKILL.md가 바뀌면 다시 만든다', async () => {
  const {home, proj} = await fakeHome();
  const cacheDir = path.join(home, 'cache');
  const a = await loadRoster({home, cwd: proj, env: {}, cacheDir, agents: ['claude']});
  const b = await loadRoster({home, cwd: proj, env: {}, cacheDir, agents: ['claude']});
  assert.equal(a.cache, 'miss');
  assert.equal(b.cache, 'hit');
  await new Promise((r) => setTimeout(r, 20));
  await write(path.join(home, '.claude/skills/new/SKILL.md'), md('new', '새로 깐 스킬'));
  const c = await loadRoster({home, cwd: proj, env: {}, cacheDir, agents: ['claude']});
  assert.equal(c.cache, 'miss');
  assert.equal(c.count, a.count + 1);
});

test('합치기를 끄면(--no-dedupe) 중복이 후보로 남는다 → 확률이 쪼개지는 시연용', () => {
  const s = (name, real, hash) => ({name, realpath: real, content_hash: hash, agents: ['dir'], scopes: ['dir:x'], aliases: []});
  assert.equal(mergeSkills([s('a', '/1', 'h'), s('a', '/2', 'h')]).length, 1);
  const off = mergeSkills([s('a', '/1', 'h'), s('a', '/2', 'h')], {dedupe: false});
  assert.deepEqual(off.map((x) => x.key), ['a', 'dir:a']);
});

// ---------------------------------------------------------------- 큰 로스터·작은 로스터

const fakeSkills = (n) => Array.from({length: n}, (_, i) => ({key: `s${i}`, name: `s${i}`, description: `skill ${i}`, description_full: `skill ${i} full`, body: `body ${i}`, aliases: []}));

test('조 나누기: Choice 하나에 255개를 넘지 않고, 빠지는 후보가 없다', () => {
  for (const n of [0, 1, 2, WIDE_MAX, WIDE_MAX + 1, 453, 600, 1500]) {
    const batches = planBatches(fakeSkills(n));
    assert.equal(batches.flat().length, n, `n=${n}`);
    assert.ok(batches.every((b) => b.length <= 255), `n=${n}`);
    if (n > WIDE_MAX) assert.ok(batches.length > 1);
  }
});

test('큰 로스터: 조가 많으면 요청을 나누고, 게이트는 첫 요청에만', () => {
  const {requests} = wideRequests({skills: fakeSkills(1500)});
  assert.equal(requests.length, 2);
  assert.equal(Object.keys(requests[0]).filter((k) => k.startsWith('which::')).length, 4);
  assert.equal(Object.keys(requests[0]).filter((k) => k.startsWith('gate::')).length, 3);
  assert.equal(Object.keys(requests[1]).filter((k) => k.startsWith('gate::')).length, 0);
});

test('후보가 하나뿐이면 빠져나갈 문을 넣고, 2차는 fits만 묻는다', () => {
  const one = {skills: fakeSkills(1)};
  const q = wideRequests(one).requests[0];
  assert.deepEqual(Object.keys(q['which::0'].criteria), ['s0', NONE_KEY]);
  const rq = rerankQuestions(one, ['s0']);
  assert.equal(rq.which, undefined);
  assert.ok(rq['fits::s0']);
  assert.equal(readRerank({'fits::s0': {noul: 0.9}}, ['s0']).winner, 's0');
});

// 가짜 Jev: 정해 둔 후보를 크게, 나머지는 고르게. noul은 고정값
function fakeJev(target, noul = 0.8) {
  const calls = [];
  return {calls, call: async ({questions}) => {
    calls.push(Object.keys(questions));
    const answers = {};
    for (const [k, q] of Object.entries(questions)) {
      if (q.type === 'noul') { answers[k] = {type: 'noul', noul: noul}; continue; }
      const keys = Object.keys(q.criteria);
      const hit = keys.includes(target);
      const probabilities = Object.fromEntries(keys.map((c) => [c, hit ? (c === target ? 0.9 : 0.1 / (keys.length - 1)) : 1 / keys.length]));
      answers[k] = {type: 'choice', choice: hit ? target : keys[0], probabilities, confidence: 0.5};
    }
    return {model: 'fake', answers, usage: {input_tokens: 1}, seconds: 0, cached: false};
  }};
}

test('suggest: 큰 로스터는 조별 랭킹 → 결선 → 재검증 순서로 돈다', async () => {
  const jev = fakeJev('s777');
  const r = await suggest('요청', {skills: fakeSkills(1500)}, jev);
  assert.deepEqual(r.suggestion, ['s777']);
  assert.deepEqual(r.calls.map((c) => c.stage), ['wide#0', 'wide#1', 'pool', 'rerank']);
});

test('suggest: 빈 로스터는 호출 없이 제안 없음', async () => {
  const jev = fakeJev('x');
  const r = await suggest('요청', {skills: []}, jev);
  assert.equal(r.reason, 'empty_roster');
  assert.equal(jev.calls.length, 0);
});

test('suggest: 작은 로스터는 요청 2개(쿡북과 같음)', async () => {
  const jev = fakeJev('s3');
  const r = await suggest('요청', {skills: fakeSkills(26)}, jev);
  assert.deepEqual(r.calls.map((c) => c.stage), ['wide', 'rerank']);
  assert.deepEqual(r.suggestion, ['s3']);
});

test('decide: 게이트·fits 문턱', () => {
  assert.equal(decide({gate: 0.1}, null).reason, 'gate_below_threshold');
  assert.equal(decide({gate: 0.5}, null).reason, 'rerank_missing');
  assert.equal(decide({gate: 0.5}, {winner: 'a', fits: {a: 0.1}}).reason, 'nothing_fits');
  assert.deepEqual(decide({gate: 0.5}, {winner: 'a', fits: {a: 0.9}}).suggestion, ['a']);
  assert.ok(suggestionBlock(['a']).includes('a'));
});

test('평가: 정답을 별칭으로 적어도 맞추고, 로스터에 없는 정답은 건너뛴다', () => {
  const roster = {skills: [{key: 'voice', name: 'voice', aliases: ['voice-alias']}, {key: 'pdf', name: 'pdf', aliases: []}]};
  const rows = resolveGold([
    {id: 'a', text: 't', gold: ['voice-alias']},
    {id: 'b', text: 't', gold: ['없는스킬']},
    {id: 'c', text: 't', gold: []},
  ], roster);
  assert.deepEqual(rows[0].gold, ['voice']);
  assert.equal(rows[1].skipped, true);
  const s = score([
    {...rows[0], suggestion: ['voice']}, {...rows[1], suggestion: []}, {...rows[2], suggestion: ['pdf']},
  ]);
  assert.equal(s.skipped, 1);
  assert.equal(s.wrong_suggestion, 0);
  assert.equal(s.needless_suggestion, 1);
});

// ---------------------------------------------------------------- 방화벽(403) 대비

test('본문 발췌에서 코드·태그·URL을 뺀다(방화벽이 공격 패턴으로 보는 것들)', async () => {
  const {proseOnly} = await import('./skills.mjs');
  const out = proseOnly('설명 문장.\n```python\nimport os; os.system("rm -rf /")\n```\n`<script>` 태그와 <b>굵게</b>, https://x.y/z?a=1 링크 {템플릿} $HOME');
  assert.equal(out, '설명 문장. 태그와 굵게 , 링크 템플릿 HOME');
});

test('재검증 요청이 403으로 막히면 설명만으로 한 번 더 묻고, 그래도 안 되면 제안 없이 끝낸다', async () => {
  const skills = fakeSkills(3);
  let blockedOnce = 0;
  const jev = {call: async ({questions}) => {
    const hasBody = Object.values(questions).some((q) => q.type === 'choice' && Object.values(q.criteria).some((t) => String(t).includes('body')));
    if (questions.which && Object.keys(questions).some((k) => k.startsWith('fits::')) && hasBody) { blockedOnce++; throw new Error('jev_http_403'); }
    return fakeJev('s1').call({questions});
  }};
  const r = await suggest('요청', {skills}, jev);
  assert.equal(blockedOnce, 1);
  assert.deepEqual(r.suggestion, ['s1']);
  assert.equal(r.calls.at(-1).degraded, 'jev_http_403');
  const dead = await suggest('요청', {skills}, {call: async () => { throw new Error('jev_http_403'); }});
  assert.deepEqual(dead.suggestion, []);
  assert.match(dead.reason, /^api_error/);
});
