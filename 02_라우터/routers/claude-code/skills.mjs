// 스킬 로스터 추상화: 누구 컴퓨터에서든 "지금 설치된 스킬"을 모아 라우터 후보로 만든다.
//
//   출처(SOURCES)   에이전트마다 스킬을 두는 폴더 규칙. 새 에이전트는 여기에 함수 하나만 더한다.
//   읽기            SKILL.md 앞머리(YAML 일부)를 관대하게 읽는다. 설명이 없으면 본문 첫 문단으로 채운다.
//   합치기          같은 파일(심링크)·같은 내용(복사본)은 후보 하나로. 이름만 같고 내용이 다르면 에이전트 이름을 붙여 구분.
//   캐시            SKILL.md 경로·크기·수정 시각의 지문이 같으면 다시 읽지 않는다.
//                   캐시는 ~/.cache/jev-skill-router 에 둔다. 강의 폴더에는 개인 스킬 목록이 남지 않는다.
//
// 외부 패키지 없음(Node 20+).
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';

export const ROSTER_VERSION = 3;
export const INDEX_CHARS = 160;   // 1차 랭킹에서 후보 설명으로 쓰는 길이(쿡북 Hermes는 60자, 한국어는 더 필요)
export const FULL_CHARS = 600;    // 2차 재검증에서 쓰는 설명 길이
export const BODY_CHARS = 1600;   // SKILL.md 본문 보관 길이(2차는 앞 700자만 씀)
const MAX_FILE_BYTES = 256 * 1024;
const MAX_KEY_CHARS = 80;

export const AGENT_ORDER = ['claude', 'codex', 'openclaw', 'shared'];

export function homes(env = process.env, home = os.homedir()) {
  return {
    home,
    claude: env.CLAUDE_CONFIG_DIR || path.join(home, '.claude'),
    codex: env.CODEX_HOME || path.join(home, '.codex'),
    openclaw: env.OPENCLAW_STATE_DIR || path.join(home, '.openclaw'),
    shared: path.join(home, '.agents'),
  };
}

export function defaultCacheDir(env = process.env, home = os.homedir()) {
  return env.SKILL_ROUTER_CACHE_DIR || path.join(env.XDG_CACHE_HOME || path.join(home, '.cache'), 'jev-skill-router');
}

async function isDir(p) { try { return (await fs.stat(p)).isDirectory(); } catch { return false; } }

async function childDirs(dir, test = () => true) {
  try {
    const entries = await fs.readdir(dir, {withFileTypes: true});
    const out = [];
    for (const e of entries) if (test(e.name) && (e.isDirectory() || (e.isSymbolicLink() && await isDir(path.join(dir, e.name))))) out.push(path.join(dir, e.name));
    return out;
  } catch { return []; }
}

// Claude Code 플러그인: installed_plugins.json의 installPath/skills, 그리고 plugins/synced 아래 skills 폴더
async function claudePluginRoots(claudeDir) {
  const roots = [];
  try {
    const installed = JSON.parse(await fs.readFile(path.join(claudeDir, 'plugins', 'installed_plugins.json'), 'utf8'));
    for (const [key, entries] of Object.entries(installed.plugins ?? {})) {
      const short = key.split('@')[0];
      for (const entry of [].concat(entries ?? [])) {
        if (entry?.installPath) roots.push({scope: `plugin:${short}`, root: path.join(entry.installPath, 'skills'), prefix: `${short}:`});
      }
    }
  } catch { /* 플러그인 레지스트리가 없으면 건너뜀 */ }
  async function walk(dir, depth) {
    if (depth > 4) return;
    for (const sub of await childDirs(dir, (n) => !n.startsWith('.') && n !== 'node_modules')) {
      if (path.basename(sub) === 'skills') {
        const owner = path.basename(dir);
        roots.push({scope: `synced:${owner}`, root: sub, prefix: `${owner}:`});
      } else await walk(sub, depth + 1);
    }
  }
  await walk(path.join(claudeDir, 'plugins', 'synced'), 0);
  return roots;
}

