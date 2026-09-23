// 키 없이 도는 시험: npm test
import test from "node:test";
import assert from "node:assert/strict";
import { decide, modelOverride, buildRequest } from "../lib/router.js";
import { registerJevRouter, createJudge } from "../lib/plugin.js";

const ans = (choice, p) => ({ route: { type: "choice", choice, probabilities: { chat: 0, task: 0, unclear: 0, spam: 0, [choice]: p } } });

test("정책: 스팸은 조용히, 애매하면 되묻기, 대화는 가벼운 모델, 작업은 그대로", () => {
  const cfg = { lightModel: "anthropic/claude-haiku-4-5" };
  assert.equal(decide(ans("spam", 0.95), cfg).action, "silence");
  assert.equal(decide(ans("spam", 0.7), cfg).action, "pass");          // 스팸 확신 부족
  assert.equal(decide(ans("unclear", 0.9), cfg).action, "clarify");
  assert.equal(decide(ans("chat", 0.9), cfg).action, "light_model");
  assert.equal(decide(ans("chat", 0.9), {}).action, "pass");            // lightModel이 없으면 그대로
  assert.equal(decide(ans("task", 0.99), cfg).action, "pass");
  assert.equal(decide(ans("chat", 0.5), cfg).reason, "uncertain");     // route 확률 0.6 미만
  assert.equal(decide({ route: { choice: "weird" } }, cfg).reason, "invalid_answer");
});

test("모델 이름: provider/model을 나눈다", () => {
  assert.deepEqual(modelOverride("anthropic/claude-haiku-4-5"), { providerOverride: "anthropic", modelOverride: "claude-haiku-4-5" });
  assert.deepEqual(modelOverride("qwen3.5:4b"), { modelOverride: "qwen3.5:4b" });
  assert.equal(modelOverride(""), undefined);
});

test("요청 본문: 질문 1개, 메시지는 데이터로", () => {
  const b = buildRequest("안녕");
  assert.deepEqual(Object.keys(b.questions), ["route"]);
  assert.equal(b.state.message, "안녕");
});

function fakeApi(pluginConfig) {
  const hooks = {};
  return { hooks, pluginConfig, on(name, fn, opts) { hooks[name] = { fn, opts }; }, logger: { info() {} } };
}

test("플러그인: 훅 두 개를 붙이고, 같은 턴은 Jev를 한 번만 부른다", async () => {
  let calls = 0;
  const api = fakeApi({ lightModel: "anthropic/claude-haiku-4-5" });
  registerJevRouter(api, { call: async () => { calls++; return { answers: ans("chat", 0.97).route ? ans("chat", 0.97) : null, latencyMs: 1 }; }, env: {} });
  assert.deepEqual(Object.keys(api.hooks).sort(), ["before_agent_reply", "before_model_resolve"]);
  assert.deepEqual(api.hooks.before_agent_reply.opts, { eligibleTriggers: ["user"] });
  const ctx = { runId: "r1", trigger: "user" };
  const m = await api.hooks.before_model_resolve.fn({ prompt: "고마워요!" }, ctx);
  const r = await api.hooks.before_agent_reply.fn({ cleanedBody: "고마워요!" }, ctx);
  assert.deepEqual(m, { providerOverride: "anthropic", modelOverride: "claude-haiku-4-5" });
  assert.equal(r, undefined);            // 대화는 모델이 답한다
  assert.equal(calls, 1);
});

test("플러그인: 스팸은 조용히, 애매하면 되묻기(모델 호출 없이)", async () => {
  const api = fakeApi({});
  let next = ans("spam", 0.99);
  registerJevRouter(api, { call: async () => ({ answers: next, latencyMs: 1 }), env: {} });
  assert.deepEqual(await api.hooks.before_agent_reply.fn({ cleanedBody: "[광고] 코인" }, { runId: "a" }), { handled: true, reason: "jev-router: spam" });
  next = ans("unclear", 0.9);
  const r = await api.hooks.before_agent_reply.fn({ cleanedBody: "그거 해 줘" }, { runId: "b" });
  assert.equal(r.handled, true);
  assert.match(r.reply.text, /무엇을 도와드리면/);
});

test("플러그인: Jev가 실패하거나 하트비트면 아무것도 안 한다(fail-open)", async () => {
  const api = fakeApi({ lightModel: "x/y" });
  registerJevRouter(api, { call: async () => { throw new Error("jev_http_503"); }, env: {} });
  assert.equal(await api.hooks.before_agent_reply.fn({ cleanedBody: "무엇이든" }, { runId: "c" }), undefined);
  assert.equal(await api.hooks.before_model_resolve.fn({ prompt: "무엇이든" }, { runId: "d" }), undefined);
  assert.equal(await api.hooks.before_model_resolve.fn({ prompt: "x" }, { runId: "e", trigger: "heartbeat" }), undefined);
});

test("캐시: 2분이 지나면 다시 묻는다", async () => {
  let t = 0, calls = 0;
  const { judge } = createJudge({}, { call: async () => { calls++; return { answers: ans("task", 0.9), latencyMs: 1 }; }, now: () => t, env: {} });
  await judge("작업", { runId: "z" });
  await judge("작업", { runId: "z" });
  t = 130_000;
  await judge("작업", { runId: "z" });
  assert.equal(calls, 2);
});
