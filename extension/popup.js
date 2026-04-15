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

const puzzleRegistry = globalThis.PuzzleRegistry || {};

function populatePuzzleTypeOptions() {
  const definitions = Array.isArray(puzzleRegistry.definitions) ? puzzleRegistry.definitions : [];
  if (!definitions.length || !puzzleTypeSelect) {
    return;
  }

  const currentValue = puzzleTypeSelect.value;
  puzzleTypeSelect.innerHTML = "";

  for (const definition of definitions) {
    if (!definition || typeof definition.key !== "string") {
      continue;
    }

    const option = document.createElement("option");
    option.value = definition.key;
    option.textContent =
      typeof definition.label === "string" && definition.label.trim()
        ? definition.label.trim()
        : definition.key;
    puzzleTypeSelect.appendChild(option);
  }

  if (currentValue && definitions.some((definition) => definition && definition.key === currentValue)) {
    puzzleTypeSelect.value = currentValue;
  }
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
        files: ["puzzle_registry.js", "content.js"],
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
  const response = await sendRuntimeMessage({
    type: "autoDetectBoardSelection",
    tabId: tab.id,
    puzzleType,
  });

  if (!response || !response.ok || !response.selection) {
    throw new Error((response && response.error) || "Could not auto-detect a board. Use Select Board.");
  }

  setStatus(response.status || "Board auto-detected.");
}

async function solveForTab(tab, options = {}) {
  const previewOnly = options.previewOnly !== false;
  const puzzleType = puzzleTypeSelect.value;
  const solveResponse = await sendRuntimeMessage({
    type: "quickSolveFromPage",
    tabId: tab.id,
    puzzleType,
    previewOnly,
  });

  if (!solveResponse || !solveResponse.ok) {
    throw new Error((solveResponse && solveResponse.error) || "Solver request failed.");
  }

  const solveSelection = normalizeSelection(solveResponse.selection);

  const payload = {
    puzzleType: solveResponse.puzzleType || puzzleType,
    result: solveResponse.result || null,
    selection: solveSelection,
  };

  if (payload.result && solveSelection) {
    await storageSet({
      [selectionStorageKey(tab.id)]: payload,
    });
  }

  setResult(summarizeResult(payload.puzzleType, payload.result));

  if (solveResponse.solved) {
    if (previewOnly) {
      if (solveResponse.previewed) {
        setStatus("Solved and overlay rendered.");
      } else {
        setStatus(solveResponse.error || "Solved board but failed to render overlay preview.", true);
      }
    } else if (solveResponse.applied) {
      setStatus(buildApplyStatusText(solveResponse));
    } else {
      setStatus(solveResponse.error || "Solved board but failed to apply moves.", true);
    }
  } else {
    setStatus(solveResponse.error || "No solution found.", true);
  }

  return { ...payload, ...solveResponse };
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

async function applyCachedPayloadForTab(tab, payload) {
  const applySettings = getApplySettingsFromUi();
  const response = await sendRuntimeMessage({
    type: "applySolvedPayload",
    tabId: tab.id,
    puzzleType: payload.puzzleType,
    result: payload.result,
    selection: payload.selection,
    settings: {
      interClickDelayMs: applySettings.interClickDelayMs,
      interMoveDelayMs: applySettings.interMoveDelayMs,
      tangoApplyMode: applySettings.tangoApplyMode,
    },
  });

  if (!response || !response.ok) {
    throw new Error((response && response.error) || "Failed to apply moves.");
  }

  const statusText = buildApplyStatusText(response);
  if (applySettings.autoCloseAfterApply) {
    setStatus(`${statusText} Closing...`);
    setTimeout(() => {
      window.close();
    }, 420);
  } else {
    setStatus(statusText);
  }

  return response;
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

  await applyCachedPayloadForTab(tab, payload);
}

async function handleSolveAndApply() {
  const tab = await getActiveTab();
  const solvedPayload = await solveForTab(tab, { previewOnly: false });

  if (!solvedPayload.solved || !solvedPayload.applied || !solvedPayload.result || !solvedPayload.selection) {
    return;
  }

  await storageSet({
    [selectionStorageKey(tab.id)]: {
      puzzleType: solvedPayload.puzzleType,
      result: solvedPayload.result,
      selection: solvedPayload.selection,
    },
  });

  const applySettings = getApplySettingsFromUi();
  if (applySettings.autoCloseAfterApply) {
    setStatus(`${buildApplyStatusText(solvedPayload)} Closing...`);
    setTimeout(() => {
      window.close();
    }, 420);
  }
}

async function handleClearOverlay() {
  const tab = await getActiveTab();
  const puzzleType = puzzleTypeSelect.value;
  const response = await sendRuntimeMessage({
    type: "clearOverlaysForTab",
    tabId: tab.id,
    puzzleType,
  });

  if (!response || !response.ok) {
    throw new Error((response && response.error) || "Failed to clear overlay.");
  }

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

populatePuzzleTypeOptions();
loadPreferences().catch((error) => {
  setStatus(error.message || String(error), true);
});
