const DEFAULT_API_URL = "http://127.0.0.1:8000";
const STORAGE_API_KEY = "solver_api_url";
const STORAGE_PUZZLE_KEY = "solver_puzzle_type";
const STORAGE_AUTO_CLOSE_KEY = "solver_auto_close_after_apply";
const STORAGE_INTER_CLICK_DELAY_KEY = "solver_inter_click_delay_ms";
const STORAGE_INTER_MOVE_DELAY_KEY = "solver_inter_move_delay_ms";
const STORAGE_TANGO_APPLY_MODE_KEY = "solver_tango_apply_mode";

const DEFAULT_AUTO_CLOSE_AFTER_APPLY = true;
const DEFAULT_INTER_CLICK_DELAY_MS = 45;
const DEFAULT_INTER_MOVE_DELAY_MS = 40;
const DEFAULT_TANGO_APPLY_MODE = "left-cycle";

const puzzleTypeSelect = document.getElementById("puzzleType");
const apiUrlInput = document.getElementById("apiUrl");
const selectBoardButton = document.getElementById("selectBoard");
const autoDetectButton = document.getElementById("autoDetect");
const solveButton = document.getElementById("solveBoard");
const solveAndApplyButton = document.getElementById("solveAndApply");
const applyButton = document.getElementById("applyMoves");
const clearOverlayButton = document.getElementById("clearOverlay");
const autoCloseAfterApplyCheckbox = document.getElementById("autoCloseAfterApply");
const interClickDelayInput = document.getElementById("interClickDelayMs");
const interMoveDelayInput = document.getElementById("interMoveDelayMs");
const tangoApplyModeSelect = document.getElementById("tangoApplyMode");
const resultBox = document.getElementById("result");
const statusBox = document.getElementById("status");

function storageGet(keys) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get(keys, (items) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      resolve(items);
    });
  });
}

function storageSet(items) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.set(items, () => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      resolve();
    });
  });
}

function tabsQuery(queryInfo) {
  return new Promise((resolve, reject) => {
    chrome.tabs.query(queryInfo, (tabs) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      resolve(tabs);
    });
  });
}

function tabsGet(tabId) {
  return new Promise((resolve, reject) => {
    chrome.tabs.get(tabId, (tab) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      resolve(tab);
    });
  });
}

function sendTabMessage(tabId, message, options = {}) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, message, options, (response) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      resolve(response);
    });
  });
}

function executeContentScript(tabId, frameId = 0) {
  return new Promise((resolve, reject) => {
    const target = Number.isInteger(frameId) ? { tabId, frameIds: [frameId] } : { tabId };

    chrome.scripting.executeScript(
      {
        target,
        files: ["content.js"],
      },
      () => {
        const error = chrome.runtime.lastError;
        if (error) {
          reject(new Error(error.message));
          return;
        }
        resolve();
      }
    );
  });
}

function isNoReceiverError(error) {
  const message = error && error.message ? error.message : "";
  return message.includes("Receiving end does not exist");
}

async function sendTabMessageWithInjection(tabId, message, options = {}) {
  try {
    return await sendTabMessage(tabId, message, options);
  } catch (error) {
    if (!isNoReceiverError(error)) {
      throw error;
    }

    const frameId = Number.isInteger(options.frameId) ? options.frameId : 0;
    await executeContentScript(tabId, frameId);
    return sendTabMessage(tabId, message, options);
  }
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

function webNavigationGetAllFrames(tabId) {
  return new Promise((resolve, reject) => {
    chrome.webNavigation.getAllFrames({ tabId }, (frames) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      resolve(Array.isArray(frames) ? frames : []);
    });
  });
}

async function safeSendTabMessage(tabId, message, options = {}) {
  try {
    return await sendTabMessageWithInjection(tabId, message, options);
  } catch (error) {
    return null;
  }
}

function normalizeRect(rect) {
  if (!rect || typeof rect !== "object") {
    return null;
  }

  const left = Number(rect.left);
  const top = Number(rect.top);
  const width = Number(rect.width);
  const height = Number(rect.height);

  if (!Number.isFinite(left) || !Number.isFinite(top) || !Number.isFinite(width) || !Number.isFinite(height)) {
    return null;
  }

  if (width < 10 || height < 10) {
    return null;
  }

  return { left, top, width, height };
}

function normalizeViewport(viewport) {
  if (!viewport || typeof viewport !== "object") {
    return null;
  }

  const width = Number(viewport.width);
  const height = Number(viewport.height);

  if (!Number.isFinite(width) || !Number.isFinite(height)) {
    return null;
  }

  if (width < 10 || height < 10) {
    return null;
  }

  return { width, height };
}

