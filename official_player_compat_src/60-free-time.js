  function installFreeTimeBypass() {
    var patched = false;
    var bypass = function (success, failure) {
      this.__officialProxyFreeTimeBypassed = true;
      if (window.GloableData && GloableData.getInstance) {
        GloableData.getInstance().isFreeLimit = false;
        GloableData.getInstance().isFreeTime = 0;
      }
      compatLog("official proxy bypass free-time gate");
      if (typeof success === "function") return success();
      if (typeof failure === "function") return failure();
      return undefined;
    };

    if (window.OrgWebFree && OrgWebFree.prototype && !OrgWebFree.prototype.__officialProxyFreeTimeBypassed) {
      OrgWebFree.prototype.getFreeTime = bypass;
      OrgWebFree.prototype.__officialProxyFreeTimeBypassed = true;
      patched = true;
    }

    if (window.UIManager && UIManager.getInstance) {
      var ui;
      try {
        ui = UIManager.getInstance();
      } catch (error) {
        return patched;
      }
      var layer = ui && ui.orgWebFreeLayer;
      if (layer && !layer.__officialProxyFreeTimeBypassed) {
        layer.getFreeTime = bypass;
        layer.__officialProxyFreeTimeBypassed = true;
        patched = true;
      }
    }

    if (patched) compatLog("official proxy local free-time gate bypass enabled");
    return patched;
  }

  registerCompatPatch("free-time", 100, installFreeTimeBypass);
