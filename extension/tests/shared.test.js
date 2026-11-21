const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function sharedContext(globals = {}) {
  const context = vm.createContext({ ...globals });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'shared.js'), 'utf8'), context);
  return context;
}

test('re-injected content scripts are the ones the manifest loads', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'manifest.json'), 'utf8'));
  assert.deepEqual([...sharedContext().CONTENT_SCRIPT_FILES], manifest.content_scripts[0].js);
});

test('shared.js can be injected twice into the same page', () => {
  const context = sharedContext();
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'shared.js'), 'utf8'), context);
  assert.equal(context.DEFAULT_MOVE_INTERVAL_MS, 100);
});

test('selections and delays are normalized the same way everywhere', () => {
  const context = sharedContext();
  assert.deepEqual({ ...context.normalizeSelection({ x: '1', y: 2, width: 30, height: 40 }) },
    { x: 1, y: 2, width: 30, height: 40, devicePixelRatio: 1 });
  assert.equal(context.normalizeSelection({ x: 0, y: 0, width: 9, height: 40 }), null);
  assert.equal(context.normalizeDelay('720', 45), 500);
  assert.equal(context.normalizeDelay('abc', 45), 45);
});

test('content scripts are injected when a tab has no receiver yet', async () => {
  const sent = [], injected = [];
  let ready = false;
  const chrome = {
    runtime: { lastError: null },
    tabs: { sendMessage(_tab, message, _options, done) {
      sent.push(message.type);
      chrome.runtime.lastError = ready ? null : { message: 'Could not establish connection. Receiving end does not exist.' };
      done(ready ? { ok: true } : undefined);
    } },
    scripting: { executeScript(details, done) { injected.push(details); ready = true; chrome.runtime.lastError = null; done([]); } },
  };
  const context = sharedContext({ chrome });
  const response = await context.sendTabMessageWithInjection(7, { type: 'ping' }, { frameId: 3 });
  assert.deepEqual({ ...response }, { ok: true });
  assert.deepEqual(sent, ['ping', 'ping']);
  assert.deepEqual(JSON.parse(JSON.stringify(injected)), [{ target: { tabId: 7, frameIds: [3] }, files: [...context.CONTENT_SCRIPT_FILES] }]);
});
