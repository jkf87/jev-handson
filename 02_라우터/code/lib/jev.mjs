// TypeSafe Jev(/v1/systemone) 최소 클라이언트. 외부 패키지 없이 Node 20+ fetch만 쓴다.
// - 키: TYPESAFE_API_KEY 환경변수, 없으면 실행 폴더의 .env
// - 주소: TYPESAFE_BASE_URL (기본 https://api.typesafe.ai). 3강에서 로컬 호환 서버로 바꿀 때 이 값만 바꾼다.
// - 실패는 예외로 던진다. 라우터가 받아서 'review(api_error)'로 처리한다.
import fs from 'node:fs';
import path from 'node:path';

export function readDotenv(name, dir = process.cwd()) {
  const file = path.join(dir, '.env');
  if (!fs.existsSync(file)) return undefined;
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*(?:export\s+)?([A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
    if (m && m[1] === name) return m[2].replace(/^['"]|['"]$/g, '');
  }
  return undefined;
}

export function jevConfig(env = process.env) {
  return {
    apiKey: env.TYPESAFE_API_KEY || readDotenv('TYPESAFE_API_KEY'),
    baseUrl: (env.TYPESAFE_BASE_URL || readDotenv('TYPESAFE_BASE_URL') || 'https://api.typesafe.ai').replace(/\/$/, ''),
    model: env.TYPESAFE_DEFAULT_MODEL || readDotenv('TYPESAFE_DEFAULT_MODEL') || 'jev-latest',
    timeoutMs: Number(env.JEV_TIMEOUT_MS || 15000),
  };
}

export async function callJev(body, cfg = jevConfig()) {
  if (!cfg.apiKey && cfg.baseUrl.includes('api.typesafe.ai')) {
    throw Object.assign(new Error('TYPESAFE_API_KEY가 없습니다 (.env 또는 환경변수)'), { kind: 'no_api_key' });
  }
  const started = performance.now();
  const res = await fetch(`${cfg.baseUrl}/v1/systemone`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(cfg.apiKey ? { Authorization: `Bearer ${cfg.apiKey}` } : {}),
    },
    body: JSON.stringify({ model: cfg.model, ...body }),
    signal: AbortSignal.timeout(cfg.timeoutMs),
  });
  const latencyMs = Math.round(performance.now() - started);
  const text = await res.text();
  if (!res.ok) {
    throw Object.assign(new Error(`HTTP ${res.status}: ${text.slice(0, 300)}`), { kind: 'http_error', status: res.status, latencyMs });
  }
  return { ...JSON.parse(text), latencyMs };
}
