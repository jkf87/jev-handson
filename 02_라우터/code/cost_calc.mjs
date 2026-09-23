#!/usr/bin/env node
// 파이프라인 비용 계산기: '라우터 두뇌' 비용(실측)과 '처리' 비용(가정)을 나눠서 본다.
//   node cost_calc.mjs                          # 40건 정답 분포 + 기본 가정
//   AGENT_TASK_USD=0.2 SMALL_REPLY_USD=0.0005 N=100000 node cost_calc.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const rows = fs.readFileSync(path.join(HERE, 'data/messages.jsonl'), 'utf8').trim().split('\n').map((l) => JSON.parse(l));
const share = (k) => rows.filter((r) => r.route === k).length / rows.length;

// 라우터 두뇌 1건 비용: results/compare-*.json 실측값(없으면 아래 기본값 = 2026-09-23 실측)
const measured = { jev: 0.0000348, 'claude-cli:haiku': 0.0027747, 'claude-cli:sonnet': 0.0050792, 'ollama:qwen3.5:4b': 0 };
for (const f of fs.existsSync(path.join(HERE, 'results')) ? fs.readdirSync(path.join(HERE, 'results')) : []) {
  if (!f.startsWith('compare-') || !f.endsWith('.json')) continue;
  const s = JSON.parse(fs.readFileSync(path.join(HERE, 'results', f), 'utf8')).summary;
  if (s?.engine) measured[s.engine] = s.costPer1kUsd / 1000;
}
// 처리 비용은 가정이다(작업 크기에 따라 수십 배 달라짐). 내 기록으로 바꿔 넣는다.
const AGENT = Number(process.env.AGENT_TASK_USD || 0.05);     // 작업 1건을 코딩 에이전트 세션이 처리
const SMALL = Number(process.env.SMALL_REPLY_USD || 0.0009);  // 대화 1건을 작은 모델이 답장 (Haiku 500in/80out 가정)
const N = Number(process.env.N || rows.length);

const mix = { chat: share('chat'), task: share('task'), unclear: share('unclear'), spam: share('spam') };
const handling = N * (mix.chat * SMALL + mix.task * AGENT);          // 되묻기·차단은 처리 비용 0으로 둔다
const scenarios = [
  ['A. 라우터 없이 모든 메시지를 에이전트 세션으로', N * AGENT, 0],
  ...Object.entries(measured).map(([k, v]) => [`B. 라우터(${k}) + 분기 처리`, N * v + handling, N * v]),
];
console.log(`메시지 ${N}건 · 구성 chat ${(mix.chat * 100).toFixed(0)}% task ${(mix.task * 100).toFixed(0)}% unclear ${(mix.unclear * 100).toFixed(0)}% spam ${(mix.spam * 100).toFixed(0)}%`);
console.log(`가정: 작업 1건 에이전트 $${AGENT} · 대화 답장 1건 $${SMALL}\n`);
console.log('| 방식 | 총비용 | 그중 라우터 두뇌 | A 대비 |\n|---|---:|---:|---:|');
const base = scenarios[0][1];
for (const [name, total, brain] of scenarios) console.log(`| ${name} | $${total.toFixed(4)} | $${brain.toFixed(4)} | ${((1 - total / base) * 100).toFixed(1)}% 절감 |`);
