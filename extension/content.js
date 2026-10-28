let boardSelection = null;
let solutionOverlayRoot = null;
let quickSolveWidgetRoot = null;
let quickSolveButton = null;
let quickSolveStatus = null;
let quickSolveBusy = false;
let quickSolveObservedUrl = "";
let sudokuApplyBusy = false;

const puzzleRegistry = globalThis.PuzzleRegistry;
if (!puzzleRegistry) {
  throw new Error("PuzzleRegistry is not available in content context.");
}

const { detectPuzzleTypeFromUrl, puzzleTypeToLabel, puzzleTypeToFrameSlug } = puzzleRegistry;
if (
  typeof detectPuzzleTypeFromUrl !== "function" ||
  typeof puzzleTypeToLabel !== "function" ||
  typeof puzzleTypeToFrameSlug !== "function"
) {
  throw new Error("PuzzleRegistry is missing required content helpers.");
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
  quickSolveStatus.hidden = !text;
  quickSolveStatus.classList.toggle("error", isError);
}

function updateQuickSolveButtonText() {
  if (!quickSolveButton) {
    return;
  }

  const puzzleType = detectPuzzleTypeFromPage();
  const puzzleLabel = puzzleTypeToLabel(puzzleType);

  if (quickSolveBusy) {
    quickSolveButton.textContent = `Solving ${puzzleLabel}\u2026`;
  } else {
    quickSolveButton.textContent = `Solve ${puzzleLabel}`;
  }
  quickSolveButton.setAttribute("aria-label", quickSolveButton.textContent);
  quickSolveButton.setAttribute("aria-busy", String(quickSolveBusy));
  quickSolveButton.style.backgroundImage = `url("${chrome.runtime.getURL(`assets/games/${puzzleType}.svg`)}")`;
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
    setQuickSolveStatus("Open Queens, Tango, Mini Sudoku, Zip, Patches, or Wend page.", true);
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
  setQuickSolveStatus("Solving and applying to the board\u2026");

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
      setQuickSolveStatus(`Preview ready \u00b7 ${moves} moves marked.`);
      return;
    }

    if (!response.applied) {
      setQuickSolveStatus(`Solved, but apply failed: ${response.error || "unknown"}`, true);
      return;
    }

    const appliedCount = Number(response.appliedCount) || 0;
    setQuickSolveStatus(`Solution applied \u00b7 ${appliedCount} moves.`);
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
  // Keep the page's styles from changing the extension's controls.
  const shadow = container.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = `
    :host { all: initial; }
    * { box-sizing: border-box; }
    .widget { width: 210px; max-width: calc(100vw - 32px); padding: 12px;
      border: 1px solid #cbd9e5; border-radius: 10px; background: #f5f8fb;
      box-shadow: 0 4px 20px #18354d14; color: #18354d;
      font: 12px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .title { display: flex; align-items: center; gap: 7px; margin-bottom: 12px;
      font-size: 11px; font-weight: 600; letter-spacing: -.1px; }
    .title img { width: 30px; height: 24px; border-radius: 3px; object-fit: contain; }
    button { display: flex; justify-content: space-between; align-items: center; gap: 10px;
      width: 100%; padding: 11px 10px 11px 39px; border: 1px solid #0a66c2; border-radius: 6px;
      background-color: #0a66c2; background-size: 23px; background-position: 9px center;
      background-repeat: no-repeat; color: #ffffff; text-align: left;
      font: 550 12px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      cursor: pointer; transition: background .15s; }
    button::after { content: "\\2192"; color: #d5ecff; font-size: 16px; }
    button:hover { background-color: #08549e; }
    button:focus-visible { outline: 2px solid #0a73c7; outline-offset: 3px; }
    button:disabled { opacity: .6; cursor: wait; }
    button[aria-busy="true"]::after { content: ""; width: 12px; height: 12px;
      flex: none; border: 1.5px solid #ffffff40; border-top-color: #d5ecff;
      border-radius: 50%; animation: spin .8s linear infinite; }
    .status { margin: 10px 0 0; font-size: 11px; line-height: 1.5;
      color: #4f6c85; overflow-wrap: anywhere; }
    .status.error { color: #aa3827; }
    [hidden] { display: none; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @media (prefers-reduced-motion: reduce) { *, *::after { animation: none !important; transition: none !important; } }
  `;
  const panel = document.createElement("section");
  panel.className = "widget";
  panel.setAttribute("aria-label", "Puzzle Solver");

  const title = document.createElement("div");
  title.className = "title";
  const logo = document.createElement("img");
  logo.src = chrome.runtime.getURL("assets/logo.png");
  logo.alt = "";
  title.append(logo, "Puzzle Solver");

  const button = document.createElement("button");
  button.type = "button";
  button.addEventListener("click", () => {
    onQuickSolveClick();
  });

  const status = document.createElement("p");
  status.className = "status";
  status.hidden = true;
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  status.setAttribute("aria-atomic", "true");

  panel.append(title, button, status);
  shadow.append(style, panel);
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
      boardSelection = null;
      clearSolutionOverlay();
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

