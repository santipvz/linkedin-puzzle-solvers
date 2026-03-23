const DEFAULT_API_BASE = "http://127.0.0.1:8000";

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

function captureVisibleTab(windowId) {
  return new Promise((resolve, reject) => {
    chrome.tabs.captureVisibleTab(windowId, { format: "png" }, (dataUrl) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
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

async function solveBoardRequest(message) {
  const tab = await tabsGet(message.tabId);
  const screenshotDataUrl = await captureVisibleTab(tab.windowId);
  const boardImage = await cropCapturedImage(screenshotDataUrl, message.selection);
  const result = await callSolverApi(message.apiBaseUrl, message.puzzleType, boardImage);

  return {
    result,
    selection: normalizeSelection(message.selection),
    puzzleType: message.puzzleType === "tango" ? "tango" : "queens",
  };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== "solveBoard") {
    return;
  }

  solveBoardRequest(message)
    .then((payload) => {
      sendResponse({ ok: true, ...payload });
    })
    .catch((error) => {
      sendResponse({ ok: false, error: error.message || String(error) });
    });

  return true;
});
