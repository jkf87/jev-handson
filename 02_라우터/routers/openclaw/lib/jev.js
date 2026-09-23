// Jev(/v1/systemone) 최소 클라이언트. 키는 환경변수 → keyFile(.env) 순서로 찾고 출력하지 않는다.
import { readFileSync } from "node:fs";
import os from "node:os";

export function readKey({ keyFile, env = process.env } = {}) {
  if (env.TYPESAFE_API_KEY) return env.TYPESAFE_API_KEY.trim();
  if (!keyFile) return "";
  try {
    const text = readFileSync(keyFile.replace(/^~(?=\/)/, os.homedir()), "utf8");
    const m = text.match(/^\s*(?:export\s+)?TYPESAFE_API_KEY\s*=\s*(.*?)\s*$/m);
    return m ? m[1].replace(/^['"]|['"]$/g, "") : "";
  } catch {
    return "";
  }
}

export async function callJev(body, { apiKey, baseUrl = "https://api.typesafe.ai", timeoutMs = 8000, fetchImpl = fetch } = {}) {
  const url = `${baseUrl.replace(/\/$/, "")}/v1/systemone`;
  if (!apiKey && url.includes("api.typesafe.ai")) throw new Error("no_api_key");
  const started = Date.now();
  const res = await fetchImpl(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "User-Agent": "openclaw-jev-router/1.0", ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}) },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!res.ok) throw new Error(`jev_http_${res.status}`);
  return { ...(await res.json()), latencyMs: Date.now() - started };
}