function getFrameScale(iframeRect, frameViewport) {
  const rect = normalizeRect(iframeRect);
  const viewport = normalizeViewport(frameViewport);
  if (!rect || !viewport) {
    return { scaleX: 1, scaleY: 1 };
  }

  const scaleX = rect.width / viewport.width;
  const scaleY = rect.height / viewport.height;

  if (!Number.isFinite(scaleX) || !Number.isFinite(scaleY) || scaleX <= 0 || scaleY <= 0) {
    return { scaleX: 1, scaleY: 1 };
  }

  return { scaleX, scaleY };
}

function normalizeSelection(selection) {
  if (!selection || typeof selection !== "object") {
    return null;
  }

  const x = Number(selection.x);
  const y = Number(selection.y);
  const width = Number(selection.width);
  const height = Number(selection.height);
  const dpr = Number(selection.devicePixelRatio) || 1;

  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(width) || !Number.isFinite(height)) {
    return null;
  }

  if (width < 10 || height < 10) {
    return null;
  }

  return {
    x,
    y,
    width,
    height,
    devicePixelRatio: dpr,
  };
}

function translateFrameSelectionToTab(frameSelection, iframeRect, frameViewport) {
  const selection = normalizeSelection(frameSelection);
  const rect = normalizeRect(iframeRect);
  if (!selection || !rect) {
    return null;
  }

  const { scaleX, scaleY } = getFrameScale(rect, frameViewport);

  return normalizeSelection({
    x: rect.left + selection.x * scaleX,
    y: rect.top + selection.y * scaleY,
    width: selection.width * scaleX,
    height: selection.height * scaleY,
    devicePixelRatio: selection.devicePixelRatio,
  });
}

function translateTabSelectionToFrame(tabSelection, iframeRect, frameViewport) {
  const selection = normalizeSelection(tabSelection);
  const rect = normalizeRect(iframeRect);
  if (!selection || !rect) {
    return null;
  }

  const viewport = normalizeViewport(frameViewport);
  const { scaleX, scaleY } = getFrameScale(rect, viewport);

  const relativeX = (selection.x - rect.left) / scaleX;
  const relativeY = (selection.y - rect.top) / scaleY;

  const clampedX = Math.max(0, relativeX);
  const clampedY = Math.max(0, relativeY);
  const frameWidth = viewport ? viewport.width : rect.width / scaleX;
  const frameHeight = viewport ? viewport.height : rect.height / scaleY;
  const maxWidth = frameWidth - clampedX;
  const maxHeight = frameHeight - clampedY;

  if (maxWidth < 10 || maxHeight < 10) {
    return null;
  }

  return normalizeSelection({
    x: clampedX,
    y: clampedY,
    width: Math.min(selection.width / scaleX, maxWidth),
    height: Math.min(selection.height / scaleY, maxHeight),
    devicePixelRatio: selection.devicePixelRatio,
  });
}

function puzzleTypeToFrameSlug(puzzleType) {
  if (puzzleType === "sudoku") {
    return "mini-sudoku";
  }
  return puzzleType;
}

function findLinkedInGameFrame(frames, puzzleType) {
  if (!Array.isArray(frames) || !frames.length) {
    return null;
  }

  const exactNeedle = `/games/view/${puzzleTypeToFrameSlug(puzzleType)}/desktop`;
  const exactMatch = frames.find((frame) => typeof frame.url === "string" && frame.url.includes(exactNeedle));
  if (exactMatch) {
    return exactMatch;
  }

  return frames.find((frame) => typeof frame.url === "string" && frame.url.includes("/games/view")) || null;
}

async function getGameFrameContext(tabId, puzzleType) {
  let gameFrameId = 0;
  let iframeRect = null;
  let frameViewport = null;

  try {
    const frames = await webNavigationGetAllFrames(tabId);
    const gameFrame = findLinkedInGameFrame(frames, puzzleType);
    if (gameFrame && Number.isInteger(gameFrame.frameId)) {
      gameFrameId = gameFrame.frameId;
    }
  } catch (error) {
    gameFrameId = 0;
  }

  const iframeResponse = await safeSendTabMessage(
    tabId,
    { type: "getGameIframeRect", puzzleType },
    { frameId: 0 }
  );

  if (iframeResponse && iframeResponse.ok && iframeResponse.rect) {
    iframeRect = normalizeRect(iframeResponse.rect);
  }

  if (gameFrameId !== 0) {
    const frameViewportResponse = await safeSendTabMessage(tabId, { type: "getViewportMetrics" }, { frameId: gameFrameId });
    if (frameViewportResponse && frameViewportResponse.ok) {
      frameViewport = normalizeViewport(frameViewportResponse.viewport || frameViewportResponse.selection);
    }
  }

  return { gameFrameId, iframeRect, frameViewport };
}

