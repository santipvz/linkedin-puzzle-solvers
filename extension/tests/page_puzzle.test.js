const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

require('../page_puzzle.js');
const { readLinkedInPuzzle, zipBoardFromPuzzle, tangoBoardFromPuzzle, queensBoardFromPuzzle, patchesBoardFromPuzzle } = globalThis.PagePuzzle;

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

// Tango 2026-11-20: preset cells and = / x clues. cell-zero is a sun, cell-one a moon.
const TANGO_PUZZLE = {
  $case: 'lotkaGamePuzzle',
  lotkaGamePuzzle: {
    gridSize: 6,
    presetCellIdxes: [1, 4, 6, 11, 24, 29, 31, 34],
    edges: [[2, 3, true], [14, 15, true], [20, 21, false], [32, 33, true], [12, 18, true], [14, 20, true], [15, 21, false], [17, 23, false]]
      .map(([startIdx, endIdx, isEqual]) => ({ $type: 'LotkaEdge', startIdx, endIdx, isEqual })),
    solution: ['LotkaCellValue_ZERO'],
  },
};
const TANGO_MARKS = { 1: 'cell-one', 4: 'cell-one', 6: 'cell-zero', 11: 'cell-zero', 24: 'cell-zero', 29: 'cell-one', 31: 'cell-zero', 34: 'cell-zero' };
const TANGO_FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, '../../games/tango_solver/tests/fixtures/linkedin-2026-11-20.json'), 'utf8'));

// A document whose board element sits a few React fibers below the component holding `game`.
function pageWith(puzzle, { selector = '[data-testid="interactive-grid"]', depth = 5, marks = {} } = {}) {
  let fiber = { memoizedProps: { game: { $type: 'Game', puzzle } }, return: null };
  for (let i = 0; i < depth; i += 1) fiber = { memoizedProps: { className: 'cell' }, return: fiber };
  const board = {
    '__reactFiber$abc123': fiber,
    getBoundingClientRect: () => ({ left: 10, top: 20, width: 350, height: 350 }),
  };
  const cells = Object.entries(marks).map(([index, mark]) => ({
    getAttribute: name => (name === 'data-cell-idx' ? index : null),
    querySelectorAll: () => [{ getAttribute: () => mark }],
  }));
  return {
    document: {
      querySelectorAll: wanted => (wanted === selector ? [board] : wanted === '[data-cell-idx]' ? cells : []),
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

test('builds the Tango page board from presets as the cells show them', () => {
  const page = runInPage(pageWith(TANGO_PUZZLE, { marks: TANGO_MARKS }));
  assert.deepEqual(page.cellMarks[6], ['cell-zero']);
  assert.deepEqual(tangoBoardFromPuzzle(page), TANGO_FIXTURE);
  // A preset cell that shows no piece means the page is not what we expect.
  const missing = runInPage(pageWith(TANGO_PUZZLE, { marks: { ...TANGO_MARKS, 6: 'cell-empty' } }));
  assert.equal(tangoBoardFromPuzzle(missing), null);
});

test('Tango with a page board makes one API call instead of searching crops', async () => {
  const context = vm.createContext({ chrome: { runtime: { onMessage: { addListener() {} } } } });
  for (const file of ['puzzle_registry.js', 'api_config.js', 'page_puzzle.js', 'background.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  }
  const pageSelection = { x: 25, y: 30, width: 350, height: 350, devicePixelRatio: 1 };
  context.tabsGet = async () => ({ windowId: 1 });
  context.captureVisibleTab = async () => '';
  context.cropCapturedImage = async () => ({});
  context.readPagePuzzle = async () => ({ kind: 'lotkaGamePuzzle', puzzle: TANGO_PUZZLE.lotkaGamePuzzle,
    cellMarks: Object.fromEntries(Object.entries(TANGO_MARKS).map(([cell, mark]) => [cell, [mark]])), selection: pageSelection });
  const calls = [];
  context.callSolverApi = async (_base, puzzle, _image, value) => { calls.push({ puzzle, value }); return { solved: true, details: {} }; };
  context.solveTangoWithCandidateSearch = async () => { throw new Error('crop search should not run'); };
  const solved = await context.solveBoardCore({ tabId: 1, puzzleType: 'tango', apiBaseUrl: 'http://localhost',
    selection: { x: 0, y: 0, width: 400, height: 400, devicePixelRatio: 1 } });
  assert.equal(calls.length, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0].value.parsedBoard)), TANGO_FIXTURE);
  assert.deepEqual(JSON.parse(JSON.stringify(solved.selection)), pageSelection);
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

test('builds the Queens page board from the colour grid', () => {
  const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, '../../games/queen_solver/tests/fixtures/linkedin-2026-11-20.json'), 'utf8'));
  const puzzle = { $case: 'queensGamePuzzle', queensGamePuzzle: { gridSize: 9, solution: [{ row: 0, col: 7 }],
    colorGrid: fixture.regions.map(colors => ({ $type: 'QueensGameColorRow', colors })) } };
  const page = runInPage(pageWith(puzzle));
  assert.equal('solution' in page.puzzle, false);
  assert.deepEqual(queensBoardFromPuzzle(page), fixture);
  assert.equal(queensBoardFromPuzzle({ kind: 'queensGamePuzzle', puzzle: { gridSize: 2, colorGrid: [{ colors: [0, 'x'] }] } }), null);
});

test('builds the Patches page board from clue cells', () => {
  const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, '../../games/patches_solver/tests/fixtures/linkedin-2026-11-20.json'), 'utf8'));
  const linkedInShape = { any: 'UNKNOWN', square: 'SQUARE', wide: 'HORIZONTAL_RECT', tall: 'VERTICAL_RECT' };
  const clueCells = fixture.clues.map(([cellIdx, shape, area]) => ({ $type: 'PatchesClueCell', cellIdx,
    shapeConstraint: `PatchesShapeConstraint_${linkedInShape[shape]}`, numberConstraint: area || 0 }));
  const puzzle = { $case: 'patchesGamePuzzle', patchesGamePuzzle: { gridRows: 7, gridCols: 7, clueCells, solution: [{ cellIdxes: [0] }] } };
  const page = runInPage(pageWith(puzzle, { selector: '[data-testid="interactive-grid"]' }));
  assert.equal('solution' in page.puzzle, false);
  assert.deepEqual(patchesBoardFromPuzzle(page), fixture);
  assert.equal(patchesBoardFromPuzzle({ kind: 'patchesGamePuzzle', puzzle: { gridRows: 6, gridCols: 7, clueCells } }), null);
  const unknownShape = [{ cellIdx: 0, shapeConstraint: 'PatchesShapeConstraint_TRIANGLE', numberConstraint: 0 }];
  assert.equal(patchesBoardFromPuzzle({ kind: 'patchesGamePuzzle', puzzle: { gridRows: 7, gridCols: 7, clueCells: unknownShape } }), null);
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