function getBoardBboxFromResult(result) {
  const details = result && typeof result === "object" ? result.details : null;
  const bbox = details && typeof details === "object" ? details.board_bbox || details.crop_bbox || null : null;
  if (!bbox || typeof bbox !== "object") {
    return null;
  }

  const x = Number(bbox.x);
  const y = Number(bbox.y);
  const width = Number(bbox.width);
  const height = Number(bbox.height);

  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(width) || !Number.isFinite(height)) {
    return null;
  }

  if (width < 20 || height < 20) {
    return null;
  }

  return { x, y, width, height };
}

function refineSelectionWithBoardBbox(selection, result) {
  const normalized = normalizeSelection(selection);
  const boardBbox = getBoardBboxFromResult(result);
  if (!normalized || !boardBbox) {
    return normalized;
  }

  const dpr = normalized.devicePixelRatio || 1;
  const selectionPixelWidth = normalized.width * dpr;
  const selectionPixelHeight = normalized.height * dpr;

  if (selectionPixelWidth <= 0 || selectionPixelHeight <= 0) {
    return normalized;
  }

  const bboxWidthRatio = boardBbox.width / selectionPixelWidth;
  const bboxHeightRatio = boardBbox.height / selectionPixelHeight;
  if (bboxWidthRatio >= 0.92 && bboxHeightRatio >= 0.92) {
    return normalized;
  }

  const maxX = normalized.x + normalized.width - 10;
  const maxY = normalized.y + normalized.height - 10;
  const refinedX = Math.max(normalized.x, Math.min(maxX, normalized.x + boardBbox.x / dpr));
  const refinedY = Math.max(normalized.y, Math.min(maxY, normalized.y + boardBbox.y / dpr));
  const remainingWidth = normalized.x + normalized.width - refinedX;
  const remainingHeight = normalized.y + normalized.height - refinedY;

  return normalizeSelection({
    x: refinedX,
    y: refinedY,
    width: Math.max(10, Math.min(boardBbox.width / dpr, remainingWidth)),
    height: Math.max(10, Math.min(boardBbox.height / dpr, remainingHeight)),
    devicePixelRatio: normalized.devicePixelRatio,
  });
}

