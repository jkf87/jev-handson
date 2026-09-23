#!/usr/bin/env node
// 게임: 틱택토 판을 글로 주고 Jev가 둘 칸을 고른다. 둘 수 있는 칸인지, 판이 끝났는지는 코드가 본다.
//   node usecases/game_move.mjs            # 판 3개 퀴즈: 이기기 · 막기 · 첫 수 (Jev 호출 3번)
//   node usecases/game_move.mjs --play     # 규칙 봇(O)과 한 판. Jev가 X로 먼저 둔다 (호출 3~4번)
//   node usecases/game_move.mjs --replay usecases/results/<기록>.json
import { fileURLToPath } from 'node:url';
import { askJev, runScenarios, readChoice, saveRun } from './jev.mjs';

export const LINES = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]];
const CELL_NAMES = ['top-left corner', 'top edge', 'top-right corner', 'left edge', 'center', 'right edge', 'bottom-left corner', 'bottom edge', 'bottom-right corner'];

// 판은 9칸 배열: 'X' · 'O' · '.'(빈칸). 줄 문자열 여러 개나 9글자 하나로 받는다.
export const parse = (rows) => [].concat(rows).join('').replace(/\s/g, '').split('');
export const free = (b) => b.map((v, i) => (v === '.' ? i : -1)).filter((i) => i >= 0);
export function winner(b) {
  for (const [a, c, d] of LINES) if (b[a] !== '.' && b[a] === b[c] && b[a] === b[d]) return b[a];
  return free(b).length ? null : 'draw';
}
export function winningCell(b, who) {            // 한 수로 이기는 칸, 없으면 -1
  for (const i of free(b)) { const t = [...b]; t[i] = who; if (winner(t) === who) return i; }
  return -1;
}
// 규칙 봇: 이길 수 있으면 이기고, 막아야 하면 막고, 아니면 가운데 → 모서리 → 변
export function ruleMove(b, me = 'O', other = 'X') {
  for (const i of [winningCell(b, me), winningCell(b, other)]) if (i >= 0) return i;
  return [4, 0, 2, 6, 8, 1, 3, 5, 7].find((i) => b[i] === '.') ?? -1;
}

export const SCENARIOS = [
  { id: 'win_first', rows: ['XX.', 'OO.', '...'], expect: 'play:c3' },    // 막기보다 이기기가 먼저
  { id: 'block', rows: ['OO.', 'X..', '..X'], expect: 'play:c3' },        // O가 다음 수에 이긴다 → 막기
  { id: 'opening', rows: ['...', '...', '...'], expect: ['play:c5', 'play:c1', 'play:c3', 'play:c7', 'play:c9'] },
];

const show3 = (b) => [0, 3, 6].map((r) => b.slice(r, r + 3).join('')).join('/');

export function buildRequest(sc) {
  const b = parse(sc.rows);
  return {
    state: {
      game: 'tic-tac-toe on a 3x3 board. Cells are numbered 1-9 from the top-left, row by row. Three in a row (row, column, or diagonal) wins.',
      board: { row1: b.slice(0, 3).join(' '), row2: b.slice(3, 6).join(' '), row3: b.slice(6, 9).join(' ') },
      you: 'X', opponent: 'O', empty: '.',
    },
    questions: {
      move: {
        type: 'choice',
        instructions: 'You are X and it is your turn. Which empty cell should X take? Win now if you can; otherwise stop O from winning on its next move; otherwise take the strongest cell.',
        criteria: Object.fromEntries(free(b).map((i) => [`c${i + 1}`, `cell ${i + 1}: ${CELL_NAMES[i]}`])),
      },
    },
  };
}

// 둘 수 없는 칸이거나 확률이 낮으면 코드(규칙)가 대신 둔다(강의용 시작값).
export const POLICY = { minP: 0.4 };
export function decide(answers, sc, policy = POLICY) {
  const m = readChoice(answers?.move, free(parse(sc.rows)).map((i) => `c${i + 1}`));
  if (!m) return { key: 'fallback', reason: 'invalid_answer' };
  if (m.p < policy.minP) return { key: 'fallback', reason: 'uncertain', cell: m.choice, p: m.p };
  return { key: `play:${m.choice}`, reason: 'ok', cell: m.choice, p: m.p };
}

async function play() {
  const b = parse('.........');
  const log = [];
  for (let turn = 'X'; !winner(b); turn = turn === 'X' ? 'O' : 'X') {
    if (turn === 'O') {
      const i = ruleMove(b);
      b[i] = 'O';
      log.push({ who: 'O', cell: i + 1, how: '규칙 봇', board: b.join('') });
      console.log(`O → ${i + 1}  규칙 봇                    ${show3(b)}`);
      continue;
    }
    let i, how, response = null;
    if (free(b).length === 1) { i = free(b)[0]; how = '남은 한 칸'; }           // 선택지가 하나면 묻지 않는다(Choice는 2개 이상)
    else {
      response = await askJev(buildRequest({ rows: b.join('') }));
      const d = decide(response.answers, { rows: b.join('') });
      if (d.key.startsWith('play:')) { i = Number(d.cell.slice(1)) - 1; how = `Jev ${d.p}`; }
      else { i = ruleMove(b, 'X', 'O'); how = `코드가 대신 (Jev ${d.cell ?? '?'} ${d.p ?? d.reason})`; }
    }
    const missed = [winningCell(b, 'X'), winningCell(b, 'O')].find((c) => c >= 0);   // 이기거나 막아야 했던 칸
    b[i] = 'X';
    log.push({ who: 'X', cell: i + 1, how, mustPlay: missed === undefined ? null : missed + 1, board: b.join(''), response });
    console.log(`X → ${i + 1}  ${how.padEnd(22)}${response ? ` ${String(response.latencyMs).padStart(4)}ms` : '       '}  ${show3(b)}${missed !== undefined && missed !== i ? `  ← ${missed + 1}에 둬야 했음` : ''}`);
  }
  const w = winner(b);
  const jev = log.filter((x) => x.how.startsWith('Jev')).length;
  console.log(`\n결과: ${w === 'draw' ? '무승부' : w === 'X' ? 'Jev(X) 승' : '규칙 봇(O) 승'} · Jev가 둔 수 ${jev}번 · 코드가 대신 둔 수 ${log.filter((x) => x.how.startsWith('코드')).length}번`);
  console.log(`기록: ${saveRun('game_play', log, { result: w })}`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--play')) await play();
  else await runScenarios('game_move', SCENARIOS, {
    build: buildRequest,
    decide,
    show: (sc, r, d, pass) => console.log(`${pass ? '✓' : '✗'} ${sc.id.padEnd(9)} ${show3(parse(sc.rows))}  Jev: ${r.answers.move.choice} ${d.p ?? '?'} → 코드: ${d.key.startsWith('play:') ? `${d.cell.slice(1)}번 칸에 둠` : `규칙이 대신(${d.reason})`} · ${r.latencyMs ?? '-'}ms`),
  });
}
