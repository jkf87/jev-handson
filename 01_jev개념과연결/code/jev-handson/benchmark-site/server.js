import { createReadStream, existsSync, readFileSync } from "node:fs";
import { access, readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { dirname, extname, join, resolve } from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { OpenRouter } from "@openrouter/sdk";

const here = dirname(fileURLToPath(import.meta.url));
const publicDir = join(here, "public");
const samplePath = join(here, "data", "sample-100.json");
const baselinePath = join(here, "data", "baseline-summary.json");
const schemaPath = join(here, "schemas", "agy-classification.schema.json");
const port = Number(process.env.PORT || 4173);
const labels = ["none", "offensive", "hate"];
const activeRuns = new Set();

if (!existsSync(samplePath)) {
  throw new Error("Sample data is missing. Run `npm run sample` first.");
}

const sampleBundle = JSON.parse(readFileSync(samplePath, "utf8"));

const CLASSIFICATION_GUIDE = `You are a backend routing classifier for Korean entertainment-news comments.
Use the news title only as context and classify each comment into exactly one label.

Labels:
- none: The comment contains no hatred, severe insult, or offensive/aggressive expression.
- offensive: The comment is rude, aggressive, sarcastic, unethical, or likely to offend, but does not reach the level of strong hate or severe insult.
- hate: The comment displays strong hate or severe insult toward a target, or an aggressive stance toward an individual or group based on characteristics such as gender, sexual identity, race, nationality, political stance, religion, disability, age, appearance, wealth, or occupation. It may also include sexual harassment, harmful rumors presented offensively, or malicious coined terms.

Important:
- Mere presence of profanity does not automatically mean hate.
- Preserve the distinction between offensive and hate.
- Return one result for every supplied id and do not add ids that were not supplied.`;

function sendJson(response, status, payload) {
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store"
  });
  response.end(JSON.stringify(payload));
}

function sse(response, event, payload) {
  response.write(`event: ${event}\n`);
  response.write(`data: ${JSON.stringify(payload)}\n\n`);
}

function splitIntoBatches(items, size) {
  const batches = [];
  for (let index = 0; index < items.length; index += size) {
    batches.push(items.slice(index, index + size));
  }
  return batches;
}

async function loadOpenRouterKey() {
  if (process.env.OPENROUTER_API_KEY?.trim()) return process.env.OPENROUTER_API_KEY.trim();
  const candidates = [resolve(here, "../env.txt"), resolve(here, "env.txt")];
  for (const candidate of candidates) {
    try {
      const value = (await readFile(candidate, "utf8")).trim();
      if (value) return value;
    } catch {
      // Try the next local-only key location.
    }
  }
  throw new Error("OPENROUTER_API_KEY is not configured and env.txt was not found.");
}

async function commandExists(command) {
  const probe = process.platform === "win32" ? "where.exe" : "which";
  return await new Promise((resolvePromise) => {
    const child = spawn(probe, [command], { stdio: "ignore" });
    child.on("error", () => resolvePromise(false));
    child.on("exit", (code) => resolvePromise(code === 0));
  });
}

function buildAgyPrompt(batch) {
  const inputs = batch.map(({ id, news_title, comments }) => ({
    id,
    news_title,
    comments
  }));
  return `${CLASSIFICATION_GUIDE}\n\nClassify the following JSON samples. Return only the schema-compliant result.\n\n${JSON.stringify(inputs)}`;
}

function findResults(value, depth = 0) {
  if (depth > 8 || value == null) return null;
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = findResults(item, depth + 1);
      if (found) return found;
    }
    return null;
  }
  if (typeof value === "object") {
    if (Array.isArray(value.results)) return value.results;
    for (const child of Object.values(value)) {
      const found = findResults(child, depth + 1);
      if (found) return found;
    }
    return null;
  }
  if (typeof value === "string") {
    const trimmed = value.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
    if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return null;
    try {
      return findResults(JSON.parse(trimmed), depth + 1);
    } catch {
      return null;
    }
  }
  return null;
}

function classifyWithAgy(batch, { model, signal }) {
  const executable = process.env.AGY_PATH || "agy";
  const args = [
    "-p",
    buildAgyPrompt(batch),
    "--output-format",
    "json",
    "--json-schema",
    schemaPath,
    "--disable-slash-commands",
    "--mode",
    "plan",
    "--effort",
    "low",
    "--model",
    model
  ];

  return new Promise((resolvePromise, reject) => {
    const child = spawn(executable, args, {
      cwd: here,
      windowsHide: true,
      signal,
      env: { ...process.env, NO_COLOR: "1" }
    });
    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`agy exited with code ${code}: ${stderr.trim().slice(-800)}`));
        return;
      }
      try {
        const parsed = JSON.parse(stdout);
        const results = findResults(parsed);
        if (!results) throw new Error("No schema-compliant results array was found in AGY output.");
        resolvePromise(results);
      } catch (error) {
        reject(new Error(`Could not parse AGY output: ${error.message}`));
      }
    });
  });
}

