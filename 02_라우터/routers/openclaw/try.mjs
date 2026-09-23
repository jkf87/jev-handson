#!/usr/bin/env node
// OpenClaw 없이 라우터 판단만 시험한다. 플러그인이 이 메시지를 어떻게 처리할지 보여 준다.
//   node try.mjs "[광고] 코인 무료 에어드랍"
//   node try.mjs --all                    # 2강 메시지 40건으로 행동 일치율
//   LIGHT_MODEL=anthropic/claude-haiku-4-5 node try.mjs "고마워요"
// 키: 환경변수 TYPESAFE_API_KEY → 실행 폴더 .env
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildRequest, decide } from "./lib/router.js";
import { callJev, readKey } from "./lib/jev.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const config = { lightModel: process.env.LIGHT_MODEL || "anthropic/claude-haiku-4-5" };
const apiKey = readKey({ keyFile: path.join(process.cwd(), ".env") });
const baseUrl = process.env.TYPESAFE_BASE_URL || undefined;
const SAYS = { silence: "답하지 않음(모델 호출 없음)", clarify: "되묻기(모델 호출 없음)", light_model: `가벼운 모델(${config.lightModel})`, pass: "원래 모델 그대로" };

async function one(text) {
  const r = await callJev(buildRequest(text), { apiKey, baseUrl });
  return { d: decide(r.answers, config), latencyMs: r.latencyMs, model: r.model };
}

// 2강 정답 라벨 → 이 플러그인의 기대 행동
const expected = (row) => (row.route === "spam" ? "silence" : row.route === "unclear" ? "clarify" : row.route === "chat" ? "light_model" : "pass");

if (process.argv.includes("--all")) {
  const rows = fs.readFileSync(path.join(HERE, "../../code/data/messages.jsonl"), "utf8").trim().split("\n").map((l) => JSON.parse(l));
  let ok = 0, saved = 0;
  const lat = [];
  for (const row of rows) {
    const { d, latencyMs } = await one(row.text);
    lat.push(latencyMs);
    if (d.action === expected(row)) ok++; else console.log(`✗ ${row.id} ${row.text.slice(0, 34)} → ${d.action}${d.route ? ` (${d.route} ${d.p})` : ""} · 기대 ${expected(row)}`);
    if (d.action === "silence" || d.action === "clarify") saved++;
  }
  lat.sort((a, b) => a - b);
  console.log(`\n행동 일치 ${ok}/${rows.length} · 모델 호출 없이 끝난 메시지 ${saved}건 · Jev 지연 중앙값 ${lat[lat.length >> 1]}ms`);
} else {
  const text = process.argv.slice(2).join(" ").trim();
  if (!text) { console.error('사용법: node try.mjs "메시지" | --all'); process.exit(2); }
  const { d, latencyMs, model } = await one(text);
  console.log(JSON.stringify({ ...d, 처리: SAYS[d.action], latencyMs, jev: model }));
}
