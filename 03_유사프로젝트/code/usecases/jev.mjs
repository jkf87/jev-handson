// 활용 사례 예제가 같이 쓰는 Jev(/v1/systemone) 최소 클라이언트와 실행 틀. Node 20+, 외부 패키지 없음.
// - 키: 환경변수 TYPESAFE_API_KEY → 실행 폴더 .env → code/.env (값은 출력하지 않는다)
// - 주소: TYPESAFE_BASE_URL (3강 로컬 decider 서버로 바꿀 수 있다. 로컬은 키 없이 된다)
// - --replay <기록.json>: API를 부르지 않고 저장한 응답으로 정책만 다시 돌린다
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));

function fromDotenv(name) {
  for (const dir of [process.cwd(), path.join(HERE, '..')]) {
    try {
      for (const line of fs.readFileSync(path.join(dir, '.env'), 'utf8').split(/\r?\n/)) {
        const m = line.match(/^\s*(?:export\s+)?([A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
        if (m && m[1] === name && m[2]) return m[2].replace(/^['"]|['"]$/g, '');
      }
    } catch { /* 다음 후보 */ }
  }
  return undefined;
}

export async function askJev({ state, questions }) {
  const baseUrl = (process.env.TYPESAFE_BASE_URL || fromDotenv('TYPESAFE_BASE_URL') || 'https://api.typesafe.ai').replace(/\/$/, '');
  const apiKey = process.env.TYPESAFE_API_KEY || fromDotenv('TYPESAFE_API_KEY');
  if (!apiKey && baseUrl.includes('api.typesafe.ai')) {
    throw new Error('TYPESAFE_API_KEY가 없습니다(.env 또는 환경변수). 키 없이 보려면 --replay <results/…json>');
  }
  const started = performance.now();
  const res = await fetch(`${baseUrl}/v1/systemone`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'User-Agent': 'jev-lecture-usecases/1.0', ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}) },
    body: JSON.stringify({ model: process.env.TYPESAFE_DEFAULT_MODEL || fromDotenv('TYPESAFE_DEFAULT_MODEL') || 'jev-latest', state, questions }),
    signal: AbortSignal.timeout(20000),
  });
  const latencyMs = Math.round(performance.now() - started);
  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
  const { answers, model, usage } = JSON.parse(text);
  return { answers, model, usage, latencyMs };
}

// Choice 답에서 고른 것과 그 확률, Noul 답에서 '예' 확률을 꺼낸다. 형식이 이상하면 null.
export function readChoice(answer, keys) {
  const ps = answer?.probabilities;
  if (!answer || !keys.includes(answer.choice) || !ps) return null;
  const p = ps[answer.choice];
  return Number.isFinite(p) ? { choice: answer.choice, p } : null;
}
export function readNoul(answer) {
  const p = answer?.noul;
  return Number.isFinite(p) && p >= 0 && p <= 1 ? p : null;
}

export function replayFile() {
  const i = process.argv.indexOf('--replay');
  return i >= 0 ? process.argv[i + 1] : null;
}

// 저장한 기록을 읽어 id → 응답으로. 기록이 없으면 null
export function loadReplay() {
  const file = replayFile();
  if (!file) return null;
  const rec = JSON.parse(fs.readFileSync(file, 'utf8'));
  return new Map(rec.rows.map((r) => [r.id, r.response]));
}

export function saveRun(name, rows, extra = {}) {
  const dir = path.join(HERE, 'results');
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `${name}-${new Date().toISOString().replace(/[:.]/g, '-')}.json`);
  fs.writeFileSync(file, JSON.stringify({ name, at: new Date().toISOString(), ...extra, rows }, null, 1) + '\n');
  return path.relative(process.cwd(), file);
}

// 시나리오마다 묻고(또는 기록을 재생하고) 정책을 적용한다. show()가 한 줄씩 출력한다.
export async function runScenarios(name, scenarios, { build, decide, show }) {
  const replay = loadReplay();
  const rows = [];
  let ok = 0;
  for (const sc of scenarios) {
    const response = replay ? replay.get(sc.id) : await askJev(build(sc));
    if (!response) { console.log(`- ${sc.id}: 기록 없음`); continue; }
    const decision = decide(response.answers, sc);
    const pass = sc.expect ? [].concat(sc.expect).includes(decision.key) : null;
    if (pass) ok++;
    rows.push({ id: sc.id, response, decision, expect: sc.expect ?? null, pass });
    show(sc, response, decision, pass);
  }
  const lat = rows.map((r) => r.response.latencyMs).filter(Number.isFinite).sort((a, b) => a - b);
  console.log(`\n기대와 같음 ${ok}/${rows.length}${lat.length ? ` · Jev 지연 중앙값 ${lat[lat.length >> 1]}ms` : ''}${replay ? ' (기록 재생, API 호출 0번)' : ''}`);
  if (!replay) console.log(`기록: ${saveRun(name, rows)}  (키 없이 다시 보기: --replay <이 파일>)`);
  return rows;
}