function resolveInteractionTarget(topSelection, frameContext) {
  const selection = normalizeSelection(topSelection);
  if (!selection) {
    return null;
  }

  if (
    frameContext &&
    Number.isInteger(frameContext.gameFrameId) &&
    frameContext.gameFrameId !== 0 &&
    frameContext.iframeRect
  ) {
    const frameSelection = translateTabSelectionToFrame(selection, frameContext.iframeRect, frameContext.frameViewport);
    if (frameSelection) {
      return { frameId: frameContext.gameFrameId, selection: frameSelection };
    }
  }

  return { frameId: 0, selection };
}

function findLinkedInGameFrameIds(frames, puzzleType) {
  if (!Array.isArray(frames) || !frames.length) {
    return [];
  }

  const ids = [];
  const seen = new Set();

  const pushFrameId = (frame) => {
    if (!frame || !Number.isInteger(frame.frameId) || frame.frameId === 0) {
      return;
    }
    if (seen.has(frame.frameId)) {
      return;
    }
    seen.add(frame.frameId);
    ids.push(frame.frameId);
  };

  const exactNeedle = `/games/view/${puzzleTypeToFrameSlug(puzzleType)}`;
  for (const frame of frames) {
    if (typeof frame.url === "string" && frame.url.includes(exactNeedle)) {
      pushFrameId(frame);
    }
  }

  for (const frame of frames) {
    if (typeof frame.url === "string" && frame.url.includes("/games/view")) {
      pushFrameId(frame);
    }
  }

  for (const frame of frames) {
    if (typeof frame.url === "string" && frame.url.includes("linkedin.com")) {
      pushFrameId(frame);
    }
  }

  return ids;
}

async function buildApplyTargets(tabId, puzzleType, topSelection, frameContext, interactionTarget) {
  const normalizedTopSelection = normalizeSelection(topSelection);
  if (!normalizedTopSelection) {
    return [];
  }

  const targets = [];
  const seen = new Set();

  const pushTarget = (frameId, selection) => {
    if (!Number.isInteger(frameId)) {
      return;
    }

    const normalizedSelection = normalizeSelection(selection);
    if (!normalizedSelection) {
      return;
    }

    const key = `${frameId}:${Math.round(normalizedSelection.x)}:${Math.round(normalizedSelection.y)}:${Math.round(
      normalizedSelection.width
    )}:${Math.round(normalizedSelection.height)}`;

    if (seen.has(key)) {
      return;
    }

    seen.add(key);
    targets.push({ frameId, selection: normalizedSelection });
  };

  if (interactionTarget) {
    pushTarget(interactionTarget.frameId, interactionTarget.selection);
  }

  const mappedFrameSelection =
    frameContext && frameContext.iframeRect
      ? translateTabSelectionToFrame(normalizedTopSelection, frameContext.iframeRect, frameContext.frameViewport)
      : null;

  if (mappedFrameSelection) {
    if (frameContext && Number.isInteger(frameContext.gameFrameId) && frameContext.gameFrameId !== 0) {
      pushTarget(frameContext.gameFrameId, mappedFrameSelection);
    }

    try {
      const frames = await webNavigationGetAllFrames(tabId);
      const frameIds = findLinkedInGameFrameIds(frames, puzzleType);
      for (const frameId of frameIds) {
        pushTarget(frameId, mappedFrameSelection);
      }
    } catch (error) {
      // Ignore frame enumeration failures and fall back to top frame.
    }
  }

  pushTarget(0, normalizedTopSelection);
  return targets;
}

function hasMeaningfulSelectionDelta(baseSelection, nextSelection) {
  const base = normalizeSelection(baseSelection);
  const next = normalizeSelection(nextSelection);
  if (!base || !next) {
    return false;
  }

  return (
    Math.abs(base.x - next.x) > 2 ||
    Math.abs(base.y - next.y) > 2 ||
    Math.abs(base.width - next.width) > 2 ||
    Math.abs(base.height - next.height) > 2
  );
}

async function getActiveTab() {
  const tabs = await tabsQuery({ active: true, currentWindow: true });
  if (!tabs.length || !tabs[0].id) {
    throw new Error("No active tab found.");
  }
  return tabs[0];
}