// 에이전트별 스킬 폴더. root 아래 <폴더>/SKILL.md 하나가 스킬 하나다.
export const SOURCES = {
  claude: async (h, cwd) => [
    {scope: 'user', root: path.join(h.claude, 'skills')},
    {scope: 'project', root: path.join(cwd, '.claude', 'skills')},
    ...(await claudePluginRoots(h.claude)),
  ],
  codex: async (h, cwd) => [
    {scope: 'user', root: path.join(h.codex, 'skills')},
    {scope: 'system', root: path.join(h.codex, 'skills', '.system')},
    {scope: 'project', root: path.join(cwd, '.agents', 'skills')},
  ],
  openclaw: async (h, cwd) => [
    {scope: 'user', root: path.join(h.openclaw, 'skills')},
    ...(await childDirs(h.openclaw, (n) => n.startsWith('workspace'))).map((w) => ({scope: `workspace:${path.basename(w)}`, root: path.join(w, 'skills')})),
    {scope: 'project', root: path.join(cwd, 'skills')},
  ],
  // skills CLI가 전역 설치 때 원본을 두는 공유 폴더. 어느 에이전트가 직접 읽는지는 도구마다 달라서 따로 둔다.
  shared: async (h) => [{scope: 'user', root: path.join(h.shared, 'skills')}],
};

export function parseAgents(value) {
  if (!value || value === 'all') return [...AGENT_ORDER];
  if (value === 'none') return [];
  const list = String(value).split(',').map((s) => s.trim()).filter(Boolean);
  const bad = list.filter((a) => !SOURCES[a]);
  if (bad.length) throw new Error(`모르는 에이전트: ${bad.join(', ')} (가능: ${AGENT_ORDER.join(', ')}, all)`);
  return list;
}

// ---------------------------------------------------------------- SKILL.md 읽기

