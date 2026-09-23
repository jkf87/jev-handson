#!/usr/bin/env node
// 2강 프롬프트 ④의 예제 답안: 라우터를 HTTP 서비스로.
//   node mini/server.mjs
//   curl -s localhost:8792/route -H 'Content-Type: application/json' -d '{"message":"내일 9시 회의 알림 걸어 줘"}'
import http from 'node:http';
import { buildRequest, askJev, decide } from './router.mjs';

const PORT = Number(process.env.PORT || 8792);
http.createServer(async (req, res) => {
  const send = (code, body) => res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' }).end(JSON.stringify(body));
  if (req.method !== 'POST' || req.url !== '/route') return send(404, { error: 'POST /route {"message": "..."}' });
  let raw = '';
  for await (const chunk of req) raw += chunk;
  let message;
  try { message = JSON.parse(raw).message; } catch { return send(400, { error: 'JSON 본문이 필요합니다' }); }
  if (typeof message !== 'string' || !message.trim()) return send(400, { error: 'message는 비어 있지 않은 문자열' });
  try {
    const r = await askJev(buildRequest(message));
    send(200, { ...decide(r.answers), latencyMs: r.latencyMs, model: r.model });
  } catch (e) {
    send(502, { action: 'review', error: String(e.message).slice(0, 200) });   // 호출 실패 → 사람 검토
  }
}).listen(PORT, '127.0.0.1', () => console.log(`POST http://127.0.0.1:${PORT}/route`));