async function classifyWithJev(batch, { signal }) {
  const apiKey = await loadOpenRouterKey();
  const openrouter = new OpenRouter({ apiKey });
  const state = JSON.stringify(batch.map(({ id, news_title, comments }) => ({
    id,
    news_title,
    comments
  })));
  const questions = Object.fromEntries(batch.map(({ id }) => [
    id,
    {
      type: "choice",
      instructions: `${CLASSIFICATION_GUIDE}\nClassify only the sample whose id is ${JSON.stringify(id)}.`,
      criteria: {
        none: "No hatred, severe insult, or offensive/aggressive expression.",
        offensive: "Rude, aggressive, sarcastic, unethical, or offensive, but not strong hate or severe insult.",
        hate: "Strong hate, severe insult, discriminatory aggression, sexual harassment, malicious rumor, or comparably harmful attack."
      }
    }
  ]));

  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
  const decision = await openrouter.alpha.decisions.create({
    decisionsRequest: {
      model: "~typesafe/jev-latest",
      state,
      questions
    }
  });
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");

  return batch.map(({ id }) => {
    const answer = decision.answers[id];
    if (!answer || answer.type !== "choice") {
      throw new Error(`JEV returned an invalid answer for ${id}.`);
    }
    const confidence = Number(answer.probabilities?.[answer.choice] ?? 0);
    return { id, label: answer.choice, confidence, probabilities: answer.probabilities };
  });
}

function sanitizeResults(batch, rawResults, method) {
  const byId = new Map(rawResults.map((result) => [String(result.id), result]));
  return batch.map((sample) => {
    const raw = byId.get(sample.id);
    const prediction = labels.includes(raw?.label) ? raw.label : "error";
    const confidence = Number.isFinite(Number(raw?.confidence))
      ? Math.max(0, Math.min(1, Number(raw.confidence)))
      : null;
    return {
      id: sample.id,
      truth: sample.hate,
      prediction,
      confidence,
      probabilities: method === "jev" ? raw?.probabilities ?? null : null,
      route: prediction === "hate" ? "block" : prediction === "offensive" ? "review" : prediction === "none" ? "allow" : "error"
    };
  });
}

function summarize(results, elapsedMs) {
  const valid = results.filter((result) => labels.includes(result.prediction));
  const correct = valid.filter((result) => result.prediction === result.truth).length;
  const perClass = Object.fromEntries(labels.map((label) => {
    const tp = valid.filter((r) => r.truth === label && r.prediction === label).length;
    const fp = valid.filter((r) => r.truth !== label && r.prediction === label).length;
    const fn = valid.filter((r) => r.truth === label && r.prediction !== label).length;
    const precision = tp + fp === 0 ? 0 : tp / (tp + fp);
    const recall = tp + fn === 0 ? 0 : tp / (tp + fn);
    const f1 = precision + recall === 0 ? 0 : (2 * precision * recall) / (precision + recall);
    return [label, { precision, recall, f1 }];
  }));
  const routeCounts = { allow: 0, review: 0, block: 0, error: 0 };
  for (const result of results) routeCounts[result.route] += 1;

  return {
    completed: results.length,
    elapsedMs,
    avgMsPerItem: results.length ? elapsedMs / results.length : 0,
    itemsPerSecond: elapsedMs ? (results.length * 1000) / elapsedMs : 0,
    accuracy: valid.length ? correct / valid.length : 0,
    macroF1: labels.reduce((sum, label) => sum + perClass[label].f1, 0) / labels.length,
    perClass,
    routeCounts
  };
}

