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

  // Page board builders by puzzle type; types without one keep using the image.
  const PAGE_BOARD_BUILDERS = { zip: zipBoardFromPuzzle, tango: tangoBoardFromPuzzle };

  root.PagePuzzle = { readLinkedInPuzzle, zipBoardFromPuzzle, tangoBoardFromPuzzle, PAGE_BOARD_BUILDERS };
})(globalThis);
