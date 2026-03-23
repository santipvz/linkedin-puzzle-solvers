const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const DEFAULT_INTER_CLICK_DELAY_MS = 45;
const DEFAULT_INTER_MOVE_DELAY_MS = 40;
const DEFAULT_TANGO_APPLY_MODE = "left-cycle";

const STORAGE_API_KEY = "solver_api_url";
const STORAGE_INTER_CLICK_DELAY_KEY = "solver_inter_click_delay_ms";
const STORAGE_INTER_MOVE_DELAY_KEY = "solver_inter_move_delay_ms";
const STORAGE_TANGO_APPLY_MODE_KEY = "solver_tango_apply_mode";

function normalizeApiBase(value) {
  if (!value || typeof value !== "string") {
    return DEFAULT_API_BASE;
  }

  return value.trim().replace(/\/+$/, "") || DEFAULT_API_BASE;
}

function sanitizePuzzleType(value) {
  if (value === "tango") {
    return "tango";
  }
  if (value === "queens") {
    return "queens";
  }
  return null;
}

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
  return null;
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

  return { x, y, width, height, devicePixelRatio: dpr };
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

function translateFrameSelectionToTab(frameSelection, iframeRect) {
  const selection = normalizeSelection(frameSelection);
  const rect = normalizeRect(iframeRect);
  if (!selection || !rect) {
    return null;
  }

  return normalizeSelection({
    x: rect.left + selection.x,
    y: rect.top + selection.y,
    width: selection.width,
    height: selection.height,
    devicePixelRatio: selection.devicePixelRatio,
  });
}

function normalizeDelay(value, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }

  return Math.max(0, Math.min(500, Math.round(parsed)));
}

