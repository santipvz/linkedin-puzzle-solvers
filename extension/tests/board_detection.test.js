const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

function scripts(context, files) {
  for (const file of files) vm.runInContext(fs.readFileSync(path.join(__dirname, "..", file), "utf8"), context);
}

test("detects Queens from its section landmark with opaque CSS classes and role note", () => {
  const rect = { left: 528, top: 97, width: 416, height: 416, right: 944, bottom: 513 };
  const board = { tagName: "SECTION", className: "ajrmrz ajrmry", role: "note", getBoundingClientRect: () => rect };
  const context = vm.createContext({
    document: { querySelector: (selector) => selector === "#queens-game-board" ? board : null,
      querySelectorAll: () => [] },
    window: { self: {}, top: {}, innerWidth: 1487, innerHeight: 692, devicePixelRatio: 1.25 },
    chrome: { runtime: { onMessage: { addListener() {} } } },
  });
  scripts(context, ["puzzle_registry.js", "content.js"]);
  assert.deepEqual(JSON.parse(JSON.stringify(context.autoDetectBoardSelection("queens"))),
    { x: 528, y: 97, width: 416, height: 416, devicePixelRatio: 1.25 });
});

test("explicit board detection bypasses a cached viewport selection", async () => {
  const context = vm.createContext({ chrome: { runtime: { onMessage: { addListener() {} } } } });
  scripts(context, ["puzzle_registry.js", "api_config.js", "background.js"]);
  const selection = { x: 528, y: 97, width: 416, height: 416, devicePixelRatio: 1.25 };
  context.getTopBoardSelection = async () => { throw new Error("Must not reuse a cached fallback"); };
  context.safeSendTabMessage = async () => ({ selection });
  context.setTopBoardSelection = async (_, value) => value;
  context.resolveInteractionTarget = (value) => ({ frameId: 0, selection: value });
  const response = await context.detectSelectionForQuickSolve(1, "queens", {}, {}, { forceDetect: true });
  assert.equal(response.topSelection.x, 528);
  assert.equal(response.topSelection.width, 416);
});
