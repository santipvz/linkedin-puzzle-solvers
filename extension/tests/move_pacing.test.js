const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function contentContext() {
  const context = vm.createContext({
    setTimeout, clearTimeout,
    document: { querySelector: () => null },
    window: { self: {}, top: {}, innerWidth: 800, innerHeight: 800, location: { pathname: '/games/queens/' } },
    chrome: { runtime: { onMessage: { addListener() {} } } },
  });
  for (const file of ['puzzle_registry.js', 'content.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  }
  return context;
}

test('every game shares one move interval, starting moves at a fixed pace', async () => {
  const context = contentContext();
  const nextMove = context.createMovePacer(40);
  const starts = [];
  for (let move = 0; move < 4; move += 1) {
    await nextMove();
    starts.push(Date.now());
  }
  const gaps = starts.slice(1).map((start, index) => start - starts[index]);
  assert.ok(gaps.every(gap => gap >= 38 && gap < 80), `gaps ${gaps}`);
});

test('time spent inside a move counts toward the interval instead of adding to it', async () => {
  const context = contentContext();
  const nextMove = context.createMovePacer(60);
  await nextMove();
  const started = Date.now();
  await new Promise(resolve => setTimeout(resolve, 45));
  await nextMove();
  const gap = Date.now() - started;
  assert.ok(gap >= 58 && gap < 90, `gap ${gap}`);
});

test('a move slower than the interval is followed immediately by the next one', async () => {
  const context = contentContext();
  const nextMove = context.createMovePacer(10);
  await nextMove();
  await new Promise(resolve => setTimeout(resolve, 30));
  const before = Date.now();
  await nextMove();
  assert.ok(Date.now() - before < 5);
});

test('the default move interval is the same for every game', () => {
  const context = contentContext();
  assert.equal(context.normalizeApplySettings({}).moveIntervalMs, 100);
  assert.equal(context.normalizeApplySettings({ moveIntervalMs: 250 }).moveIntervalMs, 250);
  assert.equal(context.normalizeApplySettings({ interMoveDelayMs: 5 }).moveIntervalMs, 100);
});

test('waitFor returns as soon as the game confirms and null on timeout', async () => {
  const context = contentContext();
  let calls = 0;
  const started = Date.now();
  assert.equal(await context.waitFor(() => (++calls >= 3 ? 'ok' : null), 500, 5), 'ok');
  assert.ok(Date.now() - started < 100);
  assert.equal(await context.waitFor(() => null, 20, 5), null);
});

test('a Zip path is one stroke drawn at the Wend drag speed, not one move per step', async () => {
  const context = contentContext();
  const sleeps = [];
  const keys = [];
  context.sleep = async (ms) => { sleeps.push(ms); };
  context.leftClickViewportPoint = () => true;
  context.dispatchArrowKey = (direction) => { keys.push(direction); return true; };
  const result = { solved: true, board_size: 3, path: [{ row: 0, col: 0 }, { row: 0, col: 1 }, { row: 1, col: 1 }, { row: 1, col: 0 }],
    directions: ['right', 'down', 'left'] };
  const applied = await context.applyZipSolution(result, { x: 0, y: 0, width: 90, height: 90 }, { moveIntervalMs: 500 });
  assert.equal(applied.ok, true);
  assert.deepEqual(keys, ['right', 'down', 'left']);
  const stepWaits = sleeps.slice(1);
  // PATH_CELL_MS: one cell every 32 ms, the same speed as a Wend word drag.
  assert.deepEqual(stepWaits, [32, 32]);
});

test('the quick solve status shows where the time went', () => {
  const context = contentContext();
  assert.equal(context.formatQuickSolveTimings({ detectMs: 120, solveMs: 640, serverMs: 250, applyMs: 2300 }),
    '\nboard 0.1 s · solve 0.6 s (server 0.3 s) · apply 2.3 s');
  assert.equal(context.formatQuickSolveTimings({ detectMs: 50, solveMs: 900, serverMs: null, applyMs: 10 }),
    '\nboard 0.1 s · solve 0.9 s · apply 0.0 s');
  assert.equal(context.formatQuickSolveTimings(undefined), '');
});

test('the API client reads the server solve time from Server-Timing', async () => {
  const context = vm.createContext({ Blob, FormData, chrome: { runtime: { onMessage: { addListener() {} } } },
    fetch: async () => ({ ok: true, headers: { get: (name) => (name === 'Server-Timing' ? 'solve;dur=212.4' : null) },
      text: async () => '{"solved":true,"details":{}}' }) });
  for (const file of ['puzzle_registry.js', 'api_config.js', 'background.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  }
  const payload = await context.callSolverApi('http://127.0.0.1:8000', 'queens', new Blob(['x'], { type: 'image/png' }), {});
  assert.equal(payload.details.server_solve_ms, 212.4);
});
