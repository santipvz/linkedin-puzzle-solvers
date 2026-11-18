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
