(function registerSolverApiConfig(globalScope) {
  const localUrl = "http://127.0.0.1:8000";
  const onlineUrl = "https://linkedin-puzzle-solvers.vercel.app";
  const normalize = (value) => typeof value === "string" && value.trim()
    ? value.trim().replace(/\/+$/, "") : localUrl;
  globalScope.SolverApiConfig = Object.freeze({
    localUrl,
    onlineUrl,
    defaultUrl: onlineUrl,
    permissionOrigin(value) {
      const url = new URL(normalize(value));
      if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) {
        throw new Error("Use an HTTP or HTTPS service address without embedded credentials.");
      }
      return `${url.protocol}//${url.hostname}/*`;
    },
    maxOnlineUploadBytes: 4 * 1024 * 1024,
    normalize,
    isOnline: (value) => normalize(value) === onlineUrl,
  });
})(globalThis);
