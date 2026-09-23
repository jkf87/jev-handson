// 큰 로스터에서도 도는지 시험: 데모 스킬에 가짜 스킬을 섞어 N개로 늘린 뒤, 데모 요청 몇 건을 라우팅한다.
//   node stress.mjs --n 600 --k 6      # 600개 → Choice 3개 + 결선. 정답이 이기는지, 토큰·지연은 얼마인지
// 가짜 스킬은 데모 요청과 겹치지 않는 분야(클라우드·모바일·IoT 등)로 만든다. 임시 폴더에 쓰고 끝나면 지운다.
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {loadRoster} from './skills.mjs';
import {suggest, openJev} from './suggest.mjs';
import {resolveGold} from './evaluate.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TOPICS = ['aws-s3', 'gcp-gcs', 'azure-blob', 'k8s', 'helm', 'terraform', 'ansible', 'nginx', 'redis', 'kafka', 'rabbitmq', 'elastic',
  'grafana', 'prometheus', 'sentry', 'datadog', 'stripe', 'shopify', 'wordpress', 'android', 'ios', 'flutter', 'unity', 'arduino',
  'raspberry', 'mqtt', 'ldap', 'okta', 'vault', 'jenkins', 'circleci', 'airflow', 'dbt', 'snowflake', 'bigquery', 'tableau',
  'figma', 'blender', 'ffmpeg-audio', 'podman', 'consul', 'etcd'];
const ACTIONS = [['monitor', '상태를 모니터링하고 경보를 설정'], ['backup', '백업을 만들고 복원을 시험'], ['audit', '권한과 설정을 감사'],
  ['scale', '용량을 늘리고 줄이는 규칙을 관리'], ['rotate-keys', '키와 인증서를 교체'], ['export', '설정을 내보내 버전 관리'],
  ['lint', '설정 파일 문법을 검사'], ['benchmark', '성능을 측정해 기준선과 비교'], ['cost', '비용을 집계해 줄일 곳을 찾기'],
  ['upgrade', '버전을 올리고 호환성을 점검'], ['logs', '로그를 모아 오류 패턴을 찾기'], ['provision', '새 환경을 만들어 초기 설정'],
  ['teardown', '안 쓰는 자원을 찾아 정리'], ['docs', '운영 문서와 런북을 갱신']];

async function makeStressDir(n) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), `jev-skill-router-stress-${n}-`));
  const demo = path.join(HERE, 'demo', 'skills');
  let count = 0;
  for (const name of await fs.readdir(demo)) {
    try { await fs.cp(path.join(demo, name), path.join(dir, name), {recursive: true}); count++; } catch { /* 폴더 아님 */ }
  }
  const REGIONS = ['', 'kr', 'us', 'eu', 'jp'];   // 조합이 모자라면 지역을 붙여 늘린다(최대 약 2,900개)
  outer: for (const region of REGIONS) for (const [act, ko] of ACTIONS) for (const t of TOPICS) {
    if (count >= n) break outer;
    const name = [t, act, region].filter(Boolean).join('-');
    const where = region ? ` (${region.toUpperCase()} 리전)` : '';
    await fs.mkdir(path.join(dir, name));
    await fs.writeFile(path.join(dir, name, 'SKILL.md'), `---\nname: ${name}\ndescription: ${t}${where}의 ${ko}합니다. ${t} 전용 운영 스킬\n---\n# ${name}\n\n${t}${where} 환경에서 ${ko}하는 절차.\n`);
    count++;
  }
  return dir;
}

if (fileURLToPath(import.meta.url) === path.resolve(process.argv[1] || '')) {
  const args = process.argv.slice(2);
  const num = (f, d) => { const i = args.indexOf(f); return i >= 0 ? Number(args[i + 1]) : d; };
  const n = num('--n', 600), k = num('--k', 6);
  const dir = await makeStressDir(n);
  try {
    const roster = await loadRoster({agents: [], dirs: [dir], refresh: true});
    const requests = resolveGold(JSON.parse(await fs.readFile(path.join(HERE, 'demo', 'requests.json'), 'utf8')), roster)
      .filter((r) => r.gold.length).slice(0, k);
    const jev = await openJev(args);
    let ok = 0, tokens = 0;
    console.log(`로스터 ${roster.count}개 (${dir})`);
    for (const r of requests) {
      const s = await suggest(r.text, roster, jev, {alwaysRerank: true});
      const hit = r.gold.includes(s.suggestion[0]) || r.gold.includes(s.rerank?.winner);
      ok += hit ? 1 : 0;
      const t = s.calls.reduce((a, c) => a + (c.usage?.input_tokens ?? 0), 0);
      tokens += t;
      const secs = s.calls.map((c) => `${c.stage} ${Number(c.seconds).toFixed(2)}s`).join(' · ');
      console.log(`${hit ? 'OK  ' : 'MISS'} ${String(s.rerank?.winner ?? '-').padEnd(20)} 정답 ${r.gold[0].padEnd(20)} 입력 ${t}토큰 · ${secs}`);
    }
    console.log(`\n${ok}/${requests.length} 정답이 결선·재검증까지 살아남음 · 요청당 입력 평균 ${Math.round(tokens / requests.length)}토큰(≈ $${(tokens / requests.length * 0.042 / 1e6).toFixed(5)})`);
  } finally {
    await fs.rm(dir, {recursive: true, force: true});
  }
}
