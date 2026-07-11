  function isValidGameIndex(value) {
    var parsed = Number(value);
    return isFinite(parsed) && parsed > 0 && Math.floor(parsed) === parsed;
  }

  function installQueryGameIndexFallback() {
    if (!hasCompatCapability("proxy-query-game-index")) return false;
    if (!window.Main || !Main.prototype || !Main.prototype.setGameConfig) return false;
    if (Main.prototype.__officialProxyGameIndexPatched) return true;

    var originalSetGameConfig = Main.prototype.setGameConfig;
    Main.prototype.setGameConfig = function () {
      var result = originalSetGameConfig.apply(this, arguments);
      var queryGameIndex = Number(window.__officialProxyGameId);
      if (!isValidGameIndex(queryGameIndex)) return result;

      if (window.GloableData && GloableData.getInstance) {
        var data = GloableData.getInstance();
        if (data && data.gameInfo && !isValidGameIndex(data.gameInfo.gIndex)) {
          data.gameInfo.gIndex = queryGameIndex;
        }
      }
      if (
        window.commonPlayer && commonPlayer.userInfos &&
        !isValidGameIndex(commonPlayer.userInfos.gindex)
      ) {
        commonPlayer.userInfos.gindex = String(queryGameIndex);
      }
      return result;
    };
    Main.prototype.__officialProxyGameIndexPatched = true;
    compatLog("official proxy query game index fallback enabled");
    return true;
  }

  registerCompatPatch("query game index", 15, installQueryGameIndexFallback);
