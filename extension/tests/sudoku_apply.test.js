const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

function createGame(options = {}) {
  const values = Array(36).fill(0);
  let selected = -1;
  let now = 0;
  let boardGone = false;
  let victoryAt = 0;
  const writes = [];
  const timers = [];
  let cells;
  let notesEnabled = Boolean(options.notesEnabled);
  const noteCells = new Set(options.notesAtStart || []);
  for (const index of noteCells) values[index] = 1;
  class Element {
    constructor(index, child = false) {
      this.index = index;
      this.child = child;
      this.isConnected = true;
      this.parentElement = null;
    }
    getBoundingClientRect() {
      const x = 20 + (this.index % 6) * 50;
      const y = 20 + Math.floor(this.index / 6) * 50;
      const inset = this.child ? 19 : 0;
      return { left: x + inset, top: y + inset, width: 50 - inset * 2, height: 50 - inset * 2 };
    }
    get textContent() { return values[this.index] ? String(values[this.index]) : ""; }
    getAttribute(name) {
      if (name === "data-cell-idx") return this.child || this.index < 0 ? null : String(this.index);
      return name === "aria-selected" ? String(selected === this.index) : null;
    }
    get classList() { return { contains: (name) => name === "sudoku-cell-active" && selected === this.index }; }
    querySelector(selector) { return selector === ".sudoku-cell-notes" && noteCells.has(this.index) ? {} : null; }
    // LinkedIn's cells are divs without tabindex; only the grid can take focus.
    focus() { if (this.index === -2) document.activeElement = this; }
    closest(selector) { return selector === ".sudoku-grid" ? grid : null; }
    contains(other) { return other === this || other?.parentElement === this; }
    dispatchEvent(event) {
      if (!this.isConnected) return true;
      if (event.type === "click") {
        if (this.index === -1) { notesEnabled = false; return true; }
        if (options.ignoreClicks) return true;
        const select = () => { selected = this.index; };
        if (options.selectionDelay) timers.push({ at: now + options.selectionDelay, run: select });
        else select();
        if (options.rerender) render();
      }
      if (event.type === "keydown" && selected >= 0 && !options.ignoreKeys &&
          (!options.requireGridFocus || document.activeElement === grid)) {
        const write = () => {
          const index = options.wrongCell ? (selected + 1) % 36 : selected;
          const finishing = options.finishAtWrite === writes.length + 1;
          if (!finishing || !options.skipFinishingValue) values[index] = Number(event.key);
          if (notesEnabled) noteCells.add(index);
          else noteCells.delete(index);
          writes.push(index);
          if (finishing) {
            boardGone = true;
            victoryAt = now + (options.victoryDelay || 0);
            for (const cell of cells) cell.isConnected = false;
          }
        };
        if (options.writeDelay) timers.push({ at: now + options.writeDelay, run: write });
        else write();
      }
      return true;
    }
  }
  const grid = new Element(-2);
  function render() {
    if (cells) for (const cell of cells) { cell.isConnected = false; cell.childElement.isConnected = false; }
    cells = values.map((_, i) => {
      const cell = new Element(i);
      cell.childElement = new Element(i, true);
      cell.childElement.parentElement = cell;
      return cell;
    });
  }
  render();
  const notesControl = new Element(-1);
  notesControl.getBoundingClientRect = () => ({ left: 0, top: 350, width: 100, height: 30 });
  const document = {
    body: { get innerText() { return boardGone && options.victoryReceipt && now >= victoryAt ? "Mini Sudoku ¡Estás arrasando! Resuelto en 0:19" : ""; } },
    activeElement: null,
    querySelector(selector) {
      if (selector === '[data-control-btn="notes"]') return notesControl;
      return notesEnabled && selector.includes("sudoku-under-board__text--active") ? {} : null;
    },
    elementFromPoint(x, y) {
      if (boardGone) return null;
      if (y >= 350 && y <= 380) return notesControl;
      if (x < 20 || y < 20 || x >= 320 || y >= 320) return null;
      const index = Math.floor((y - 20) / 50) * 6 + Math.floor((x - 20) / 50);
      if (options.missingCell === index) return null;
      return options.childTargets ? cells[index].childElement : cells[index];
    },
  };
  const context = vm.createContext({
    window: { self: {}, top: {}, innerWidth: 400, innerHeight: 400, devicePixelRatio: 1,
      location: { pathname: "/games/view/mini-sudoku/desktop/" } },
    document,
    chrome: { runtime: { onMessage: { addListener() {} } } },
    Element, HTMLElement: Element, HTMLIFrameElement: class {},
    MouseEvent: class { constructor(type, data) { this.type = type; Object.assign(this, data); } },
    KeyboardEvent: class { constructor(type, data) { this.type = type; Object.assign(this, data); } },
  });
  for (const file of ["puzzle_registry.js", "content.js"]) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, "..", file), "utf8"), context);
  }
  context.sleep = async (ms) => {
    now += ms;
    for (const timer of [...timers]) if (timer.at <= now) { timers.splice(timers.indexOf(timer), 1); timer.run(); }
  };
  context.autoDetectBoardSelection = () => null;
  const selection = { x: 20, y: 20, width: 300, height: 300, devicePixelRatio: 1 };
  const result = { solved: true, board_size: 6, initial_grid: Array.from({ length: 6 }, () => Array(6).fill(0)),
    moves: [{ row: 0, col: 0, value: 1 }, { row: 0, col: 1, value: 2 }, { row: 1, col: 2, value: 3 }] };
  return { context, values, writes, result, selection,
    apply: () => context.applySudokuSolution(result, selection, { interClickDelayMs: 0, interMoveDelayMs: 0 }) };
}

