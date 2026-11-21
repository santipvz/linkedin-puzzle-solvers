// Helpers shared by the popup, the background worker and the content script.
// Classic scripts share one global scope, so these are plain global functions.
// `var` keeps a second injection of the content scripts from failing.

var DEFAULT_INTER_CLICK_DELAY_MS = 45;
var DEFAULT_MOVE_INTERVAL_MS = 100;
var MIN_DELAY_MS = 0;
var MAX_DELAY_MS = 500;
// Scripts injected into a game page that was open before the extension loaded.
var CONTENT_SCRIPT_FILES = ["puzzle_registry.js", "shared.js", "wend_paths.js", "content.js"];

// A board rectangle in CSS pixels, or null when it is unusable (missing or under 10 px).
function normalizeSelection(selection) {
  if (!selection || typeof selection !== "object") {
    return null;
  }
  const x = Number(selection.x);
  const y = Number(selection.y);
  const width = Number(selection.width);
  const height = Number(selection.height);
  const dpr = Number(selection.devicePixelRatio) || globalThis.devicePixelRatio || 1;
  if (![x, y, width, height].every(Number.isFinite) || width < 10 || height < 10) {
    return null;
  }
  return { x, y, width, height, devicePixelRatio: dpr };
}

function normalizeDelay(value, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(MIN_DELAY_MS, Math.min(MAX_DELAY_MS, Math.round(parsed)));
}

// The board rectangle OCR found inside the uploaded crop, in image pixels.
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
  if (![x, y, width, height].every(Number.isFinite) || width < 20 || height < 20) {
    return null;
  }
  return { x, y, width, height };
}

// Shrinks a loose user selection to the board OCR found inside it.
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
  // A bbox that already covers the selection adds nothing.
  if (boardBbox.width / selectionPixelWidth >= 0.92 && boardBbox.height / selectionPixelHeight >= 0.92) {
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

// --- Extension messaging (popup and background) ---------------------------

// Wraps a callback-style chrome API call in a promise that rejects on runtime.lastError.
function chromeCall(invoke) {
  return new Promise((resolve, reject) => {
    invoke((value) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      resolve(value);
    });
  });
}

function storageGet(keys) {
  return chromeCall((done) => chrome.storage.local.get(keys, done));
}

function sendTabMessage(tabId, message, options = {}) {
  return chromeCall((done) => chrome.tabs.sendMessage(tabId, message, options, done));
}

// Injects the content scripts into one frame (or every frame when frameId is not an integer).
async function executeContentScript(tabId, frameId = 0) {
  if (chrome.scripting && typeof chrome.scripting.executeScript === "function") {
    const target = Number.isInteger(frameId) ? { tabId, frameIds: [frameId] } : { tabId };
    await chromeCall((done) => chrome.scripting.executeScript({ target, files: CONTENT_SCRIPT_FILES }, done));
    return;
  }
  if (chrome.tabs && typeof chrome.tabs.executeScript === "function") {
    const details = Number.isInteger(frameId) ? { frameId, runAt: "document_idle" } : { runAt: "document_idle" };
    for (const file of CONTENT_SCRIPT_FILES) {
      await chromeCall((done) => chrome.tabs.executeScript(tabId, { ...details, file }, done));
    }
    return;
  }
  throw new Error("No supported script injection API available in this browser.");
}

function isNoReceiverError(error) {
  const message = error && error.message ? error.message : "";
  return message.includes("Receiving end does not exist");
}

// Sends a message to a tab, injecting the content scripts first if nothing answers.
async function sendTabMessageWithInjection(tabId, message, options = {}) {
  try {
    return await sendTabMessage(tabId, message, options);
  } catch (error) {
    if (!isNoReceiverError(error)) {
      throw error;
    }
    await executeContentScript(tabId, Number.isInteger(options.frameId) ? options.frameId : 0);
    return sendTabMessage(tabId, message, options);
  }
}
