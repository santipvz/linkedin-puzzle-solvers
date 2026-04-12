if (typeof importScripts === "function") {
  try {
    importScripts("puzzle_registry.js");
  } catch (error) {
    void error;
  }
}

const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const DEFAULT_INTER_CLICK_DELAY_MS = 45;
const DEFAULT_INTER_MOVE_DELAY_MS = 40;
const DEFAULT_TANGO_APPLY_MODE = "left-cycle";

const STORAGE_API_KEY = "solver_api_url";
const STORAGE_INTER_CLICK_DELAY_KEY = "solver_inter_click_delay_ms";
const STORAGE_INTER_MOVE_DELAY_KEY = "solver_inter_move_delay_ms";
const STORAGE_TANGO_APPLY_MODE_KEY = "solver_tango_apply_mode";

const puzzleRegistry = globalThis.PuzzleRegistry || {};
const sanitizePuzzleType =
  typeof puzzleRegistry.sanitizePuzzleType === "function"
    ? puzzleRegistry.sanitizePuzzleType
    : function fallbackSanitizePuzzleType(value) {
        if (value === "patches") {
          return "patches";
        }
        if (value === "zip") {
          return "zip";
        }
        if (value === "sudoku") {
          return "sudoku";
        }
        if (value === "tango") {
          return "tango";
        }
        if (value === "queens") {
          return "queens";
        }
        return null;
      };

const detectPuzzleTypeFromUrl =
  typeof puzzleRegistry.detectPuzzleTypeFromUrl === "function"
    ? puzzleRegistry.detectPuzzleTypeFromUrl
    : function fallbackDetectPuzzleTypeFromUrl(url) {
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
        if (normalized.includes("/games/patches") || normalized.includes("/games/view/patches")) {
          return "patches";
        }
        return null;
      };

const puzzleTypeToFrameSlug =
  typeof puzzleRegistry.puzzleTypeToFrameSlug === "function"
    ? puzzleRegistry.puzzleTypeToFrameSlug
    : function fallbackPuzzleTypeToFrameSlug(puzzleType) {
        if (puzzleType === "sudoku") {
          return "mini-sudoku";
        }
        return puzzleType;
      };

