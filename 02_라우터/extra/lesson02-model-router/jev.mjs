// TypeSafe System One 클라이언트. 키는 환경변수 또는 --key-file에서만 읽고 절대 출력·저장하지 않는다.
// 응답은 요청 본문 해시로 캐시해 같은 요청은 API를 다시 부르지 않는다(쿡북의 JsonCache와 같은 역할).
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {parseEnv} from 'node:util';

export const ENDPOINT = 'https://api.typesafe.ai/v1/systemone';

export function digest(value) {
  return crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');
}

export async function resolveKey(keyFile) {
  const key = process.env.TYPESAFE_API_KEY || (keyFile ? parseEnv(await fs.readFile(keyFile, 'utf8')).TYPESAFE_API_KEY : null);
  if (!key) throw new Error('missing_typesafe_api_key');
  return key;
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
    await fs.writeFile(this.file, JSON.stringify(this.data, null, 1) + '\n');
  }
}

export function createJev({keyFile, model = 'jev-latest', cache = null, fetchImpl = fetch, timeoutMs = 60000, maxRetries = 3} = {}) {
  let key = null;
  async function call({state, questions}) {
    const body = {model, state, questions};
    const cacheKey = digest(body);
    const hit = cache?.get(cacheKey);
    if (hit) return {...hit, cached: true};
    key ??= await resolveKey(keyFile);
    for (let attempt = 0; ; attempt++) {
      const started = Date.now();
      const response = await fetchImpl(ENDPOINT, {
        method: 'POST',
        headers: {Authorization: `Bearer ${key}`, 'Content-Type': 'application/json'},
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(timeoutMs)
      });
      if ((response.status === 429 || response.status === 529) && attempt < maxRetries) {
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