function selectionStorageKey(tabId) {
  return `solver_last_solution_${tabId}`;
}

function setStatus(message, isError = false) {
  statusBox.textContent = message || "";
  statusBox.classList.toggle("error", isError);
}

function setResult(message) {
  resultBox.textContent = message;
}

function summarizeResult(puzzleType, result) {
  if (!result) {
    return "No result.";
  }

  const lines = [];
  lines.push(`Puzzle: ${puzzleType}`);
  lines.push(`Solved: ${Boolean(result.solved)}`);

  if (result.board_size) {
    lines.push(`Board size: ${result.board_size}`);
  }

  if (Array.isArray(result.moves)) {
    lines.push(`Moves: ${result.moves.length}`);
  }

  if (result.details && typeof result.details === "object") {
    for (const [key, value] of Object.entries(result.details)) {
      if (value && typeof value === "object") {
        lines.push(`${key}: ${JSON.stringify(value)}`);
      } else {
        lines.push(`${key}: ${value}`);
      }
    }
  }

  if (result.error) {
    lines.push(`Error: ${result.error}`);
  }

  return lines.join("\n");
}

function normalizeDelay(value, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(0, Math.min(500, Math.round(parsed)));
}

function normalizeTangoApplyMode(value) {
  if (value === "right-moon") {
    return "right-moon";
  }
  return "left-cycle";
}

function getApplySettingsFromUi() {
  return {
    autoCloseAfterApply: Boolean(autoCloseAfterApplyCheckbox.checked),
    interClickDelayMs: normalizeDelay(interClickDelayInput.value, DEFAULT_INTER_CLICK_DELAY_MS),
    interMoveDelayMs: normalizeDelay(interMoveDelayInput.value, DEFAULT_INTER_MOVE_DELAY_MS),
    tangoApplyMode: normalizeTangoApplyMode(tangoApplyModeSelect.value),
  };
}

async function savePreferences() {
  const applySettings = getApplySettingsFromUi();

  await storageSet({
    [STORAGE_API_KEY]: apiUrlInput.value.trim() || DEFAULT_API_URL,
    [STORAGE_PUZZLE_KEY]: puzzleTypeSelect.value,
    [STORAGE_AUTO_CLOSE_KEY]: applySettings.autoCloseAfterApply,
    [STORAGE_INTER_CLICK_DELAY_KEY]: applySettings.interClickDelayMs,
    [STORAGE_INTER_MOVE_DELAY_KEY]: applySettings.interMoveDelayMs,
    [STORAGE_TANGO_APPLY_MODE_KEY]: applySettings.tangoApplyMode,
  });
}

async function loadPreferences() {
  const stored = await storageGet([
    STORAGE_API_KEY,
    STORAGE_PUZZLE_KEY,
    STORAGE_AUTO_CLOSE_KEY,
    STORAGE_INTER_CLICK_DELAY_KEY,
    STORAGE_INTER_MOVE_DELAY_KEY,
    STORAGE_TANGO_APPLY_MODE_KEY,
  ]);

  apiUrlInput.value = stored[STORAGE_API_KEY] || DEFAULT_API_URL;
  puzzleTypeSelect.value = stored[STORAGE_PUZZLE_KEY] || "queens";

  const autoCloseStored = stored[STORAGE_AUTO_CLOSE_KEY];
  autoCloseAfterApplyCheckbox.checked =
    typeof autoCloseStored === "boolean" ? autoCloseStored : DEFAULT_AUTO_CLOSE_AFTER_APPLY;

  interClickDelayInput.value = String(
    normalizeDelay(stored[STORAGE_INTER_CLICK_DELAY_KEY], DEFAULT_INTER_CLICK_DELAY_MS)
  );
  interMoveDelayInput.value = String(
    normalizeDelay(stored[STORAGE_INTER_MOVE_DELAY_KEY], DEFAULT_INTER_MOVE_DELAY_MS)
  );
  tangoApplyModeSelect.value = normalizeTangoApplyMode(stored[STORAGE_TANGO_APPLY_MODE_KEY]);
}

async function getTopBoardSelection(tabId) {
  const existing = await safeSendTabMessage(tabId, { type: "getBoardSelection" }, { frameId: 0 });
  if (!existing || !existing.selection) {
    return null;
  }
  return normalizeSelection(existing.selection);
}

function selectionFromTabBounds(tab) {
  const width = Number(tab && tab.width);
  const height = Number(tab && tab.height);
  if (!Number.isFinite(width) || !Number.isFinite(height)) {
    return null;
  }

  return normalizeSelection({
    x: 0,
    y: 0,
    width,
    height,
    devicePixelRatio: 1,
  });
}