test("applies numbers to fresh cell elements after a click rerenders the board", async () => {
  const game = createGame({ rerender: true, childTargets: true });
  const response = await game.apply();
  assert.equal(response.ok, true);
  assert.deepEqual(game.writes, [0, 1, 8]);
  assert.equal(response.appliedCount, 3);
});

test("waits for selection and for the game to accept each number", async () => {
  const game = createGame({ selectionDelay: 150, writeDelay: 100 });
  const response = await game.apply();
  assert.equal(response.ok, true);
  assert.deepEqual(game.writes, [0, 1, 8]);
});

test("focuses the keyboard grid on the first apply without a page reload", async () => {
  const game = createGame({ requireGridFocus: true });
  assert.equal((await game.apply()).ok, true);
  assert.deepEqual(game.writes, [0, 1, 8]);
});

test("does not type into the previous selection when clicks are ignored", async () => {
  const game = createGame({ ignoreClicks: true });
  const response = await game.apply();
  assert.equal(response.ok, false);
  assert.equal(response.appliedCount, 0);
  assert.deepEqual(game.writes, []);
});

test("does not report success or repeat a solution when the game ignores keys", async () => {
  const game = createGame({ ignoreKeys: true });
  const response = await game.apply();
  assert.equal(response.ok, false);
  assert.equal(response.appliedCount, 0);
  assert.equal(response.keyCount, 1);
});

test("requires a complete grid before sending any keys", async () => {
  const game = createGame({ missingCell: 35 });
  const response = await game.apply();
  assert.equal(response.ok, false);
  assert.deepEqual(game.writes, []);
});

test("stops immediately if a number appears in another cell", async () => {
  const game = createGame({ wrongCell: true });
  const response = await game.apply();
  assert.equal(response.ok, false);
  assert.deepEqual(game.writes, [1]);
  assert.equal(response.appliedCount, 0);
});

test("serializes concurrent apply requests in the same game", async () => {
  const game = createGame({ writeDelay: 100 });
  const first = game.apply();
  const second = await game.apply();
  assert.equal(second.ok, false);
  assert.match(second.error, /progress/i);
  assert.equal((await first).ok, true);
  assert.deepEqual(game.writes, [0, 1, 8]);
});

test("disables notes before entering committed values", async () => {
  const game = createGame({ notesEnabled: true });
  const response = await game.apply();
  assert.equal(response.ok, true);
  assert.deepEqual(game.writes, [0, 1, 8]);
  assert.equal(response.appliedCount, 3);
});

test("rejects shifted coordinates even if the geometry looks like a grid", async () => {
  const game = createGame();
  const originalGetAttribute = game.context.Element.prototype.getAttribute;
  game.context.Element.prototype.getAttribute = function(name) {
    return name === "data-cell-idx" ? String((this.index + 1) % 36) : originalGetAttribute.call(this, name);
  };
  assert.equal((await game.apply()).ok, false);
  assert.deepEqual(game.writes, []);
});

