let boardSelection = null;
let solutionOverlayRoot = null;
let quickSolveWidgetRoot = null;
let quickSolveButton = null;
let quickSolveStatus = null;
let quickSolveBusy = false;
let quickSolveObservedUrl = "";

function detectPuzzleTypeFromUrl(url) {
  if (!url || typeof url !== "string") {
    return null;
  }

  const normalized = url.toLowerCase();
  if (normalized.includes("/games/queens") || normalized.includes("/games/view/queens")) {
    return "queens";
  }
  if (normalized.includes("/games/tango") || normalized.includes("/games/view/tango")) {
    return "tango";
  }
  if (normalized.includes("/games/mini-sudoku") || normalized.includes("/games/view/mini-sudoku")) {
    return "sudoku";
  }
  if (normalized.includes("/games/zip") || normalized.includes("/games/view/zip")) {
    return "zip";
  }
  return null;
}

function detectPuzzleTypeFromPage() {
  const fromLocation = detectPuzzleTypeFromUrl(window.location.href);
  if (fromLocation) {
    return fromLocation;
  }

  const iframe = document.querySelector("iframe[src*='/games/view']");
  if (iframe && typeof iframe.src === "string") {
    return detectPuzzleTypeFromUrl(iframe.src);
  }

  return null;
}

function sendRuntimeMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      resolve(response);
    });
  });
}

function setQuickSolveStatus(text, isError = false) {
  if (!quickSolveStatus) {
    return;
  }

  quickSolveStatus.textContent = text || "";
  quickSolveStatus.style.color = isError ? "#b42318" : "#166534";
}

function updateQuickSolveButtonText() {
  if (!quickSolveButton) {
    return;
  }

  const puzzleType = detectPuzzleTypeFromPage();
  const puzzleLabel =
    puzzleType === "tango"
      ? "Tango"
      : puzzleType === "sudoku"
      ? "Mini Sudoku"
      : puzzleType === "zip"
      ? "Zip"
      : "Queens";

  if (quickSolveBusy) {
    quickSolveButton.textContent = `Solving ${puzzleLabel}...`;
  } else {
    quickSolveButton.textContent = `Solve ${puzzleLabel}`;
  }
}

function removeQuickSolveWidget() {
  if (quickSolveWidgetRoot && quickSolveWidgetRoot.parentNode) {
    quickSolveWidgetRoot.parentNode.removeChild(quickSolveWidgetRoot);
  }

  quickSolveWidgetRoot = null;
  quickSolveButton = null;
  quickSolveStatus = null;
  quickSolveBusy = false;
}

async function onQuickSolveClick() {
  const puzzleType = detectPuzzleTypeFromPage();
  if (!puzzleType) {
    setQuickSolveStatus("Open Queens, Tango, Mini Sudoku, or Zip page.", true);
    return;
  }

  if (quickSolveBusy) {
    return;
  }

  quickSolveBusy = true;
  if (quickSolveButton) {
    quickSolveButton.disabled = true;
  }
  updateQuickSolveButtonText();
  const previewOnly = false;
  setQuickSolveStatus("Solving and applying...");

  try {
    const response = await sendRuntimeMessage({
      type: "quickSolveFromPage",
      puzzleType,
      previewOnly,
    });

    if (!response || !response.ok) {
      throw new Error((response && response.error) || "Quick solve failed.");
    }

    if (!response.solved) {
      setQuickSolveStatus(response.error || "No solution found.", true);
      return;
    }

    if (response.previewed) {
      const moves = Array.isArray(response.result?.moves) ? response.result.moves.length : 0;
      const strategyText = response.strategy ? ` (${response.strategy})` : "";
      setQuickSolveStatus(`Preview ready: ${moves} moves marked${strategyText}. Take a screenshot.`);
      return;
    }

    if (!response.applied) {
      setQuickSolveStatus(`Solved, but apply failed: ${response.error || "unknown"}`, true);
      return;
    }

    const appliedCount = Number(response.appliedCount) || 0;
    const clickCount = Number(response.clickCount) || 0;
    const strategyText = response.strategy ? ` (${response.strategy})` : "";
    setQuickSolveStatus(`Solved and applied ${appliedCount} moves with ${clickCount} clicks${strategyText}.`);
  } catch (error) {
    setQuickSolveStatus(error.message || String(error), true);
  } finally {
    quickSolveBusy = false;
    if (quickSolveButton) {
      quickSolveButton.disabled = false;
    }
    updateQuickSolveButtonText();
  }
}

function createQuickSolveWidget() {
  if (quickSolveWidgetRoot || window.self !== window.top) {
    return;
  }

  const container = document.createElement("div");
  container.style.position = "fixed";
  container.style.right = "16px";
  container.style.bottom = "16px";
  container.style.zIndex = "2147483645";
  container.style.width = "220px";
  container.style.padding = "10px";
  container.style.borderRadius = "12px";
  container.style.background = "linear-gradient(165deg, rgba(255,255,255,0.96), rgba(236,245,255,0.96))";
  container.style.border = "1px solid #b6c6d9";
  container.style.boxShadow = "0 6px 18px rgba(15, 23, 42, 0.22)";
  container.style.backdropFilter = "blur(2px)";

  const title = document.createElement("div");
  title.textContent = "Puzzle Quick Solve";
  title.style.font = "700 12px/1.2 'Segoe UI', sans-serif";
  title.style.color = "#1f2937";
  title.style.marginBottom = "8px";

  const button = document.createElement("button");
  button.type = "button";
  button.style.width = "100%";
  button.style.border = "1px solid #0f766e";
  button.style.background = "#0f766e";
  button.style.color = "#ffffff";
  button.style.borderRadius = "8px";
  button.style.padding = "8px 10px";
  button.style.font = "600 13px/1.2 'Segoe UI', sans-serif";
  button.style.cursor = "pointer";
  button.addEventListener("click", () => {
    onQuickSolveClick();
  });

  const status = document.createElement("div");
  status.style.marginTop = "8px";
  status.style.minHeight = "16px";
  status.style.font = "500 11px/1.3 'Segoe UI', sans-serif";
  status.style.color = "#166534";

  container.appendChild(title);
  container.appendChild(button);
  container.appendChild(status);
  document.documentElement.appendChild(container);

  quickSolveWidgetRoot = container;
  quickSolveButton = button;
  quickSolveStatus = status;
  updateQuickSolveButtonText();
}