function selectionFromRect(rect, insetRatio = 0.04) {
  const normalizedRect = normalizeRect(rect);
  if (!normalizedRect) {
    return null;
  }

  const inset = Math.max(0, Math.min(normalizedRect.width, normalizedRect.height) * insetRatio);
  return normalizeSelection({
    x: normalizedRect.left + inset,
    y: normalizedRect.top + inset,
    width: Math.max(10, normalizedRect.width - inset * 2),
    height: Math.max(10, normalizedRect.height - inset * 2),
    devicePixelRatio: 1,
  });
}

function maybeNormalizeSelectionForPuzzle(puzzleType, selection, frameContext) {
  const normalized = normalizeSelection(selection);
  if (!normalized) {
    return null;
  }

  if (puzzleType !== "tango") {
    return normalized;
  }

  const frameSelection = selectionFromRect(frameContext && frameContext.iframeRect, 0);
  if (!frameSelection) {
    return normalized;
  }

  const tooLargeForFrame =
    normalized.width > frameSelection.width * 0.95 ||
    normalized.height > frameSelection.height * 0.95;

  if (!tooLargeForFrame) {
    return normalized;
  }

  return centeredBoardSelection(frameSelection) || normalized;
}

function centeredBoardSelection(baseSelection) {
  const normalized = normalizeSelection(baseSelection);
  if (!normalized) {
    return null;
  }

  const side = Math.max(10, Math.min(normalized.width * 0.74, normalized.height * 0.86));
  const x = normalized.x + (normalized.width - side) / 2;
  const y = normalized.y + (normalized.height - side) / 2;

  return normalizeSelection({
    x,
    y,
    width: side,
    height: side,
    devicePixelRatio: normalized.devicePixelRatio,
  });
}

async function getViewportFallbackSelection(tab) {
  const viewportResponse = await safeSendTabMessage(tab.id, { type: "getViewportMetrics" }, { frameId: 0 });
  if (viewportResponse && viewportResponse.ok && viewportResponse.selection) {
    const viewportSelection = normalizeSelection(viewportResponse.selection);
    if (viewportSelection) {
      return centeredBoardSelection(viewportSelection) || viewportSelection;
    }
  }

  const tabSelection = selectionFromTabBounds(tab);
  if (!tabSelection) {
    return null;
  }

  return centeredBoardSelection(tabSelection) || tabSelection;
}

async function setTopBoardSelection(tabId, selection) {
  const normalized = normalizeSelection(selection);
  if (!normalized) {
    return null;
  }

  const response = await safeSendTabMessage(
    tabId,
    { type: "setBoardSelection", selection: normalized },
    { frameId: 0 }
  );

  if (!response || !response.ok) {
    return null;
  }

  return normalizeSelection(response.selection);
}

async function ensureBoardSelection(tabId, puzzleType, frameContext) {
  const existing = await getTopBoardSelection(tabId);
  if (existing) {
    const normalizedExisting = maybeNormalizeSelectionForPuzzle(puzzleType, existing, frameContext);
    if (normalizedExisting && hasMeaningfulSelectionDelta(existing, normalizedExisting)) {
      const savedNormalized = await setTopBoardSelection(tabId, normalizedExisting);
      if (savedNormalized) {
        setStatus("Adjusted board region for Tango grid.");
        return savedNormalized;
      }
    }
    return normalizedExisting || existing;
  }

  if (
    frameContext &&
    Number.isInteger(frameContext.gameFrameId) &&
    frameContext.gameFrameId !== 0 &&
    frameContext.iframeRect
  ) {
    const frameDetected = await safeSendTabMessage(
      tabId,
      { type: "autoDetectBoard", puzzleType },
      { frameId: frameContext.gameFrameId }
    );

    if (frameDetected && frameDetected.selection) {
      const topSelection = translateFrameSelectionToTab(
        frameDetected.selection,
        frameContext.iframeRect,
        frameContext.frameViewport
      );
      const normalizedTopSelection = maybeNormalizeSelectionForPuzzle(puzzleType, topSelection, frameContext);
      if (normalizedTopSelection) {
        const savedSelection = await setTopBoardSelection(tabId, normalizedTopSelection);
        if (savedSelection) {
          setStatus("Board auto-detected inside game frame.");
          return savedSelection;
        }
      }
    }
  }

  const topDetected = await safeSendTabMessage(
    tabId,
    { type: "autoDetectBoard", puzzleType },
    { frameId: 0 }
  );

  if (topDetected && topDetected.selection) {
    const normalizedTopSelection = maybeNormalizeSelectionForPuzzle(puzzleType, topDetected.selection, frameContext);
    if (normalizedTopSelection) {
      setStatus("Board auto-detected.");
      return normalizedTopSelection;
    }
  }

  const frameBaseSelection = selectionFromRect(frameContext && frameContext.iframeRect, 0.04);
  const frameFallbackSelection = frameBaseSelection;

  if (frameFallbackSelection) {
    const savedSelection = await setTopBoardSelection(tabId, frameFallbackSelection);
    if (savedSelection) {
      setStatus("Board auto-detect missed; using game-frame fallback.");
      return savedSelection;
    }
  }

  const tab = await tabsGet(tabId);
  const fallbackSelection = await getViewportFallbackSelection(tab);
  if (fallbackSelection) {
    const savedSelection = await setTopBoardSelection(tabId, fallbackSelection);
    if (savedSelection) {
      setStatus("Board auto-detect missed; using viewport fallback.");
      return savedSelection;
    }
  }

  throw new Error("No board region selected. Use Select Board first.");
}

