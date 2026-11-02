const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

function background() {
  const calls = [];
  const context = vm.createContext({URL, chrome: {
    runtime: {onMessage: {addListener() {}}},
    tabs: {captureVisibleTab(windowId, options, callback) {calls.push({windowId, options}); callback('image');}},
  }});
  for (const file of ['puzzle_registry.js', 'api_config.js', 'background.js'])
    vm.runInContext(fs.readFileSync(path.join(__dirname, '..', file), 'utf8'), context);
  return {context, calls};
}

test('a fresh installation can capture from the game widget without a toolbar grant', async () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'manifest.json')));
  assert.ok(manifest.host_permissions.includes('<all_urls>'));
  const {context, calls} = background();
  assert.equal(await context.captureVisibleTab({windowId: 7, active: true, url: 'https://www.linkedin.com/games/zip/'}), 'image');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].windowId, 7);
});

test('capture rejects inactive games, unrelated sites, spoofed hosts and other LinkedIn pages', async () => {
  const {context, calls} = background();
  for (const tab of [
    {active: false, url: 'https://www.linkedin.com/games/zip/'},
    {active: true, url: 'https://example.org/games/zip/'},
    {active: true, url: 'https://linkedin.com.example.org/games/zip/'},
    {active: true, url: 'https://www.linkedin.com/feed/'},
    {active: true, url: 'http://www.linkedin.com/games/zip/'},
    {active: true, url: 'invalid'},
  ]) await assert.rejects(context.captureVisibleTab({...tab, windowId: 7}));
  assert.equal(calls.length, 0);
});
