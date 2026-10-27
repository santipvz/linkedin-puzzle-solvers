const assert = require("node:assert/strict");
const { test } = require("node:test");
const { validateGitflow } = require("../check_gitflow.js");

test("features and bugfixes enter develop; releases and hotfixes enter main", () => {
  for (const head of ["feature/sudoku", "bugfix/wend"]) {
    assert.equal(validateGitflow("develop", head), true);
    assert.equal(validateGitflow("main", head), false);
  }
  for (const head of ["release/0.2.0", "hotfix/sudoku"]) {
    assert.equal(validateGitflow("main", head), true);
    assert.equal(validateGitflow("develop", head), true);
  }
});

test("main can sync back into develop; develop needs a release branch", () => {
  assert.equal(validateGitflow("develop", "main"), true);
  assert.equal(validateGitflow("main", "develop"), false);
});

test("rejects missing refs, empty topics and unsupported branch names", () => {
  for (const [base, head] of [[undefined, undefined], ["main", "release/"], ["develop", "feature/"],
    ["main", "random"], ["feature/topic", "feature/other"], ["develop", "develop"]]) {
    assert.equal(validateGitflow(base, head), false);
  }
});