async function runBenchmark(method, options, response, controller) {
  const { batchSize, concurrency, model, limit } = options;
  const benchmarkSamples = sampleBundle.samples.slice(0, limit);
  const batches = splitIntoBatches(benchmarkSamples, batchSize);
  const results = [];
  let cursor = 0;
  let completedBatches = 0;
  const startedAt = performance.now();

  sse(response, "start", {
    method,
    total: benchmarkSamples.length,
    batches: batches.length,
    batchSize,
    concurrency,
    model: method === "agy" ? model : "~typesafe/jev-latest"
  });

  async function worker() {
    while (cursor < batches.length && !controller.signal.aborted) {
      const batchIndex = cursor++;
      const batch = batches[batchIndex];
      const batchStartedAt = performance.now();
      const raw = method === "agy"
        ? await classifyWithAgy(batch, { model, signal: controller.signal })
        : await classifyWithJev(batch, { signal: controller.signal });
      const normalized = sanitizeResults(batch, raw, method);
      results.push(...normalized);
      completedBatches += 1;
      sse(response, "batch", {
        batchIndex,
        batchMs: performance.now() - batchStartedAt,
        completedBatches,
        completed: results.length,
        total: benchmarkSamples.length,
        results: normalized
      });
    }
  }

  await Promise.all(Array.from({ length: Math.min(concurrency, batches.length) }, worker));
  results.sort((a, b) => a.id.localeCompare(b.id));
  const elapsedMs = performance.now() - startedAt;
  sse(response, "complete", { method, summary: summarize(results, elapsedMs), results });
  response.end();
}

function serveStatic(request, response) {
  const requestUrl = new URL(request.url, `http://${request.headers.host || "localhost"}`);
  const relativePath = requestUrl.pathname === "/" ? "index.html" : requestUrl.pathname.slice(1);
  const filePath = resolve(publicDir, relativePath);
  if (!filePath.startsWith(resolve(publicDir))) {
    sendJson(response, 403, { error: "Forbidden" });
    return;
  }
  if (!existsSync(filePath)) {
    sendJson(response, 404, { error: "Not found" });
    return;
  }
  const mime = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8"
  }[extname(filePath)] || "application/octet-stream";
  response.writeHead(200, { "content-type": mime, "cache-control": "no-store" });
  createReadStream(filePath).pipe(response);
}

const server = createServer(async (request, response) => {
  const requestUrl = new URL(request.url, `http://${request.headers.host || "localhost"}`);

  if (request.method === "GET" && requestUrl.pathname === "/api/config") {
    const [agyAvailable, openRouterConfigured] = await Promise.all([
      commandExists(process.env.AGY_PATH || "agy"),
      loadOpenRouterKey().then(() => true, () => false)
    ]);
    sendJson(response, 200, {
      agyAvailable,
      openRouterConfigured,
      sample: sampleBundle.metadata,
      agyModels: [
        "gemini-3.8-flash-low",
        "gemini-3.8-flash-medium",
        "gemini-3.8-flash-high",
        "gemini-3.7-flash-low",
        "gemini-3.1-pro-low",
        "claude-sonnet-4-6",
        "gpt-oss-120b-medium"
      ]
    });
    return;
  }

  if (request.method === "GET" && requestUrl.pathname === "/api/samples") {
    sendJson(response, 200, sampleBundle);
    return;
  }

  if (request.method === "GET" && requestUrl.pathname === "/api/baseline") {
    sendJson(response, 200, JSON.parse(readFileSync(baselinePath, "utf8")));
    return;
  }

  const match = request.method === "GET" && requestUrl.pathname.match(/^\/api\/benchmark\/(agy|jev)\/stream$/);
  if (match) {
    const method = match[1];
    if (activeRuns.has(method)) {
      sendJson(response, 409, { error: `${method.toUpperCase()} benchmark is already running.` });
      return;
    }
    const batchSize = Math.max(1, Math.min(20, Number(requestUrl.searchParams.get("batchSize")) || 10));
    const concurrency = Math.max(1, Math.min(4, Number(requestUrl.searchParams.get("concurrency")) || 1));
    const limit = Math.max(1, Math.min(100, Number(requestUrl.searchParams.get("limit")) || 100));
    const model = requestUrl.searchParams.get("model") || "gemini-3.8-flash-low";
    const controller = new AbortController();
    let finished = false;

    response.writeHead(200, {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
      "x-accel-buffering": "no"
    });
    response.flushHeaders?.();
    activeRuns.add(method);
    request.on("close", () => {
      if (!finished) controller.abort();
    });

    try {
      await runBenchmark(method, { batchSize, concurrency, model, limit }, response, controller);
      finished = true;
    } catch (error) {
      if (!response.writableEnded) {
        sse(response, "failure", { message: error.name === "AbortError" ? "Benchmark cancelled." : error.message });
        response.end();
      }
    } finally {
      activeRuns.delete(method);
    }
    return;
  }

  serveStatic(request, response);
});

server.listen(port, "127.0.0.1", () => {
  console.log(`Hate routing benchmark is running at http://127.0.0.1:${port}`);
});
