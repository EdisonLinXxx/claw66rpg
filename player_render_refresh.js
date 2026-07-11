(function () {
  "use strict";

  if (window.__playerRenderRefreshInstalled) return;
  window.__playerRenderRefreshInstalled = true;

  var canvas = null;
  var refreshTimer = 0;
  var refreshGeneration = 0;
  var lastStageSignature = "";
  var ignoreSignatureUntil = 0;

  function log(message) {
    if (window.debug === true || /(?:^|[?&])(?:debug|trace)=1(?:&|$)/.test(String(window.location.search || ""))) {
      console.log("[player-render-refresh] " + message);
    }
  }

  function getChildren(node) {
    return (node && (node._children || node._childs || node._$childs)) || [];
  }

  function invalidateTree(node, budget) {
    if (!node || budget.count >= 2048) return;
    budget.count += 1;

    if (typeof node.repaint === "function") node.repaint(1);
    node._repaint = 3;
    if (node._cacheStyle) node._cacheStyle.reCache = true;

    var children = getChildren(node);
    for (var index = 0; index < children.length; index += 1) {
      invalidateTree(children[index], budget);
      if (budget.count >= 2048) break;
    }
  }

  function repaintStage() {
    var stage = window.Laya && Laya.stage;
    if (!stage) return false;

    invalidateTree(stage, { count: 0 });
    if (typeof stage.repaint === "function") stage.repaint(1);
    if (window.Laya && Laya.timer && typeof Laya.timer.frameOnce === "function") {
      Laya.timer.frameOnce(1, null, function () {
        invalidateTree(stage, { count: 0 });
      });
    }
    return true;
  }

  function runRefreshSequence(reason) {
    refreshTimer = 0;
    refreshGeneration += 1;
    var generation = refreshGeneration;
    ignoreSignatureUntil = Date.now() + 2300;
    var repaintDelays = [0, 50, 140, 320, 650, 1100, 1800];

    repaintDelays.forEach(function (delay) {
      window.setTimeout(function () {
        if (generation === refreshGeneration) repaintStage();
      }, delay);
    });
    log("refresh sequence: " + reason);
  }

  function requestRefresh(reason) {
    if (refreshTimer) window.clearTimeout(refreshTimer);
    refreshTimer = window.setTimeout(function () {
      runRefreshSequence(reason);
    }, 40);
  }

  function findCanvas() {
    var nextCanvas = document.getElementById("layaCanvas") || document.querySelector("canvas");
    if (!nextCanvas || nextCanvas === canvas) return nextCanvas;

    canvas = nextCanvas;
    ["click", "touchend"].forEach(function (eventName) {
      canvas.addEventListener(eventName, function (event) {
        if (event.isTrusted === true) {
          requestRefresh("user-input");
        }
      }, true);
    });
    requestRefresh("canvas-ready");
    return canvas;
  }

  function stageSignature() {
    var stage = window.Laya && Laya.stage;
    if (!stage) return "";
    var queue = [stage];
    var queueIndex = 0;
    var parts = [];
    var visited = 0;
    while (queueIndex < queue.length && visited < 512) {
      var node = queue[queueIndex];
      queueIndex += 1;
      var children = getChildren(node);
      var texture = node && (node.texture || node._texture);
      parts.push(
        children.length,
        node && node.visible === false ? 0 : 1,
        texture && (texture.url || texture.sourceWidth || texture.width || 1) || 0
      );
      for (var index = 0; index < children.length; index += 1) queue.push(children[index]);
      visited += 1;
    }
    return parts.join("|");
  }

  window.addEventListener("load", function () { requestRefresh("window-load"); }, true);
  window.addEventListener("resize", function () { requestRefresh("resize"); }, true);
  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) requestRefresh("visible");
  });

  if (window.PerformanceObserver) {
    try {
      var resourceObserver = new PerformanceObserver(function (list) {
        var entries = list.getEntries();
        for (var index = 0; index < entries.length; index += 1) {
          var entry = entries[index];
          if (
            /(?:shareres|graphics|\.png(?:\?|$)|\.jpe?g(?:\?|$)|\.webp(?:\?|$))/i.test(String(entry.name || ""))
          ) {
            requestRefresh("resource-complete");
            break;
          }
        }
      });
      resourceObserver.observe({ entryTypes: ["resource"] });
    } catch (_) {}
  }

  window.setInterval(function () {
    findCanvas();
    var signature = stageSignature();
    if (!signature || signature === lastStageSignature) return;
    lastStageSignature = signature;
    if (Date.now() >= ignoreSignatureUntil) requestRefresh("stage-change");
  }, 300);

  window.__playerRenderRefresh = {
    request: requestRefresh,
    repaint: repaintStage
  };
})();
