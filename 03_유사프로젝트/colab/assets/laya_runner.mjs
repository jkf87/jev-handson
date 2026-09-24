// laya_runner.mjs — @receptron/laya(Node.js + ONNX Runtime)로 댓글 판정을 한 프로세스에서 끝까지 돌려요.
//
//   node laya_runner.mjs <입력.jsonl> <출력.jsonl>
//
// 입력 한 줄: {"id": "v001", "state": {...}, "questions": {"toxicity": {"type": "choice", ...}}}
// 출력 한 줄: {"id", "pred", "probs", "ms", "input_tokens", "truncated"}   (댓글 글은 출력하지 않아요)
// 마지막 줄(stdout): {"summary": {...}}   ← 노트북이 읽어요
//
// 환경변수
//   LAYA_EP            실행 장치 후보. "|"로 나눠 앞에서부터 시도해요. 예: "cuda|cpu" (기본 "cpu")
//   LAYA_REVISION      receptron/laya-onnx 커밋(재현성을 위해 고정). 기본 main
//   LAYA_THREADS       CPU 스레드 수(intraOpNumThreads). 비우면 ONNX Runtime 기본값
//   LAYA_TIME_BUDGET_S 0보다 크면 판정이 이 시간(초)을 넘을 때 멈추고 여기까지 결과만 남겨요(받기·올리기 시간은 빼고 셈).
//                      GPU면 보통 수십 초 안에 끝나서 걸리지 않고, CPU로 돌 때(또는 GPU를 못 쓰고 있을 때) 시간을 지켜 줘요.
//   LAYA_CACHE         가중치 캐시 폴더(패키지 기본 ~/.cache/receptron-laya)
// 모델을 한 번만 올리고 모든 댓글을 차례로 판정해요(댓글마다 프로세스를 새로 띄우면 1.7GB를 매번 다시 올려야 해요).
import { createReadStream, createWriteStream } from "node:fs";
import readline from "node:readline";
import { Laya } from "@receptron/laya";

const [inPath, outPath] = process.argv.slice(2);
if (!inPath || !outPath) {
  console.error("사용법: node laya_runner.mjs <입력.jsonl> <출력.jsonl>");
  process.exit(2);
}
const epCandidates = (process.env.LAYA_EP || "cpu").split("|").map((s) => s.split(",").map((x) => x.trim()).filter(Boolean));
const revision = process.env.LAYA_REVISION || "main";
const threads = Number(process.env.LAYA_THREADS || 0);
const budgetS = Number(process.env.LAYA_TIME_BUDGET_S || 0);
const log = (msg) => process.stderr.write(msg + "\n");

// ① 입력 읽기
const items = [];
for await (const line of readline.createInterface({ input: createReadStream(inPath, "utf8"), crlfDelay: Infinity })) {
  if (line.trim()) items.push(JSON.parse(line));
}
if (items.length === 0) {
  console.error("입력이 비어 있어요");
  process.exit(2);
}

// ② 모델 받기(처음 한 번, 약 1.7GB) + 올리기. 장치 후보를 앞에서부터 시도해요.
const lastShown = {};
const onProgress = ({ file, received, total }) => {
  if (!total || total < 50e6) return; // 큰 파일(laya.onnx.data)만 보여 줘요
  const pct = Math.floor((received / total) * 10);
  if (pct !== lastShown[file] && (pct % 2 === 0 || received === total)) {
    lastShown[file] = pct;
    log(`[laya] 받는 중 ${file} ${(received / 1e9).toFixed(2)} / ${(total / 1e9).toFixed(2)} GB`);
  }
};
const t0 = performance.now();
let laya = null;
let ep = null;
const epErrors = [];
for (const cand of epCandidates) {
  try {
    laya = await Laya.load({
      revision,
      onProgress,
      executionProviders: cand,
      sessionOptions: threads > 0 ? { intraOpNumThreads: threads } : {},
    });
    ep = cand.join(",");
    break;
  } catch (e) {
    const msg = String(e && e.message ? e.message : e).split("\n")[0].slice(0, 200);
    epErrors.push(`${cand.join(",")}: ${msg}`);
    log(`[laya] 장치 ${cand.join(",")} 실패 → 다음 후보로: ${msg}`);
  }
}
if (!laya) {
  console.log(JSON.stringify({ summary: { ok: false, ep_errors: epErrors } }));
  process.exit(1);
}
const loadS = (performance.now() - t0) / 1000;
log(`[laya] 올리기 끝 ${loadS.toFixed(1)}초 · 장치 ${ep} · max_len ${laya.config.max_len}`);

// ③ 워밍업 1번(버림) 뒤 한 건씩 판정
await laya.systemOne(items[0].state, items[0].questions);
const out = createWriteStream(outPath, "utf8");
const tRun = performance.now();
let done = 0;
let stoppedEarly = false;
for (const it of items) {
  if (budgetS > 0 && (performance.now() - tRun) / 1000 > budgetS) {
    stoppedEarly = true;
    break;
  }
  const s = performance.now();
  const res = await laya.systemOne(it.state, it.questions);
  const ms = performance.now() - s;
  const qid = Object.keys(it.questions)[0];
  const a = res.answers[qid];
  out.write(
    JSON.stringify({
      id: it.id,
      pred: a.choice,
      probs: a.probabilities,
      ms: Math.round(ms * 10) / 10,
      input_tokens: res.usage.input_tokens,
      truncated: res.usage.input_tokens >= laya.config.max_len,
    }) + "\n",
  );
  done += 1;
  if (done % 25 === 0 || done === items.length) {
    const el = (performance.now() - tRun) / 1000;
    log(`[laya] ${done}/${items.length} · ${el.toFixed(1)}초 · 건당 ${((el / done) * 1000).toFixed(0)}ms`);
  }
}
await new Promise((resolve) => out.end(resolve));
await laya.close();
console.log(
  JSON.stringify({
    summary: {
      ok: true,
      ep,
      ep_errors: epErrors,
      load_s: Math.round(loadS * 10) / 10,
      n: done,
      n_input: items.length,
      run_s: Math.round(((performance.now() - tRun) / 1000) * 10) / 10,
      stopped_early: stoppedEarly,
      max_len: laya.config.max_len,
      revision,
      node: process.version,
    },
  }),
);