function normalizeApiBase(value) {
  if (!value || typeof value !== "string") {
    return DEFAULT_API_BASE;
  }

  return value.trim().replace(/\/+$/, "") || DEFAULT_API_BASE;
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

function normalizeViewport(viewport) {
  if (!viewport || typeof viewport !== "object") {
    return null;
  }

  const width = Number(viewport.width);
  const height = Number(viewport.height);
  const devicePixelRatio = Number(viewport.devicePixelRatio);

  if (!Number.isFinite(width) || !Number.isFinite(height)) {
    return null;
  }

  if (width < 10 || height < 10) {
    return null;
  }

  return {
    width,
    height,
    devicePixelRatio: Number.isFinite(devicePixelRatio) && devicePixelRatio > 0 ? devicePixelRatio : undefined,
  };
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

function getBoardBboxFromResult(result) {
  const details = result && typeof result === "object" ? result.details : null;
  const bbox =
    details && typeof details === "object"
      ? details.board_bbox || details.crop_bbox || null
      : null;
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
  const offsetX = boardBbox.x / dpr;
  const offsetY = boardBbox.y / dpr;
  const refinedWidth = boardBbox.width / dpr;
  const refinedHeight = boardBbox.height / dpr;

  const maxX = normalized.x + normalized.width - 10;
  const maxY = normalized.y + normalized.height - 10;

  const refinedX = Math.max(normalized.x, Math.min(maxX, normalized.x + offsetX));
  const refinedY = Math.max(normalized.y, Math.min(maxY, normalized.y + offsetY));

  const remainingWidth = normalized.x + normalized.width - refinedX;
  const remainingHeight = normalized.y + normalized.height - refinedY;

  return normalizeSelection({
    x: refinedX,
    y: refinedY,
    width: Math.max(10, Math.min(refinedWidth, remainingWidth)),
    height: Math.max(10, Math.min(refinedHeight, remainingHeight)),
    devicePixelRatio: normalized.devicePixelRatio,
  });
}

function buildTangoSelectionCandidates(baseSelection) {
  const normalizedBase = normalizeSelection(baseSelection);
  if (!normalizedBase) {
    return [];
  }

  const specs = [
    { sideRatio: 1.0, yOffsetRatio: 0 },
    { sideRatio: 0.94, yOffsetRatio: -0.02 },
    { sideRatio: 0.88, yOffsetRatio: -0.04 },
    { sideRatio: 0.82, yOffsetRatio: -0.06 },
    { sideRatio: 0.76, yOffsetRatio: -0.08 },
    { sideRatio: 0.7, yOffsetRatio: -0.08 },
    { sideRatio: 0.64, yOffsetRatio: -0.08 },
    { sideRatio: 0.64, yOffsetRatio: 0 },
  ];

  const candidates = [];
  const seen = new Set();

  for (const spec of specs) {
    const side = Math.max(10, Math.min(normalizedBase.width, normalizedBase.height) * spec.sideRatio);
    const rawX = normalizedBase.x + (normalizedBase.width - side) / 2;
    const rawY = normalizedBase.y + (normalizedBase.height - side) / 2 + normalizedBase.height * spec.yOffsetRatio;

    const minX = normalizedBase.x;
    const maxX = normalizedBase.x + normalizedBase.width - side;
    const minY = normalizedBase.y;
    const maxY = normalizedBase.y + normalizedBase.height - side;

    const clampedX = clamp(rawX, minX, maxX);
    const clampedY = clamp(rawY, minY, maxY);

    const candidate = normalizeSelection({
      x: clampedX,
      y: clampedY,
      width: side,
      height: side,
      devicePixelRatio: normalizedBase.devicePixelRatio,
    });

    if (!candidate) {
      continue;
    }

    const key = `${Math.round(candidate.x)}:${Math.round(candidate.y)}:${Math.round(candidate.width)}:${Math.round(
      candidate.height
    )}`;

    if (seen.has(key)) {
      continue;
    }

    seen.add(key);
    candidates.push(candidate);
  }

  return candidates;
}

function tangoAttemptScore(result, attemptSelection, baseSelection) {
  const details = result && typeof result === "object" && result.details && typeof result.details === "object" ? result.details : {};
  const solved = Boolean(result && result.solved);
  const fixedCount = Number(details.fixed_count) || 0;
  const constraintCount = Number(details.constraint_count) || 0;
  const movesCount = Array.isArray(result && result.moves) ? result.moves.length : 0;

  const attemptArea = attemptSelection ? attemptSelection.width * attemptSelection.height : 0;
  const baseArea = baseSelection ? baseSelection.width * baseSelection.height : 1;
  const areaRatio = baseArea > 0 ? attemptArea / baseArea : 1;

  let score = 0;
  if (solved) {
    score += 4500;
  } else {
    score -= 2600;
  }

  score -= Math.abs(fixedCount - 12) * 42;
  score -= Math.abs(constraintCount - 9) * 36;

  if (fixedCount < 3) {
    score -= 700;
  } else if (fixedCount > 24) {
    score -= 500;
  }

  if (constraintCount < 2) {
    score -= 520;
  } else if (constraintCount > 24) {
    score -= 360;
  }

  if (solved && movesCount === 0 && fixedCount < 36) {
    score -= 1000;
  }

  if (areaRatio < 0.35) {
    score -= Math.round((0.35 - areaRatio) * 1600);
  } else if (areaRatio > 1.05) {
    score -= Math.round((areaRatio - 1.05) * 900);
  } else if (areaRatio >= 0.5 && areaRatio <= 0.95) {
    score += 120;
  }

  if (attemptSelection) {
    const ratio = attemptSelection.width / Math.max(1, attemptSelection.height);
    if (ratio >= 0.9 && ratio <= 1.1) {
      score += 80;
    }
  }

  return score;
}

async function solveTangoWithCandidateSearch({ normalizedSelection, screenshotDataUrl, apiBaseUrl }) {
  const candidates = buildTangoSelectionCandidates(normalizedSelection);
  if (!candidates.length) {
    throw new Error("Could not build Tango board candidates.");
  }

  let best = null;

  for (let index = 0; index < candidates.length; index += 1) {
    const candidate = candidates[index];
    const boardImage = await cropCapturedImage(screenshotDataUrl, candidate);
    const result = await callSolverApi(apiBaseUrl, "tango", boardImage, {
      captureBoardStart: index === 0,
    });
    const refinedSelection = refineSelectionWithBoardBbox(candidate, result) || candidate;
    const score = tangoAttemptScore(result, refinedSelection, normalizedSelection);

    if (!best || score > best.score) {
      best = {
        score,
        result,
        selection: refinedSelection,
        attempt: index + 1,
        attemptCount: candidates.length,
      };
    }
  }

  if (!best) {
    throw new Error("No Tango solve attempt completed.");
  }

  const details =
    best.result && typeof best.result === "object" && best.result.details && typeof best.result.details === "object"
      ? best.result.details
      : {};

  details.selection_attempt = best.attempt;
  details.selection_attempts = best.attemptCount;
  details.selection_search_score = best.score;

  if (best.result && typeof best.result === "object") {
    best.result.details = details;
  }

  return {
    result: best.result,
    selection: best.selection,
  };
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

function executeContentScript(tabId, frameId = 0) {
  return new Promise((resolve, reject) => {
    if (chrome.scripting && typeof chrome.scripting.executeScript === "function") {
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
      return;
    }

    if (chrome.tabs && typeof chrome.tabs.executeScript === "function") {
      const details = Number.isInteger(frameId)
        ? { file: "content.js", frameId, runAt: "document_idle" }
        : { file: "content.js", runAt: "document_idle" };

      chrome.tabs.executeScript(tabId, details, () => {
        const error = chrome.runtime.lastError;
        if (error) {
          reject(new Error(error.message));
          return;
        }
        resolve();
      });
      return;
    }

    reject(new Error("No supported script injection API available in this browser."));
  });
}

function isNoReceiverError(error) {
  const message = error && error.message ? error.message : "";
  return message.includes("Receiving end does not exist");
}

async function sendTabMessageWithInjection(tabId, message, options = {}) {
  try {
    return await tabsSendMessage(tabId, message, options);
  } catch (error) {
    if (!isNoReceiverError(error)) {
      throw error;
    }

    const frameId = Number.isInteger(options.frameId) ? options.frameId : 0;
    await executeContentScript(tabId, frameId);
    return tabsSendMessage(tabId, message, options);
  }
}

async function safeSendTabMessage(tabId, message, options = {}) {
  try {
    return await sendTabMessageWithInjection(tabId, message, options);
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

async function callSolverApi(apiBaseUrl, puzzleType, imageBlob, options = {}) {
  const safePuzzleType =
    puzzleType === "tango"
      ? "tango"
      : puzzleType === "sudoku"
      ? "sudoku"
      : puzzleType === "zip"
      ? "zip"
      : puzzleType === "patches"
      ? "patches"
      : "queens";
  const endpoint = `${normalizeApiBase(apiBaseUrl)}/solve/${safePuzzleType}`;

  const formData = new FormData();
  formData.append("image", imageBlob, `${safePuzzleType}_board.png`);

  const headers = {};
  if (options.captureBoardStart) {
    headers["X-Board-Capture"] = "start";
  }

  const response = await fetch(endpoint, {
    method: "POST",
    headers,
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
  const normalizedSelection = normalizeSelection(selection);
  const tab = await tabsGet(tabId);
  const screenshotDataUrl = await captureVisibleTab(tab.windowId);

  let result;
  let refinedSelection;

  if (puzzleType === "tango") {
    const tangoSolved = await solveTangoWithCandidateSearch({
      normalizedSelection,
      screenshotDataUrl,
      apiBaseUrl,
    });
    result = tangoSolved.result;
    refinedSelection = normalizeSelection(tangoSolved.selection) || normalizedSelection;
  } else {
    const boardImage = await cropCapturedImage(screenshotDataUrl, normalizedSelection);
    result = await callSolverApi(apiBaseUrl, puzzleType, boardImage, {
      captureBoardStart: true,
    });
    refinedSelection = refineSelectionWithBoardBbox(normalizedSelection, result);
  }

  return {
    result,
    selection: refinedSelection,
    puzzleType:
    puzzleType === "tango"
      ? "tango"
      : puzzleType === "sudoku"
      ? "sudoku"
      : puzzleType === "zip"
      ? "zip"
      : puzzleType === "patches"
      ? "patches"
      : "queens",
  };
}

function findLinkedInGameFrame(frames, puzzleType) {
  if (!Array.isArray(frames) || !frames.length) {
    return null;
  }

  if (puzzleType) {
    const exactNeedle = `/games/view/${puzzleTypeToFrameSlug(puzzleType)}/desktop`;
    const exactMatch = frames.find((frame) => typeof frame.url === "string" && frame.url.includes(exactNeedle));
    if (exactMatch) {
      return exactMatch;
    }
  }

  return frames.find((frame) => typeof frame.url === "string" && frame.url.includes("/games/view")) || null;
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

async function getGameFrameContext(tabId, puzzleType) {
  let gameFrameId = 0;
  let iframeRect = null;
  let frameViewport = null;
  let topViewport = null;

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

  const topViewportResponse = await safeSendTabMessage(tabId, { type: "getViewportMetrics" }, { frameId: 0 });
  if (topViewportResponse && topViewportResponse.ok) {
    topViewport = normalizeViewport(topViewportResponse.viewport || topViewportResponse.selection);
  }

  if (gameFrameId !== 0) {
    const frameViewportResponse = await safeSendTabMessage(tabId, { type: "getViewportMetrics" }, { frameId: gameFrameId });
    if (frameViewportResponse && frameViewportResponse.ok) {
      frameViewport = normalizeViewport(frameViewportResponse.viewport || frameViewportResponse.selection);
    }
  }

  return { gameFrameId, iframeRect, frameViewport, topViewport };
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

function selectionFromRect(rect, insetRatio = 0.04, devicePixelRatio = 1) {
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
    devicePixelRatio,
  });
}

async function getTopBoardSelection(tabId) {
  const existing = await safeSendTabMessage(tabId, { type: "getBoardSelection" }, { frameId: 0 });
  if (!existing || !existing.selection) {
    return null;
  }
  return normalizeSelection(existing.selection);
}

async function setTopBoardSelection(tabId, selection) {
  const normalized = normalizeSelection(selection);
  if (!normalized) {
    return null;
  }

  const response = await safeSendTabMessage(tabId, { type: "setBoardSelection", selection: normalized }, { frameId: 0 });
  if (!response || !response.ok) {
    return null;
  }

  return normalizeSelection(response.selection);
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

function maybeNormalizeSelectionForPuzzle(puzzleType, selection, frameRect) {
  const normalized = normalizeSelection(selection);
  if (!normalized) {
    return null;
  }

  if (puzzleType !== "tango") {
    return normalized;
  }

  const frameSelection = selectionFromRect(frameRect, 0, normalized.devicePixelRatio || 1);
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

async function getViewportFallbackSelection(tabId, tab) {
  const viewportResponse = await safeSendTabMessage(tabId, { type: "getViewportMetrics" }, { frameId: 0 });
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

async function detectSelectionForQuickSolve(tabId, puzzleType, frameContext, tab) {
  const existing = await getTopBoardSelection(tabId);

  if (existing) {
    const normalizedExisting = maybeNormalizeSelectionForPuzzle(puzzleType, existing, frameContext?.iframeRect);
    const topSelection = normalizedExisting || existing;

    if (normalizedExisting && hasMeaningfulSelectionDelta(existing, normalizedExisting)) {
      const savedSelection = await setTopBoardSelection(tabId, normalizedExisting);
      if (savedSelection) {
        const savedTarget = resolveInteractionTarget(savedSelection, frameContext);
        if (savedTarget) {
          return {
            topSelection: savedSelection,
            interactionFrameId: savedTarget.frameId,
            interactionSelection: savedTarget.selection,
          };
        }
      }
    }

    const existingTarget = resolveInteractionTarget(topSelection, frameContext);
    if (existingTarget) {
      return {
        topSelection,
        interactionFrameId: existingTarget.frameId,
        interactionSelection: existingTarget.selection,
      };
    }
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
      const normalizedTopSelection = maybeNormalizeSelectionForPuzzle(
        puzzleType,
        topSelection,
        frameContext.iframeRect
      );

      if (normalizedTopSelection) {
        const savedSelection = await setTopBoardSelection(tabId, normalizedTopSelection);
        const finalTopSelection = savedSelection || normalizedTopSelection;
        const interactionTarget = resolveInteractionTarget(finalTopSelection, frameContext);
        if (interactionTarget) {
          return {
            topSelection: finalTopSelection,
            interactionFrameId: interactionTarget.frameId,
            interactionSelection: interactionTarget.selection,
          };
        }
      }
    }
  }

  const topDetected = await safeSendTabMessage(tabId, { type: "autoDetectBoard", puzzleType }, { frameId: 0 });
  if (topDetected && topDetected.selection) {
    const topSelection = maybeNormalizeSelectionForPuzzle(puzzleType, topDetected.selection, frameContext?.iframeRect);
    if (topSelection) {
      const savedSelection = await setTopBoardSelection(tabId, topSelection);
      const finalTopSelection = savedSelection || topSelection;
      const interactionTarget = resolveInteractionTarget(finalTopSelection, frameContext);
      if (interactionTarget) {
        return {
          topSelection: finalTopSelection,
          interactionFrameId: interactionTarget.frameId,
          interactionSelection: interactionTarget.selection,
        };
      }
    }
  }

  const fallbackDevicePixelRatio =
    frameContext?.topViewport?.devicePixelRatio ||
    frameContext?.frameViewport?.devicePixelRatio ||
    existing?.devicePixelRatio ||
    1;

  if (frameContext && frameContext.iframeRect) {
    const frameBaseSelection = selectionFromRect(frameContext.iframeRect, 0.04, fallbackDevicePixelRatio);
    const topSelection = frameBaseSelection;

    if (topSelection) {
      const savedSelection = await setTopBoardSelection(tabId, topSelection);
      const finalTopSelection = savedSelection || topSelection;
      const interactionTarget = resolveInteractionTarget(finalTopSelection, frameContext);
      if (interactionTarget) {
        return {
          topSelection: finalTopSelection,
          interactionFrameId: interactionTarget.frameId,
          interactionSelection: interactionTarget.selection,
          usedViewportFallback: true,
        };
      }
    }
  }

  const fallbackSelection = await getViewportFallbackSelection(tabId, tab);
  if (fallbackSelection) {
    const savedSelection = await setTopBoardSelection(tabId, fallbackSelection);
    const finalTopSelection = savedSelection || fallbackSelection;
    const interactionTarget = resolveInteractionTarget(finalTopSelection, frameContext);
    if (interactionTarget) {
      return {
        topSelection: finalTopSelection,
        interactionFrameId: interactionTarget.frameId,
        interactionSelection: interactionTarget.selection,
        usedViewportFallback: true,
      };
    }
  }

  throw new Error("Could not auto-detect board region.");
}

async function buildApplyTargets(tabId, puzzleType, topSelection, frameContext, interactionFrameId, interactionSelection) {
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

  pushTarget(interactionFrameId, interactionSelection);

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
      // Ignore and rely on the targets already queued.
    }
  }

  pushTarget(0, normalizedTopSelection);
  return targets;
}

function shouldRetrySudokuApplyWithoutSelection(response) {
  if (!response) {
    return true;
  }

  if (response.ok) {
    return false;
  }

  const appliedCount = Number(response.appliedCount) || 0;
  const clickCount = Number(response.clickCount) || 0;
  const keyCount = Number(response.keyCount) || 0;

  return appliedCount === 0 && clickCount === 0 && keyCount === 0;
}

async function applySolutionForSelection(
  tabId,
  puzzleType,
  result,
  interactionFrameId,
  interactionSelection,
  topSelection,
  frameContext,
  applySettings
) {
  const applyTargets = await buildApplyTargets(
    tabId,
    puzzleType,
    topSelection,
    frameContext,
    interactionFrameId,
    interactionSelection
  );

  if (!applyTargets.length) {
    return { ok: false, error: "Could not map board selection for applying moves." };
  }

  const messagePayloadBase = {
    type: "applySolution",
    puzzleType,
    result,
    settings: applySettings,
  };

  let response = null;
  for (const target of applyTargets) {
    response = await safeSendTabMessage(
      tabId,
      {
        ...messagePayloadBase,
        selection: target.selection,
      },
      { frameId: target.frameId }
    );

    const shouldRetryWithoutSelection =
      puzzleType === "sudoku" && shouldRetrySudokuApplyWithoutSelection(response);

    if (shouldRetryWithoutSelection) {
      const fallbackResponse = await safeSendTabMessage(
        tabId,
        {
          ...messagePayloadBase,
          selection: null,
        },
        { frameId: target.frameId }
      );

      if (fallbackResponse && fallbackResponse.ok) {
        response = fallbackResponse;
      } else if (!response) {
        response = fallbackResponse;
      }
    }

    if (response && response.ok) {
      break;
    }
  }

  if ((!response || !response.ok) && puzzleType === "sudoku" && shouldRetrySudokuApplyWithoutSelection(response)) {
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
      const frames = await webNavigationGetAllFrames(tabId);
      const frameIds = findLinkedInGameFrameIds(frames, puzzleType);
      for (const frameId of frameIds) {
        pushFallbackFrameId(frameId);
      }
    } catch (error) {
      // Ignore frame enumeration failures and return the prior apply response.
    }

    for (const frameId of fallbackFrameIds) {
      const fallbackResponse = await safeSendTabMessage(
        tabId,
        {
          ...messagePayloadBase,
          selection: null,
        },
        { frameId }
      );

      if (fallbackResponse && fallbackResponse.ok) {
        response = fallbackResponse;
        break;
      }

      if (!response) {
        response = fallbackResponse;
      }
    }
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
  const senderTabId = sender && sender.tab && Number.isInteger(sender.tab.id) ? sender.tab.id : null;
  const messageTabId = Number.isInteger(message && message.tabId) ? message.tabId : null;
  const tabId = senderTabId !== null ? senderTabId : messageTabId;
  if (tabId === null) {
    throw new Error("Could not resolve active game tab.");
  }

  const tab = await tabsGet(tabId);
  const requestedPuzzleType = sanitizePuzzleType(message.puzzleType);
  const detectedPuzzleType = detectPuzzleTypeFromUrl(tab.url);
  const puzzleType = requestedPuzzleType || detectedPuzzleType;

  if (!puzzleType) {
    throw new Error("Open LinkedIn Queens, Tango, Mini Sudoku, Zip, or Patches page first.");
  }

  const quickSettings = await loadQuickSettings();
  const previewOnly = Boolean(message && message.previewOnly);
  const frameContext = await getGameFrameContext(tabId, puzzleType);
  await clearOverlaysForFrameContext(tabId, frameContext);

  const selectionContext = await detectSelectionForQuickSolve(tabId, puzzleType, frameContext, tab);

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

  const solvedSelection = normalizeSelection(solvedPayload.selection) || selectionContext.topSelection;
  let applyTopSelection = solvedSelection;
  if (hasMeaningfulSelectionDelta(selectionContext.topSelection, solvedSelection)) {
    const savedSolvedSelection = await setTopBoardSelection(tabId, solvedSelection);
    if (savedSolvedSelection) {
      applyTopSelection = savedSolvedSelection;
    }
  }

  let applyFrameId = selectionContext.interactionFrameId;
  let applyInteractionSelection = selectionContext.interactionSelection;

  if (
    frameContext &&
    frameContext.iframeRect &&
    Number.isInteger(frameContext.gameFrameId) &&
    frameContext.gameFrameId !== 0
  ) {
    const mappedFrameSelection = translateTabSelectionToFrame(
      applyTopSelection,
      frameContext.iframeRect,
      frameContext.frameViewport
    );
    if (mappedFrameSelection) {
      applyFrameId = frameContext.gameFrameId;
      applyInteractionSelection = mappedFrameSelection;
    } else if (applyFrameId === 0) {
      applyInteractionSelection = applyTopSelection;
    }
  } else if (applyFrameId === 0) {
    applyInteractionSelection = applyTopSelection;
  }

  if (
    applyFrameId !== 0 &&
    frameContext &&
    frameContext.iframeRect &&
    Number.isInteger(frameContext.gameFrameId)
  ) {
    if (!normalizeSelection(applyInteractionSelection)) {
      applyFrameId = 0;
      applyInteractionSelection = applyTopSelection;
    }
  }

  if (previewOnly) {
    let renderResponse = await safeSendTabMessage(
      tabId,
      {
        type: "renderSolution",
        puzzleType,
        result: solvedPayload.result,
        selection: applyInteractionSelection,
      },
      { frameId: applyFrameId }
    );

    if ((!renderResponse || !renderResponse.ok) && applyFrameId !== 0) {
      renderResponse = await safeSendTabMessage(
        tabId,
        {
          type: "renderSolution",
          puzzleType,
          result: solvedPayload.result,
          selection: applyTopSelection,
        },
        { frameId: 0 }
      );
    }

    if (!renderResponse || !renderResponse.ok) {
      return {
        puzzleType,
        solved: true,
        applied: false,
        previewed: false,
        selection: solvedPayload.selection,
        result: solvedPayload.result,
        error: (renderResponse && renderResponse.error) || "Solved board but failed to render overlay preview.",
      };
    }

    return {
      puzzleType,
      solved: true,
      applied: false,
      previewed: true,
      selection: applyTopSelection,
      result: solvedPayload.result,
      strategy: "overlay-preview",
    };
  }

  const applyResponse = await applySolutionForSelection(
    tabId,
    puzzleType,
    solvedPayload.result,
    applyFrameId,
    applyInteractionSelection,
    applyTopSelection,
    frameContext,
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
    selection: applyTopSelection,
    result: solvedPayload.result,
    appliedCount: Number(applyResponse.appliedCount) || 0,
    clickCount: Number(applyResponse.clickCount) || 0,
    strategy: applyResponse.strategy || null,
  };
}

function normalizeApplySettings(settings, fallbackSettings) {
  const raw = settings && typeof settings === "object" ? settings : fallbackSettings;
  const source = raw && typeof raw === "object" ? raw : {};

  return {
    interClickDelayMs: normalizeDelay(source.interClickDelayMs, DEFAULT_INTER_CLICK_DELAY_MS),
    interMoveDelayMs: normalizeDelay(source.interMoveDelayMs, DEFAULT_INTER_MOVE_DELAY_MS),
    tangoApplyMode: normalizeTangoApplyMode(source.tangoApplyMode || DEFAULT_TANGO_APPLY_MODE),
  };
}

async function applySolvedPayload(message, sender) {
  const senderTabId = sender && sender.tab && Number.isInteger(sender.tab.id) ? sender.tab.id : null;
  const messageTabId = Number.isInteger(message && message.tabId) ? message.tabId : null;
  const tabId = senderTabId !== null ? senderTabId : messageTabId;
  if (tabId === null) {
    throw new Error("Could not resolve target tab.");
  }

  const tab = await tabsGet(tabId);
  const requestedPuzzleType = sanitizePuzzleType(message.puzzleType);
  const detectedPuzzleType = detectPuzzleTypeFromUrl(tab.url);
  const puzzleType = requestedPuzzleType || detectedPuzzleType;
  if (!puzzleType) {
    throw new Error("Open LinkedIn Queens, Tango, Mini Sudoku, Zip, or Patches page first.");
  }

  if (!message || !message.result || typeof message.result !== "object") {
    throw new Error("No solved payload provided. Solve first.");
  }

  if (!message.result.solved) {
    throw new Error("Cached payload is not solved. Solve first.");
  }

  const quickSettings = await loadQuickSettings();
  const applySettings = normalizeApplySettings(message.settings, quickSettings.applySettings);

  const frameContext = await getGameFrameContext(tabId, puzzleType);
  let topSelection = maybeNormalizeSelectionForPuzzle(puzzleType, message.selection, frameContext && frameContext.iframeRect);
  let interactionTarget = topSelection ? resolveInteractionTarget(topSelection, frameContext) : null;

  if (!topSelection) {
    const existing = await getTopBoardSelection(tabId);
    const normalizedExisting = maybeNormalizeSelectionForPuzzle(puzzleType, existing, frameContext && frameContext.iframeRect);
    topSelection = normalizedExisting || existing;
    interactionTarget = topSelection ? resolveInteractionTarget(topSelection, frameContext) : null;
  }

  if (!topSelection || !interactionTarget) {
    const selectionContext = await detectSelectionForQuickSolve(tabId, puzzleType, frameContext, tab);
    topSelection = selectionContext.topSelection;
    interactionTarget = {
      frameId: selectionContext.interactionFrameId,
      selection: selectionContext.interactionSelection,
    };
  }

  if (!topSelection) {
    throw new Error("Board selection is required before applying moves.");
  }

  const savedTopSelection = await setTopBoardSelection(tabId, topSelection);
  if (savedTopSelection) {
    topSelection = savedTopSelection;
  }

  if (!interactionTarget || !normalizeSelection(interactionTarget.selection)) {
    interactionTarget = resolveInteractionTarget(topSelection, frameContext) || {
      frameId: 0,
      selection: topSelection,
    };
  }

  const applyResponse = await applySolutionForSelection(
    tabId,
    puzzleType,
    message.result,
    interactionTarget.frameId,
    interactionTarget.selection,
    topSelection,
    frameContext,
    applySettings
  );

  if (!applyResponse || !applyResponse.ok) {
    return {
      puzzleType,
      applied: false,
      selection: topSelection,
      error:
        applyResponse && applyResponse.error
          ? applyResponse.error
          : "Solved board but failed to apply moves.",
      appliedCount: Number(applyResponse && applyResponse.appliedCount) || 0,
      clickCount: Number(applyResponse && applyResponse.clickCount) || 0,
      keyCount: Number(applyResponse && applyResponse.keyCount) || 0,
      strategy: (applyResponse && applyResponse.strategy) || null,
    };
  }

  await clearOverlaysForFrameContext(tabId, frameContext);

  return {
    puzzleType,
    applied: true,
    selection: topSelection,
    appliedCount: Number(applyResponse.appliedCount) || 0,
    clickCount: Number(applyResponse.clickCount) || 0,
    keyCount: Number(applyResponse.keyCount) || 0,
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

  if (message.type === "applySolvedPayload") {
    applySolvedPayload(message, sender)
      .then((payload) => {
        sendResponse({ ok: true, ...payload });
      })
      .catch((error) => {
        sendResponse({ ok: false, error: error.message || String(error) });
      });

    return true;
  }
});