function unquote(s) {
  s = s.trim();
  if (s.startsWith('"')) {
    const end = s.lastIndexOf('"');
    const inner = s.slice(1, end > 0 ? end : undefined);
    return inner.replace(/\\(["\\\/nrt])/g, (_, c) => ({n: '\n', r: '', t: '\t'})[c] ?? c);
  }
  if (s.startsWith("'")) {
    const end = s.lastIndexOf("'");
    return s.slice(1, end > 0 ? end : undefined).replace(/''/g, "'");
  }
  return s;
}

// YAML 앞머리 중 최상위 "키: 값"만 읽는다. 블록 스칼라(>, |), 따옴표, 여러 줄 평문을 받고 중첩 매핑은 건너뛴다.
export function parseSkillMd(text) {
  const src = String(text).replace(/^﻿/, '').replace(/\r\n?/g, '\n');
  const m = src.match(/^---[ \t]*\n([\s\S]*?)\n---[ \t]*(?:\n|$)([\s\S]*)$/);
  if (!m) return {frontmatter: {}, body: src};
  const lines = m[1].split('\n');
  const fm = {};
  for (let i = 0; i < lines.length; i++) {
    const kv = /^([A-Za-z0-9_-]+):(?:[ \t]+(.*))?$/.exec(lines[i]);
    if (!kv) continue;
    const key = kv[1];
    let value = (kv[2] ?? '').replace(/[ \t]+#.*$/, (c) => (/^["']/.test(kv[2] ?? '') ? c : '')).trim();
    const cont = [];
    let j = i + 1;
    while (j < lines.length && (/^[ \t]+\S/.test(lines[j]) || lines[j].trim() === '')) cont.push(lines[j++]);
    const nested = cont.some((l) => /^[ \t]+[A-Za-z0-9_-]+:(\s|$)/.test(l)) && !/^[>|]/.test(value);
    const block = /^([>|])[+-]?\d*$/.exec(value);
    if (block) {
      const texty = cont.filter((l) => l.trim());
      const indent = texty.length ? Math.min(...texty.map((l) => l.match(/^[ \t]*/)[0].length)) : 0;
      const raw = cont.map((l) => l.slice(indent));
      value = block[1] === '|' ? raw.join('\n') : raw.join('\n').split(/\n\s*\n/).map((p) => p.replace(/\n/g, ' ')).join('\n');
      i = j - 1;
    } else if (/^["']/.test(value)) {
      // 닫는 따옴표를 찾을 때까지 다음 줄을 잇는다(\" 와 '' 이스케이프는 건너뜀). 닫힌 뒤의 # 주석은 버린다.
      const q = value[0];
      const closeAt = (s) => {
        for (let p = 1; p < s.length; p++) {
          if (q === '"' && s[p] === '\\') { p++; continue; }
          if (s[p] === q) { if (q === "'" && s[p + 1] === "'") { p++; continue; } return p; }
        }
        return -1;
      };
      let joined = value;
      let k = i + 1;
      while (closeAt(joined) < 0 && k < lines.length && /^[ \t]/.test(lines[k])) joined += ' ' + lines[k++].trim();
      const end = closeAt(joined);
      value = unquote(end > 0 ? joined.slice(0, end + 1) : joined);
      i = k - 1;
    } else if (!nested && cont.some((l) => l.trim())) {
      value = [value, ...cont.map((l) => l.trim()).filter(Boolean)].join(' ').trim();
      i = j - 1;
    } else if (nested) {
      i = j - 1;   // metadata: 같은 중첩 매핑은 통째로 건너뜀
    }
    if (!(key in fm)) fm[key] = value;
  }
  return {frontmatter: fm, body: m[2]};
}

const squash = (s) => String(s ?? '').replace(/\s+/g, ' ').trim();

// 단어 경계에서 자른다(너무 짧아지면 글자에서)
export function clip(s, limit) {
  const t = squash(s);
  if (t.length <= limit) return t;
  const cut = t.slice(0, limit - 1);
  const sp = cut.lastIndexOf(' ');
  return (sp > limit * 0.6 ? cut.slice(0, sp) : cut) + '…';
}

// 본문 첫 문단: 제목·코드·주석·가로줄·표를 건너뛰고 마크다운 기호를 벗긴다
export function firstParagraph(body) {
  const out = [];
  let fence = false;
  for (const raw of String(body).split('\n')) {
    const line = raw.trim();
    if (/^(```|~~~)/.test(line)) { fence = !fence; continue; }
    if (fence) continue;
    if (!line) { if (out.length) break; continue; }
    if (/^(#|<!--|-->|---|\*\*\*|\||>|!\[)/.test(line)) { if (out.length) break; continue; }
    out.push(line.replace(/^[-*+]\s+/, ''));
  }
  return squash(out.join(' ').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/[*_`]{1,3}/g, ''));
}

const hash = (s) => crypto.createHash('sha256').update(s).digest('hex');

// 라우팅에 쓰는 본문은 설명문만 남긴다: 코드 블록·인라인 코드·HTML/XML 태그·URL을 뺀다.
// 이유 1) 판단에 필요한 건 "무엇을 하는 스킬인가"라서 코드가 신호를 흐린다.
// 이유 2) 코드·태그가 섞인 본문은 API 앞단 방화벽(Cloudflare)이 공격 패턴으로 보고 403으로 막는다
//         (2026-09-23 실측: 어떤 pptx 스킬 본문 발췌가 들어간 요청만 403, 설명만 보내면 200).
export function proseOnly(body) {
  return squash(String(body)
    .replace(/(```|~~~)[\s\S]*?(\1|$)/g, ' ')          // 코드 블록(닫히지 않았으면 끝까지)
    .replace(/`[^`\n]*`/g, ' ')                           // 인라인 코드
    .replace(/<!--[\s\S]*?-->/g, ' ')                     // HTML 주석
    .replace(/<\/?[A-Za-z][^>]*>/g, ' ')                   // HTML/XML 태그
    .replace(/https?:\/\/\S+/g, ' ')                       // URL
    .replace(/[<>{}$\\|]/g, ' '));                         // 남은 기호
}

export function maskHome(p, home = os.homedir()) {
  return p && home && p.startsWith(home) ? '~' + p.slice(home.length) : p;
}

export async function readSkill(file, {dirName, agent, scope, prefix = '', home = os.homedir()}) {
  const handle = await fs.open(file, 'r');
  let text;
  try {
    const {size} = await handle.stat();
    const buf = Buffer.alloc(Math.min(size, MAX_FILE_BYTES));
    await handle.read(buf, 0, buf.length, 0);
    text = buf.toString('utf8');
  } finally { await handle.close(); }
  const {frontmatter, body} = parseSkillMd(text);
  const name = prefix + (squash(frontmatter.name) || dirName);
  const fromFm = squash(frontmatter.description);
  const described = proseOnly(fromFm || firstParagraph(body) || '');
  const realpath = await fs.realpath(file).catch(() => file);
  const bodyText = proseOnly(body).slice(0, BODY_CHARS);
  return {
    name,
    description: clip(described || `(설명 없음) ${name}`, INDEX_CHARS),
    description_full: clip(described || `(설명 없음) ${name}`, FULL_CHARS),
    description_missing: !fromFm,
    body: bodyText,
    agents: [agent],
    scopes: [`${agent}:${scope}`],
    aliases: [],
    path: maskHome(file, home),
    realpath,
    content_hash: hash(squash(fromFm) + '\n' + bodyText),
  };
}

// ---------------------------------------------------------------- 찾기·합치기

export async function collectRoots({agents = [...AGENT_ORDER], dirs = [], cwd = process.cwd(), env = process.env, home = os.homedir()} = {}) {
  const h = homes(env, home);
  const roots = [];
  for (const agent of agents) for (const r of await SOURCES[agent](h, cwd)) roots.push({agent, ...r});
  for (const d of dirs) roots.push({agent: 'dir', scope: path.basename(path.resolve(d)), root: path.resolve(d)});
  // 같은 폴더가 두 번 잡히면(예: cwd가 홈이라 project=user) 한 번만
  const seen = new Set();
  return roots.filter((r) => { const k = path.resolve(r.root); if (seen.has(k)) return false; seen.add(k); return true; });
}

export async function listSkillFiles(roots) {
  const files = [];
  for (const r of roots) {
    for (const dir of await childDirs(r.root, (n) => !n.startsWith('.'))) {
      const file = path.join(dir, 'SKILL.md');
      try {
        const st = await fs.stat(file);
        if (st.isFile()) files.push({...r, dirName: path.basename(dir), file, size: st.size, mtimeMs: Math.round(st.mtimeMs)});
      } catch { /* SKILL.md 없는 폴더는 스킬이 아님 */ }
    }
  }
  return files;
}

export function fingerprint(files, extra = {}) {
  const lines = files.map((f) => `${f.agent}|${f.scope}|${f.file}|${f.size}|${f.mtimeMs}`).sort();
  return hash(JSON.stringify({v: ROSTER_VERSION, extra, lines}));
}

// 1) 같은 실제 파일(심링크)  2) 같은 내용(복사본) → 후보 하나. 대표 이름은 실제 폴더 이름과 같은 쪽.
// 3) 이름만 같고 내용이 다르면 뒤에 온 쪽에 에이전트 이름을 붙인다(gpt:pdf 처럼).
export function mergeSkills(list, {dedupe = true} = {}) {
  const merged = [];
  const byReal = new Map();
  const byContent = new Map();
  for (const s of list) {
    const hit = dedupe ? (byReal.get(s.realpath) ?? byContent.get(s.content_hash)) : null;
    if (!hit) {
      const rec = {...s};
      merged.push(rec);
      byReal.set(s.realpath, rec);
      byContent.set(s.content_hash, rec);
      continue;
    }
    for (const a of s.agents) if (!hit.agents.includes(a)) hit.agents.push(a);
    for (const sc of s.scopes) if (!hit.scopes.includes(sc)) hit.scopes.push(sc);
    const realName = path.basename(path.dirname(s.realpath));
    if (s.name !== hit.name) {
      if (s.name === realName && hit.name !== realName) { hit.aliases.push(hit.name); hit.name = s.name; }
      else if (!hit.aliases.includes(s.name)) hit.aliases.push(s.name);
    }
    byReal.set(s.realpath, hit);
  }
  // 후보 키(=Choice 선택지 이름)는 고유해야 한다
  const used = new Map();
  for (const s of merged) {
    let key = s.name.slice(0, MAX_KEY_CHARS);
    if (used.has(key)) {
      const base = `${s.agents[0]}:${s.name}`.slice(0, MAX_KEY_CHARS - 3);
      key = base;
      for (let n = 2; used.has(key); n++) key = `${base}#${n}`;
    }
    used.set(key, true);
    s.key = key;
  }
  return merged.sort((a, b) => a.key.localeCompare(b.key));
}

export async function buildRoster({agents = [...AGENT_ORDER], dirs = [], cwd = process.cwd(), env = process.env, home = os.homedir(), dedupe = true, files: given} = {}) {
  const roots = await collectRoots({agents, dirs, cwd, env, home});
  const files = given ?? await listSkillFiles(roots);
  const skills = [];
  const skipped = [];
  for (const f of files) {
    try { skills.push(await readSkill(f.file, {dirName: f.dirName, agent: f.agent, scope: f.scope, prefix: f.prefix ?? '', home})); }
    catch (e) { skipped.push({path: maskHome(f.file, home), reason: String(e.code || e.message).slice(0, 80)}); }
  }
  const merged = mergeSkills(skills, {dedupe});
  const sources = [];
  for (const r of roots) {
    const n = files.filter((f) => f.root === r.root).length;
    if (n) sources.push({agent: r.agent, scope: r.scope, root: maskHome(r.root, home), count: n});
  }
  return {
    version: ROSTER_VERSION, generated_at: new Date().toISOString(), agents, dirs: dirs.map((d) => maskHome(path.resolve(d), home)),
    found: files.length, count: merged.length, merged_duplicates: files.length - skipped.length - merged.length,
    description_missing: merged.filter((s) => s.description_missing).length,
    sources, skipped,
    skills: merged.map(({realpath, content_hash, ...rest}) => rest),
  };
}

// 캐시를 거쳐 로스터를 돌려준다. 스킬을 새로 깔거나 지우면 지문이 바뀌어 저절로 다시 만든다.
export async function loadRoster({agents = [...AGENT_ORDER], dirs = [], cwd = process.cwd(), env = process.env, home = os.homedir(), dedupe = true, refresh = false, cacheDir = defaultCacheDir(env, home)} = {}) {
  const roots = await collectRoots({agents, dirs, cwd, env, home});
  const files = await listSkillFiles(roots);
  const fp = fingerprint(files, {agents, dirs: dirs.map((d) => path.resolve(d)), dedupe});
  const cacheFile = path.join(cacheDir, `roster-${fp.slice(0, 16)}.json`);
  if (!refresh) {
    try { return {...JSON.parse(await fs.readFile(cacheFile, 'utf8')), cache: 'hit', cacheFile}; } catch { /* 없으면 새로 */ }
  }
  const roster = await buildRoster({agents, dirs, cwd, env, home, dedupe, files});
  try {
    await fs.mkdir(cacheDir, {recursive: true});
    await fs.writeFile(cacheFile, JSON.stringify(roster) + '\n');
  } catch { /* 캐시를 못 써도 라우팅은 계속 */ }
  return {...roster, cache: 'miss', cacheFile};
}
