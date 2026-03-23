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

function translateTabSelectionToFrame(tabSelection, iframeRect) {
  const selection = normalizeSelection(tabSelection);
  const rect = normalizeRect(iframeRect);
  if (!selection || !rect) {
    return null;
  }

  const relativeX = selection.x - rect.left;
  const relativeY = selection.y - rect.top;

  const clampedX = Math.max(0, relativeX);
  const clampedY = Math.max(0, relativeY);
  const maxWidth = rect.width - clampedX;
  const maxHeight = rect.height - clampedY;

  if (maxWidth < 10 || maxHeight < 10) {
    return null;
  }

  return normalizeSelection({
    x: clampedX,
    y: clampedY,
    width: Math.min(selection.width, maxWidth),
    height: Math.min(selection.height, maxHeight),
    devicePixelRatio: selection.devicePixelRatio,
  });
}

function findLinkedInGameFrame(frames, puzzleType) {
  if (!Array.isArray(frames) || !frames.length) {
    return null;
  }

  const exactNeedle = `/games/view/${puzzleType}/desktop`;
  const exactMatch = frames.find((frame) => typeof frame.url === "string" && frame.url.includes(exactNeedle));
  if (exactMatch) {
    return exactMatch;
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
    const frameSelection = translateTabSelectionToFrame(selection, frameContext.iframeRect);
    if (frameSelection) {
      return { frameId: frameContext.gameFrameId, selection: frameSelection };
    }
  }

  return { frameId: 0, selection };
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
    return existing;
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
      const topSelection = translateFrameSelectionToTab(frameDetected.selection, frameContext.iframeRect);
      if (topSelection) {
        const savedSelection = await setTopBoardSelection(tabId, topSelection);
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
    setStatus("Board auto-detected.");
    return normalizeSelection(topDetected.selection);
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
      const topSelection = translateFrameSelectionToTab(frameResponse.selection, frameContext.iframeRect);
      const saved = await setTopBoardSelection(tab.id, topSelection);
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
    throw new Error("Could not auto-detect a board. Use Select Board.");
  }

  setStatus("Board auto-detected.");
}

async function solveForTab(tab, options = {}) {
  const renderSolution = options.renderSolution !== false;
  const puzzleType = puzzleTypeSelect.value;
  const apiBaseUrl = apiUrlInput.value.trim() || DEFAULT_API_URL;

  const frameContext = await getGameFrameContext(tab.id, puzzleType);
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

  if (renderSolution) {
    const interactionTarget = resolveInteractionTarget(topSelection, frameContext);
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
          selection: topSelection,
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
    selection: topSelection,
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

  return `${appliedText}${clickText}${strategyText}`;
}

async function applyPayloadToTab(tab, payload, frameContext) {
  const interactionTarget = resolveInteractionTarget(payload.selection, frameContext);
  if (!interactionTarget) {
    throw new Error("Could not map board selection for applying moves.");
  }

  const applySettings = getApplySettingsFromUi();
  const messagePayload = {
    type: "applySolution",
    puzzleType: payload.puzzleType,
    result: payload.result,
    selection: interactionTarget.selection,
    settings: {
      interClickDelayMs: applySettings.interClickDelayMs,
      interMoveDelayMs: applySettings.interMoveDelayMs,
      tangoApplyMode: applySettings.tangoApplyMode,
    },
  };

  let response = await safeSendTabMessage(tab.id, messagePayload, { frameId: interactionTarget.frameId });

  if ((!response || !response.ok) && interactionTarget.frameId !== 0) {
    response = await safeSendTabMessage(
      tab.id,
      {
        ...messagePayload,
        selection: payload.selection,
      },
      { frameId: 0 }
    );
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
