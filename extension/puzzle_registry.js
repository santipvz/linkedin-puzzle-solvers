(function registerPuzzleRegistry(globalScope) {
  const definitions = [
    {
      key: "queens",
      label: "Queens",
      frameSlug: "queens",
      urlNeedles: ["/games/queens", "/games/view/queens"],
    },
    {
      key: "tango",
      label: "Tango",
      frameSlug: "tango",
      urlNeedles: ["/games/tango", "/games/view/tango"],
    },
    {
      key: "sudoku",
      label: "Mini Sudoku",
      frameSlug: "mini-sudoku",
      urlNeedles: ["/games/mini-sudoku", "/games/view/mini-sudoku"],
    },
    {
      key: "zip",
      label: "Zip",
      frameSlug: "zip",
      urlNeedles: ["/games/zip", "/games/view/zip"],
    },
    {
      key: "patches",
      label: "Patches",
      frameSlug: "patches",
      urlNeedles: ["/games/patches", "/games/view/patches"],
    },
  ];

  const byKey = {};
  for (const definition of definitions) {
    byKey[definition.key] = definition;
  }

  function sanitizePuzzleType(value) {
    if (typeof value !== "string") {
      return null;
    }
    return byKey[value] ? value : null;
  }

  function puzzleTypeToFrameSlug(puzzleType) {
    const normalized = sanitizePuzzleType(puzzleType);
    if (!normalized) {
      return puzzleType;
    }
    return byKey[normalized].frameSlug;
  }

  function puzzleTypeToLabel(puzzleType) {
    const normalized = sanitizePuzzleType(puzzleType);
    if (!normalized) {
      return "Queens";
    }
    return byKey[normalized].label;
  }

  function detectPuzzleTypeFromUrl(url) {
    if (!url || typeof url !== "string") {
      return null;
    }

    const normalized = url.toLowerCase();
    for (const definition of definitions) {
      for (const needle of definition.urlNeedles) {
        if (normalized.includes(needle)) {
          return definition.key;
        }
      }
    }

    return null;
  }

  globalScope.PuzzleRegistry = Object.freeze({
    definitions: Object.freeze(definitions.map((definition) => Object.freeze({ ...definition }))),
    sanitizePuzzleType,
    puzzleTypeToFrameSlug,
    puzzleTypeToLabel,
    detectPuzzleTypeFromUrl,
  });
})(typeof globalThis !== "undefined" ? globalThis : this);