test("a single existing note is not mistaken for an already filled cell", async () => {
  const game = createGame({ notesAtStart: [0] });
  assert.equal((await game.apply()).ok, true);
  assert.deepEqual(game.writes, [0, 1, 8]);
});

function completeGame(options) {
  const game = createGame(options);
  const moves = Array.from({ length: 36 }, (_, index) => ({ row: Math.floor(index / 6), col: index % 6,
    value: (Math.floor(index / 6) * 3 + Math.floor(index / 12) + index % 6 + 5) % 6 + 1 }));
  // The reported failure was 6 in row 6, column 2, after winning.
  game.result.moves = [...moves.filter((move) => move.row !== 5 || move.col !== 1), moves[31]];
  return game;
}

test("confirms the final 6 after the winning key removes the completed board", async () => {
  const game = completeGame({ finishAtWrite: 36 });
  const response = await game.apply();
  assert.equal(response.ok, true);
  assert.equal(response.appliedCount, 36);
  assert.equal(game.values[31], 6);
  assert.equal(game.writes.length, 36);
});

test("accepts the explicit victory receipt when the final digit is not painted", async () => {
  const game = completeGame({ finishAtWrite: 36, skipFinishingValue: true, victoryReceipt: true, victoryDelay: 1000 });
  const response = await game.apply();
  assert.equal(response.ok, true);
  assert.equal(response.appliedCount, 36);
  assert.equal(game.writes.length, 36);
});

test("does not infer victory from a disappearing grid with an unconfirmed final digit", async () => {
  const game = completeGame({ finishAtWrite: 36, skipFinishingValue: true });
  const response = await game.apply();
  assert.equal(response.ok, false);
  assert.equal(response.appliedCount, 35);
  assert.equal(response.keyCount, 36);
  assert.equal(game.writes.length, 36);
});

test("does not accept a victory receipt before the other 35 values are verified", async () => {
  const game = completeGame({ finishAtWrite: 1, skipFinishingValue: true, victoryReceipt: true });
  assert.equal((await game.apply()).ok, false);
  assert.equal(game.writes.length, 1);
});

function createBackground() {
  const context = vm.createContext({ chrome: { runtime: { onMessage: { addListener() {} } } } });
  for (const file of ["puzzle_registry.js", "api_config.js", "background.js"]) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, "..", file), "utf8"), context);
  }
  context.buildApplyTargets = async () => [{ frameId: 1, selection: {} }, { frameId: 2, selection: {} }];
  return context;
}

for (const outcome of [
  { ok: false, appliedCount: 1, clickCount: 1, keyCount: 1 },
  { ok: false, appliedCount: 0, clickCount: 1, keyCount: 1 },
  { ok: false, inProgress: true },
  { ok: false, deliveryUnknown: true },
]) {
  test(`background does not replay a Sudoku apply after ${JSON.stringify(outcome)}`, async () => {
    const context = createBackground();
    let requests = 0;
    context.safeSendTabMessage = async () => { requests += 1; return outcome; };
    assert.equal(await context.applySolutionForSelection(1, "sudoku", {}, 1, {}, {}, {}, {}), outcome);
    assert.equal(requests, 1);
  });
}

test("background preserves a partial write from the auto-detect fallback", async () => {
  const context = createBackground();
  let requests = 0;
  const partial = { ok: false, appliedCount: 1, keyCount: 1 };
  context.safeSendTabMessage = async () => (++requests === 1 ? { ok: false } : partial);
  assert.equal(await context.applySolutionForSelection(1, "sudoku", {}, 1, {}, {}, {}, {}), partial);
  assert.equal(requests, 2);
});

test("a lost response is treated as unknown delivery rather than safe to replay", async () => {
  const context = createBackground();
  context.sendTabMessageWithInjection = async () => { throw new Error("The message port closed before a response was received."); };
  const response = await context.safeSendTabMessage(1, { type: "applySolution", puzzleType: "sudoku" });
  assert.equal(response.deliveryUnknown, true);
  assert.equal(context.shouldRetrySudokuApplyWithoutSelection(response), false);
});
