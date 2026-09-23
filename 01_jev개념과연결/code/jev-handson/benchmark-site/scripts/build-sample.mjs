import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const DATASET = "nayohan/korean-hate-speech";
const SPLIT = "train";
const TOTAL_ROWS = 7896;
const PAGE_SIZE = 100;
const SEED = 20260923;
const TARGETS = { hate: 34, offensive: 33, none: 33 };
const here = dirname(fileURLToPath(import.meta.url));
const outputPath = resolve(here, "../data/sample-100.json");

function seededRandom(seed) {
  let value = seed >>> 0;
  return () => {
    value = (1664525 * value + 1013904223) >>> 0;
    return value / 0x100000000;
  };
}

async function fetchPage(offset) {
  const url = new URL("https://datasets-server.huggingface.co/rows");
  url.searchParams.set("dataset", DATASET);
  url.searchParams.set("config", "default");
  url.searchParams.set("split", SPLIT);
  url.searchParams.set("offset", String(offset));
  url.searchParams.set("length", String(Math.min(PAGE_SIZE, TOTAL_ROWS - offset)));

  const response = await fetch(url, { headers: { "user-agent": "jev-benchmark-sampler/1.0" } });
  if (!response.ok) {
    throw new Error(`Hugging Face rows API failed (${response.status}) at offset ${offset}`);
  }
  const payload = await response.json();
  return payload.rows.map(({ row_idx, row }) => ({ rowIndex: row_idx, ...row }));
}

async function mapWithConcurrency(items, limit, worker) {
  const output = new Array(items.length);
  let cursor = 0;

  async function consume() {
    while (cursor < items.length) {
      const index = cursor++;
      output[index] = await worker(items[index]);
    }
  }

  await Promise.all(Array.from({ length: limit }, consume));
  return output;
}

const offsets = Array.from(
  { length: Math.ceil(TOTAL_ROWS / PAGE_SIZE) },
  (_, index) => index * PAGE_SIZE
);
const pages = await mapWithConcurrency(offsets, 8, fetchPage);
const rows = pages.flat();

if (rows.length !== TOTAL_ROWS) {
  throw new Error(`Expected ${TOTAL_ROWS} rows, received ${rows.length}`);
}

const random = seededRandom(SEED);
for (let index = rows.length - 1; index > 0; index -= 1) {
  const swapIndex = Math.floor(random() * (index + 1));
  [rows[index], rows[swapIndex]] = [rows[swapIndex], rows[index]];
}

const counts = { hate: 0, offensive: 0, none: 0 };
const samples = [];
for (const row of rows) {
  const label = row.hate;
  if (!(label in TARGETS) || counts[label] >= TARGETS[label]) continue;

  counts[label] += 1;
  samples.push({
    id: `train-${String(row.rowIndex).padStart(4, "0")}`,
    rowIndex: row.rowIndex,
    comments: row.comments,
    contain_gender_bias: row.contain_gender_bias,
    bias: row.bias,
    hate: row.hate,
    news_title: row.news_title
  });

  if (samples.length === 100) break;
}

if (samples.length !== 100) {
  throw new Error(`Could only build ${samples.length} samples: ${JSON.stringify(counts)}`);
}

await mkdir(dirname(outputPath), { recursive: true });
await writeFile(
  outputPath,
  `${JSON.stringify({
    metadata: {
      dataset: DATASET,
      split: SPLIT,
      seed: SEED,
      strategy: "deterministic-stratified",
      sourceRowCount: TOTAL_ROWS,
      sampleCount: samples.length,
      labelCounts: counts,
      generatedAt: new Date().toISOString()
    },
    samples
  }, null, 2)}\n`,
  "utf8"
);

console.log(`Saved ${samples.length} unchanged rows to ${outputPath}`);
console.log(counts);
