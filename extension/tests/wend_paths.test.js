const assert = require("node:assert/strict");
const { normalizeWords } = require("../wend_paths.js");

const valid = {
  board_size: 2,
  words: [
    {
      word: "ABC",
      path: [
        { row: 0, col: 0 },
        { row: 0, col: 1 },
        { row: 1, col: 1 },
      ],
    },
  ],
};

assert.deepEqual(normalizeWords(valid), valid.words);
assert.deepEqual(
  normalizeWords({ ...valid, words: [...valid.words, { word: "X", path: [{ row: 9, col: 9 }] }] }),
  []
);
assert.deepEqual(
  normalizeWords({ board_size: 2, words: [{ word: "AB", path: [{ row: 0, col: 0 }, { row: 1, col: 1 }] }] }),
  []
);
assert.deepEqual(
  normalizeWords({ board_size: 2, words: [{ word: "AA", path: [{ row: 0, col: 0 }, { row: 0, col: 0 }] }] }),
  []
);