function syncQuickSolveWidget() {
  if (window.self !== window.top) {
    removeQuickSolveWidget();
    return;
  }

  const puzzleType = detectPuzzleTypeFromPage();
  if (!puzzleType) {
    removeQuickSolveWidget();
    return;
  }

  if (!quickSolveWidgetRoot) {
    createQuickSolveWidget();
  }

  updateQuickSolveButtonText();
}

function initializeQuickSolveWidget() {
  if (window.self !== window.top) {
    return;
  }

  quickSolveObservedUrl = window.location.href;
  syncQuickSolveWidget();

  setInterval(() => {
    if (window.location.href !== quickSolveObservedUrl) {
      quickSolveObservedUrl = window.location.href;
    }
    syncQuickSolveWidget();
  }, 1200);
}

function normalizeSelection(selection) {
  if (!selection) {
    return null;
  }

  const x = Number(selection.x);
  const y = Number(selection.y);
  const width = Number(selection.width);
  const height = Number(selection.height);
  const dpr = Number(selection.devicePixelRatio) || window.devicePixelRatio || 1;

  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(width) || !Number.isFinite(height)) {
    return null;
  }

  if (width < 10 || height < 10) {
    return null;
  }

  return { x, y, width, height, devicePixelRatio: dpr };
}

function clearSolutionOverlay() {
  if (solutionOverlayRoot && solutionOverlayRoot.parentNode) {
    solutionOverlayRoot.parentNode.removeChild(solutionOverlayRoot);
  }
  solutionOverlayRoot = null;
}

function isRectVisible(rect) {
  if (!rect) {
    return false;
  }

  if (rect.width < 120 || rect.height < 120) {
    return false;
  }

  if (rect.bottom <= 0 || rect.right <= 0) {
    return false;
  }

  if (rect.top >= window.innerHeight || rect.left >= window.innerWidth) {
    return false;
  }

  return true;
}

function puzzleTypeToFrameSlug(puzzleType) {
  if (puzzleType === "sudoku") {
    return "mini-sudoku";
  }
  return puzzleType;
}

function detectLinkedInGameIframe(puzzleType) {
  const selectors = [];

  if (puzzleType) {
    selectors.push(`iframe[src*="/games/view/${puzzleTypeToFrameSlug(puzzleType)}"]`);
  }

  selectors.push("iframe[src*='/games/view']");
  selectors.push("iframe.game-launch-page__iframe");

  const seen = new Set();
  const candidates = [];

  for (const selector of selectors) {
    const nodes = document.querySelectorAll(selector);
    for (const node of nodes) {
      if (seen.has(node)) {
        continue;
      }
      seen.add(node);

      const rect = node.getBoundingClientRect();
      if (!isRectVisible(rect)) {
        continue;
      }

      const area = rect.width * rect.height;
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const viewportCenterX = window.innerWidth / 2;
      const viewportCenterY = window.innerHeight / 2;
      const centerDistance = Math.hypot(centerX - viewportCenterX, centerY - viewportCenterY);
      const score = area - centerDistance * 150;
      candidates.push({ score, node, rect });
    }
  }

  if (!candidates.length) {
    return null;
  }

  candidates.sort((a, b) => b.score - a.score);
  return candidates[0];
}

function getGameIframeRect(puzzleType) {
  const detected = detectLinkedInGameIframe(puzzleType);
  if (!detected) {
    return null;
  }

  const rect = detected.rect;
  return {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height,
  };
}

function autoDetectBoardSelection(puzzleType = null) {
  const selectors = [
    "canvas",
    "svg",
    "[role='grid']",
    "table",
    "div[class*='board']",
    "div[class*='grid']",
    "div[class*='game-board']",
    "div[data-test*='board']",
    "div[data-testid*='board']",
    "[aria-label*='board' i]",
  ];

  const candidates = [];
  const seen = new Set();

  for (const selector of selectors) {
    const nodes = document.querySelectorAll(selector);
    for (const node of nodes) {
      if (seen.has(node)) {
        continue;
      }
      seen.add(node);

      const rect = node.getBoundingClientRect();
      if (!isRectVisible(rect)) {
        continue;
      }

      const ratio = rect.width / rect.height;
      if (ratio < 0.65 || ratio > 1.45) {
        continue;
      }

      const area = rect.width * rect.height;
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const viewportCenterX = window.innerWidth / 2;
      const viewportCenterY = window.innerHeight / 2;
      const centerDistance = Math.hypot(centerX - viewportCenterX, centerY - viewportCenterY);

      const score = area - centerDistance * 350;

      candidates.push({ score, rect });
    }
  }

  if (candidates.length === 0) {
    return null;
  }

  candidates.sort((a, b) => b.score - a.score);
  const bestRect = candidates[0].rect;

  return normalizeSelection({
    x: bestRect.left,
    y: bestRect.top,
    width: bestRect.width,
    height: bestRect.height,
    devicePixelRatio: window.devicePixelRatio,
  });
}

function autoDetectBoardSelectionWithFallback(puzzleType) {
  const directSelection = autoDetectBoardSelection(puzzleType);
  if (directSelection) {
    return directSelection;
  }

  const iframeRect = getGameIframeRect(puzzleType);
  if (!iframeRect) {
    return null;
  }

  const inset = Math.max(0, Math.min(iframeRect.width, iframeRect.height) * 0.04);

  return normalizeSelection({
    x: iframeRect.left + inset,
    y: iframeRect.top + inset,
    width: Math.max(10, iframeRect.width - inset * 2),
    height: Math.max(10, iframeRect.height - inset * 2),
    devicePixelRatio: window.devicePixelRatio,
  });
}

function getViewportSelection() {
  return normalizeSelection({
    x: 0,
    y: 0,
    width: window.innerWidth,
    height: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio,
  });
}

