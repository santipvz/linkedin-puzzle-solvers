const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
require("../api_config.js");

test("only the hosted URL opts into the online upload policy; saved local/custom URLs stay local", () => {
  const config = globalThis.SolverApiConfig;
  assert.equal(config.normalize(null), config.localUrl);
  assert.equal(config.isOnline(" https://linkedin-puzzle-solvers.vercel.app/ "), true);
  for (const url of [null, "http://127.0.0.1:18000", "http://localhost:8000", "https://example.org"])
    assert.equal(config.isOnline(url), false);
  assert.equal(config.normalize(" http://127.0.0.1:18000/ "), "http://127.0.0.1:18000");
});

async function popup(storage) {
  const elements = new Map();
  const context = vm.createContext({
    URL,
    document: { querySelector() { return { dataset: {}, setAttribute() {} }; }, getElementById(id) {
      if (!elements.has(id)) elements.set(id, {
        value: "", checked: true, classList: { toggle() {} }, events: {},
        addEventListener(event, callback) { this.events[event] = callback; },
      });
      return elements.get(id);
    } },
    chrome: { runtime: {}, storage: { local: {
      get(keys, callback) { callback({ ...storage }); },
      set(values, callback) { Object.assign(storage, values); callback(); },
    } } },
  });
  for (const file of ["api_config.js", "popup.js"])
    vm.runInContext(fs.readFileSync(path.join(__dirname, "..", file), "utf8"), context);
  await new Promise(setImmediate);
  elements.context = context;
  return elements;
}

test("selecting online preserves the old local URL across closing and reopening the popup", async () => {
  const storage = { solver_api_url: "http://127.0.0.1:18000" };
  let ui = await popup(storage);
  assert.equal(ui.get("apiMode").value, "local");
  assert.equal(ui.get("apiUrl").value, "http://127.0.0.1:18000");
  ui.get("apiMode").value = "online";
  ui.get("apiMode").events.change();
  assert.equal(storage.solver_api_url, globalThis.SolverApiConfig.onlineUrl);
  assert.equal(ui.get("apiUrl").readOnly, true);
  ui = await popup(storage);
  assert.equal(ui.get("apiMode").value, "online");
  ui.get("apiMode").value = "local";
  ui.get("apiMode").events.change();
  assert.equal(storage.solver_api_url, "http://127.0.0.1:18000");
  assert.equal(ui.get("apiUrl").readOnly, false);
});

function transport(oversized = false) {
  const calls = {};
  const context = vm.createContext({
    chrome: { runtime: { onMessage: { addListener() {} } } },
    createImageBitmap: async () => ({ width: 1200, height: 900, close() { calls.closed = true; } }),
    OffscreenCanvas: class {
      constructor(width, height) { calls.dimensions = [width, height]; }
      getContext() { return { fillRect() {}, drawImage() {} }; }
      async convertToBlob() { return { type: "image/jpeg", size: oversized ? 5 * 1024 * 1024 : 1000 }; }
    },
    FormData: class { append(key, blob, filename) { calls.filename = filename; } },
    fetch: async (url, options) => {
      calls.url = url;
      calls.options = options;
      return { ok: true, text: async () => '{"solved":true}' };
    },
  });
  for (const file of ["puzzle_registry.js", "api_config.js", "background.js"])
    vm.runInContext(fs.readFileSync(path.join(__dirname, "..", file), "utf8"), context);
  return { context, calls };
}

test("large online uploads preserve dimensions when compressed and use the correct JPEG filename", async () => {
  const { context, calls } = transport();
  await context.callSolverApi(globalThis.SolverApiConfig.onlineUrl, "sudoku", { size: 5 * 1024 * 1024 });
  assert.deepEqual(calls.dimensions, [1200, 900]);
  assert.equal(calls.filename, "sudoku_board.jpg");
  assert.equal(calls.closed, true);
  assert.equal(calls.url, `${globalThis.SolverApiConfig.onlineUrl}/solve/sudoku`);
});

test("an image still over the online limit is rejected before sending a request", async () => {
  const { context, calls } = transport(true);
  await assert.rejects(context.callSolverApi(globalThis.SolverApiConfig.onlineUrl, "sudoku", { size: 5 * 1024 * 1024 }), /too large/);
  assert.equal(calls.url, undefined);
});


test("new installations default to Online without changing saved local addresses", async () => {
  assert.equal(globalThis.SolverApiConfig.defaultUrl, globalThis.SolverApiConfig.onlineUrl);
  const ui = await popup({});
  assert.equal(ui.get("apiMode").value, "online");
  ui.get("apiMode").value = "local";
  ui.get("apiMode").events.change();
  assert.equal(ui.get("apiUrl").value, globalThis.SolverApiConfig.localUrl);
});

test("custom service permissions are scoped to one host and reject embedded credentials", () => {
  const config = globalThis.SolverApiConfig;
  assert.equal(config.permissionOrigin("https://solver.example:8443/api/"), "https://solver.example/*");
  assert.equal(config.permissionOrigin("http://127.0.0.1:18000"), "http://127.0.0.1/*");
  assert.throws(() => config.permissionOrigin("https://name:password@solver.example/"), /credentials/);
  assert.throws(() => config.permissionOrigin("file:///tmp/solver"), /HTTP/);
});


test("a custom service asks for only its host and a declined request stops the action", async () => {
  const ui = await popup({solver_api_url: "https://solver.example:8443/api"});
  let requested;
  ui.context.chrome.permissions = {
    contains: (permissions, callback) => callback(false),
    request: (permissions, callback) => { requested = JSON.parse(JSON.stringify(permissions)); callback(false); },
  };
  await assert.rejects(ui.context.ensureApiPermission(), /not granted/);
  assert.deepEqual(requested, {origins: ["https://solver.example/*"]});
});

test("already allowed services do not trigger a permission prompt", async () => {
  const ui = await popup({});
  ui.context.chrome.permissions = {contains: (permissions, callback) => callback(true),
    request: () => { throw new Error("Unexpected prompt"); }};
  await ui.context.ensureApiPermission();
});
