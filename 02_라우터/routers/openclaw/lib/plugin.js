// OpenClaw 훅 두 개에 라우터를 붙인다. 두 훅이 같은 턴에서 Jev를 한 번만 부르도록 판정을 잠깐 기억한다.
//   before_model_resolve  대화면 가벼운 모델로 바꾼다
//   before_agent_reply    스팸은 조용히, 애매하면 되묻는다(모델 호출 없이 끝냄)
import { appendFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import os from "node:os";
import { buildRequest, decide, modelOverride, DEFAULTS } from "./router.js";
import { callJev, readKey } from "./jev.js";

const TTL_MS = 120_000;

// 설정의 파일 경로: ~는 홈, 상대 경로는 OpenClaw 상태 폴더(프로필마다 다름, 기본 ~/.openclaw) 기준
export function resolvePath(p, env = process.env) {
  if (!p) return "";
  if (p === "~" || p.startsWith("~/")) return path.join(os.homedir(), p.slice(2));
  if (path.isAbsolute(p)) return p;
  return path.join(env.OPENCLAW_STATE_DIR || path.join(os.homedir(), ".openclaw"), p);
}

export function createJudge(config = {}, { call = callJev, now = () => Date.now(), env = process.env } = {}) {
  const cfg = { ...DEFAULTS, ...config };
  const cache = new Map();   // key → {at, promise}
  const logFile = resolvePath(cfg.logFile, env);
  function log(row) {
    if (!logFile) return;
    try {
      mkdirSync(path.dirname(logFile), { recursive: true });
      appendFileSync(logFile, JSON.stringify({ at: new Date(now()).toISOString(), ...row }) + "\n");
    } catch { /* 기록 실패는 라우팅을 막지 않는다 */ }
  }
  async function judge(text, ctx = {}, hook = "") {
    const key = ctx.runId || `${ctx.sessionKey ?? ""}\u0000${String(text).trim()}`;
    for (const [k, v] of cache) if (now() - v.at > TTL_MS) cache.delete(k);
    let hit = cache.get(key);
    if (!hit) {
      const promise = (async () => {
        try {
          const apiKey = readKey({ keyFile: resolvePath(cfg.keyFile, env), env });
          const r = await call(buildRequest(text), { apiKey, baseUrl: cfg.baseUrl || env.TYPESAFE_BASE_URL || undefined });
          const d = decide(r.answers, cfg);
          log({ hook, runId: ctx.runId ?? null, agentId: ctx.agentId ?? null, route: d.route ?? null, p: d.p ?? null, action: d.action, reason: d.reason ?? null, latencyMs: r.latencyMs, chars: String(text).length });
          return d;
        } catch (e) {
          log({ hook, runId: ctx.runId ?? null, action: "pass", reason: `error:${String(e.message).slice(0, 40)}` });
          return { action: "pass", reason: "jev_error" };
        }
      })();
      hit = { at: now(), promise };
      cache.set(key, hit);
    }
    return hit.promise;
  }
  return { judge, config: cfg, logFile };
}

export function registerJevRouter(api, deps = {}) {
  const { judge, config, logFile } = createJudge(api.pluginConfig ?? {}, deps);
  api.on("before_model_resolve", async (event, ctx = {}) => {
    if (ctx.trigger && ctx.trigger !== "user") return undefined;   // 하트비트·크론은 건드리지 않는다
    const d = await judge(event?.prompt ?? "", ctx, "before_model_resolve");
    return d.action === "light_model" ? modelOverride(d.model) : undefined;
  });
  api.on("before_agent_reply", async (event, ctx = {}) => {
    const d = await judge(event?.cleanedBody ?? "", ctx, "before_agent_reply");
    if (d.action === "silence") return { handled: true, reason: "jev-router: spam" };
    if (d.action === "clarify") return { handled: true, reply: { text: config.clarifyText }, reason: "jev-router: unclear" };
    return undefined;
  }, { eligibleTriggers: ["user"] });
  api.logger?.info?.(`jev-router: ready (lightModel=${config.lightModel || "없음"}, minRouteP=${config.minRouteP}, log=${logFile || "없음"})`);
}
