const assert = require("node:assert/strict");

require("../puzzle_registry.js");

assert.equal(globalThis.PuzzleRegistry.detectPuzzleTypeFromUrl("https://www.linkedin.com/games/wend/"), "wend");
assert.equal(globalThis.PuzzleRegistry.puzzleTypeToFrameSlug("sudoku"), "mini-sudoku");
assert.equal(globalThis.PuzzleRegistry.sanitizePuzzleType("unknown"), null);