function startBoardSelection() {
  return new Promise((resolve, reject) => {
    const layer = document.createElement("div");
    layer.style.position = "fixed";
    layer.style.left = "0";
    layer.style.top = "0";
    layer.style.width = "100vw";
    layer.style.height = "100vh";
    layer.style.zIndex = "2147483647";
    layer.style.cursor = "crosshair";
    layer.style.background = "rgba(20, 20, 20, 0.15)";

    const helper = document.createElement("div");
    helper.textContent = "Drag to select puzzle board. Press Esc to cancel.";
    helper.style.position = "fixed";
    helper.style.top = "12px";
    helper.style.left = "12px";
    helper.style.padding = "8px 12px";
    helper.style.background = "rgba(0, 0, 0, 0.8)";
    helper.style.color = "#fff";
    helper.style.font = "13px/1.2 sans-serif";
    helper.style.borderRadius = "8px";
    helper.style.pointerEvents = "none";

    const box = document.createElement("div");
    box.style.position = "fixed";
    box.style.border = "2px solid #14b8a6";
    box.style.background = "rgba(20, 184, 166, 0.18)";
    box.style.display = "none";
    box.style.pointerEvents = "none";

    layer.appendChild(helper);
    layer.appendChild(box);
    document.documentElement.appendChild(layer);

    let isDrawing = false;
    let startX = 0;
    let startY = 0;

    const cleanup = () => {
      layer.removeEventListener("mousedown", onMouseDown, true);
      layer.removeEventListener("mousemove", onMouseMove, true);
      layer.removeEventListener("mouseup", onMouseUp, true);
      document.removeEventListener("keydown", onKeyDown, true);

      if (layer.parentNode) {
        layer.parentNode.removeChild(layer);
      }
    };

    const onMouseDown = (event) => {
      event.preventDefault();
      event.stopPropagation();

      isDrawing = true;
      startX = event.clientX;
      startY = event.clientY;

      box.style.display = "block";
      box.style.left = `${startX}px`;
      box.style.top = `${startY}px`;
      box.style.width = "0px";
      box.style.height = "0px";
    };

    const onMouseMove = (event) => {
      if (!isDrawing) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();

      const currentX = event.clientX;
      const currentY = event.clientY;
      const left = Math.min(startX, currentX);
      const top = Math.min(startY, currentY);
      const width = Math.abs(currentX - startX);
      const height = Math.abs(currentY - startY);

      box.style.left = `${left}px`;
      box.style.top = `${top}px`;
      box.style.width = `${width}px`;
      box.style.height = `${height}px`;
    };

    const onMouseUp = (event) => {
      if (!isDrawing) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      isDrawing = false;

      const endX = event.clientX;
      const endY = event.clientY;
      const left = Math.min(startX, endX);
      const top = Math.min(startY, endY);
      const width = Math.abs(endX - startX);
      const height = Math.abs(endY - startY);

      cleanup();

      const selection = normalizeSelection({
        x: left,
        y: top,
        width,
        height,
        devicePixelRatio: window.devicePixelRatio,
      });

      if (!selection) {
        reject(new Error("Selection too small. Please try again."));
        return;
      }

      boardSelection = selection;
      resolve(selection);
    };

    const onKeyDown = (event) => {
      if (event.key !== "Escape") {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      cleanup();
      reject(new Error("Board selection canceled."));
    };

    layer.addEventListener("mousedown", onMouseDown, true);
    layer.addEventListener("mousemove", onMouseMove, true);
    layer.addEventListener("mouseup", onMouseUp, true);
    document.addEventListener("keydown", onKeyDown, true);
  });
}

function createOverlayRoot(selection) {
  clearSolutionOverlay();

  const root = document.createElement("div");
  root.style.position = "fixed";
  root.style.left = "0";
  root.style.top = "0";
  root.style.width = "100vw";
  root.style.height = "100vh";
  root.style.zIndex = "2147483646";
  root.style.pointerEvents = "none";

  const frame = document.createElement("div");
  frame.style.position = "fixed";
  frame.style.left = `${selection.x}px`;
  frame.style.top = `${selection.y}px`;
  frame.style.width = `${selection.width}px`;
  frame.style.height = `${selection.height}px`;
  frame.style.border = "2px solid #22c55e";
  frame.style.boxSizing = "border-box";
  frame.style.background = "rgba(34, 197, 94, 0.06)";
  frame.style.pointerEvents = "none";

  root.appendChild(frame);
  document.documentElement.appendChild(root);
  solutionOverlayRoot = root;

  return root;
}

function renderQueensOverlay(root, selection, result) {
  const boardSize = Number(result.board_size);
  if (!boardSize || !Array.isArray(result.moves)) {
    return;
  }

  const cellWidth = selection.width / boardSize;
  const cellHeight = selection.height / boardSize;

  for (const move of result.moves) {
    const row = Number(move.row);
    const col = Number(move.col);

    if (!Number.isFinite(row) || !Number.isFinite(col)) {
      continue;
    }

    const marker = document.createElement("div");
    marker.textContent = "Q";
    marker.style.position = "fixed";
    marker.style.width = "24px";
    marker.style.height = "24px";
    marker.style.borderRadius = "12px";
    marker.style.left = `${selection.x + (col + 0.5) * cellWidth - 12}px`;
    marker.style.top = `${selection.y + (row + 0.5) * cellHeight - 12}px`;
    marker.style.display = "flex";
    marker.style.alignItems = "center";
    marker.style.justifyContent = "center";
    marker.style.font = "700 13px/1 sans-serif";
    marker.style.background = "#facc15";
    marker.style.color = "#111827";
    marker.style.border = "2px solid #111827";
    marker.style.boxShadow = "0 2px 6px rgba(0, 0, 0, 0.35)";

    root.appendChild(marker);
  }
}

function renderTangoOverlay(root, selection, result) {
  const boardSize = Number(result.board_size);
  const grid = Array.isArray(result.solution_grid) ? result.solution_grid : null;
  if (!boardSize || !grid) {
    return;
  }

  const fixedPieces = Array.isArray(result.fixed_pieces) ? result.fixed_pieces : [];
  const fixedSet = new Set(fixedPieces.map((piece) => `${piece.row},${piece.col}`));

  const cellWidth = selection.width / boardSize;
  const cellHeight = selection.height / boardSize;

  for (let row = 0; row < grid.length; row += 1) {
    const rowValues = grid[row];
    if (!Array.isArray(rowValues)) {
      continue;
    }

    for (let col = 0; col < rowValues.length; col += 1) {
      if (fixedSet.has(`${row},${col}`)) {
        continue;
      }

      const value = Number(rowValues[col]);
      if (value !== 0 && value !== 1) {
        continue;
      }

      const marker = document.createElement("div");
      marker.textContent = value === 0 ? "M" : "S";
      marker.style.position = "fixed";
      marker.style.width = "22px";
      marker.style.height = "22px";
      marker.style.borderRadius = "11px";
      marker.style.left = `${selection.x + (col + 0.5) * cellWidth - 11}px`;
      marker.style.top = `${selection.y + (row + 0.5) * cellHeight - 11}px`;
      marker.style.display = "flex";
      marker.style.alignItems = "center";
      marker.style.justifyContent = "center";
      marker.style.font = "700 12px/1 sans-serif";
      marker.style.background = value === 0 ? "#93c5fd" : "#fdba74";
      marker.style.color = "#1f2937";
      marker.style.border = "1px solid #1f2937";

      root.appendChild(marker);
    }
  }
}

function renderSudokuOverlay(root, selection, result) {
  const boardSize = Number(result.board_size);
  const moves = Array.isArray(result.moves) ? result.moves : [];
  if (!boardSize || !moves.length) {
    return;
  }

  const cellWidth = selection.width / boardSize;
  const cellHeight = selection.height / boardSize;

  for (const move of moves) {
    const row = Number(move.row);
    const col = Number(move.col);
    const value = Number(move.value);

    if (!Number.isFinite(row) || !Number.isFinite(col) || !Number.isFinite(value)) {
      continue;
    }

    const marker = document.createElement("div");
    marker.textContent = String(value);
    marker.style.position = "fixed";
    marker.style.width = "24px";
    marker.style.height = "24px";
    marker.style.borderRadius = "12px";
    marker.style.left = `${selection.x + (col + 0.5) * cellWidth - 12}px`;
    marker.style.top = `${selection.y + (row + 0.5) * cellHeight - 12}px`;
    marker.style.display = "flex";
    marker.style.alignItems = "center";
    marker.style.justifyContent = "center";
    marker.style.font = "700 13px/1 sans-serif";
    marker.style.background = "#f59e0b";
    marker.style.color = "#111827";
    marker.style.border = "2px solid #111827";
    marker.style.boxShadow = "0 2px 6px rgba(0, 0, 0, 0.35)";

    root.appendChild(marker);
  }
}

function renderZipOverlay(root, selection, result) {
  const boardSize = Number(result.board_size);
  const path = Array.isArray(result.path) ? result.path : [];
  if (!boardSize || path.length < 2) {
    return;
  }

  const cellWidth = selection.width / boardSize;
  const cellHeight = selection.height / boardSize;

  const centers = path
    .map((step) => {
      const row = Number(step.row);
      const col = Number(step.col);
      if (!Number.isFinite(row) || !Number.isFinite(col)) {
        return null;
      }
      return {
        x: selection.x + (col + 0.5) * cellWidth,
        y: selection.y + (row + 0.5) * cellHeight,
      };
    })
    .filter(Boolean);

  if (centers.length < 2) {
    return;
  }

  for (let index = 0; index < centers.length - 1; index += 1) {
    const current = centers[index];
    const next = centers[index + 1];

    const dx = next.x - current.x;
    const dy = next.y - current.y;
    const length = Math.hypot(dx, dy);
    const angle = Math.atan2(dy, dx);

    const segment = document.createElement("div");
    segment.style.position = "fixed";
    segment.style.left = `${current.x}px`;
    segment.style.top = `${current.y}px`;
    segment.style.width = `${length}px`;
    segment.style.height = "6px";
    segment.style.transformOrigin = "0 50%";
    segment.style.transform = `translateY(-3px) rotate(${angle}rad)`;
    segment.style.borderRadius = "999px";
    segment.style.background = "rgba(14, 116, 144, 0.85)";
    segment.style.boxShadow = "0 0 0 1px rgba(255, 255, 255, 0.65)";
    root.appendChild(segment);
  }

  const start = centers[0];
  const end = centers[centers.length - 1];

  const startDot = document.createElement("div");
  startDot.style.position = "fixed";
  startDot.style.left = `${start.x - 7}px`;
  startDot.style.top = `${start.y - 7}px`;
  startDot.style.width = "14px";
  startDot.style.height = "14px";
  startDot.style.borderRadius = "50%";
  startDot.style.background = "#0284c7";
  startDot.style.border = "2px solid #ffffff";
  root.appendChild(startDot);

  const endDot = document.createElement("div");
  endDot.style.position = "fixed";
  endDot.style.left = `${end.x - 7}px`;
  endDot.style.top = `${end.y - 7}px`;
  endDot.style.width = "14px";
  endDot.style.height = "14px";
  endDot.style.borderRadius = "50%";
  endDot.style.background = "#f97316";
  endDot.style.border = "2px solid #ffffff";
  root.appendChild(endDot);
}

function renderSolutionOverlay(puzzleType, result, selection) {
  const normalized = normalizeSelection(selection || boardSelection);
  if (!normalized) {
    throw new Error("Board region is not selected.");
  }

  const root = createOverlayRoot(normalized);

  const badge = document.createElement("div");
  badge.textContent = result && result.solved ? "Solution ready" : "No solution";
  badge.style.position = "fixed";
  badge.style.left = `${normalized.x}px`;
  badge.style.top = `${Math.max(0, normalized.y - 30)}px`;
  badge.style.padding = "5px 10px";
  badge.style.borderRadius = "999px";
  badge.style.font = "600 12px/1 sans-serif";
  badge.style.background = result && result.solved ? "#16a34a" : "#b91c1c";
  badge.style.color = "white";
  badge.style.boxShadow = "0 2px 8px rgba(0, 0, 0, 0.35)";
  root.appendChild(badge);

  if (!result || !result.solved) {
    return;
  }

  if (puzzleType === "tango") {
    renderTangoOverlay(root, normalized, result);
    return;
  }

  if (puzzleType === "sudoku") {
    renderSudokuOverlay(root, normalized, result);
    return;
  }

  if (puzzleType === "zip") {
    renderZipOverlay(root, normalized, result);
    return;
  }

  renderQueensOverlay(root, normalized, result);
}

function clickViewportPoint(x, y, button = 0) {
  const safeX = Math.max(0, Math.min(window.innerWidth - 1, x));
  const safeY = Math.max(0, Math.min(window.innerHeight - 1, y));
  const target = document.elementFromPoint(safeX, safeY);

  if (!target) {
    return false;
  }

  if (target instanceof HTMLIFrameElement) {
    return false;
  }

  const isRightClick = button === 2;
  const eventTypes = isRightClick
    ? ["pointerdown", "mousedown", "pointerup", "mouseup", "contextmenu"]
    : ["pointerdown", "mousedown", "pointerup", "mouseup", "click"];

  const buttonMask = isRightClick ? 2 : 1;

  for (const type of eventTypes) {
    const isDown = type === "pointerdown" || type === "mousedown";
    const eventButtons = isDown ? buttonMask : 0;

    const event = new MouseEvent(type, {
      bubbles: true,
      cancelable: true,
      composed: true,
      clientX: safeX,
      clientY: safeY,
      button,
      buttons: eventButtons,
      view: window,
    });
    target.dispatchEvent(event);
  }

  return true;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const DEFAULT_QUEENS_CLICKS_PER_MOVE = 2;
const DEFAULT_INTER_CLICK_DELAY_MS = 45;
const DEFAULT_INTER_MOVE_DELAY_MS = 40;
const DEFAULT_TANGO_APPLY_MODE = "left-cycle";
const TANGO_SUN_LEFT_CLICKS = 1;
const TANGO_MOON_LEFT_CLICKS = 2;
const MIN_DELAY_MS = 0;
const MAX_DELAY_MS = 500;

function leftClickViewportPoint(x, y) {
  return clickViewportPoint(x, y, 0);
}

function rightClickViewportPoint(x, y) {
  return clickViewportPoint(x, y, 2);
}

function isPointInsideSelection(x, y, selection, inset = 0) {
  const normalized = normalizeSelection(selection);
  if (!normalized) {
    return false;
  }

  return (
    x >= normalized.x + inset &&
    x <= normalized.x + normalized.width - inset &&
    y >= normalized.y + inset &&
    y <= normalized.y + normalized.height - inset
  );
}

function getElementAtViewportPoint(x, y) {
  const safeX = Math.max(0, Math.min(window.innerWidth - 1, Number(x)));
  const safeY = Math.max(0, Math.min(window.innerHeight - 1, Number(y)));

  if (!Number.isFinite(safeX) || !Number.isFinite(safeY)) {
    return null;
  }

  const element = document.elementFromPoint(safeX, safeY);
  if (!element || element instanceof HTMLIFrameElement) {
    return null;
  }

  return {
    x: safeX,
    y: safeY,
    element,
  };
}

function isLikelySudokuCellElement(element, selection, cellWidth, cellHeight) {
  if (!(element instanceof Element)) {
    return false;
  }

  const rect = element.getBoundingClientRect();
  if (!rect || rect.width < 6 || rect.height < 6) {
    return false;
  }

  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;
  if (!isPointInsideSelection(centerX, centerY, selection, 0)) {
    return false;
  }

  const minWidth = Math.max(6, cellWidth * 0.22);
  const minHeight = Math.max(6, cellHeight * 0.22);
  const maxWidth = Math.max(cellWidth * 2.4, 18);
  const maxHeight = Math.max(cellHeight * 2.4, 18);

  if (rect.width < minWidth || rect.height < minHeight) {
    return false;
  }

  if (rect.width > maxWidth || rect.height > maxHeight) {
    return false;
  }

  return true;
}

function findSudokuCellElementAtPoint(x, y, selection, cellWidth, cellHeight) {
  const point = getElementAtViewportPoint(x, y);
  if (!point) {
    return null;
  }

  let current = point.element;
  for (let depth = 0; current && depth < 8; depth += 1) {
    if (isLikelySudokuCellElement(current, selection, cellWidth, cellHeight)) {
      return current;
    }
    current = current.parentElement;
  }

  return null;
}

function inferSudokuGridPositionFromCell(cellElement, selection, cellWidth, cellHeight, boardSize) {
  if (!(cellElement instanceof Element)) {
    return null;
  }

  const rect = cellElement.getBoundingClientRect();
  if (!rect) {
    return null;
  }

  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;
  if (!isPointInsideSelection(centerX, centerY, selection, 0)) {
    return null;
  }

  const row = Math.floor((centerY - selection.y) / cellHeight);
  const col = Math.floor((centerX - selection.x) / cellWidth);

  if (!Number.isFinite(row) || !Number.isFinite(col)) {
    return null;
  }

  if (row < 0 || row >= boardSize || col < 0 || col >= boardSize) {
    return null;
  }

  return { row, col };
}

function buildSudokuPointCandidates(baseX, baseY, cellWidth, cellHeight, selection) {
  const factors = [
    [0, 0],
    [0.18, 0],
    [-0.18, 0],
    [0, 0.18],
    [0, -0.18],
    [0.14, 0.14],
    [0.14, -0.14],
    [-0.14, 0.14],
    [-0.14, -0.14],
  ];

  const points = [];
  const seen = new Set();

  for (const [fx, fy] of factors) {
    const x = baseX + fx * cellWidth;
    const y = baseY + fy * cellHeight;
    if (!isPointInsideSelection(x, y, selection, 1)) {
      continue;
    }

    const key = `${Math.round(x)}:${Math.round(y)}`;
    if (seen.has(key)) {
      continue;
    }

    seen.add(key);
    points.push({ x, y });
  }

  if (!points.length && isPointInsideSelection(baseX, baseY, selection, 0)) {
    points.push({ x: baseX, y: baseY });
  }

  return points;
}

function findKeyboardTarget(element) {
  let current = element instanceof Element ? element : null;

  for (let depth = 0; current && depth < 8; depth += 1) {
    if (typeof current.dispatchEvent === "function") {
      return current;
    }
    current = current.parentElement;
  }

  return null;
}

function focusKeyboardTarget(target) {
  if (!(target instanceof HTMLElement) || typeof target.focus !== "function") {
    return;
  }

  try {
    target.focus({ preventScroll: true });
  } catch (error) {
    target.focus();
  }
}

function dispatchKeyboardKey(key, code, keyCode, options = {}) {
  if (!key || !code || !Number.isFinite(keyCode)) {
    return false;
  }

  const includeKeypress = options.includeKeypress !== false;
  const preferredTarget = options.target;
  const activeElement = document.activeElement;

  let target = null;
  if (preferredTarget && typeof preferredTarget.dispatchEvent === "function") {
    target = preferredTarget;
  } else if (activeElement && typeof activeElement.dispatchEvent === "function") {
    target = activeElement;
  } else if (document.body && typeof document.body.dispatchEvent === "function") {
    target = document.body;
  } else if (document.documentElement && typeof document.documentElement.dispatchEvent === "function") {
    target = document.documentElement;
  } else if (typeof document.dispatchEvent === "function") {
    target = document;
  } else if (typeof window.dispatchEvent === "function") {
    target = window;
  }

  if (!target) {
    return false;
  }

  if (options.focusTarget !== false) {
    focusKeyboardTarget(target);
  }

  const eventTypes = includeKeypress ? ["keydown", "keypress", "keyup"] : ["keydown", "keyup"];

  for (const type of eventTypes) {
    const event = new KeyboardEvent(type, {
      key,
      code,
      keyCode,
      which: keyCode,
      bubbles: true,
      cancelable: true,
      composed: true,
    });

    target.dispatchEvent(event);
  }

  return true;
}

function dispatchDigitKey(digitValue, target = null) {
  const key = String(digitValue);
  const keyCode = key.charCodeAt(0);
  const code = `Digit${key}`;
  return dispatchKeyboardKey(key, code, keyCode, { includeKeypress: true, target });
}

function dispatchArrowKey(direction) {
  const normalized = typeof direction === "string" ? direction.toLowerCase() : "";
  if (normalized === "up") {
    return dispatchKeyboardKey("ArrowUp", "ArrowUp", 38, { includeKeypress: false });
  }
  if (normalized === "down") {
    return dispatchKeyboardKey("ArrowDown", "ArrowDown", 40, { includeKeypress: false });
  }
  if (normalized === "left") {
    return dispatchKeyboardKey("ArrowLeft", "ArrowLeft", 37, { includeKeypress: false });
  }
  if (normalized === "right") {
    return dispatchKeyboardKey("ArrowRight", "ArrowRight", 39, { includeKeypress: false });
  }
  return false;
}

function normalizeDelay(value, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(MIN_DELAY_MS, Math.min(MAX_DELAY_MS, Math.round(parsed)));
}

function normalizeApplySettings(settings) {
  const tangoApplyMode =
    settings && settings.tangoApplyMode === "right-moon"
      ? "right-moon"
      : DEFAULT_TANGO_APPLY_MODE;

  return {
    queensClicksPerMove: DEFAULT_QUEENS_CLICKS_PER_MOVE,
    interClickDelayMs: normalizeDelay(settings?.interClickDelayMs, DEFAULT_INTER_CLICK_DELAY_MS),
    interMoveDelayMs: normalizeDelay(settings?.interMoveDelayMs, DEFAULT_INTER_MOVE_DELAY_MS),
    tangoApplyMode,
  };
}

function buildApplySelectionCandidates(puzzleType, primarySelection) {
  const candidates = [];
  const seen = new Set();

  const pushCandidate = (selection, source) => {
    const normalized = normalizeSelection(selection);
    if (!normalized) {
      return;
    }

    const key = `${Math.round(normalized.x)}:${Math.round(normalized.y)}:${Math.round(normalized.width)}:${Math.round(
      normalized.height
    )}`;

    if (seen.has(key)) {
      return;
    }

    seen.add(key);
    candidates.push({ selection: normalized, source });
  };

  pushCandidate(primarySelection, "provided");
  pushCandidate(boardSelection, "stored");
  pushCandidate(autoDetectBoardSelection(puzzleType), "auto-detect");

  return candidates;
}

function getTangoClickCountForValue(value, applySettings) {
  // Tango solver encoding: 0 = moon, 1 = sun
  if (value === 0) {
    if (applySettings.tangoApplyMode === "right-moon") {
      return 0;
    }
    return TANGO_MOON_LEFT_CLICKS;
  }
  if (value === 1) {
    return TANGO_SUN_LEFT_CLICKS;
  }
  return 0;
}

function buildTangoMoveList(result) {
  if (Array.isArray(result?.moves) && result.moves.length > 0) {
    return result.moves;
  }

  const grid = Array.isArray(result?.solution_grid) ? result.solution_grid : null;
  const fixedPieces = Array.isArray(result?.fixed_pieces) ? result.fixed_pieces : [];
  if (!grid) {
    return [];
  }

  const fixedSet = new Set(fixedPieces.map((piece) => `${piece.row},${piece.col}`));
  const moves = [];

  for (let row = 0; row < grid.length; row += 1) {
    const rowValues = Array.isArray(grid[row]) ? grid[row] : [];
    for (let col = 0; col < rowValues.length; col += 1) {
      if (fixedSet.has(`${row},${col}`)) {
        continue;
      }
      const value = Number(rowValues[col]);
      if (value !== 0 && value !== 1) {
        continue;
      }
      moves.push({ row, col, value });
    }
  }

  return moves;
}

async function applyQueensSolution(result, selection, settings) {
  const applySettings = normalizeApplySettings(settings);
  const normalized = normalizeSelection(selection || boardSelection);
  if (!normalized) {
    return { ok: false, error: "Board selection is required before applying moves." };
  }

  if (!result || !Array.isArray(result.moves)) {
    return { ok: false, error: "No Queens solution moves are available." };
  }

  const boardSize = Number(result.board_size);
  if (!boardSize) {
    return { ok: false, error: "Invalid board size in solution." };
  }

  const cellWidth = normalized.width / boardSize;
  const cellHeight = normalized.height / boardSize;
  let appliedCount = 0;
  let clickCount = 0;

  for (const move of result.moves) {
    const row = Number(move.row);
    const col = Number(move.col);

    if (!Number.isFinite(row) || !Number.isFinite(col)) {
      continue;
    }

    const x = normalized.x + (col + 0.5) * cellWidth;
    const y = normalized.y + (row + 0.5) * cellHeight;

    const firstClickApplied = leftClickViewportPoint(x, y);
    if (!firstClickApplied) {
      continue;
    }

    appliedCount += 1;
    clickCount += 1;

    for (let clickIndex = 1; clickIndex < applySettings.queensClicksPerMove; clickIndex += 1) {
      await sleep(applySettings.interClickDelayMs);
      if (leftClickViewportPoint(x, y)) {
        clickCount += 1;
      }
    }

    await sleep(applySettings.interMoveDelayMs);
  }

  if (result.moves.length > 0 && appliedCount === 0) {
    return {
      ok: false,
      error: "Could not dispatch Queens clicks to board cells.",
      appliedCount,
      clickCount,
      clicksPerMove: applySettings.queensClicksPerMove,
    };
  }

  return {
    ok: true,
    appliedCount,
    clickCount,
    clicksPerMove: applySettings.queensClicksPerMove,
  };
}

async function applyTangoSolution(result, selection, settings) {
  const applySettings = normalizeApplySettings(settings);
  const normalized = normalizeSelection(selection || boardSelection);
  if (!normalized) {
    return { ok: false, error: "Board selection is required before applying moves." };
  }

  const boardSize = Number(result?.board_size);
  if (!boardSize) {
    return { ok: false, error: "Invalid board size in solution." };
  }

  const moves = buildTangoMoveList(result);
  if (!moves.length) {
    const fixedCount = Number(result?.details?.fixed_count);
    if (Number.isFinite(fixedCount) && fixedCount >= boardSize * boardSize) {
      return {
        ok: true,
        appliedCount: 0,
        clickCount: 0,
        strategy: "already-filled",
      };
    }

    return { ok: false, error: "No Tango solution moves are available." };
  }

  const cellWidth = normalized.width / boardSize;
  const cellHeight = normalized.height / boardSize;

  let appliedCount = 0;
  let clickCount = 0;

  for (const move of moves) {
    const row = Number(move.row);
    const col = Number(move.col);
    const value = Number(move.value);

    if (!Number.isFinite(row) || !Number.isFinite(col) || (value !== 0 && value !== 1)) {
      continue;
    }

    const x = normalized.x + (col + 0.5) * cellWidth;
    const y = normalized.y + (row + 0.5) * cellHeight;

    let localClicks = 0;

    if (value === 0 && applySettings.tangoApplyMode === "right-moon") {
      if (rightClickViewportPoint(x, y)) {
        localClicks += 1;
        clickCount += 1;
      } else {
        const fallbackClicks = TANGO_MOON_LEFT_CLICKS;
        for (let clickIndex = 0; clickIndex < fallbackClicks; clickIndex += 1) {
          if (leftClickViewportPoint(x, y)) {
            localClicks += 1;
            clickCount += 1;
          }
          if (clickIndex < fallbackClicks - 1) {
            await sleep(applySettings.interClickDelayMs);
          }
        }
      }
    } else {
      const clicksNeeded = getTangoClickCountForValue(value, applySettings);
      for (let clickIndex = 0; clickIndex < clicksNeeded; clickIndex += 1) {
        if (leftClickViewportPoint(x, y)) {
          localClicks += 1;
          clickCount += 1;
        }
        if (clickIndex < clicksNeeded - 1) {
          await sleep(applySettings.interClickDelayMs);
        }
      }
    }

    if (localClicks > 0) {
      appliedCount += 1;
    }

    await sleep(applySettings.interMoveDelayMs);
  }

  const strategy =
    applySettings.tangoApplyMode === "right-moon"
      ? "left-sun-right-moon"
      : "left-cycle";

  if (appliedCount === 0) {
    return {
      ok: false,
      error: "Could not dispatch Tango clicks to board cells.",
      appliedCount,
      clickCount,
      strategy,
    };
  }

  return {
    ok: true,
    appliedCount,
    clickCount,
    strategy,
    clicksPerValue: applySettings.tangoApplyMode === "right-moon" ? { 0: "right", 1: 1 } : { 0: 2, 1: 1 },
  };
}

async function applySudokuSolution(result, selection, settings) {
  const applySettings = normalizeApplySettings(settings);

  const boardSize = Number(result?.board_size);
  if (!boardSize) {
    return { ok: false, error: "Invalid board size in solution." };
  }

  const moves = Array.isArray(result?.moves) ? result.moves : [];
  if (!moves.length) {
    if (result?.solved) {
      return {
        ok: true,
        appliedCount: 0,
        clickCount: 0,
        keyCount: 0,
        strategy: "already-filled",
      };
    }
    return { ok: false, error: "No Sudoku solution moves are available." };
  }

  const actionableMoves = moves
    .map((move) => ({
      row: Number(move?.row),
      col: Number(move?.col),
      value: Number(move?.value),
    }))
    .filter(
      (move) =>
        Number.isInteger(move.row) &&
        Number.isInteger(move.col) &&
        Number.isInteger(move.value) &&
        move.row >= 0 &&
        move.row < boardSize &&
        move.col >= 0 &&
        move.col < boardSize &&
        move.value >= 1 &&
        move.value <= boardSize
    );

  if (!actionableMoves.length) {
    return { ok: false, error: "No valid Sudoku solution moves are available." };
  }

  const selectionCandidates = buildApplySelectionCandidates("sudoku", selection);
  if (!selectionCandidates.length) {
    return { ok: false, error: "Board selection is required before applying moves." };
  }

  let bestAttempt = {
    appliedCount: 0,
    clickCount: 0,
    keyCount: 0,
    alignedCount: 0,
  };

  for (let candidateIndex = 0; candidateIndex < selectionCandidates.length; candidateIndex += 1) {
    const candidateEntry = selectionCandidates[candidateIndex];
    const candidate = candidateEntry.selection;
    const cellWidth = candidate.width / boardSize;
    const cellHeight = candidate.height / boardSize;

    let appliedCount = 0;
    let clickCount = 0;
    let keyCount = 0;
    let alignedCount = 0;

    for (const move of actionableMoves) {
      const row = move.row;
      const col = move.col;
      const value = move.value;

      const baseX = candidate.x + (col + 0.5) * cellWidth;
      const baseY = candidate.y + (row + 0.5) * cellHeight;
      const pointCandidates = buildSudokuPointCandidates(baseX, baseY, cellWidth, cellHeight, candidate);

      let moveApplied = false;

      for (const point of pointCandidates) {
        const cellElement = findSudokuCellElementAtPoint(point.x, point.y, candidate, cellWidth, cellHeight);
        if (!cellElement) {
          continue;
        }

        const inferredPosition = inferSudokuGridPositionFromCell(cellElement, candidate, cellWidth, cellHeight, boardSize);
        if (!inferredPosition || inferredPosition.row !== row || inferredPosition.col !== col) {
          continue;
        }

        const clicked = leftClickViewportPoint(point.x, point.y);
        if (!clicked) {
          continue;
        }

        alignedCount += 1;
        clickCount += 1;
        await sleep(applySettings.interClickDelayMs);

        const livePointTarget = getElementAtViewportPoint(point.x, point.y);
        const keyboardTarget =
          findKeyboardTarget(cellElement) || findKeyboardTarget(livePointTarget && livePointTarget.element) || null;

        focusKeyboardTarget(cellElement);
        if (dispatchDigitKey(value, keyboardTarget)) {
          keyCount += 1;
          appliedCount += 1;
          moveApplied = true;
          break;
        }
      }

      await sleep(applySettings.interMoveDelayMs);

      if (!moveApplied) {
        continue;
      }
    }

    if (
      appliedCount > bestAttempt.appliedCount ||
      (appliedCount === bestAttempt.appliedCount && alignedCount > bestAttempt.alignedCount) ||
      (appliedCount === bestAttempt.appliedCount && alignedCount === bestAttempt.alignedCount && clickCount > bestAttempt.clickCount)
    ) {
      bestAttempt = {
        appliedCount,
        clickCount,
        keyCount,
        alignedCount,
      };
    }

    if (appliedCount === actionableMoves.length && alignedCount === actionableMoves.length) {
      return {
        ok: true,
        appliedCount,
        clickCount,
        keyCount,
        strategy:
          candidateEntry.source === "auto-detect"
            ? "strict-cell-then-keyboard:auto-detect"
            : "strict-cell-then-keyboard",
      };
    }
  }

  return {
    ok: false,
    error: `Could not confidently apply Sudoku moves. Tried ${selectionCandidates.length} region(s).`,
    appliedCount: bestAttempt.appliedCount,
    clickCount: bestAttempt.clickCount,
    keyCount: bestAttempt.keyCount,
    alignedCount: bestAttempt.alignedCount,
    strategy: "strict-cell-then-keyboard",
  };
}

function buildZipDirectionList(result) {
  if (Array.isArray(result?.directions) && result.directions.length > 0) {
    return result.directions;
  }

  const path = Array.isArray(result?.path) ? result.path : [];
  if (path.length < 2) {
    return [];
  }

  const directions = [];
  for (let index = 0; index < path.length - 1; index += 1) {
    const current = path[index];
    const next = path[index + 1];
    const rowA = Number(current?.row);
    const colA = Number(current?.col);
    const rowB = Number(next?.row);
    const colB = Number(next?.col);

    if (!Number.isFinite(rowA) || !Number.isFinite(colA) || !Number.isFinite(rowB) || !Number.isFinite(colB)) {
      continue;
    }

    if (rowB === rowA - 1 && colB === colA) {
      directions.push("up");
      continue;
    }
    if (rowB === rowA + 1 && colB === colA) {
      directions.push("down");
      continue;
    }
    if (rowB === rowA && colB === colA - 1) {
      directions.push("left");
      continue;
    }
    if (rowB === rowA && colB === colA + 1) {
      directions.push("right");
      continue;
    }
  }

  return directions;
}

function getZipStartCell(result) {
  const start = result?.start_cell;
  const startRow = Number(start?.row);
  const startCol = Number(start?.col);
  if (Number.isFinite(startRow) && Number.isFinite(startCol)) {
    return { row: startRow, col: startCol };
  }

  const path = Array.isArray(result?.path) ? result.path : [];
  const first = path[0] || null;
  const pathRow = Number(first?.row);
  const pathCol = Number(first?.col);
  if (Number.isFinite(pathRow) && Number.isFinite(pathCol)) {
    return { row: pathRow, col: pathCol };
  }

  return null;
}

async function applyZipSolution(result, selection, settings) {
  const applySettings = normalizeApplySettings(settings);
  const normalized = normalizeSelection(selection || boardSelection);
  if (!normalized) {
    return { ok: false, error: "Board selection is required before applying moves." };
  }

  const boardSize = Number(result?.board_size);
  if (!boardSize) {
    return { ok: false, error: "Invalid board size in solution." };
  }

  const directions = buildZipDirectionList(result);
  if (!directions.length) {
    if (result?.solved) {
      return {
        ok: true,
        appliedCount: 0,
        clickCount: 0,
        keyCount: 0,
        strategy: "already-filled",
      };
    }
    return { ok: false, error: "No Zip path directions are available." };
  }

  const start = getZipStartCell(result);
  if (!start) {
    return { ok: false, error: "Zip solution is missing a start cell." };
  }

  const cellWidth = normalized.width / boardSize;
  const cellHeight = normalized.height / boardSize;

  const startX = normalized.x + (start.col + 0.5) * cellWidth;
  const startY = normalized.y + (start.row + 0.5) * cellHeight;

  const clicked = leftClickViewportPoint(startX, startY);
  if (!clicked) {
    return { ok: false, error: "Could not activate Zip start cell." };
  }

  await sleep(Math.max(80, applySettings.interClickDelayMs));

  let keyCount = 0;
  for (const direction of directions) {
    if (dispatchArrowKey(direction)) {
      keyCount += 1;
    }
    await sleep(applySettings.interMoveDelayMs);
  }

  return {
    ok: true,
    appliedCount: directions.length,
    clickCount: 1,
    keyCount,
    strategy: "start-click-then-arrows",
  };
}

async function applySolution(puzzleType, result, selection, settings) {
  if (puzzleType === "tango") {
    return applyTangoSolution(result, selection, settings);
  }

  if (puzzleType === "sudoku") {
    return applySudokuSolution(result, selection, settings);
  }

  if (puzzleType === "zip") {
    return applyZipSolution(result, selection, settings);
  }

  return applyQueensSolution(result, selection, settings);
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || !message.type) {
    return;
  }

  if (message.type === "startBoardSelection") {
    startBoardSelection()
      .then((selection) => sendResponse({ ok: true, selection }))
      .catch((error) => sendResponse({ ok: false, error: error.message || String(error) }));
    return true;
  }

  if (message.type === "setBoardSelection") {
    boardSelection = normalizeSelection(message.selection);
    sendResponse({ ok: Boolean(boardSelection), selection: boardSelection });
    return;
  }

  if (message.type === "getBoardSelection") {
    sendResponse({ ok: true, selection: boardSelection });
    return;
  }

  if (message.type === "getGameIframeRect") {
    const rect = getGameIframeRect(message.puzzleType);
    sendResponse({ ok: Boolean(rect), rect });
    return;
  }

  if (message.type === "autoDetectBoard") {
    boardSelection = autoDetectBoardSelectionWithFallback(message.puzzleType);
    sendResponse({ ok: Boolean(boardSelection), selection: boardSelection });
    return;
  }

  if (message.type === "getViewportMetrics") {
    const selection = getViewportSelection();
    sendResponse({
      ok: Boolean(selection),
      selection,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
        devicePixelRatio: window.devicePixelRatio,
      },
    });
    return;
  }

  if (message.type === "renderSolution") {
    try {
      renderSolutionOverlay(message.puzzleType, message.result, message.selection);
      sendResponse({ ok: true });
    } catch (error) {
      sendResponse({ ok: false, error: error.message || String(error) });
    }
    return;
  }

  if (message.type === "clearSolutionOverlay") {
    clearSolutionOverlay();
    sendResponse({ ok: true });
    return;
  }

  if (message.type === "applySolution") {
    applySolution(message.puzzleType, message.result, message.selection, message.settings)
      .then((resultPayload) => sendResponse(resultPayload))
      .catch((error) => sendResponse({ ok: false, error: error.message || String(error) }));
    return true;
  }
});

initializeQuickSolveWidget();