function setBusy(isBusy) {
  selectBoardButton.disabled = isBusy;
  autoDetectButton.disabled = isBusy;
  solveButton.disabled = isBusy;
  solveAndApplyButton.disabled = isBusy;
  applyButton.disabled = isBusy;
  clearOverlayButton.disabled = isBusy;
  autoCloseAfterApplyCheckbox.disabled = isBusy;
  interClickDelayInput.disabled = isBusy;
  interMoveDelayInput.disabled = isBusy;
  tangoApplyModeSelect.disabled = isBusy;
}

async function clearOverlaysForFrameContext(tabId, frameContext) {
  await safeSendTabMessage(tabId, { type: "clearSolutionOverlay" }, { frameId: 0 });

  if (frameContext && frameContext.gameFrameId && frameContext.gameFrameId !== 0) {
    await safeSendTabMessage(tabId, { type: "clearSolutionOverlay" }, { frameId: frameContext.gameFrameId });
  }
}

async function handleSelectBoard() {
  const tab = await getActiveTab();
  const response = await sendTabMessageWithInjection(tab.id, { type: "startBoardSelection" }, { frameId: 0 });

  if (!response || !response.ok) {
    throw new Error((response && response.error) || "Board selection failed.");
  }

  setStatus("Board region selected.");
}

async function handleAutoDetect() {
  const tab = await getActiveTab();
  const puzzleType = puzzleTypeSelect.value;
  const frameContext = await getGameFrameContext(tab.id, puzzleType);

  if (
    Number.isInteger(frameContext.gameFrameId) &&
    frameContext.gameFrameId !== 0 &&
    frameContext.iframeRect
  ) {
    const frameResponse = await safeSendTabMessage(
      tab.id,
      { type: "autoDetectBoard", puzzleType },
      { frameId: frameContext.gameFrameId }
    );

    if (frameResponse && frameResponse.ok && frameResponse.selection) {
      const topSelection = translateFrameSelectionToTab(
        frameResponse.selection,
        frameContext.iframeRect,
        frameContext.frameViewport
      );
      const normalizedTopSelection = maybeNormalizeSelectionForPuzzle(puzzleType, topSelection, frameContext);
      const saved = await setTopBoardSelection(tab.id, normalizedTopSelection);
      if (saved) {
        setStatus("Board auto-detected inside game frame.");
        return;
      }
    }
  }

  const response = await sendTabMessageWithInjection(
    tab.id,
    { type: "autoDetectBoard", puzzleType },
    { frameId: 0 }
  );

  if (!response || !response.ok || !response.selection) {
    const frameBaseSelection = selectionFromRect(frameContext && frameContext.iframeRect, 0.04);
    const frameFallbackSelection = frameBaseSelection;

    if (frameFallbackSelection) {
      const savedSelection = await setTopBoardSelection(tab.id, frameFallbackSelection);
      if (savedSelection) {
        setStatus("Board auto-detect missed; using game-frame fallback.");
        return;
      }
    }

    const fallbackSelection = await getViewportFallbackSelection(tab);
    if (fallbackSelection) {
      const savedSelection = await setTopBoardSelection(tab.id, fallbackSelection);
      if (savedSelection) {
        setStatus("Board auto-detect missed; using viewport fallback.");
        return;
      }
    }

    throw new Error("Could not auto-detect a board. Use Select Board.");
  }

  const normalizedDetected = maybeNormalizeSelectionForPuzzle(puzzleType, response.selection, frameContext);
  if (!normalizedDetected) {
    throw new Error("Could not normalize detected board region.");
  }

  const savedSelection = await setTopBoardSelection(tab.id, normalizedDetected);
  if (!savedSelection) {
    throw new Error("Could not save detected board region.");
  }

  setStatus("Board auto-detected.");
}

