#!/usr/bin/env node
// 라우터를 HTTP 서비스로. 메신저 봇·OpenClaw 훅·웹훅 앞단에 붙인다.
//   node server.mjs                       # 127.0.0.1:8792
//   curl -s localhost:8792/route -d '{"message":"내일 9시 회의 알림 걸어 줘"}' -H 'Content-Type: application/json'
import http from 'node:http';
import { route } from './router.mjs';
import { DEFAULT_POLICY } from './lib/policy.mjs';

const PORT = Number(process.env.PORT || 8792);
const server = http.createServer(async (req, res) => {
  const send = (code, body) => { res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' }); res.end(JSON.stringify(body)); };
  if (req.method === 'GET' && req.url === '/health') return send(200, { ok: true, policy: DEFAULT_POLICY });
  if (req.method !== 'POST' || req.url !== '/route') return send(404, { error: 'POST /route {message}' });
  let raw = '';
  for await (const chunk of req) { raw += chunk; if (raw.length > 10000) return send(413, { error: 'too large' }); }
  let message;
  try { message = JSON.parse(raw).message; } catch { return send(400, { error: 'JSON 본문이 필요합니다' }); }
  if (typeof message !== 'string' || !message.trim()) return send(400, { error: 'message는 비어 있지 않은 문자열' });
  const d = await route(message);
  send(200, { action: d.action, target: d.target ?? null, reason: d.reason, latencyMs: d.latencyMs ?? null, model: d.model ?? null,
    route: d.route ? { choice: d.route.choice, p: d.route.p } : null, confirmP: d.confirmP ?? null });
});
server.listen(PORT, '127.0.0.1', () => console.log(`router on http://127.0.0.1:${PORT}  (POST /route)`));
