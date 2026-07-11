  function applyLocalSaveUserFlags(target) {
    if (!target || typeof target !== "object") return false;
    var changed = false;
    function setValue(key, value) {
      if (target[key] !== value) {
        target[key] = value;
        changed = true;
      }
    }
    setValue("savePageShowLocal", 1);
    setValue("showLocalLoadM", 1);
    if (target.curOPCloudOption === undefined || target.curOPCloudOption === null) {
      target.curOPCloudOption = 0;
      changed = true;
    }
    return changed;
  }

  function applyCommonPlayerLocalSaveFlags() {
    if (!window.commonPlayer) return false;
    commonPlayer.userInfos = commonPlayer.userInfos || {};
    return applyLocalSaveUserFlags(commonPlayer.userInfos);
  }

  function installLocalSaveModePatch() {
    var patched = applyCommonPlayerLocalSaveFlags();

    if (typeof window.SAL_getUserData === "function" && !window.SAL_getUserData.__officialProxyLocalSaveWrapped) {
      var originalGetUserData = window.SAL_getUserData;
      window.SAL_getUserData = function () {
        var userData = originalGetUserData.apply(this, arguments) || {};
        applyLocalSaveUserFlags(userData);
        if (userData.userData) applyLocalSaveUserFlags(userData.userData);
        if (userData.userInfos) applyLocalSaveUserFlags(userData.userInfos);
        return userData;
      };
      window.SAL_getUserData.__officialProxyLocalSaveWrapped = true;
      patched = true;
      compatLog("official proxy local save user-data patch enabled");
    }

    if (patched) compatLog("official proxy local save flags enabled");
    return patched;
  }

  var cloudSavePayloadInstalled = false;

  var saveFileLocalModeInstalled = false;

  function installSaveFileLocalModePatch() {
    if (
      saveFileLocalModeInstalled ||
      !window.view ||
      !view.SaveFileUI ||
      !view.SaveFileUI.prototype
    ) return false;

    var proto = view.SaveFileUI.prototype;
    var patched = false;

    function selectLocalMode(saveView, updateState) {
      try {
        var gd = window.GloableData && GloableData.getInstance ? GloableData.getInstance() : null;
        if (gd) {
          gd.isCloud = false;
          gd.isOpenSaveFileUI = true;
        }
        if (window.utils && utils.addCookie && window.GloableStaticData && saveView) {
          if (saveView.saveSelectkey) {
            utils.addCookie(saveView.saveSelectkey, GloableStaticData.SELECT_SAVE_TYPE_LOCAL);
          }
          if (saveView.saveGuidekey) utils.addCookie(saveView.saveGuidekey, "1");
          if (saveView.firstOpenKey) utils.addCookie(saveView.firstOpenKey, "1");
        }
        if (saveView) {
          try {
            if (saveView.saveGuidekey) localStorage.setItem(saveView.saveGuidekey, "1");
            if (saveView.firstOpenKey) localStorage.setItem(saveView.firstOpenKey, "1");
          } catch (storageError) {}
          if (updateState && typeof saveView.changeState === "function") saveView.changeState(0);
        }
        if (window.UIManager && UIManager.getInstance && window.view && view.SaveFileGuideMediator) {
          UIManager.getInstance().closeView(view.SaveFileGuideMediator.NAME, false);
        }
      } catch (error) {
        compatLog("official proxy local save UI selection failed: " + (error && (error.stack || error.message) || error));
      }
    }

    if (typeof proto.drawCloudBtn === "function" && !proto.drawCloudBtn.__officialProxyLocalModeWrapped) {
      var originalDrawCloudBtn = proto.drawCloudBtn;
      proto.drawCloudBtn = function () {
        selectLocalMode(this, false);
        var result = originalDrawCloudBtn.apply(this, arguments);
        selectLocalMode(this, true);
        return result;
      };
      proto.drawCloudBtn.__officialProxyLocalModeWrapped = true;
      patched = true;
    }

    if (typeof proto.clickCloud === "function" && !proto.clickCloud.__officialProxyLocalModeWrapped) {
      proto.clickCloud = function () {
        selectLocalMode(this, false);
        if (typeof this.clickLocal === "function") return this.clickLocal();
      };
      proto.clickCloud.__officialProxyLocalModeWrapped = true;
      patched = true;
    }

    if (!patched) return false;
    proto.__officialProxyLocalModePatched = true;
    saveFileLocalModeInstalled = true;
    compatLog("official proxy save UI forced to local mode");
    return true;
  }

  function installCloudSavePayloadPatch() {
    if (
      cloudSavePayloadInstalled ||
      !window.view ||
      !view.SaveFileUI ||
      !view.SaveFileUI.prototype ||
      typeof view.SaveFileUI.prototype.downComplete !== "function"
    ) return false;

    var originalDownComplete = view.SaveFileUI.prototype.downComplete;
    view.SaveFileUI.prototype.downComplete = function (response) {
      if (response && response.data && typeof response.data !== "string") {
        var normalized = {};
        for (var key in response) {
          if (Object.prototype.hasOwnProperty.call(response, key)) normalized[key] = response[key];
        }
        normalized.data = JSON.stringify(response.data);
        response = normalized;
      }
      return originalDownComplete.call(this, response);
    };
    view.SaveFileUI.prototype.downComplete.__officialProxyPayloadWrapped = true;
    cloudSavePayloadInstalled = true;
    compatLog("official proxy cloud save payload normalization enabled");
    return true;
  }

  registerCompatPatch("local save mode", 70, installLocalSaveModePatch);
  registerCompatPatch("save UI local mode", 80, installSaveFileLocalModePatch);
  registerCompatPatch("cloud save payload", 90, installCloudSavePayloadPatch);
