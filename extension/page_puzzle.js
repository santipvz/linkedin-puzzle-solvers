// Reads the puzzle LinkedIn's game already holds in memory, so no screenshot
// or OCR is needed. The React games keep it as `game.puzzle` in the props of
// their board components. Those props are only visible from the page's own
// JavaScript world, so the background runs readLinkedInPuzzle() there with
// chrome.scripting.executeScript({ world: "MAIN" }).
(function initPagePuzzle(root) {
  // Must stay self-contained: executeScript serializes the function on its own.
  function readLinkedInPuzzle() {
    const boardSelectors = ['[data-testid="interactive-grid"]', "[data-numo-design]", '[data-testid$="-game-board"]'];
    const rootSelectors = boardSelectors.concat(['[data-testid$="-game-container"]', "[data-cell-idx]"]);
    const findPuzzle = element => {
      const fiberKey = Object.keys(element).find(key => key.startsWith("__reactFiber$"));
      for (let fiber = fiberKey && element[fiberKey], depth = 0; fiber && depth < 40; fiber = fiber.return, depth += 1) {
        const puzzle = fiber.memoizedProps?.game?.puzzle;
        if (puzzle && typeof puzzle.$case === "string" && puzzle[puzzle.$case]) return puzzle;
      }
      return null;
    };
    // Mini Sudoku is a separate (non-React) app whose cells carry readable classes.
    const sudokuCells = Array.from(document.querySelectorAll(".sudoku-cell[data-cell-idx]"));
    if (sudokuCells.length) {
      const rects = sudokuCells.map(cell => cell.getBoundingClientRect());
      const left = Math.min(...rects.map(rect => rect.left)), top = Math.min(...rects.map(rect => rect.top));
      return {
        kind: "miniSudokuCells",
        puzzle: {
          cells: sudokuCells.map(cell => ({
            index: Number(cell.getAttribute("data-cell-idx")),
            prefilled: cell.classList.contains("sudoku-cell-prefilled"),
            text: (cell.querySelector(".sudoku-cell-content")?.textContent || "").trim(),
          })),
        },
        cellMarks: {},
        selection: { x: left, y: top, width: Math.max(...rects.map(rect => rect.right)) - left,
          height: Math.max(...rects.map(rect => rect.bottom)) - top, devicePixelRatio: window.devicePixelRatio || 1 },
      };
    }
    for (const selector of rootSelectors) {
      for (const element of document.querySelectorAll(selector)) {
        const puzzle = findPuzzle(element);
        if (!puzzle) continue;
        const board = boardSelectors.map(item => document.querySelector(item)).find(Boolean) || element;
        const rect = board.getBoundingClientRect();
        // What each cell shows right now (e.g. Tango's preset "cell-zero"), by cell index.
        const cellMarks = {};
        for (const cell of document.querySelectorAll("[data-cell-idx]")) {
          const marks = Array.from(cell.querySelectorAll('[data-testid^="cell-"]'), mark => mark.getAttribute("data-testid"));
          if (marks.length) cellMarks[cell.getAttribute("data-cell-idx")] = marks;
        }
        // The official answer is left behind on purpose: we solve the puzzle ourselves.
        const data = JSON.parse(JSON.stringify(puzzle[puzzle.$case],
          (key, value) => (key === "solution" ? undefined : typeof value === "bigint" ? Number(value) : value)));
        return {
          kind: puzzle.$case,
          puzzle: data,
          cellMarks,
          selection: { x: rect.left, y: rect.top, width: rect.width, height: rect.height,
            devicePixelRatio: window.devicePixelRatio || 1 },
        };
      }
    }
    return null;
  }

  // Zip ("trail" in LinkedIn's code): numbered cells in order plus walls.
  function zipBoardFromPuzzle(page) {
    const puzzle = page?.kind === "trailGamePuzzle" ? page.puzzle : null;
    if (!puzzle || !Number.isInteger(puzzle.gridSize) || !Array.isArray(puzzle.orderedSequence)) return null;
    const walls = [];
    for (const wall of Array.isArray(puzzle.walls) ? puzzle.walls : []) {
      const direction = String(wall?.direction || "").replace(/^WallDirection_/, "").toLowerCase();
      if (!Number.isInteger(wall?.cellIdx) || !["up", "down", "left", "right"].includes(direction)) return null;
      walls.push([wall.cellIdx, direction]);
    }
    return { size: puzzle.gridSize, sequence: puzzle.orderedSequence.slice(), walls };
  }

  // Tango ("lotka" in LinkedIn's code). Preset values are only stored with the
  // answer, so they are read from what the preset cells show: "cell-zero" is a
  // sun and "cell-one" a moon.
  function tangoBoardFromPuzzle(page) {
    const puzzle = page?.kind === "lotkaGamePuzzle" ? page.puzzle : null;
    if (!puzzle || !Number.isInteger(puzzle.gridSize) || !Array.isArray(puzzle.presetCellIdxes)) return null;
    const board = { size: puzzle.gridSize, suns: [], moons: [], equal: [], opposite: [] };
    for (const cell of puzzle.presetCellIdxes) {
      const marks = page.cellMarks?.[cell] || [];
      if (marks.includes("cell-zero")) board.suns.push(cell);
      else if (marks.includes("cell-one")) board.moons.push(cell);
      else return null;
    }
    for (const edge of Array.isArray(puzzle.edges) ? puzzle.edges : []) {
      if (!Number.isInteger(edge?.startIdx) || !Number.isInteger(edge?.endIdx)) return null;
      board[edge.isEqual ? "equal" : "opposite"].push([edge.startIdx, edge.endIdx]);
    }
    return board;
  }

  // Queens: the colour region id of every cell.
  function queensBoardFromPuzzle(page) {
    const puzzle = page?.kind === "queensGamePuzzle" ? page.puzzle : null;
    if (!puzzle || !Number.isInteger(puzzle.gridSize) || !Array.isArray(puzzle.colorGrid)) return null;
    const regions = puzzle.colorGrid.map(row => (Array.isArray(row?.colors) ? row.colors.slice() : null));
    if (regions.some(row => !row || !row.every(Number.isInteger))) return null;
    return { size: puzzle.gridSize, regions };
  }

  // Patches: each clue's cell, the rectangle shape it asks for and its area (0 = no number).
  const PATCHES_SHAPES = {
    PatchesShapeConstraint_UNKNOWN: "any",
    PatchesShapeConstraint_SQUARE: "square",
    PatchesShapeConstraint_HORIZONTAL_RECT: "wide",
    PatchesShapeConstraint_VERTICAL_RECT: "tall",
  };
  function patchesBoardFromPuzzle(page) {
    const puzzle = page?.kind === "patchesGamePuzzle" ? page.puzzle : null;
    // The solver handles square boards only; anything else keeps using the image.
    if (!puzzle || !Number.isInteger(puzzle.gridRows) || puzzle.gridRows !== puzzle.gridCols || !Array.isArray(puzzle.clueCells)) {
      return null;
    }
    const clues = [];
    for (const clue of puzzle.clueCells) {
      const shape = PATCHES_SHAPES[clue?.shapeConstraint];
      if (!Number.isInteger(clue?.cellIdx) || !shape || !Number.isInteger(clue.numberConstraint || 0)) return null;
      clues.push([clue.cellIdx, shape, clue.numberConstraint || null]);
    }
    return { size: puzzle.gridRows, clues };
  }

  // Mini Sudoku: only the preset digits count; values the player typed are not clues.
  function sudokuBoardFromPuzzle(page) {
    const cells = page?.kind === "miniSudokuCells" ? page.puzzle?.cells : null;
    const size = Math.round(Math.sqrt(cells?.length || 0));
    if (!Array.isArray(cells) || size < 2 || size * size !== cells.length) return null;
    const board = Array.from({ length: size }, () => new Array(size).fill(0));
    for (const cell of cells) {
      if (!Number.isInteger(cell.index) || cell.index < 0 || cell.index >= cells.length) return null;
      if (!cell.prefilled) continue;
      if (!/^[1-9]$/.test(cell.text)) return null;
      board[Math.floor(cell.index / size)][cell.index % size] = Number(cell.text);
    }
    return { board };
  }

  // Page board builders by puzzle type; types without one keep using the image.
  const PAGE_BOARD_BUILDERS = {
    zip: zipBoardFromPuzzle,
    tango: tangoBoardFromPuzzle,
    queens: queensBoardFromPuzzle,
    patches: patchesBoardFromPuzzle,
    sudoku: sudokuBoardFromPuzzle,
  };

  root.PagePuzzle = {
    readLinkedInPuzzle, zipBoardFromPuzzle, tangoBoardFromPuzzle, queensBoardFromPuzzle, patchesBoardFromPuzzle,
    sudokuBoardFromPuzzle, PAGE_BOARD_BUILDERS,
  };
})(globalThis);