async function solveForTab(tab, options = {}) {
  const renderSolution = options.renderSolution !== false;
  const puzzleType = puzzleTypeSelect.value;
  const apiBaseUrl = apiUrlInput.value.trim() || DEFAULT_API_URL;

  const frameContext = await getGameFrameContext(tab.id, puzzleType);
  await clearOverlaysForFrameContext(tab.id, frameContext);
  const topSelection = await ensureBoardSelection(tab.id, puzzleType, frameContext);

  const solveResponse = await sendRuntimeMessage({
    type: "solveBoard",
    tabId: tab.id,
    puzzleType,
    apiBaseUrl,
    selection: topSelection,
  });

  if (!solveResponse || !solveResponse.ok) {
    throw new Error((solveResponse && solveResponse.error) || "Solver request failed.");
  }

  const solveSelection = normalizeSelection(solveResponse.selection) || topSelection;
  if (hasMeaningfulSelectionDelta(topSelection, solveSelection)) {
    await setTopBoardSelection(tab.id, solveSelection);
  }

  if (renderSolution) {
    const interactionTarget = resolveInteractionTarget(solveSelection, frameContext);
    if (!interactionTarget) {
      throw new Error("Could not map board selection for rendering.");
    }

    let renderResponse = await safeSendTabMessage(
      tab.id,
      {
        type: "renderSolution",
        puzzleType: solveResponse.puzzleType,
        result: solveResponse.result,
        selection: interactionTarget.selection,
      },
      { frameId: interactionTarget.frameId }
    );

    if ((!renderResponse || !renderResponse.ok) && interactionTarget.frameId !== 0) {
      renderResponse = await safeSendTabMessage(
        tab.id,
        {
          type: "renderSolution",
          puzzleType: solveResponse.puzzleType,
          result: solveResponse.result,
          selection: solveSelection,
        },
        { frameId: 0 }
      );
    }

    if (!renderResponse || !renderResponse.ok) {
      throw new Error((renderResponse && renderResponse.error) || "Failed to render solution overlay.");
    }
  }

  const payload = {
    puzzleType: solveResponse.puzzleType,
    result: solveResponse.result,
    selection: solveSelection,
  };

  await storageSet({
    [selectionStorageKey(tab.id)]: payload,
  });

  setResult(summarizeResult(solveResponse.puzzleType, solveResponse.result));
  if (solveResponse.result.solved) {
    setStatus(renderSolution ? "Solved and overlay rendered." : "Solved.");
  } else {
    setStatus("No solution found.", true);
  }

  return {
    ...payload,
    frameContext,
  };
}

function buildApplyStatusText(response) {
  const appliedText =
    typeof response.appliedCount === "number"
      ? `Applied ${response.appliedCount} moves.`
      : "Applied solution.";

  let clickText = "";
  if (typeof response.clickCount === "number" && typeof response.clicksPerMove === "number") {
    clickText = ` (${response.clickCount} clicks, ${response.clicksPerMove} per move)`;
  } else if (typeof response.clickCount === "number") {
    clickText = ` (${response.clickCount} clicks)`;
  }

  const strategyText =
    typeof response.strategy === "string" && response.strategy
      ? ` [${response.strategy}]`
      : "";

  const keyText = typeof response.keyCount === "number" ? ` (${response.keyCount} key events)` : "";

  return `${appliedText}${clickText}${keyText}${strategyText}`;
}

