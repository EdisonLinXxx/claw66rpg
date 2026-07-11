(function (root, factory) {
  "use strict";

  var loaderApi = factory();
  if (typeof module === "object" && module.exports) module.exports = loaderApi;
  if (root && root.document) root.__officialProxyProfileReady = loaderApi.load(root);
})(typeof window !== "undefined" ? window : globalThis, function () {
  "use strict";

  function normalizeGameId(value) {
    var gameId = String(value || "");
    return /^\d+$/.test(gameId) ? gameId : "";
  }

  function profileUrl(gameId, version) {
    var normalizedGameId = normalizeGameId(gameId);
    if (!normalizedGameId) return "";
    return "official_player_game_profiles/" + normalizedGameId + ".js?v=" +
      encodeURIComponent(String(version || "unversioned"));
  }

  function load(target) {
    var url = profileUrl(target.__officialProxyGameId, target.__officialProxyVersion);
    return new target.Promise(function (resolve) {
      if (!url) {
        resolve({ status: "skipped", url: "" });
        return;
      }

      var script = target.document.createElement("script");
      script.src = url;
      script.async = true;
      script.onload = function () {
        resolve({ status: "loaded", url: url });
      };
      script.onerror = function () {
        if (typeof target.logLine === "function") {
          target.logLine("official proxy no game profile " + url);
        }
        resolve({ status: "missing", url: url });
      };
      (target.document.head || target.document.documentElement).appendChild(script);
    });
  }

  return {
    load: load,
    normalizeGameId: normalizeGameId,
    profileUrl: profileUrl
  };
});