function normalizeTangoApplyMode(value) {
  return value === "right-moon" ? "right-moon" : "left-cycle";
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

function tabsSendMessage(tabId, message, options = {}) {
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

async function safeSendTabMessage(tabId, message, options = {}) {
  try {
    return await tabsSendMessage(tabId, message, options);
  } catch (error) {
    return null;
  }
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

function captureVisibleTab(windowId) {
  return new Promise((resolve, reject) => {
    chrome.tabs.captureVisibleTab(windowId, { format: "png" }, (dataUrl) => {
      const error = chrome.runtime.lastError;
      if (error) {
        const message = String(error.message || "");
        if (message.includes("Either the '<all_urls>' or 'activeTab' permission is required")) {
          reject(
            new Error(
              "Missing screenshot permission. Reload the extension and accept updated permissions."
            )
          );
          return;
        }

        reject(new Error(message));
        return;
      }
      resolve(dataUrl);
    });
  });
}

async function dataUrlToBlob(dataUrl) {
  const response = await fetch(dataUrl);
  return response.blob();
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

async function cropCapturedImage(dataUrl, selection) {
  const sourceBlob = await dataUrlToBlob(dataUrl);
  const normalized = normalizeSelection(selection);

  if (!normalized || typeof OffscreenCanvas === "undefined") {
    return sourceBlob;
  }

  const bitmap = await createImageBitmap(sourceBlob);

  const sx = Math.floor(normalized.x * normalized.devicePixelRatio);
  const sy = Math.floor(normalized.y * normalized.devicePixelRatio);
  const sw = Math.floor(normalized.width * normalized.devicePixelRatio);
  const sh = Math.floor(normalized.height * normalized.devicePixelRatio);

  const sourceX = clamp(sx, 0, bitmap.width - 1);
  const sourceY = clamp(sy, 0, bitmap.height - 1);
  const sourceW = clamp(sw, 1, bitmap.width - sourceX);
  const sourceH = clamp(sh, 1, bitmap.height - sourceY);

  if (sourceW <= 0 || sourceH <= 0) {
    bitmap.close();
    return sourceBlob;
  }

  const canvas = new OffscreenCanvas(sourceW, sourceH);
  const ctx = canvas.getContext("2d");
  ctx.drawImage(bitmap, sourceX, sourceY, sourceW, sourceH, 0, 0, sourceW, sourceH);
  bitmap.close();

  return canvas.convertToBlob({ type: "image/png" });
}

async function callSolverApi(apiBaseUrl, puzzleType, imageBlob) {
  const safePuzzleType = puzzleType === "tango" ? "tango" : "queens";
  const endpoint = `${normalizeApiBase(apiBaseUrl)}/solve/${safePuzzleType}`;

  const formData = new FormData();
  formData.append("image", imageBlob, `${safePuzzleType}_board.png`);

  const response = await fetch(endpoint, {
    method: "POST",
    body: formData,
  });

  const text = await response.text();
  let payload;

  try {
    payload = JSON.parse(text);
  } catch (error) {
    payload = { detail: text };
  }

  if (!response.ok) {
    const message = payload.detail || `Solver API request failed with status ${response.status}.`;
    throw new Error(message);
  }

  return payload;
}

async function solveBoardCore({ tabId, puzzleType, apiBaseUrl, selection }) {
  const tab = await tabsGet(tabId);
  const screenshotDataUrl = await captureVisibleTab(tab.windowId);
  const boardImage = await cropCapturedImage(screenshotDataUrl, selection);
  const result = await callSolverApi(apiBaseUrl, puzzleType, boardImage);

  return {
    result,
    selection: normalizeSelection(selection),
    puzzleType: puzzleType === "tango" ? "tango" : "queens",
  };
}

function findLinkedInGameFrame(frames, puzzleType) {
  if (!Array.isArray(frames) || !frames.length) {
    return null;
  }

  if (puzzleType) {
    const exactNeedle = `/games/view/${puzzleType}/desktop`;
    const exactMatch = frames.find((frame) => typeof frame.url === "string" && frame.url.includes(exactNeedle));
    if (exactMatch) {
      return exactMatch;
    }
  }

  return frames.find((frame) => typeof frame.url === "string" && frame.url.includes("/games/view/")) || null;
}

async function getGameFrameContext(tabId, puzzleType) {
  let gameFrameId = 0;
  let iframeRect = null;

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

  return { gameFrameId, iframeRect };
}

async function detectSelectionForQuickSolve(tabId, puzzleType, frameContext) {
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
      const topSelection = translateFrameSelectionToTab(frameDetected.selection, frameContext.iframeRect);
      if (topSelection) {
        return {
          topSelection,
          interactionFrameId: frameContext.gameFrameId,
          interactionSelection: normalizeSelection(frameDetected.selection),
        };
      }
    }
  }

  const topDetected = await safeSendTabMessage(tabId, { type: "autoDetectBoard", puzzleType }, { frameId: 0 });
  if (topDetected && topDetected.selection) {
    const topSelection = normalizeSelection(topDetected.selection);
    return {
      topSelection,
      interactionFrameId: 0,
      interactionSelection: topSelection,
    };
  }

  throw new Error("Could not auto-detect board region.");
}

async function applySolutionForSelection(
  tabId,
  puzzleType,
  result,
  interactionFrameId,
  interactionSelection,
  topSelection,
  applySettings
) {
  let response = await safeSendTabMessage(
    tabId,
    {
      type: "applySolution",
      puzzleType,
      result,
      selection: interactionSelection,
      settings: applySettings,
    },
    { frameId: interactionFrameId }
  );

  if ((!response || !response.ok) && interactionFrameId !== 0) {
    response = await safeSendTabMessage(
      tabId,
      {
        type: "applySolution",
        puzzleType,
        result,
        selection: topSelection,
        settings: applySettings,
      },
      { frameId: 0 }
    );
  }

  return response;
}

async function clearOverlaysForFrameContext(tabId, frameContext) {
  await safeSendTabMessage(tabId, { type: "clearSolutionOverlay" }, { frameId: 0 });

  if (frameContext && frameContext.gameFrameId && frameContext.gameFrameId !== 0) {
    await safeSendTabMessage(tabId, { type: "clearSolutionOverlay" }, { frameId: frameContext.gameFrameId });
  }
}

async function loadQuickSettings() {
  const stored = await storageGet([
    STORAGE_API_KEY,
    STORAGE_INTER_CLICK_DELAY_KEY,
    STORAGE_INTER_MOVE_DELAY_KEY,
    STORAGE_TANGO_APPLY_MODE_KEY,
  ]);

  return {
    apiBaseUrl: normalizeApiBase(stored[STORAGE_API_KEY] || DEFAULT_API_BASE),
    applySettings: {
      interClickDelayMs: normalizeDelay(stored[STORAGE_INTER_CLICK_DELAY_KEY], DEFAULT_INTER_CLICK_DELAY_MS),
      interMoveDelayMs: normalizeDelay(stored[STORAGE_INTER_MOVE_DELAY_KEY], DEFAULT_INTER_MOVE_DELAY_MS),
      tangoApplyMode: normalizeTangoApplyMode(stored[STORAGE_TANGO_APPLY_MODE_KEY] || DEFAULT_TANGO_APPLY_MODE),
    },
  };
}

async function solveBoardRequest(message) {
  const safePuzzleType = sanitizePuzzleType(message.puzzleType) || "queens";

  return solveBoardCore({
    tabId: message.tabId,
    puzzleType: safePuzzleType,
    apiBaseUrl: normalizeApiBase(message.apiBaseUrl),
    selection: message.selection,
  });
}

async function quickSolveFromPage(message, sender) {
  const tabId = sender && sender.tab && Number.isInteger(sender.tab.id) ? sender.tab.id : null;
  if (tabId === null) {
    throw new Error("Could not resolve active game tab.");
  }

  const tab = await tabsGet(tabId);
  const requestedPuzzleType = sanitizePuzzleType(message.puzzleType);
  const detectedPuzzleType = detectPuzzleTypeFromUrl(tab.url);
  const puzzleType = requestedPuzzleType || detectedPuzzleType;

  if (!puzzleType) {
    throw new Error("Open LinkedIn Queens or Tango page first.");
  }

  const quickSettings = await loadQuickSettings();
  const frameContext = await getGameFrameContext(tabId, puzzleType);
  await clearOverlaysForFrameContext(tabId, frameContext);

  const selectionContext = await detectSelectionForQuickSolve(tabId, puzzleType, frameContext);

  const solvedPayload = await solveBoardCore({
    tabId,
    puzzleType,
    apiBaseUrl: quickSettings.apiBaseUrl,
    selection: selectionContext.topSelection,
  });

  if (!solvedPayload.result || !solvedPayload.result.solved) {
    return {
      puzzleType,
      solved: false,
      applied: false,
      selection: solvedPayload.selection,
      result: solvedPayload.result,
      error: solvedPayload.result && solvedPayload.result.error ? solvedPayload.result.error : "No solution found.",
    };
  }

  const applyResponse = await applySolutionForSelection(
    tabId,
    puzzleType,
    solvedPayload.result,
    selectionContext.interactionFrameId,
    selectionContext.interactionSelection,
    selectionContext.topSelection,
    quickSettings.applySettings
  );

  if (!applyResponse || !applyResponse.ok) {
    return {
      puzzleType,
      solved: true,
      applied: false,
      selection: solvedPayload.selection,
      result: solvedPayload.result,
      error:
        applyResponse && applyResponse.error
          ? applyResponse.error
          : "Solved board but failed to apply moves.",
    };
  }

  await clearOverlaysForFrameContext(tabId, frameContext);

  return {
    puzzleType,
    solved: true,
    applied: true,
    selection: solvedPayload.selection,
    result: solvedPayload.result,
    appliedCount: Number(applyResponse.appliedCount) || 0,
    clickCount: Number(applyResponse.clickCount) || 0,
    strategy: applyResponse.strategy || null,
  };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || !message.type) {
    return;
  }

  if (message.type === "solveBoard") {
    solveBoardRequest(message)
      .then((payload) => {
        sendResponse({ ok: true, ...payload });
      })
      .catch((error) => {
        sendResponse({ ok: false, error: error.message || String(error) });
      });

    return true;
  }

  if (message.type === "quickSolveFromPage") {
    quickSolveFromPage(message, sender)
      .then((payload) => {
        sendResponse({ ok: true, ...payload });
      })
      .catch((error) => {
        sendResponse({ ok: false, error: error.message || String(error) });
      });

    return true;
  }
});
