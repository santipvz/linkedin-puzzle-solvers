const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

require('../page_puzzle.js');
const { readLinkedInPuzzle, zipBoardFromPuzzle } = globalThis.PagePuzzle;

// Zip 2026-11-20 as LinkedIn's game holds it (shortened $type names).
const ZIP_PUZZLE = {
  $case: 'trailGamePuzzle',
  trailGamePuzzle: {
    $type: 'TrailGamePuzzle',
    gridSize: 7,
    orderedSequence: [12, 11, 9, 17, 24, 36, 37, 31, 39, 8, 40],
    solution: [12, 11, 10],
    walls: [1, 3, 5, 16, 18, 23, 25, 36, 38, 40].map(cellIdx => ({ $type: 'Wall', cellIdx, direction: 'WallDirection_DOWN' })),
    wallHints: [],
    orderedSequencePositions: [{ $type: 'TrailGameSequencePosition', cellIndex: 12, isMystery: false }],
  },
};
const ZIP_FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, '../../games/zip_solver/tests/fixtures/linkedin-2026-11-20.json'), 'utf8'));

// A document whose board element sits a few React fibers below the component holding `game`.
function pageWith(puzzle, { selector = '[data-testid="interactive-grid"]', depth = 5 } = {}) {
  let fiber = { memoizedProps: { game: { $type: 'Game', puzzle } }, return: null };
  for (let i = 0; i < depth; i += 1) fiber = { memoizedProps: { className: 'cell' }, return: fiber };
  const board = {
    '__reactFiber$abc123': fiber,
    getBoundingClientRect: () => ({ left: 10, top: 20, width: 350, height: 350 }),
  };
  return {
    document: {
      querySelectorAll: wanted => (wanted === selector ? [board] : []),
      querySelector: wanted => (wanted === selector ? board : null),
    },
    window: { devicePixelRatio: 2 },
  };
}

function runInPage(page) {
  const context = vm.createContext({ ...page, JSON });
  return JSON.parse(JSON.stringify(vm.runInContext(`(${readLinkedInPuzzle.toString()})()`, context)));
}

test('reads the puzzle from React props without the official solution', () => {
  const page = runInPage(pageWith(ZIP_PUZZLE));
  assert.equal(page.kind, 'trailGamePuzzle');
  assert.equal(page.puzzle.gridSize, 7);
  assert.equal('solution' in page.puzzle, false);
  assert.deepEqual(page.selection, { x: 10, y: 20, width: 350, height: 350, devicePixelRatio: 2 });
});

test('turns bigint fields into numbers and finds boards through any game root', () => {
  const puzzle = { $case: 'numoGamePuzzle', numoGamePuzzle: { gridRows: 3n, cells: [] } };
  const page = runInPage(pageWith(puzzle, { selector: '[data-numo-design]', depth: 12 }));
  assert.equal(page.puzzle.gridRows, 3);
});

test('returns null when no game puzzle is reachable', () => {
  assert.equal(runInPage(pageWith(null)), null);
  assert.equal(runInPage(pageWith(ZIP_PUZZLE, { depth: 45 })), null);
});

test('builds the Zip page board the API expects', () => {
  const page = runInPage(pageWith(ZIP_PUZZLE));
  assert.deepEqual(zipBoardFromPuzzle(page), ZIP_FIXTURE);
  assert.equal(zipBoardFromPuzzle({ kind: 'lotkaGamePuzzle', puzzle: {} }), null);
  const badWall = { kind: 'trailGamePuzzle', puzzle: { gridSize: 3, orderedSequence: [0, 8], walls: [{ cellIdx: 1, direction: 'WallDirection_SIDEWAYS' }] } };
  assert.equal(zipBoardFromPuzzle(badWall), null);
});

test('Zip solves send the page board and use its exact position', async () => {
  const context = vm.createContext({ chrome: { runtime: { onMessage: { addListener() {} } } } });
  for (const file of ['puzzle_registry.js', 'api_config.js', 'page_puzzle.js', 'background.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  }
  const userSelection = { x: 0, y: 0, width: 400, height: 400, devicePixelRatio: 1 };
  const pageSelection = { x: 25, y: 30, width: 350, height: 350, devicePixelRatio: 1 };
  context.tabsGet = async () => ({ windowId: 1 });
  context.captureVisibleTab = async () => '';
  context.cropCapturedImage = async () => ({});
  context.readPagePuzzle = async () => ({ kind: 'trailGamePuzzle', puzzle: ZIP_PUZZLE.trailGamePuzzle, selection: pageSelection });
  let options;
  context.callSolverApi = async (_base, _puzzle, _image, value) => { options = value; return { solved: true, details: {} }; };
  const solved = await context.solveBoardCore({ tabId: 1, puzzleType: 'zip', apiBaseUrl: 'http://localhost', selection: userSelection });
  assert.deepEqual(JSON.parse(JSON.stringify(options.parsedBoard)), ZIP_FIXTURE);
  assert.deepEqual(JSON.parse(JSON.stringify(solved.selection)), pageSelection);
});

test('Zip falls back to the image when the page puzzle is unavailable', async () => {
  const context = vm.createContext({ chrome: { runtime: { onMessage: { addListener() {} } } } });
  for (const file of ['puzzle_registry.js', 'api_config.js', 'page_puzzle.js', 'background.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  }
  context.tabsGet = async () => ({ windowId: 1 });
  context.captureVisibleTab = async () => '';
  context.cropCapturedImage = async () => ({});
  context.readPagePuzzle = async () => null;
  let options;
  context.callSolverApi = async (_base, _puzzle, _image, value) => { options = value; return { solved: true, details: {} }; };
  await context.solveBoardCore({ tabId: 1, puzzleType: 'zip', apiBaseUrl: 'http://localhost',
    selection: { x: 0, y: 0, width: 400, height: 400, devicePixelRatio: 1 } });
  assert.equal(options.parsedBoard, null);
});

test('the API upload carries the Zip page board', async () => {
  // Checks the real request, not a mocked callSolverApi.
  let request;
  const context = vm.createContext({ Blob, FormData, chrome: { runtime: { onMessage: { addListener() {} } } },
    fetch: async (url, options) => { request = { url, ...options }; return { ok: true, text: async () => '{"solved":true}', headers: { get: () => null } }; } });
  for (const file of ['puzzle_registry.js', 'api_config.js', 'page_puzzle.js', 'background.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  }
  await context.callSolverApi('http://127.0.0.1:18000', 'zip', new Blob(['image'], { type: 'image/png' }), { parsedBoard: ZIP_FIXTURE });
  assert.equal(request.url, 'http://127.0.0.1:18000/solve/zip');
  assert.deepEqual(JSON.parse(request.body.get('parsed_board')), ZIP_FIXTURE);
  await context.callSolverApi('http://127.0.0.1:18000', 'zip', new Blob(['image'], { type: 'image/png' }), {});
  assert.equal(request.body.get('parsed_board'), null);
});
