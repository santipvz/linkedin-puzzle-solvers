let boardSelection = null;
let solutionOverlayRoot = null;

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

function detectLinkedInGameIframe(puzzleType) {
  const selectors = [];

  if (puzzleType) {
    selectors.push(`iframe[src*="/games/view/${puzzleType}/"]`);
  }

  selectors.push("iframe[src*='/games/view/']");
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

function autoDetectBoardSelection() {
  const selectors = [
    "canvas",
    "svg",
    "[role='grid']",
    "table",
    "div[class*='board']",
    "div[class*='grid']",
    "div[data-test*='board']",
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
  const directSelection = autoDetectBoardSelection();
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

  renderQueensOverlay(root, normalized, result);
}

function clickViewportPoint(x, y, button = 0) {
  const safeX = Math.max(0, Math.min(window.innerWidth - 1, x));
  const safeY = Math.max(0, Math.min(window.innerHeight - 1, y));
  const target = document.elementFromPoint(safeX, safeY);

  if (!target) {
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

  return {
    ok: true,
    appliedCount,
    clickCount,
    strategy,
    clicksPerValue: applySettings.tangoApplyMode === "right-moon" ? { 0: "right", 1: 1 } : { 0: 2, 1: 1 },
  };
}

async function applySolution(puzzleType, result, selection, settings) {
  if (puzzleType === "tango") {
    return applyTangoSolution(result, selection, settings);
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