async function applyPayloadToTab(tab, payload, frameContext) {
  const topSelection = normalizeSelection(payload.selection);
  if (!topSelection) {
    throw new Error("Could not map board selection for applying moves.");
  }

  const interactionTarget = resolveInteractionTarget(topSelection, frameContext);
  const applyTargets = await buildApplyTargets(tab.id, payload.puzzleType, topSelection, frameContext, interactionTarget);

  if (!applyTargets.length) {
    throw new Error("Could not map board selection for applying moves.");
  }

  const applySettings = getApplySettingsFromUi();
  const messagePayloadBase = {
    type: "applySolution",
    puzzleType: payload.puzzleType,
    result: payload.result,
    settings: {
      interClickDelayMs: applySettings.interClickDelayMs,
      interMoveDelayMs: applySettings.interMoveDelayMs,
      tangoApplyMode: applySettings.tangoApplyMode,
    },
  };

  let response = null;
  for (const target of applyTargets) {
    response = await safeSendTabMessage(
      tab.id,
      {
        ...messagePayloadBase,
        selection: target.selection,
      },
      { frameId: target.frameId }
    );

    if ((!response || !response.ok) && payload.puzzleType === "sudoku") {
      response = await safeSendTabMessage(
        tab.id,
        {
          ...messagePayloadBase,
          selection: null,
        },
        { frameId: target.frameId }
      );
    }

    if (response && response.ok) {
      break;
    }
  }

  if ((!response || !response.ok) && payload.puzzleType === "sudoku") {
    const attemptedFrameIds = new Set(applyTargets.map((target) => target.frameId));
    const fallbackFrameIds = [];
    const seenFallbackFrameIds = new Set();

    const pushFallbackFrameId = (frameId) => {
      if (!Number.isInteger(frameId) || frameId === 0) {
        return;
      }
      if (attemptedFrameIds.has(frameId) || seenFallbackFrameIds.has(frameId)) {
        return;
      }
      seenFallbackFrameIds.add(frameId);
      fallbackFrameIds.push(frameId);
    };

    pushFallbackFrameId(frameContext && frameContext.gameFrameId);

    try {
      const frames = await webNavigationGetAllFrames(tab.id);
      const frameIds = findLinkedInGameFrameIds(frames, payload.puzzleType);
      for (const frameId of frameIds) {
        pushFallbackFrameId(frameId);
      }
    } catch (error) {
      // Ignore frame enumeration failures and keep the latest apply response.
    }

    for (const frameId of fallbackFrameIds) {
      response = await safeSendTabMessage(
        tab.id,
        {
          ...messagePayloadBase,
          selection: null,
        },
        { frameId }
      );

      if (response && response.ok) {
        break;
      }
    }
  }

  if (!response || !response.ok) {
    throw new Error((response && response.error) || "Failed to apply moves.");
  }

  await clearOverlaysForFrameContext(tab.id, frameContext);

  const statusText = buildApplyStatusText(response);
  if (applySettings.autoCloseAfterApply) {
    setStatus(`${statusText} Closing...`);
    setTimeout(() => {
      window.close();
    }, 420);
  } else {
    setStatus(statusText);
  }
}

async function handleSolve() {
  const tab = await getActiveTab();
  await solveForTab(tab);
}

async function handleApply() {
  const tab = await getActiveTab();
  const key = selectionStorageKey(tab.id);
  const stored = await storageGet([key]);
  const cached = stored[key];

  if (!cached || !cached.result || !cached.selection) {
    throw new Error("No cached solution for this tab. Solve first.");
  }

  const payload = {
    puzzleType: cached.puzzleType || puzzleTypeSelect.value,
    result: cached.result,
    selection: cached.selection,
  };

  const frameContext = await getGameFrameContext(tab.id, payload.puzzleType);
  await applyPayloadToTab(tab, payload, frameContext);
}

async function handleSolveAndApply() {
  const tab = await getActiveTab();
  const solvedPayload = await solveForTab(tab, { renderSolution: false });

  if (!solvedPayload.result || !solvedPayload.result.solved) {
    return;
  }

  await applyPayloadToTab(tab, solvedPayload, solvedPayload.frameContext);
}

async function handleClearOverlay() {
  const tab = await getActiveTab();
  const puzzleType = puzzleTypeSelect.value;
  const frameContext = await getGameFrameContext(tab.id, puzzleType);

  await clearOverlaysForFrameContext(tab.id, frameContext);

  setStatus("Overlay cleared.");
}

async function runAction(action) {
  setBusy(true);
  setStatus("");

  try {
    await savePreferences();
    await action();
  } catch (error) {
    setStatus(error.message || String(error), true);
  } finally {
    setBusy(false);
  }
}

selectBoardButton.addEventListener("click", () => runAction(handleSelectBoard));
autoDetectButton.addEventListener("click", () => runAction(handleAutoDetect));
solveButton.addEventListener("click", () => runAction(handleSolve));
solveAndApplyButton.addEventListener("click", () => runAction(handleSolveAndApply));
applyButton.addEventListener("click", () => runAction(handleApply));
clearOverlayButton.addEventListener("click", () => runAction(handleClearOverlay));

loadPreferences().catch((error) => {
  setStatus(error.message || String(error), true);
});
