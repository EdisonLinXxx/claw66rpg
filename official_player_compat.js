(function () {
  function compatLog(message) {
    if (typeof window.logLine === "function") window.logLine(message);
    else if (window.console && console.log) console.log(message);
  }

  function getJsonpCallbackName(url) {
    var match = String(url).match(/[?&](?:jsonCallBack|callback|cb)=([^&]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function getDevFreeUnlockPayload(url) {
    var text = String(url || "");
    var lower = text.toLowerCase();
    var isLocalApi =
      lower.indexOf("propshop/") !== -1 ||
      lower.indexOf("/engine/") !== -1 ||
      lower.indexOf("/game/") !== -1 ||
      lower.indexOf("/task/") !== -1 ||
      lower.indexOf("/pay") !== -1 ||
      lower.indexOf("/flower") !== -1 ||
      lower.indexOf("/account") !== -1 ||
      lower.indexOf("/user/") !== -1;

    if (!isLocalApi) return null;

    if (lower.indexOf("getmyaccountmoney") !== -1 || lower.indexOf("accountmoney") !== -1 || lower.indexOf("balance") !== -1) {
      return {
        status: 1,
        data: {
          coin_count: 999999,
          gold_count: 999999,
          flower_count: 999999,
          diamond_count: 999999,
          acoin: 999999
        }
      };
    }
    if (lower.indexOf("getuserhaveallpropnum") !== -1) {
      return { status: 1, data: [] };
    }
    if (lower.indexOf("getuserhavepropnum") !== -1 || lower.indexOf("propnum") !== -1) {
      return { status: 1, data: { num: 999999, count: 999999, prop_num: 999999 } };
    }
    if (lower.indexOf("get_user_hp") !== -1 || lower.indexOf("init_user_hp") !== -1) {
      return { status: 1, data: { hp: 999999, max_hp: 999999 } };
    }
    if (lower.indexOf("getlimitfreetime") !== -1 || lower.indexOf("getoldlimitfreetime") !== -1) {
      return { status: 1, data: { is_free: 1, time: 0 } };
    }
    if (
      lower.indexOf("unlock") !== -1 ||
      lower.indexOf("buy") !== -1 ||
      lower.indexOf("pay") !== -1 ||
      lower.indexOf("consume") !== -1 ||
      lower.indexOf("charge") !== -1 ||
      lower.indexOf("flower") !== -1
    ) {
      return {
        status: 1,
        msg: "local dev free unlock",
        data: { ok: 1, success: 1, is_buy: 1, is_unlock: 1, unlock: 1 }
      };
    }
    return null;
  }

  function installDevFreeUnlockPatch() {
    if (!window.__officialProxyDevFreeUnlock) return false;
    var patched = false;

    if (window.GloableData && GloableData.getInstance) {
      var data = GloableData.getInstance();
      data.isFreeLimit = false;
      data.isFreeTime = 0;
      data.flowerUnlock = 0;
      data.gameFvTimes = 999999;
    }

    var scriptSrcDescriptor = Object.getOwnPropertyDescriptor(HTMLScriptElement.prototype, "src");
    if (scriptSrcDescriptor && scriptSrcDescriptor.set && !scriptSrcDescriptor.set.__officialProxyDevFreeUnlockWrapped) {
      Object.defineProperty(HTMLScriptElement.prototype, "src", {
        get: scriptSrcDescriptor.get,
        set: function (value) {
          var payload = getDevFreeUnlockPayload(value);
          var callbackName = payload && getJsonpCallbackName(value);
          if (payload && callbackName) {
            compatLog("official proxy dev free unlock JSONP " + callbackName + " " + value);
            var script = callbackName + "(" + JSON.stringify(payload) + ");";
            return scriptSrcDescriptor.set.call(this, "data:text/javascript;charset=utf-8," + encodeURIComponent(script));
          }
          return scriptSrcDescriptor.set.call(this, value);
        }
      });
      Object.getOwnPropertyDescriptor(HTMLScriptElement.prototype, "src").set.__officialProxyDevFreeUnlockWrapped = true;
      compatLog("official proxy dev free unlock JSONP patch enabled");
      patched = true;
    }

    if (window.OrgWeb && OrgWeb.prototype && !OrgWeb.prototype.__officialProxyDevFreeUnlockPatched) {
      OrgWeb.prototype.__officialProxyDevFreeUnlockPatched = true;
      OrgWeb.prototype.getIsUnLock = function () { return true; };
      patched = true;
    }

    return patched;
  }

  function installButtonPaddingPatch() {
    if (!window.org_data || !org_data.DButton || org_data.DButton.__officialProxyPadWrapped) return false;
    var OriginalDButton = org_data.DButton;
    var readI32LE = function (stream, pos) {
      try {
        return new DataView(stream.buffer).getInt32(pos, true);
      } catch (error) {
        return null;
      }
    };
    var PaddedDButton = function (stream) {
      if (stream && typeof stream.pos === "number" && stream.buffer && stream.pos + 5 < stream.buffer.byteLength) {
        var current = readI32LE(stream, stream.pos);
        var shifted = readI32LE(stream, stream.pos + 1);
        var head = new Uint8Array(stream.buffer, stream.pos, 1)[0];
        if (head === 0 && current % 256 === 0 && shifted > 0 && shifted < 10000) {
          stream.pos += 1;
        }
      }
      return new OriginalDButton(stream);
    };
    PaddedDButton.prototype = OriginalDButton.prototype;
    PaddedDButton.__officialProxyPadWrapped = true;
    org_data.DButton = PaddedDButton;
    compatLog("official proxy DButton padding compat enabled");
    return true;
  }

  function installNewDSystemPatch() {
    if (!window.org_data || !org_data.DSystem || org_data.DSystem.__officialProxyNewPatched) return false;

    var parseEventList = function (stream) {
      var count = stream.getInt32();
      var events = new Array(count);
      for (var index = 0; index < count; index++) {
        stream.getInt32();
        events[index] = new org_data.DEvent(stream);
      }
      return events;
    };

    var NewCustomUIItem = function (stream) {
      stream.getInt32();
      this.event = parseEventList(stream);
      this.type = stream.getInt32();
      this.isUserString = stream.getInt32() !== 0;
      this.image1 = stream.readStringE();
      this.image2 = stream.readStringE();
      this.stringIndex = stream.getInt32();
      this.isUserVar = stream.getInt32() !== 0;
      this.x = stream.getInt32();
      this.y = stream.getInt32();
      this.isUserIndex = stream.getInt32() !== 0;
      this.index = stream.getInt32();
      this.maxIndex = stream.getInt32();
      this.color = new org_data.OColor(stream.readStringE());
    };

    var NewCustomUIData = function (stream, declaredSize) {
      var start = stream.pos;
      stream.getInt32();
      this.loadEvent = parseEventList(stream);
      this.afterEvent = [];
      var controlCount = stream.getInt32();
      this.controls = new Array(controlCount);
      for (var index = 0; index < controlCount; index++) {
        this.controls[index] = new NewCustomUIItem(stream);
      }
      this.showEffect = stream.getInt32();
      this.isMouseExit = stream.getInt32() !== 0;
      this.isKeyExit = stream.getInt32() !== 0;
      var actualSize = stream.pos - start;
      if (declaredSize !== actualSize) {
        throw new Error("new CUI size mismatch declared=" + declaredSize + " actual=" + actualSize + " start=" + start);
      }
    };

    var NewDSystem = function (stream) {
      this.Cuis = null;
      this.FontStyleColor = "";
      this.FontStroke = false;
      this.FontFilter = false;
      stream.getInt32();
      this.FontName = stream.readStringE();
      this.FontSize = stream.getInt32();
      this.FontSize *= 0.8;
      this.FontTalkColor = new org_data.OColor(stream.readStringE());
      this.FontUiColor = new org_data.OColor(stream.readStringE());
      if (GloableData.getInstance().gameInfo.ver >= 101) this.FontStyle = stream.getInt32();
      if (this.FontStyle !== 0) {
        switch (this.FontStyle) {
          case 1: this.FontFilter = true; this.FontStyleColor = "#000000"; break;
          case 2: this.FontFilter = true; this.FontStyleColor = "#999b9f"; break;
          case 3: this.FontFilter = true; this.FontStyleColor = "#FFFFFF"; break;
          case 4: this.FontStroke = true; this.FontStyleColor = "#000000"; break;
          case 5: this.FontStroke = true; this.FontStyleColor = "#999b9f"; break;
          case 6: this.FontStroke = true; this.FontStyleColor = "#FFFFFF"; break;
        }
      }
      this.SkipTitle = stream.getInt32() !== 0;
      this.StartStoryId = stream.getInt32();
      stream.getInt32();
      this.IconName = new org_data.DFileName(stream);
      this.ShowAD = stream.getInt32() !== 0;
      this.AuthorWords = stream.readStringE();
      this.AuthorWordsTiming = stream.getInt32();
      this.AutoRun = stream.getInt32() !== 0;
      this.ShowSystemMenu = stream.getInt32() !== 0;
      this.SEClick = new org_data.DMusicItem(stream);
      this.SEMove = new org_data.DMusicItem(stream);
      this.SECancel = new org_data.DMusicItem(stream);
      this.SEError = new org_data.DMusicItem(stream);
      this.Title = new org_data.DTitle(stream);
      this.GameMenu = new org_data.DGameMenu(stream);
      this.CG = new org_data.DCG(stream);
      this.BGM = new org_data.DBGM(stream);
      this.SaveData = new org_data.DSaveData(stream);
      this.MessageBox = new org_data.DMessageBox(stream);
      this.Replay = new org_data.DReplay(stream);
      this.Setting = new org_data.DSetting(stream);

      var oldButtonCount = stream.getInt32();
      var buttonTableHeader = null;
      var buttonCount = oldButtonCount;
      if (oldButtonCount === 80 && stream.pos + 12 <= stream.buffer.byteLength) {
        var headerMarker1 = stream.getInt32();
        var headerMarker2 = stream.getInt32();
        var declaredButtonCount = stream.getInt32();
        if (headerMarker1 === 80 && headerMarker2 === 80 && declaredButtonCount > oldButtonCount && declaredButtonCount < 10000) {
          buttonTableHeader = [oldButtonCount, headerMarker1, headerMarker2, declaredButtonCount];
          buttonCount = declaredButtonCount;
        } else {
          stream.pos -= 12;
        }
      }
      this.Buttons = new Array(buttonCount);
      for (var index = 0; index < buttonCount; index++) {
        this.Buttons[index] = new org_data.DButton(stream);
      }

      this.UIInitSave = stream.getInt32() !== 0;
      this.Cuis = null;
      this.MenuIndex = 0;
      GloableData.getInstance().autoPlay = this.AutoRun;
      if (GloableData.getInstance().gameInfo.ver >= 103) {
        var cuiCount = stream.getInt32();
        this.Cuis = new Array(cuiCount);
        for (var cuiIndex = 0; cuiIndex < cuiCount; cuiIndex++) {
          var declaredSize = stream.getInt32();
          this.Cuis[cuiIndex] = new NewCustomUIData(stream, declaredSize);
        }
        this.MenuIndex = stream.getInt32();
      }
      compatLog("official proxy DSystem compat parsed buttons=" + buttonCount + " header=" + (buttonTableHeader ? buttonTableHeader.join("/") : oldButtonCount) + " pos=" + stream.pos);
    };
    NewDSystem.__officialProxyNewPatched = true;
    org_data.DSystem = NewDSystem;
    compatLog("official proxy DSystem/CUI compat enabled");
    return true;
  }

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
      var ui = UIManager.getInstance();
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

  function install() {
    var ok = installButtonPaddingPatch();
    ok = installNewDSystemPatch() || ok;
    ok = installFreeTimeBypass() || ok;
    ok = installDevFreeUnlockPatch() || ok;
    return ok;
  }

  install();
  var tries = 0;
  var timer = setInterval(function () {
    tries += 1;
    install();
    if (tries >= 120) clearInterval(timer);
  }, 100);
})();