function refineTangoSelection(selection, result) {
  return refineSelectionWithBoardBbox(selection, result) || normalizeSelection(selection);
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

function autoDetectBoardSelection(puzzleType) {
  // LinkedIn's generated class names no longer contain "board" or "grid".
  // Prefer the game-specific landmark over nearby illustrations and tutorials.
  if (puzzleType === "queens") {
    const board = document.querySelector("#queens-game-board");
    const rect = board?.getBoundingClientRect();
    if (isRectVisible(rect) && Math.abs(rect.width / rect.height - 1) < 0.1) {
      return normalizeSelection({ x: rect.left, y: rect.top, width: rect.width,
        height: rect.height, devicePixelRatio: window.devicePixelRatio });
    }
  }
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

  const detectedSelection = normalizeSelection({
    x: bestRect.left,
    y: bestRect.top,
    width: bestRect.width,
    height: bestRect.height,
    devicePixelRatio: window.devicePixelRatio,
  });

  if (puzzleType === "tango") {
    return refineTangoSelection(detectedSelection, null) || detectedSelection;
  }

  return detectedSelection;
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
    box.style.border = "2px solid #0a73c7";
    box.style.background = "rgba(10, 115, 199, 0.1)";
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

const PREVIEW_COLORS = ["#0a66c2", "#498bbd", "#364e68", "#248398", "#657c96", "#274e84"];

function createOverlayRoot(selection) {
  clearSolutionOverlay();
  const host = document.createElement("div");
  host.id = "puzzle-solver-preview";
  Object.assign(host.style, { position: "fixed", inset: "0", zIndex: "2147483646", pointerEvents: "none" });
  const root = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = `:host { all: initial; } * { box-sizing: border-box; }
    .frame { position: fixed; border: 1px solid #0a66c270; border-radius: 6px; pointer-events: none; }
    .badge { position: fixed; display: flex; align-items: center; gap: 7px; padding: 6px 9px;
      background: #ffffff; color: #245574; border: 1px solid #caddeb; border-radius: 5px;
      box-shadow: 0 2px 8px #18354d12; font: 550 11px/1.3 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .badge img { width: 16px; height: 16px; }
    svg { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  `;
  const frame = document.createElement("div");
  frame.className = "frame";
  Object.assign(frame.style, { left: `${selection.x}px`, top: `${selection.y}px`, width: `${selection.width}px`, height: `${selection.height}px` });
  root.append(style, frame);
  document.documentElement.appendChild(host);
  solutionOverlayRoot = host;
  return root;
}

function previewSvgNode(parent, name, attributes, text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  if (text !== undefined) node.textContent = text;
  parent.appendChild(node);
  return node;
}

function createPreviewCanvas(root, selection) {
  const svg = previewSvgNode(root, "svg", { width: selection.width, height: selection.height,
    viewBox: `0 0 ${selection.width} ${selection.height}`, role: "img", "aria-label": "Solution preview" });
  Object.assign(svg.style, { position: "fixed", left: `${selection.x}px`, top: `${selection.y}px`, overflow: "visible", pointerEvents: "none" });
  return svg;
}

function previewCell(svg, x, y, size, label, options = {}) {
  previewSvgNode(svg, "rect", { x: x - size / 2, y: y - size / 2, width: size, height: size,
    rx: size * .2, fill: options.fill || "#f0f7fd", stroke: "#8eb9dc", "stroke-width": 1.25 });
  previewSvgNode(svg, "text", { x, y, "text-anchor": "middle", "dominant-baseline": "central",
    fill: options.color || "#075da5", "font-size": size * .68, "font-weight": 600 }, label);
}

function renderQueensOverlay(root, selection, result) {
  const size = Number(result.board_size);
  if (!size || !Array.isArray(result.moves)) return;
  const svg = createPreviewCanvas(root, selection);
  const cw = selection.width / size, ch = selection.height / size;
  const markerSize = Math.max(20, Math.min(38, Math.min(cw, ch) * .64));
  for (const move of result.moves) {
    if (!Number.isFinite(Number(move.row)) || !Number.isFinite(Number(move.col))) continue;
    const x = (Number(move.col) + .5) * cw, y = (Number(move.row) + .5) * ch;
    previewSvgNode(svg, "rect", { x: x - markerSize / 2, y: y - markerSize / 2, width: markerSize,
      height: markerSize, rx: 7, fill: "#ffffff", stroke: "#0a66c2", "stroke-width": 1.5 });
    const crown = previewSvgNode(svg, "g", { transform: `translate(${x - markerSize * .36} ${y - markerSize * .36}) scale(${markerSize * .03})` });
    previewSvgNode(crown, "path", { d: "M3 7l4 4 5-7 5 7 4-4-2 12H5L3 7Zm3 15h12", fill: "#0a66c2",
      stroke: "#0a66c2", "stroke-width": 1.5, "stroke-linejoin": "round" });
  }
}

function renderTangoOverlay(root, selection, result) {
  const size = Number(result.board_size), grid = result.solution_grid;
  if (!size || !Array.isArray(grid)) return;
  const fixed = new Set((result.fixed_pieces || []).map((piece) => `${piece.row},${piece.col}`));
  const svg = createPreviewCanvas(root, selection);
  const cw = selection.width / size, ch = selection.height / size;
  const markerSize = Math.max(20, Math.min(36, Math.min(cw, ch) * .65));
  for (let row = 0; row < grid.length; row += 1) {
    for (let col = 0; col < (grid[row]?.length || 0); col += 1) {
      if (fixed.has(`${row},${col}`)) continue;
      const value = Number(grid[row][col]);
      if (value !== 0 && value !== 1) continue;
      previewCell(svg, (col + .5) * cw, (row + .5) * ch, markerSize,
        value === 0 ? "\u263e" : "\u2600", { color: value === 0 ? "#455c75" : "#0a66c2", fill: value === 0 ? "#eef2f7" : "#f0f7fd" });
    }
  }
}

function renderSudokuOverlay(root, selection, result) {
  const size = Number(result.board_size);
  if (!size || !Array.isArray(result.moves)) return;
  const svg = createPreviewCanvas(root, selection);
  const cw = selection.width / size, ch = selection.height / size;
  const markerSize = Math.max(20, Math.min(38, Math.min(cw, ch) * .66));
  for (const move of result.moves) {
    if (![move.row, move.col, move.value].every((value) => Number.isFinite(Number(value)))) continue;
    previewCell(svg, (Number(move.col) + .5) * cw, (Number(move.row) + .5) * ch, markerSize, String(move.value));
  }
}

function previewPath(svg, centers, color, width, letterGap = 0) {
  if (letterGap) {
    // Leave the letters uncovered, including at bends in a word path.
    for (let index = 1; index < centers.length; index += 1) {
      const a = centers[index - 1], b = centers[index];
      const length = Math.hypot(b.x - a.x, b.y - a.y);
      if (length <= letterGap * 2) continue;
      const dx = (b.x - a.x) / length * letterGap, dy = (b.y - a.y) / length * letterGap;
      previewPath(svg, [{ x: a.x + dx, y: a.y + dy }, { x: b.x - dx, y: b.y - dy }], color, width);
    }
    return;
  }
  const points = centers.map((point) => `${point.x},${point.y}`).join(" ");
  previewSvgNode(svg, "polyline", { points, fill: "none", stroke: "#ffffff", "stroke-width": width + 3,
    "stroke-linecap": "round", "stroke-linejoin": "round", opacity: .85 });
  previewSvgNode(svg, "polyline", { points, fill: "none", stroke: color, "stroke-width": width,
    "stroke-linecap": "round", "stroke-linejoin": "round" });
}

function renderZipOverlay(root, selection, result) {
  const size = Number(result.board_size), path = result.path;
  if (!size || !Array.isArray(path) || path.length < 2) return;
  const svg = createPreviewCanvas(root, selection);
  const cw = selection.width / size, ch = selection.height / size;
  const centers = path.map((point) => ({ x: (Number(point.col) + .5) * cw, y: (Number(point.row) + .5) * ch }));
  if (centers.some((point) => !Number.isFinite(point.x) || !Number.isFinite(point.y))) return;
  previewPath(svg, centers, "#0a66c2", Math.max(4, Math.min(6, cw * .12)));
  previewSvgNode(svg, "circle", { cx: centers[0].x, cy: centers[0].y, r: 6, fill: "#ffffff", stroke: "#0a66c2", "stroke-width": 2 });
  const end = centers[centers.length - 1];
  previewSvgNode(svg, "circle", { cx: end.x, cy: end.y, r: 6, fill: "#0a66c2", stroke: "#ffffff", "stroke-width": 2 });
  for (const clue of result.clues || []) {
    const x = (Number(clue.col) + .5) * cw, y = (Number(clue.row) + .5) * ch;
    if (![x, y, Number(clue.value)].every(Number.isFinite)) continue;
    previewSvgNode(svg, "circle", { cx: x, cy: y, r: 12, fill: "#ffffff", stroke: "#0a66c2", "stroke-width": 1.5 });
    previewSvgNode(svg, "text", { x, y, "text-anchor": "middle", "dominant-baseline": "central",
      fill: "#075da5", "font-size": 12, "font-weight": 600 }, String(clue.value));
  }
}

function buildWendWordList(result) {
  const normalizeWords = globalThis.WendPaths?.normalizeWords;
  return typeof normalizeWords === "function" ? normalizeWords(result) : [];
}

function renderWendOverlay(root, selection, result) {
  const size = Number(result?.board_size), words = buildWendWordList(result);
  if (!size || !words.length) return;
  const svg = createPreviewCanvas(root, selection);
  const cw = selection.width / size, ch = selection.height / size;
  for (let index = 0; index < words.length; index += 1) {
    const entry = words[index], color = PREVIEW_COLORS[index % PREVIEW_COLORS.length];
    const centers = entry.path.map((point) => ({ x: (point.col + .5) * cw, y: (point.row + .5) * ch }));
    if (!centers.length) continue;
    previewPath(svg, centers, color, Math.max(3, Math.min(5, cw * .08)), Math.min(16, Math.min(cw, ch) * .22));
    const end = centers[centers.length - 1];
    const labelWidth = Math.max(26, entry.word.length * 6 + 12);
    const x = Math.max(0, Math.min(selection.width - labelWidth, end.x - labelWidth / 2));
    const y = end.y + ch * .25;
    previewSvgNode(svg, "rect", { x, y, width: labelWidth, height: 18, rx: 4, fill: "#ffffff", stroke: color, "stroke-width": 1 });
    previewSvgNode(svg, "text", { x: x + labelWidth / 2, y: y + 9, "text-anchor": "middle",
      "dominant-baseline": "central", fill: color, "font-size": 10, "font-weight": 600 }, entry.word);
  }
}

function buildPatchesRegionList(result) {
  const boardSize = Number(result?.board_size);
  const rawRegions =
    Array.isArray(result?.regions) && result.regions.length > 0
      ? result.regions
      : Array.isArray(result?.moves)
      ? result.moves
      : [];

  return rawRegions
    .map((region) => {
      const top = Number(region?.top ?? region?.row ?? region?.start_row);
      const left = Number(region?.left ?? region?.col ?? region?.start_col);
      const height = Number(region?.height ?? region?.rows ?? region?.span_rows ?? 1);
      const width = Number(region?.width ?? region?.cols ?? region?.span_cols ?? 1);

      if (
        !Number.isInteger(top) ||
        !Number.isInteger(left) ||
        !Number.isInteger(height) ||
        !Number.isInteger(width) ||
        height < 1 ||
        width < 1
      ) {
        return null;
      }

      if (boardSize > 0) {
        if (top < 0 || left < 0 || top + height > boardSize || left + width > boardSize) {
          return null;
        }
      }

      return {
        top,
        left,
        height,
        width,
        area: height * width,
      };
    })
    .filter(Boolean);
}

function renderPatchesOverlay(root, selection, result) {
  const size = Number(result?.board_size), regions = buildPatchesRegionList(result);
  if (!size || !regions.length) return;
  const svg = createPreviewCanvas(root, selection);
  const cw = selection.width / size, ch = selection.height / size;
  for (let index = 0; index < regions.length; index += 1) {
    const region = regions[index], color = PREVIEW_COLORS[index % PREVIEW_COLORS.length];
    previewSvgNode(svg, "rect", { x: region.left * cw + 2, y: region.top * ch + 2,
      width: region.width * cw - 4, height: region.height * ch - 4, rx: 5,
      fill: color, "fill-opacity": .08, stroke: color, "stroke-width": 2 });
  }
}

function renderSolutionOverlay(puzzleType, result, selection) {
  let normalized = normalizeSelection(selection || boardSelection);
  if (!normalized) {
    throw new Error("Board region is not selected.");
  }

  if (puzzleType === "tango") {
    normalized = refineTangoSelection(normalized, result) || normalized;
  }

  const root = createOverlayRoot(normalized);

  const badge = document.createElement("div");
  badge.className = "badge";
  const icon = document.createElement("img");
  icon.src = chrome.runtime.getURL(`assets/games/${puzzleType}.svg`);
  icon.alt = "";
  badge.append(icon, `${puzzleTypeToLabel(puzzleType)} \u00b7 ${result?.solved ? "Preview" : "No solution"}`);
  badge.style.left = `${normalized.x}px`;
  badge.style.top = `${Math.max(8, normalized.y - 34)}px`;
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

  if (puzzleType === "patches") {
    renderPatchesOverlay(root, normalized, result);
    return;
  }

  if (puzzleType === "wend") {
    renderWendOverlay(root, normalized, result);
    return;
  }

  renderQueensOverlay(root, normalized, result);
}

function dispatchMouseEventAtViewportPoint(type, x, y, button = 0, buttons = 0) {
  const safeX = Math.max(0, Math.min(window.innerWidth - 1, Number(x)));
  const safeY = Math.max(0, Math.min(window.innerHeight - 1, Number(y)));
  const target = document.elementFromPoint(safeX, safeY);

  if (!target || target instanceof HTMLIFrameElement) {
    return false;
  }

  const event = new MouseEvent(type, {
    bubbles: true,
    cancelable: true,
    composed: true,
    clientX: safeX,
    clientY: safeY,
    button,
    buttons,
    view: window,
  });
  target.dispatchEvent(event);
  return true;
}

function clickViewportPoint(x, y, button = 0) {
  const isRightClick = button === 2;
  const eventTypes = isRightClick
    ? ["pointerdown", "mousedown", "pointerup", "mouseup", "contextmenu"]
    : ["pointerdown", "mousedown", "pointerup", "mouseup", "click"];
  const buttonMask = isRightClick ? 2 : 1;

  let dispatchedAny = false;
  for (const type of eventTypes) {
    const isDown = type === "pointerdown" || type === "mousedown";
    const eventButtons = isDown ? buttonMask : 0;
    if (dispatchMouseEventAtViewportPoint(type, x, y, button, eventButtons)) {
      dispatchedAny = true;
    }
  }

  return dispatchedAny;
}

function dragViewportPoints(startX, startY, endX, endY, steps = 6) {
  const safeSteps = Math.max(1, Math.min(12, Number(steps) || 6));

  const startedPointer = dispatchMouseEventAtViewportPoint("pointerdown", startX, startY, 0, 1);
  const startedMouse = dispatchMouseEventAtViewportPoint("mousedown", startX, startY, 0, 1);
  if (!startedPointer && !startedMouse) {
    return false;
  }

  for (let step = 1; step <= safeSteps; step += 1) {
    const ratio = step / safeSteps;
    const x = startX + (endX - startX) * ratio;
    const y = startY + (endY - startY) * ratio;
    dispatchMouseEventAtViewportPoint("pointermove", x, y, 0, 1);
    dispatchMouseEventAtViewportPoint("mousemove", x, y, 0, 1);
  }

  const endedPointer = dispatchMouseEventAtViewportPoint("pointerup", endX, endY, 0, 0);
  const endedMouse = dispatchMouseEventAtViewportPoint("mouseup", endX, endY, 0, 0);
  dispatchMouseEventAtViewportPoint("click", endX, endY, 0, 0);

  return endedPointer || endedMouse;
}

async function dragViewportPath(points, stepsPerSegment = 5) {
  if (!Array.isArray(points) || points.length < 2) {
    return false;
  }

  const first = points[0];
  const last = points[points.length - 1];
  const safeSteps = Math.max(1, Math.min(10, Number(stepsPerSegment) || 5));

  const startedPointer = dispatchMouseEventAtViewportPoint("pointerdown", first.x, first.y, 0, 1);
  const startedMouse = dispatchMouseEventAtViewportPoint("mousedown", first.x, first.y, 0, 1);
  if (!startedPointer && !startedMouse) {
    return false;
  }

  await sleep(16);

  for (let index = 0; index < points.length - 1; index += 1) {
    const current = points[index];
    const next = points[index + 1];
    for (let step = 1; step <= safeSteps; step += 1) {
      const ratio = step / safeSteps;
      const x = current.x + (next.x - current.x) * ratio;
      const y = current.y + (next.y - current.y) * ratio;
      dispatchMouseEventAtViewportPoint("pointermove", x, y, 0, 1);
      dispatchMouseEventAtViewportPoint("mousemove", x, y, 0, 1);
      await sleep(8);
    }
  }

  const endedPointer = dispatchMouseEventAtViewportPoint("pointerup", last.x, last.y, 0, 0);
  const endedMouse = dispatchMouseEventAtViewportPoint("mouseup", last.x, last.y, 0, 0);
  return endedPointer || endedMouse;
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

function leftDragViewportPoints(startX, startY, endX, endY) {
  return dragViewportPoints(startX, startY, endX, endY, 6);
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

  // A digit span or a multi-cell wrapper is not a cell.
  const minWidth = cellWidth * 0.7;
  const minHeight = cellHeight * 0.7;
  const maxWidth = cellWidth * 1.3;
  const maxHeight = cellHeight * 1.3;

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
  let geometricFallback = null;
  for (let depth = 0; current && depth < 8; depth += 1) {
    if (isLikelySudokuCellElement(current, selection, cellWidth, cellHeight)) {
      if (current.getAttribute("data-cell-idx") !== null) return current;
      if (!geometricFallback) geometricFallback = current;
    }
    current = current.parentElement;
  }

  return geometricFallback;
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

function readSudokuCellValue(cell, boardSize) {
  // Notes are candidates, never a committed value (even when only one is present).
  if (cell.querySelector(".sudoku-cell-notes")) return 0;
  const text = String(cell.textContent || "").trim();
  if (!text) return 0;
  if (!/^[1-9]$/.test(text)) return null;
  const value = Number(text);
  return value <= boardSize ? value : null;
}

function getSudokuSnapshot(selection, boardSize) {
  const normalized = normalizeSelection(selection);
  if (!normalized) return null;
  const cellWidth = normalized.width / boardSize;
  const cellHeight = normalized.height / boardSize;
  const cells = [];
  const seen = new Set();
  const geometry = [];
  const values = [];

  for (let row = 0; row < boardSize; row += 1) {
    for (let col = 0; col < boardSize; col += 1) {
      const x = normalized.x + (col + 0.5) * cellWidth;
      const y = normalized.y + (row + 0.5) * cellHeight;
      const cell = findSudokuCellElementAtPoint(x, y, normalized, cellWidth, cellHeight);
      const position = inferSudokuGridPositionFromCell(cell, normalized, cellWidth, cellHeight, boardSize);
      if (!cell || !cell.isConnected || seen.has(cell) || !position || position.row !== row || position.col !== col) {
        return null;
      }
      const cellIndex = cell.getAttribute("data-cell-idx");
      if (cellIndex !== null && Number(cellIndex) !== row * boardSize + col) return null;
      const rect = cell.getBoundingClientRect();
      if (Math.abs(rect.left + rect.width / 2 - x) > cellWidth * 0.25 ||
          Math.abs(rect.top + rect.height / 2 - y) > cellHeight * 0.25) {
        return null;
      }
      const value = readSudokuCellValue(cell, boardSize);
      if (value === null) return null;
      seen.add(cell);
      cells.push(cell);
      values.push(value);
      geometry.push(...[rect.left, rect.top, rect.width, rect.height].map(Math.round));
    }
  }
  return { cells, values, geometry: geometry.join(":") };
}

function scoreSudokuSelectionCandidate(candidate, boardSize) {
  return getSudokuSnapshot(candidate, boardSize) ? boardSize * boardSize : 0;
}

async function getReadySudokuSelectionCandidates(selection, boardSize, moves) {
  let previousGeometry = new Set();
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const ready = [];
    const currentGeometry = new Set();
    for (const entry of buildApplySelectionCandidates("sudoku", selection)) {
      if (!scoreSudokuSelectionCandidate(entry.selection, boardSize, moves)) continue;
      const snapshot = getSudokuSnapshot(entry.selection, boardSize);
      if (!snapshot) continue;
      currentGeometry.add(snapshot.geometry);
      if (previousGeometry.has(snapshot.geometry)) ready.push(entry);
    }
    if (ready.length) return ready;
    previousGeometry = currentGeometry;
    await sleep(100);
  }
  return [];
}

function isSudokuCellSelected(cell) {
  if (cell.getAttribute("data-cell-idx") !== null) {
    return cell.classList.contains("sudoku-cell-active");
  }
  return cell.getAttribute("aria-selected") === "true";
}

function sudokuNotesEnabled() {
  return Boolean(document.querySelector('[data-control-btn="notes"] .sudoku-under-board__text--active'));
}

function sudokuCompletionVisible() {
  if (!String(window.location?.pathname || "").includes("/mini-sudoku")) return false;
  const text = document.body?.innerText || "";
  return /Mini\s*Sudoku/i.test(text) && /(?:Resuelto en|Solved in)\s+\d+:\d{2}/i.test(text);
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

  const autoDetectedSelection = autoDetectBoardSelection(puzzleType);

  pushCandidate(primarySelection, "provided");
  pushCandidate(boardSelection, "stored");
  pushCandidate(autoDetectedSelection, "auto-detect");

  if (puzzleType === "sudoku" && candidates.length > 0) {
    const seedCandidates = [...candidates];
    for (const entry of seedCandidates) {
      const base = entry.selection;
      const deltaX = Math.max(1, base.width * 0.0125);
      const deltaY = Math.max(1, base.height * 0.0125);

      // Minor insets/outsets make the apply logic more tolerant to thin board borders.
      pushCandidate(
        {
          x: base.x + deltaX,
          y: base.y + deltaY,
          width: base.width - deltaX * 2,
          height: base.height - deltaY * 2,
          devicePixelRatio: base.devicePixelRatio,
        },
        `${entry.source}:inset`
      );

      pushCandidate(
        {
          x: base.x - deltaX,
          y: base.y - deltaY,
          width: base.width + deltaX * 2,
          height: base.height + deltaY * 2,
          devicePixelRatio: base.devicePixelRatio,
        },
        `${entry.source}:outset`
      );
    }
  }

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
  const normalized = refineTangoSelection(selection || boardSelection, result);
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
  if (sudokuApplyBusy) {
    return { ok: false, error: "Sudoku apply is already in progress.", inProgress: true };
  }
  sudokuApplyBusy = true;
  try {
    return await applyVerifiedSudokuSolution(result, selection, settings);
  } finally {
    sudokuApplyBusy = false;
  }
}

async function applyVerifiedSudokuSolution(result, selection, settings) {
  const applySettings = normalizeApplySettings(settings);
  const boardSize = Number(result?.board_size);
  if (boardSize !== 6) return { ok: false, error: "Invalid Mini Sudoku board size." };
  const moves = Array.isArray(result?.moves) ? result.moves : [];
  if (!moves.length) {
    return result?.solved
      ? { ok: true, appliedCount: 0, clickCount: 0, keyCount: 0, strategy: "already-filled" }
      : { ok: false, error: "No Sudoku solution moves are available." };
  }
  const actionableMoves = moves.map((move) => ({ row: Number(move?.row), col: Number(move?.col), value: Number(move?.value) }));
  const coordinates = new Set();
  for (const move of actionableMoves) {
    const coordinate = `${move.row}:${move.col}`;
    if (!Number.isInteger(move.row) || !Number.isInteger(move.col) || !Number.isInteger(move.value) ||
        move.row < 0 || move.row >= boardSize || move.col < 0 || move.col >= boardSize ||
        move.value < 1 || move.value > boardSize || coordinates.has(coordinate)) {
      return { ok: false, error: "Invalid or duplicate Sudoku solution moves." };
    }
    coordinates.add(coordinate);
  }

  const counts = { appliedCount: 0, clickCount: 0, keyCount: 0 };
  const fail = (error) => ({ ok: false, error, ...counts, strategy: "verified-cell-then-keyboard" });
  if (sudokuNotesEnabled()) {
    const control = document.querySelector('[data-control-btn="notes"]');
    const rect = control?.getBoundingClientRect();
    if (!rect || !leftClickViewportPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)) {
      return fail("Could not disable Sudoku notes mode.");
    }
    counts.clickCount += 1;
    for (let attempt = 0; attempt < 12 && sudokuNotesEnabled(); attempt += 1) await sleep(50);
    if (sudokuNotesEnabled()) return fail("Sudoku notes mode is still enabled. Stopped before typing.");
  }
  const selectionCandidates = await getReadySudokuSelectionCandidates(selection, boardSize, actionableMoves);
  if (!selectionCandidates.length) {
    return fail("Sudoku board is not ready: could not identify all 36 readable cells in a stable grid.");
  }
  // Choose once, before writing. Never replay a partially applied solution in another region.
  const candidate = selectionCandidates[0].selection;
  let snapshot = getSudokuSnapshot(candidate, boardSize);
  if (!snapshot) return fail("Sudoku board changed before applying moves.");
  const initialGrid = result?.initial_grid;
  if (Array.isArray(initialGrid) && initialGrid.length === boardSize && initialGrid.every((row) => Array.isArray(row) && row.length === boardSize)) {
    for (let index = 0; index < snapshot.values.length; index += 1) {
      const expected = Number(initialGrid[Math.floor(index / boardSize)][index % boardSize]);
      const move = actionableMoves.find((entry) => entry.row * boardSize + entry.col === index);
      if (snapshot.values[index] !== expected && (!move || snapshot.values[index] !== move.value)) {
        return fail("Sudoku board no longer matches the captured puzzle. Solve again before applying.");
      }
    }
  }

  const expectedFinalValues = snapshot.values.slice();
  for (const move of actionableMoves) expectedFinalValues[move.row * boardSize + move.col] = move.value;
  const completeSolution = expectedFinalValues.every((value) => Number.isInteger(value) && value >= 1 && value <= boardSize);

  for (const move of actionableMoves) {
    if (sudokuNotesEnabled()) return fail("Sudoku notes mode was enabled during apply. Stopped before typing.");
    const index = move.row * boardSize + move.col;
    snapshot = getSudokuSnapshot(candidate, boardSize);
    if (!snapshot) return fail("Sudoku grid moved or became unreadable. Stopped applying.");
    if (snapshot.values[index] === move.value) continue;
    const beforeValues = snapshot.values;
    const finishingMove = completeSolution && beforeValues.every((value, cellIndex) =>
      cellIndex === index || value === expectedFinalValues[cellIndex]);
    const geometry = snapshot.geometry;
    const rect = snapshot.cells[index].getBoundingClientRect();
    if (!leftClickViewportPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)) {
      return fail(`Could not select Sudoku cell (${move.row + 1}, ${move.col + 1}).`);
    }
    counts.clickCount += 1;
    await sleep(Math.max(80, applySettings.interClickDelayMs));

    // A click can rerender the whole grid. Reacquire the live cell and wait for selection.
    let live = null;
    for (let attempt = 0; attempt < 12; attempt += 1) {
      live = getSudokuSnapshot(candidate, boardSize);
      if (!live || live.geometry !== geometry) return fail("Sudoku grid moved while selecting a cell.");
      if (live.values.some((value, cellIndex) => value !== beforeValues[cellIndex])) {
        return fail("Sudoku board changed while selecting a cell. Stopped applying.");
      }
      if (isSudokuCellSelected(live.cells[index])) break;
      live = null;
      await sleep(50);
    }
    if (!live) return fail(`Sudoku did not select cell (${move.row + 1}, ${move.col + 1}). Stopped before typing.`);
    // Cells are non-focusable divs. Synthetic clicks do not perform the
    // browser's default focus action, so focus the game's keyboard surface.
    const keyboardTarget = live.cells[index].closest(".sudoku-grid") || live.cells[index];
    // One keydown per value. Sending keypress too can trigger a second input handler.
    if (!dispatchKeyboardKey(String(move.value), `Digit${move.value}`, 48 + move.value,
        { includeKeypress: false, target: keyboardTarget })) {
      return fail("Could not send a Sudoku number.");
    }
    counts.keyCount += 1;

    let verified = false;
    let completed = false;
    for (let attempt = 0; attempt < (finishingMove ? 40 : 16); attempt += 1) {
      const after = getSudokuSnapshot(candidate, boardSize);
      if (after) {
        if (after.geometry !== geometry || after.values.some((value, cellIndex) => cellIndex !== index && value !== beforeValues[cellIndex])) {
          return fail("Sudoku input changed another cell or the grid moved. Stopped without replaying moves.");
        }
        if (after.values[index] === move.value) { verified = true; break; }
        if (after.values[index] !== beforeValues[index]) return fail("Sudoku entered an unexpected number. Stopped applying.");
      } else if (completeSolution && (
        live.cells.every((cell, cellIndex) => readSudokuCellValue(cell, boardSize) === expectedFinalValues[cellIndex]) ||
        (finishingMove && sudokuCompletionVisible()))) {
        // The winning key can remove/cover the grid before the next snapshot.
        // Accept all 36 retained DOM values, or the game's explicit victory
        // receipt after the other 35 values were verified. Disappearance alone
        // is never success and no key is replayed.
        verified = true;
        completed = true;
        break;
      }
      await sleep(50);
    }
    if (!verified) return fail(`Sudoku did not confirm ${move.value} in cell (${move.row + 1}, ${move.col + 1}). Stopped without replaying moves.`);
    counts.appliedCount += 1;
    if (completed) return { ok: true, ...counts, strategy: "verified-completed-grid" };
    await sleep(applySettings.interMoveDelayMs);
  }
  return { ok: true, ...counts, strategy: "verified-cell-then-keyboard" };
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

async function applyPatchesSolution(result, selection, settings) {
  const applySettings = normalizeApplySettings(settings);
  const normalized = normalizeSelection(selection || boardSelection);
  if (!normalized) {
    return { ok: false, error: "Board selection is required before applying moves." };
  }

  const boardSize = Number(result?.board_size);
  if (!boardSize) {
    return { ok: false, error: "Invalid board size in solution." };
  }

  const regions = buildPatchesRegionList(result);
  if (!regions.length) {
    if (result?.solved) {
      return {
        ok: true,
        appliedCount: 0,
        clickCount: 0,
        strategy: "already-filled",
      };
    }
    return { ok: false, error: "No Patches regions are available." };
  }

  const cellWidth = normalized.width / boardSize;
  const cellHeight = normalized.height / boardSize;

  let appliedCount = 0;
  let clickCount = 0;

  for (const region of regions) {
    const startX = normalized.x + (region.left + 0.5) * cellWidth;
    const startY = normalized.y + (region.top + 0.5) * cellHeight;
    const endX = normalized.x + (region.left + region.width - 0.5) * cellWidth;
    const endY = normalized.y + (region.top + region.height - 0.5) * cellHeight;

    let applied = leftDragViewportPoints(startX, startY, endX, endY);
    if (!applied) {
      applied = leftDragViewportPoints(endX, endY, startX, startY);
    }

    if (applied) {
      appliedCount += 1;
      clickCount += 1;
    }

    // Patches updates its drag state asynchronously; rapid consecutive drags are dropped.
    await sleep(Math.max(150, applySettings.interMoveDelayMs));
  }

  if (appliedCount === 0) {
    return {
      ok: false,
      error: "Could not dispatch Patches drag gestures to board cells.",
      appliedCount,
      clickCount,
    };
  }

  return {
    ok: true,
    appliedCount,
    clickCount,
    strategy: "corner-to-corner-drag",
  };
}

async function applyWendSolution(result, selection, settings) {
  const applySettings = normalizeApplySettings(settings);
  const normalized = normalizeSelection(selection || boardSelection);
  if (!normalized) {
    return { ok: false, error: "Board selection is required before applying Wend paths." };
  }

  const boardSize = Number(result?.board_size);
  if (!boardSize) {
    return { ok: false, error: "Invalid board size in Wend solution." };
  }

  const words = buildWendWordList(result);
  if (!words.length) {
    return { ok: false, error: "No Wend word paths are available." };
  }

  const cellWidth = normalized.width / boardSize;
  const cellHeight = normalized.height / boardSize;
  let appliedCount = 0;

  for (const entry of words) {
    const points = entry.path.map((step) => ({
      x: normalized.x + (step.col + 0.5) * cellWidth,
      y: normalized.y + (step.row + 0.5) * cellHeight,
    }));

    if (await dragViewportPath(points, 4)) {
      appliedCount += 1;
    }

    await sleep(Math.max(80, applySettings.interMoveDelayMs));
  }

  if (appliedCount !== words.length) {
    return {
      ok: false,
      error: `Applied ${appliedCount} of ${words.length} Wend word paths.`,
      appliedCount,
    };
  }

  return {
    ok: true,
    appliedCount,
    clickCount: appliedCount,
    strategy: "word-path-drag",
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

  if (puzzleType === "patches") {
    return applyPatchesSolution(result, selection, settings);
  }

  if (puzzleType === "wend") {
    return applyWendSolution(result, selection, settings);
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
