  function installStorageTracePatch() {
    if (window.__officialProxyStorageTracePatched) return false;
    var hasStorageAPI =
      typeof window.SAL_setStorage === "function" ||
      typeof window.SAL_getStorage === "function" ||
      typeof window.SAL_removeStorage === "function" ||
      typeof window.SAL_getStorageInfo === "function" ||
      (window.OStorage && OStorage.prototype);
    if (!hasStorageAPI) return false;

    window.__officialProxyStorageTracePatched = true;
    window.__officialProxyStorageTrace = window.__officialProxyStorageTrace || [];

    var AUTO_SAVE_SUFFIX = "-100";
    var PRIMARY_ARCHIVE_SLOT = "1";
    var COMPAT_ARCHIVE_SLOT = "0";
    var SAVE_INDEX_SUFFIX = "SaveFileIndex";
    var SAVE_INDEX_LOCAL_SUFFIX = "SaveFileIndexLocal";
    var SAVE_ICON_SUFFIX = "icon";
    var BRIDGE_MARKER_SUFFIX = "__officialProxyAutoArchiveBridge";
    var bridgeWriteDepth = 0;

    function trace(action, key, value) {
      var item = {
        action: action,
        key: key === undefined ? "" : String(key),
        length: value === undefined || value === null ? 0 : String(value).length,
        at: Date.now()
      };
      window.__officialProxyStorageTrace.push(item);
      if (window.__officialProxyStorageTrace.length > 100) window.__officialProxyStorageTrace.shift();
      compatLog("official proxy storage " + action + " key=" + item.key + " len=" + item.length);
    }

    function isMissingStorageValue(value) {
      return value === undefined || value === null || value === "";
    }

    function readRaw(storage, originalLoadFile, key) {
      try {
        return originalLoadFile.call(storage, key);
      } catch (error) {
        return null;
      }
    }

    function writeRaw(storage, originalSaveFile, key, value) {
      try {
        bridgeWriteDepth += 1;
        originalSaveFile.call(storage, key, value);
        return true;
      } catch (error) {
        return false;
      } finally {
        bridgeWriteDepth -= 1;
      }
    }

    function archivePrefixFromKey(key) {
      key = String(key || "");
      if (key.indexOf("local-player") < 0) return "";
      if (key.slice(-SAVE_INDEX_LOCAL_SUFFIX.length) === SAVE_INDEX_LOCAL_SUFFIX) {
        return key.slice(0, -SAVE_INDEX_LOCAL_SUFFIX.length);
      }
      if (key.slice(-SAVE_INDEX_SUFFIX.length) === SAVE_INDEX_SUFFIX) {
        return key.slice(0, -SAVE_INDEX_SUFFIX.length);
      }
      if (key.slice(-SAVE_ICON_SUFFIX.length) === SAVE_ICON_SUFFIX) {
        return key.slice(0, -SAVE_ICON_SUFFIX.length);
      }
      return "";
    }

    function archivePrefixFromAutoKey(key) {
      key = String(key || "");
      if (key.indexOf("local-player") < 0) return "";
      return key.slice(-AUTO_SAVE_SUFFIX.length) === AUTO_SAVE_SUFFIX ? key.slice(0, -AUTO_SAVE_SUFFIX.length) : "";
    }

    function isManualArchiveSlotKey(key) {
      key = String(key || "");
      return /local-player\d+$/.test(key);
    }

    function archivePrefixFromManualSlotKey(key) {
      var match = String(key || "").match(/^(.*local-player)\d+$/);
      return match ? match[1] : "";
    }

    function buildArchiveIconValue(autoSaveValue) {
      var picurl = "";
      try {
        var parsed = JSON.parse(autoSaveValue);
        var thumb = parsed && parsed.Thumbnail;
        picurl = thumb && (thumb.base64 || thumb.picurl || thumb.cloudImageUrl || thumb.cloudImageUr || "") || "";
      } catch (error) {}
      if (!picurl) picurl = buildArchivePlaceholderImage();

      var slots = [];
      for (var index = 0; index < 20; index++) {
        var active = index === parseInt(PRIMARY_ARCHIVE_SLOT, 10);
        slots.push({
          index: index,
          picurl: active ? picurl : "",
          name: active ? "自动存档" : "",
          date: active ? Date.now() : -1
        });
      }
      return encodeURIComponent(JSON.stringify(slots));
    }

    function buildArchivePlaceholderImage() {
      try {
        var canvas = document.createElement("canvas");
        canvas.width = 240;
        canvas.height = 135;
        var ctx = canvas.getContext("2d");
        var gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
        gradient.addColorStop(0, "#f9e8ff");
        gradient.addColorStop(1, "#b59cff");
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "rgba(255,255,255,.75)";
        ctx.fillRect(12, 12, canvas.width - 24, canvas.height - 24);
        ctx.strokeStyle = "rgba(134,94,190,.55)";
        ctx.lineWidth = 3;
        ctx.strokeRect(18, 18, canvas.width - 36, canvas.height - 36);
        ctx.fillStyle = "#7b56b3";
        ctx.font = "bold 22px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("AUTO SAVE", canvas.width / 2, canvas.height / 2);
        return canvas.toDataURL("image/png");
      } catch (error) {
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=";
      }
    }

    function ensureAutoArchiveBridge(storage, originalLoadFile, originalSaveFile, prefix, reason) {
      if (!prefix) return false;
      var autoKey = prefix + AUTO_SAVE_SUFFIX;
      var autoSaveValue = readRaw(storage, originalLoadFile, autoKey);
      if (isMissingStorageValue(autoSaveValue)) return false;

      var markerKey = prefix + BRIDGE_MARKER_SUFFIX;
      var marker = readRaw(storage, originalLoadFile, markerKey);
      if (marker === "manual") return false;

      var slotKey = prefix + PRIMARY_ARCHIVE_SLOT;
      var compatSlotKey = prefix + COMPAT_ARCHIVE_SLOT;
      var indexKey = prefix + SAVE_INDEX_SUFFIX;
      var localIndexKey = prefix + SAVE_INDEX_LOCAL_SUFFIX;
      var iconKey = prefix + SAVE_ICON_SUFFIX;
      var changed = false;

      if (isMissingStorageValue(readRaw(storage, originalLoadFile, slotKey)) || marker === "auto") {
        changed = writeRaw(storage, originalSaveFile, slotKey, autoSaveValue) || changed;
      }
      if (isMissingStorageValue(readRaw(storage, originalLoadFile, compatSlotKey)) || marker === "auto") {
        changed = writeRaw(storage, originalSaveFile, compatSlotKey, autoSaveValue) || changed;
      }
      if (isMissingStorageValue(readRaw(storage, originalLoadFile, indexKey)) || marker === "auto") {
        changed = writeRaw(storage, originalSaveFile, indexKey, "0||" + PRIMARY_ARCHIVE_SLOT) || changed;
      }
      if (isMissingStorageValue(readRaw(storage, originalLoadFile, localIndexKey)) || marker === "auto") {
        changed = writeRaw(storage, originalSaveFile, localIndexKey, PRIMARY_ARCHIVE_SLOT) || changed;
      }
      if (isMissingStorageValue(readRaw(storage, originalLoadFile, iconKey)) || marker === "auto") {
        changed = writeRaw(storage, originalSaveFile, iconKey, buildArchiveIconValue(autoSaveValue)) || changed;
      }
      if (marker !== "auto") {
        changed = writeRaw(storage, originalSaveFile, markerKey, "auto") || changed;
      }
      if (changed) compatLog("official proxy storage bridged autosave archive prefix=" + prefix + " reason=" + reason);
      return changed;
    }

    function bridgeKnownAutoArchives(storage, originalLoadFile, originalSaveFile, originalGetAllFileName) {
      var keys;
      try {
        keys = originalGetAllFileName.call(storage) || [];
      } catch (error) {
        return false;
      }
      var changed = false;
      for (var index = 0; index < keys.length; index++) {
        changed = ensureAutoArchiveBridge(storage, originalLoadFile, originalSaveFile, archivePrefixFromAutoKey(keys[index]), "scan") || changed;
      }
      return changed;
    }

    if (typeof window.SAL_setStorage === "function" && !window.SAL_setStorage.__officialProxyWrapped) {
      var originalSetStorage = window.SAL_setStorage;
      window.SAL_setStorage = function (key, value, callback) {
        trace("SAL_setStorage", key, value);
        return originalSetStorage.apply(this, arguments);
      };
      window.SAL_setStorage.__officialProxyWrapped = true;
    }

    if (typeof window.SAL_getStorage === "function" && !window.SAL_getStorage.__officialProxyWrapped) {
      var originalGetStorage = window.SAL_getStorage;
      window.SAL_getStorage = function (key, callback) {
        trace("SAL_getStorage", key);
        return originalGetStorage.call(this, key, function (value) {
          trace("SAL_getStorageResult", key, value);
          if (typeof callback === "function") callback(value);
        });
      };
      window.SAL_getStorage.__officialProxyWrapped = true;
    }

    if (typeof window.SAL_removeStorage === "function" && !window.SAL_removeStorage.__officialProxyWrapped) {
      var originalRemoveStorage = window.SAL_removeStorage;
      window.SAL_removeStorage = function (key, callback) {
        trace("SAL_removeStorage", key);
        return originalRemoveStorage.apply(this, arguments);
      };
      window.SAL_removeStorage.__officialProxyWrapped = true;
    }

    if (typeof window.SAL_getStorageInfo === "function" && !window.SAL_getStorageInfo.__officialProxyWrapped) {
      var originalGetStorageInfo = window.SAL_getStorageInfo;
      window.SAL_getStorageInfo = function (callback) {
        trace("SAL_getStorageInfo", "*");
        return originalGetStorageInfo.call(this, function (keys) {
          trace("SAL_getStorageInfoResult", "*", JSON.stringify(keys || []));
          if (typeof callback === "function") callback(keys);
        });
      };
      window.SAL_getStorageInfo.__officialProxyWrapped = true;
    }

    if (window.OStorage && OStorage.prototype && !OStorage.prototype.__officialProxyWrapped) {
      OStorage.prototype.__officialProxyWrapped = true;
      var originalSaveFile = OStorage.prototype.saveFile;
      var originalLoadFile = OStorage.prototype.loadFile;
      var originalRemoveFile = OStorage.prototype.removeFile;
      var originalGetAllFileName = OStorage.prototype.getAllFileName;
      OStorage.prototype.saveFile = function (key, value) {
        trace("OStorage.saveFile", key, value);
        var result = originalSaveFile.apply(this, arguments);
        if (!bridgeWriteDepth && isManualArchiveSlotKey(key)) {
          writeRaw(this, originalSaveFile, archivePrefixFromManualSlotKey(key) + BRIDGE_MARKER_SUFFIX, "manual");
        }
        ensureAutoArchiveBridge(this, originalLoadFile, originalSaveFile, archivePrefixFromAutoKey(key), "autosave");
        return result;
      };
      OStorage.prototype.loadFile = function (key) {
        var value = originalLoadFile.apply(this, arguments);
        if (isMissingStorageValue(value)) {
          ensureAutoArchiveBridge(this, originalLoadFile, originalSaveFile, archivePrefixFromKey(key), "load");
          value = originalLoadFile.apply(this, arguments);
        }
        trace("OStorage.loadFile", key, value);
        return value;
      };
      OStorage.prototype.removeFile = function (key) {
        trace("OStorage.removeFile", key);
        return originalRemoveFile.apply(this, arguments);
      };
      OStorage.prototype.getAllFileName = function () {
        bridgeKnownAutoArchives(this, originalLoadFile, originalSaveFile, originalGetAllFileName);
        var keys = originalGetAllFileName.apply(this, arguments);
        trace("OStorage.getAllFileName", "*", JSON.stringify(keys || []));
        return keys;
      };
    }

    compatLog("official proxy storage trace patch enabled");
    return true;
  }

  registerCompatPatch("storage trace", 110, installStorageTracePatch);
