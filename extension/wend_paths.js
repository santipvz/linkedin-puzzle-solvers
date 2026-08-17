(function registerWendPaths(globalScope) {
  function normalizeWords(result) {
    const boardSize = Number(result?.board_size);
    const rawWords = Array.isArray(result?.words) ? result.words : [];
    if (!boardSize || !rawWords.length) {
      return [];
    }

    const normalizedWords = rawWords.map((entry) => {
      const word = typeof entry?.word === "string" ? entry.word : "";
      const path = Array.isArray(entry?.path) ? entry.path : [];
      const normalizedPath = path.map((step) => {
        const row = Number(step?.row);
        const col = Number(step?.col);
        if (!Number.isInteger(row) || !Number.isInteger(col)) {
          return null;
        }
        if (row < 0 || col < 0 || row >= boardSize || col >= boardSize) {
          return null;
        }
        return { row, col };
      });

      if (normalizedPath.some((step) => !step)) {
        return null;
      }

      const uniqueCells = new Set(normalizedPath.map((step) => `${step.row}:${step.col}`));
      const isContiguous = normalizedPath.every((step, index) => {
        if (index === 0) {
          return true;
        }
        const previous = normalizedPath[index - 1];
        return Math.abs(step.row - previous.row) + Math.abs(step.col - previous.col) === 1;
      });

      if (
        !word ||
        normalizedPath.length !== word.length ||
        uniqueCells.size !== normalizedPath.length ||
        !isContiguous
      ) {
        return null;
      }

      return { word, path: normalizedPath };
    });

    return normalizedWords.some((entry) => !entry) ? [] : normalizedWords;
  }

  const api = Object.freeze({ normalizeWords });
  globalScope.WendPaths = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
