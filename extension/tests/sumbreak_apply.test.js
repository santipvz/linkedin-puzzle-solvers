const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

// A small model of LinkedIn's Sumbreak board: tap a tile to select it, then tap
// an equal orthogonal neighbour to merge into it. The source cell empties.
function sumbreakGame(initial, { acceptMerges = true, svgLabels = true } = {}) {
  const rows = initial.length, columns = initial[0].length;
  const values = initial.flat();
  let selected = null, clicks = 0;
  const buttons = values.map((_, index) => ({
    index,
    getAttribute: name => {
      if (name === 'aria-pressed') return String(selected === index);
      if (name === 'aria-label') return `Número ${values[index]}, fila ${Math.floor(index / columns) + 1}, columna ${index % columns + 1}`;
      return null;
    },
    click() {
      clicks += 1;
      if (values[index] === null) return;
      if (selected === null) { selected = index; return; }
      if (selected === index) { selected = null; return; }
      const a = selected, b = index;
      const adjacent = Math.abs(Math.floor(a / columns) - Math.floor(b / columns)) + Math.abs(a % columns - b % columns) === 1;
      selected = null;
      if (acceptMerges && adjacent && values[a] === values[b]) {
        values[b] *= 2;
        values[a] = null;
      }
    },
  }));
  const root = {
    getAttribute: name => (name === 'data-numo-rows' ? String(rows) : name === 'data-numo-columns' ? String(columns) : null),
    getBoundingClientRect: () => ({ left: 20, top: 40, width: columns * 100, height: rows * 100,
      right: 20 + columns * 100, bottom: 40 + rows * 100 }),
    querySelector(selector) {
      let match = selector.match(/^\[data-numo-index="(\d+)"\]( button\[data-numo-kind="number"\])?$/);
      if (match) {
        const index = Number(match[1]);
        if (index >= values.length) return null;
        const tile = values[index] === null ? null : buttons[index];
        return match[2] ? tile : { querySelector: () => tile };
      }
      match = selector.match(/^\[data-numo-svg-cell="(\d+)"\] \[data-numo-label\]$/);
      if (match) {
        const value = values[Number(match[1])];
        return svgLabels && value !== null ? { textContent: String(value) } : null;
      }
      return null;
    },
    querySelectorAll: selector => (selector === 'button[aria-pressed="true"]' && selected !== null ? [buttons[selected]] : []),
  };
  const context = vm.createContext({
    document: { querySelector: () => root },
    window: { self: {}, top: {}, innerWidth: 800, innerHeight: 800, devicePixelRatio: 1, location: { pathname: '/games/sumbreak/' } },
    chrome: { runtime: { onMessage: { addListener() {} } } },
  });
  for (const file of ['puzzle_registry.js', 'content.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  }
  context.sleep = async () => {};
  return {
    context,
    values,
    get clicks() { return clicks; },
    select(index) { selected = index; },
  };
}

const TODAY = [[1, 1, 64], [4, 2, 32], [4, 4, 16]];
const TODAY_MOVES = [
  [0, 0, 0, 1, 2], [0, 1, 1, 1, 4], [2, 0, 2, 1, 8], [1, 0, 1, 1, 8],
  [1, 1, 2, 1, 16], [2, 1, 2, 2, 32], [2, 2, 1, 2, 64], [1, 2, 0, 2, 128],
].map(([row, col, to_row, to_col, value]) => ({ row, col, to_row, to_col, value }));

function todayResult(board = TODAY) {
  return { solved: true, board_size: 3, moves: TODAY_MOVES, details: { rows: 3, columns: 3, board } };
}

test('Sumbreak reads tile values and empty cells from the page board', () => {
  const game = sumbreakGame([[2, null], [1, 1]]);
  const read = JSON.parse(JSON.stringify(game.context.readSumbreakPageBoard()));
  assert.deepEqual(read.board, [[2, null], [1, 1]]);
  assert.equal(read.selection.width, 200);
});

test('Sumbreak falls back to the localized aria-label when the SVG label is missing', () => {
  const game = sumbreakGame([[4, 4], [8, null]], { svgLabels: false });
  assert.deepEqual(JSON.parse(JSON.stringify(game.context.readSumbreakPageBoard().board)), [[4, 4], [8, null]]);
});

test('Sumbreak accepts rectangular boards for capture', () => {
  const game = sumbreakGame([[1, 1, 2, 4]].concat([[8, 8, 8, 8]]));
  assert.ok(game.context.nativeBoardSelection('sumbreak'));
});

test('Sumbreak applies every merge by tapping source then target and verifies each one', async () => {
  const game = sumbreakGame(TODAY);
  const response = await game.context.applySumbreakSolution(todayResult(), null, {});
  assert.equal(response.ok, true);
  assert.equal(response.appliedCount, 8);
  assert.equal(game.clicks, 16);
  assert.deepEqual(game.values, [null, null, 128, null, null, null, null, null, null]);
});

test('Sumbreak clears a stale manual selection before the first tap', async () => {
  const game = sumbreakGame(TODAY);
  game.select(8);
  assert.equal((await game.context.applySumbreakSolution(todayResult(), null, {})).ok, true);
  assert.equal(game.values[2], 128);
});

test('Sumbreak stops when the game does not show a merge', async () => {
  const game = sumbreakGame(TODAY, { acceptMerges: false });
  const response = await game.context.applySumbreakSolution(todayResult(), null, {});
  assert.equal(response.ok, false);
  assert.equal(response.appliedCount, 0);
});

test('Sumbreak refuses to apply moves to a board that changed since solving', async () => {
  const game = sumbreakGame([[1, 1, 64], [4, 2, 32], [4, 4, 8]]);
  const response = await game.context.applySumbreakSolution(todayResult(), null, {});
  assert.equal(response.ok, false);
  assert.equal(game.clicks, 0);
});

test('Sumbreak rejects malformed or non-adjacent moves before touching the board', async () => {
  const game = sumbreakGame(TODAY);
  const result = todayResult();
  result.moves = [{ row: 0, col: 0, to_row: 2, to_col: 2, value: 2 }];
  assert.equal((await game.context.applySumbreakSolution(result, null, {})).ok, false);
  assert.equal(game.clicks, 0);
});

test('the API upload includes Sumbreak page data', async () => {
  let request;
  const context = vm.createContext({ Blob, FormData, chrome: { runtime: { onMessage: { addListener() {} } } },
    fetch: async (url, options) => { request = { url, ...options }; return { ok: true, text: async () => '{"solved":true}' }; } });
  for (const file of ['puzzle_registry.js', 'api_config.js', 'background.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  }
  const board = { board: TODAY };
  await context.callSolverApi('http://127.0.0.1:18000', 'sumbreak', new Blob(['image'], { type: 'image/png' }), { parsedBoard: board });
  assert.equal(request.url, 'http://127.0.0.1:18000/solve/sumbreak');
  assert.deepEqual(JSON.parse(request.body.get('parsed_board')), board);
});

test('Sumbreak asks the page for its board and sends only the board values', async () => {
  const context = vm.createContext({ chrome: { runtime: { onMessage: { addListener() {} } } } });
  for (const file of ['puzzle_registry.js', 'api_config.js', 'background.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  }
  const selection = { x: 20, y: 40, width: 300, height: 300, devicePixelRatio: 1 };
  context.tabsGet = async () => ({ windowId: 1 });
  context.captureVisibleTab = async () => '';
  context.cropCapturedImage = async () => ({});
  context.getGameFrameContext = async () => ({ gameFrameId: 0 });
  let message;
  context.safeSendTabMessage = async (_tab, value) => { message = value; return { ok: true, parsedBoard: { board: TODAY, selection } }; };
  let options;
  context.callSolverApi = async (_base, _puzzle, _image, value) => { options = value; return {}; };
  await context.solveBoardCore({ tabId: 1, puzzleType: 'sumbreak', apiBaseUrl: 'http://localhost', selection });
  assert.equal(message.type, 'readSumbreakPageBoard');
  assert.deepEqual(JSON.parse(JSON.stringify(options.parsedBoard)), { board: TODAY });
});
