  function compatLog(message) {
    if (typeof window.logLine === "function") window.logLine(message);
    else if (window.console && console.log) console.log(message);
  }

  function getJsonpCallbackName(url) {
    var match = String(url).match(/[?&](?:jsonCallBack|callback|cb)=([^&]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  var DEV_INVENTORY_KEY_PREFIX = "officialProxyDevFreeUnlockInventory:v2:";
  var DEV_FLOWER_AMOUNT = 9999;
  var DEV_FLOWER_COIN_AMOUNT = DEV_FLOWER_AMOUNT * 100;

  function parseUrlParams(url) {
    var params = {};
    var query = String(url || "").split("?")[1] || "";
    query = query.split("#")[0];
    query.split("&").forEach(function (part) {
      if (!part) return;
      var pair = part.split("=");
      var key = decodeURIComponent(pair.shift() || "");
      var value = decodeURIComponent(pair.join("=") || "");
      if (!key) return;
      params[key] = value;
    });
    return params;
  }

  function intParam(params, keys, fallback) {
    for (var index = 0; index < keys.length; index++) {
      var value = params[keys[index]];
      if (value !== undefined && value !== "") {
        var parsed = parseInt(value, 10);
        if (!isNaN(parsed)) return parsed;
      }
    }
    return fallback;
  }

  function getDevInventoryKey() {
    return DEV_INVENTORY_KEY_PREFIX + String(window.__officialProxyGameId || "default");
  }

  var compatPatches = [];
  var compatGameProfiles = [];

  function registerCompatPatch(name, order, installer) {
    compatPatches.push({ name: name, order: order, installer: installer });
  }

  function registerGameProfile(profile) {
    compatGameProfiles.push(profile);
  }

  function gameProfileMatches(profile) {
    if (String(window.__officialProxyGuid || "") !== String(profile.guid || "")) return false;
    if (profile.versions === "*") return true;
    var currentVersion = String(window.__officialProxyVersion || "");
    return (profile.versions || []).some(function (version) {
      return String(version) === currentVersion;
    });
  }

  function getActiveGameProfiles() {
    return compatGameProfiles.filter(gameProfileMatches);
  }

  function getActiveCompatCapabilities() {
    var capabilities = [];
    getActiveGameProfiles().forEach(function (profile) {
      (profile.capabilities || []).forEach(function (capability) {
        if (capabilities.indexOf(capability) === -1) capabilities.push(capability);
      });
    });
    return capabilities;
  }

  function hasCompatCapability(capability) {
    return getActiveCompatCapabilities().indexOf(capability) !== -1;
  }

  function installRegisteredCompatPatches() {
    var ok = false;
    compatPatches.slice().sort(function (left, right) {
      return left.order - right.order;
    }).forEach(function (patch) {
      try {
        ok = patch.installer() || ok;
      } catch (error) {
        compatLog("official proxy " + patch.name + " patch skipped: " +
          (error && (error.stack || error.message) || error));
      }
    });
    return ok;
  }
