// TypeSafe System One 클라이언트. 키는 환경변수 → --key-file → 실행 폴더 .env → 이 폴더 .env 순서로 찾고,
// 절대 출력·저장하지 않는다. 응답은 요청 본문 해시로 캐시해 같은 요청은 API를 다시 부르지 않는다(쿡북의 JsonCache).
// 캐시는 ~/.cache/jev-skill-router/json_cache.json (요청에 내 스킬 목록이 들어 있어 강의 폴더 밖에 둔다).
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {parseEnv} from 'node:util';
import {fileURLToPath} from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const ENDPOINT = (process.env.TYPESAFE_BASE_URL || 'https://api.typesafe.ai').replace(/\/$/, '') + '/v1/systemone';

export function digest(value) {
  return crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');
}

export async function resolveKey(keyFile) {
  if (process.env.TYPESAFE_API_KEY) return process.env.TYPESAFE_API_KEY;
  for (const file of [keyFile, path.join(process.cwd(), '.env'), path.join(HERE, '.env')].filter(Boolean)) {
    try {
      const key = parseEnv(await fs.readFile(file, 'utf8')).TYPESAFE_API_KEY;
      if (key) return key;
    } catch { /* 다음 후보 */ }
  }
  if (!ENDPOINT.includes('api.typesafe.ai')) return '';   // 로컬 호환 서버는 키 없이도 된다
  throw new Error('missing_typesafe_api_key (.env 또는 환경변수 TYPESAFE_API_KEY)');
}

export class JsonCache {
  constructor(file) { this.file = file; this.data = {}; }
  async load() {
    try { this.data = JSON.parse(await fs.readFile(this.file, 'utf8')); } catch { this.data = {}; }
    return this;
  }
  get(key) { return this.data[key] ?? null; }
  async set(key, value) {
    this.data[key] = value;
    // 요청이 동시에 끝나도 파일이 섞이지 않게 쓰기를 한 줄로 세운다
    this.writing = (this.writing ?? Promise.resolve()).then(async () => {
      await fs.mkdir(path.dirname(this.file), {recursive: true});
      await fs.writeFile(this.file, JSON.stringify(this.data) + '\n');
    }).catch(() => { /* 캐시를 못 써도 라우팅은 계속 */ });
    return this.writing;
  }
}

export function createJev({keyFile, model = 'jev-latest', cache = null, fetchImpl = fetch, timeoutMs = 60000, maxRetries = 3} = {}) {
  let key = null;
  async function call({state, questions}) {
    const body = {model, state, questions};
    // 로컬 호환 서버(3강)로 바꾸면 API 답을 재사용하지 않게 주소도 열쇠에 넣는다(기본 주소는 예전 캐시 그대로)
    const cacheKey = ENDPOINT.includes('api.typesafe.ai') ? digest(body) : digest({endpoint: ENDPOINT, body});
    const hit = cache?.get(cacheKey);
    if (hit) return {...hit, cached: true};
    key ??= await resolveKey(keyFile);
    for (let attempt = 0; ; attempt++) {
      const started = Date.now();
      const response = await fetchImpl(ENDPOINT, {
        method: 'POST',
        headers: {...(key ? {Authorization: `Bearer ${key}`} : {}), 'Content-Type': 'application/json', 'User-Agent': 'jev-skill-router/2.0'},
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(timeoutMs)
      });
      if ([429, 500, 502, 503, 504, 529].includes(response.status) && attempt < maxRetries) {
        const retryAfter = Number(response.headers.get('retry-after'));
        await new Promise(r => setTimeout(r, Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter * 1000 : 500 * 2 ** attempt));
        continue;
      }
      if (!response.ok) {
        // 422는 요청 구조 오류라 본문 앞부분이 진단에 필요하다. 키·헤더는 포함되지 않는다.
        const detail = response.status === 422 ? ': ' + (await response.text()).slice(0, 300) : '';
        throw new Error(`jev_http_${response.status}${detail}`);
      }
      const {model: answeredBy, answers, usage} = await response.json();
      const record = {model: answeredBy, answers, usage, seconds: (Date.now() - started) / 1000, at: new Date().toISOString()};
      if (cache) await cache.set(cacheKey, record);
      return {...record, cached: false};
    }
  }
  return {call, model};
}

export function keyFileFromArgs(args) {
  const at = args.indexOf('--key-file');
  return at >= 0 ? args[at + 1] : undefined;
}
