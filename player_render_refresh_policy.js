(function (root, factory) {
  "use strict";

  var policyApi = factory();
  if (typeof module === "object" && module.exports) module.exports = policyApi;
  if (root) root.__playerRenderRefreshPolicy = policyApi;
})(typeof window !== "undefined" ? window : globalThis, function () {
  "use strict";

  function hasCapability(registry, capability) {
    return !!(
      registry &&
      typeof registry.hasCapability === "function" &&
      registry.hasCapability(capability)
    );
  }

  function resolve(registry) {
    var publicRepaintOnly = hasCapability(registry, "render-public-repaint-only");
    return {
      id: publicRepaintOnly ? "public-repaint-only" : "legacy-forced-repaint",
      forceRepaintLevel: !publicRepaintOnly,
      recache: !publicRepaintOnly
    };
  }

  return { resolve: resolve };
});
