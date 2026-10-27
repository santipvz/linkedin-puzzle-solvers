const validPrefixes = /^(feature|bugfix|release|hotfix)\/.+/;

function validateGitflow(base, head) {
  if (base === "main") return /^(release|hotfix)\/.+/.test(head);
  if (base === "develop") return head === "main" || validPrefixes.test(head);
  return false;
}

if (require.main === module) {
  const [base, head] = process.argv.slice(2);
  if (!validateGitflow(base, head)) {
    console.error(`Invalid Gitflow PR: ${head} -> ${base}. Target develop for features/bugfixes; target main for releases/hotfixes.`);
    process.exitCode = 1;
  } else {
    console.log(`[ok] Gitflow: ${head} -> ${base}`);
  }
}

module.exports = { validateGitflow };
