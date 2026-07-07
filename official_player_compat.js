(function () {
  function compatLog(message) {
    if (typeof window.logLine === "function") window.logLine(message);
    else if (window.console && console.log) console.log(message);
  }

  function getJsonpCallbackName(url) {
    var match = String(url).match(/[?&](?:jsonCallBack|callback|cb)=([^&]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  var DEV_INVENTORY_KEY = "officialProxyDevFreeUnlockInventory:v1";
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

  function readDevInventory() {
    try {
      var raw = window.localStorage && localStorage.getItem(DEV_INVENTORY_KEY);
      var parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (error) {
      return {};
    }
  }

  function writeDevInventory(inventory) {
    try {
      if (window.localStorage) localStorage.setItem(DEV_INVENTORY_KEY, JSON.stringify(inventory));
    } catch (error) {}
  }

  function devInventoryArray() {
    var inventory = readDevInventory();
    return Object.keys(inventory).map(function (key) {
      return { goods_id: parseInt(key, 10), using_num: parseInt(inventory[key], 10) || 0 };
    }).filter(function (item) {
      return item.goods_id > 0;
    });
  }

  function addDevInventory(goodsId, buyNum) {
    if (!goodsId || goodsId <= 0) return null;
    var inventory = readDevInventory();
    var key = String(goodsId);
    var next = (parseInt(inventory[key], 10) || 0) + Math.max(1, buyNum || 1);
    inventory[key] = next;
    writeDevInventory(inventory);
    return { goods_id: goodsId, using_num: next };
  }

  function ensureDevInventory(goodsId) {
    if (!goodsId || goodsId <= 0) return null;
    var inventory = readDevInventory();
    var key = String(goodsId);
    if (!inventory[key]) {
      inventory[key] = 1;
      writeDevInventory(inventory);
    }
    return { goods_id: goodsId, using_num: parseInt(inventory[key], 10) || 1 };
  }

  function mergeObject(target, source) {
    target = target && typeof target === "object" ? target : {};
    for (var key in source) {
      if (Object.prototype.hasOwnProperty.call(source, key)) target[key] = source[key];
    }
    return target;
  }

  function devFlowerState() {
    return {
      fresh_flower_num: DEV_FLOWER_AMOUNT,
      wild_flower_num: 0,
      wild_flower: 0,
      tanhua_flower_num: DEV_FLOWER_AMOUNT,
      tanHuaPlayFowerStr: DEV_FLOWER_AMOUNT,
      flower_num: DEV_FLOWER_AMOUNT,
      num: DEV_FLOWER_AMOUNT,
      sum: DEV_FLOWER_AMOUNT,
      payFlowerNumStr: String(DEV_FLOWER_AMOUNT)
    };
  }

  function devUserFlowerAccount() {
    return {
      coin1: { coin_count: DEV_FLOWER_COIN_AMOUNT },
      coin2: { coin_count: DEV_FLOWER_COIN_AMOUNT },
      coin_count: DEV_FLOWER_COIN_AMOUNT,
      gold_count: DEV_FLOWER_COIN_AMOUNT,
      flower_count: DEV_FLOWER_AMOUNT,
      fresh_flower_num: DEV_FLOWER_AMOUNT,
      wild_flower_num: 0,
      tanhua_flower_num: DEV_FLOWER_AMOUNT,
      num: DEV_FLOWER_AMOUNT,
      sum: DEV_FLOWER_AMOUNT
    };
  }

  function devAwardPayload() {
    return {
      is_receive: 0,
      is_received: 0,
      received: 0,
      can_receive: 1,
      can_get: 1,
      status: 1,
      flower_num: DEV_FLOWER_AMOUNT,
      need_flower: 0,
      award_flower: DEV_FLOWER_AMOUNT,
      coin_count: DEV_FLOWER_COIN_AMOUNT,
      data: devFlowerState()
    };
  }

  function applyDevFlowerState() {
    if (!window.__officialProxyDevFreeUnlock) return false;

    if (window.commonPlayer) {
      commonPlayer.loginStatus = true;
      commonPlayer.flower = mergeObject(commonPlayer.flower, devFlowerState());
      commonPlayer.flower_unlock = 0;
      commonPlayer.sendFlower = commonPlayer.sendFlower || {};
      commonPlayer.sendFlower.userCoin = mergeObject(commonPlayer.sendFlower.userCoin, devUserFlowerAccount());
      commonPlayer.sendFlower.sendFlowerState = function (callback) {
        applyDevFlowerState();
        if (typeof callback === "function") callback(true);
      };
      commonPlayer.sendFlower.up_Sent_Flower = function (num, callback) {
        applyDevFlowerState();
        if (typeof callback === "function") callback(true);
      };
    }

    if (window.GloableData && GloableData.getInstance) {
      var data = GloableData.getInstance();
      data.isFreeLimit = false;
      data.isFreeTime = 0;
      data.flowerUnlock = 0;
      data.gameFvTimes = 999999;
      data.flowerHua = DEV_FLOWER_AMOUNT;
      data.flowerMallHua = DEV_FLOWER_AMOUNT;
    }

    if (window.OrgWeb && OrgWeb.prototype && !OrgWeb.prototype.__officialProxyDevFlowerPatched) {
      OrgWeb.prototype.__officialProxyDevFlowerPatched = true;
      OrgWeb.prototype.getFlowrHuaNum = function () { return DEV_FLOWER_AMOUNT; };
      OrgWeb.prototype.getHaveFlower = function () { return DEV_FLOWER_COIN_AMOUNT; };
      OrgWeb.prototype.getReWidFlower = function () { return DEV_FLOWER_AMOUNT; };
      OrgWeb.prototype.getWebUserFlower = function (thisArg, callback) {
        applyDevFlowerState();
        if (typeof callback === "function") callback.call(thisArg, DEV_FLOWER_AMOUNT);
      };
      OrgWeb.prototype.getAllFlower = function (callback) {
        applyDevFlowerState();
        if (typeof callback === "function") callback();
      };
      OrgWeb.prototype.updateUserInfoCoin = function (callback) {
        applyDevFlowerState();
        if (typeof callback === "function") callback();
      };
      OrgWeb.prototype.sendReWidFlower = function (callback) {
        applyDevFlowerState();
        if (typeof callback === "function") callback();
      };
      OrgWeb.prototype.initSendFlower = function (thisArg, callback, priceType) {
        applyDevFlowerState();
        if (typeof callback === "function") callback.call(thisArg, true, priceType);
      };
      OrgWeb.prototype.sendFlower = function (thisArg, callback, num) {
        applyDevFlowerState();
        if (typeof callback === "function") callback.call(thisArg, [num || 1, true]);
      };
    }

    return true;
  }

  function getDevFreeUnlockPayload(url) {
    var text = String(url || "");
    var lower = text.toLowerCase();
    var params = parseUrlParams(text);
    var goodsId = intParam(params, ["goods_id", "goodsId", "goodsid", "item_id", "itemId", "id"], 0);
    var buyNum = intParam(params, ["buy_num", "buyNum", "buynum", "num", "count"], 1);
    var isLocalApi =
      lower.indexOf("propshop/") !== -1 ||
      lower.indexOf("/engine/") !== -1 ||
      lower.indexOf("/game/") !== -1 ||
      lower.indexOf("/task/") !== -1 ||
      lower.indexOf("/pay") !== -1 ||
      lower.indexOf("/flower") !== -1 ||
      lower.indexOf("/account") !== -1 ||
      lower.indexOf("/user/") !== -1 ||
      lower.indexOf("/ajax/") !== -1 ||
      lower.indexOf("ajax/") !== -1 ||
      lower.indexOf("/api/client") !== -1;

    if (!isLocalApi) return null;

    if (lower.indexOf("game_flower_by_me") !== -1) {
      return { status: 1, msg: "local platform flower state", data: devFlowerState() };
    }
    if (lower.indexOf("get_flower") !== -1) {
      return { status: 1, msg: "local platform flower account", data: devUserFlowerAccount() };
    }
    if (
      lower.indexOf("contains/flower") !== -1 ||
      lower.indexOf("share_game") !== -1 ||
      lower.indexOf("pay/flower") !== -1
    ) {
      applyDevFlowerState();
      return { status: 1, msg: "local platform flower ok", data: devFlowerState() };
    }
    if (lower.indexOf("all_share_award_conf") !== -1 || lower.indexOf("share_award_conf") !== -1) {
      return { status: 1, msg: "local platform award ok", data: devAwardPayload() };
    }
    if (lower.indexOf("getmyaccountmoney") !== -1 || lower.indexOf("accountmoney") !== -1 || lower.indexOf("balance") !== -1) {
      return {
        status: 1,
        data: {
          coin_count: DEV_FLOWER_COIN_AMOUNT,
          gold_count: DEV_FLOWER_COIN_AMOUNT,
          flower_count: DEV_FLOWER_AMOUNT,
          diamond_count: DEV_FLOWER_AMOUNT,
          acoin: DEV_FLOWER_AMOUNT
        }
      };
    }
    if (lower.indexOf("getuserhaveallpropnum") !== -1) {
      return { status: 1, data: devInventoryArray() };
    }
    if (lower.indexOf("getuserhavepropnum") !== -1 || lower.indexOf("propnum") !== -1) {
      var item = goodsId ? ensureDevInventory(goodsId) : null;
      return { status: 1, data: item ? [item] : devInventoryArray() };
    }
    if (lower.indexOf("get_user_hp") !== -1 || lower.indexOf("init_user_hp") !== -1) {
      return { status: 1, data: { hp: 999999, max_hp: 999999 } };
    }
    if (lower.indexOf("getlimitfreetime") !== -1 || lower.indexOf("getoldlimitfreetime") !== -1) {
      return { status: 1, data: { is_free: 1, time: 0 } };
    }
    if (
      lower.indexOf("createbuyorder") !== -1 ||
      lower.indexOf("unlock") !== -1 ||
      lower.indexOf("buy") !== -1 ||
      lower.indexOf("pay") !== -1 ||
      lower.indexOf("consume") !== -1 ||
      lower.indexOf("charge") !== -1 ||
      lower.indexOf("flower") !== -1
    ) {
      var boughtItem = goodsId ? addDevInventory(goodsId, buyNum) : null;
      return {
        status: 1,
        msg: "local platform unlock",
        data: {
          ok: 1,
          success: 1,
          is_buy: 1,
          is_unlock: 1,
          unlock: 1,
          goods_id: boughtItem ? boughtItem.goods_id : goodsId,
          buy_num: buyNum,
          using_num: boughtItem ? boughtItem.using_num : buyNum,
          order_id: "local-platform-unlock"
        }
      };
    }
    return null;
  }

  function installDevFreeUnlockPatch() {
    if (!window.__officialProxyDevFreeUnlock) return false;
    var patched = false;

    if (window.commonPlayer) {
      commonPlayer.loginStatus = true;
      commonPlayer.userInfos = commonPlayer.userInfos || {};
      commonPlayer.userInfos.uid = commonPlayer.userInfos.uid || "local-player";
      commonPlayer.userInfos.code = commonPlayer.userInfos.code || "local-player";
      commonPlayer.userInfos.gindex = commonPlayer.userInfos.gindex || "1569947";
      commonPlayer.userInfos.open_id = commonPlayer.userInfos.open_id || "";
      commonPlayer.userInfos.channel_type = commonPlayer.userInfos.channel_type || "";
      commonPlayer.userInfos.third_sign = commonPlayer.userInfos.third_sign || "";
      commonPlayer.login = commonPlayer.login || {};
      commonPlayer.login.midLogin = function (callback) {
        commonPlayer.loginStatus = true;
        if (typeof callback === "function") callback(true);
      };
    }
    patched = applyDevFlowerState() || patched;

    var scriptSrcDescriptor = Object.getOwnPropertyDescriptor(HTMLScriptElement.prototype, "src");
    if (scriptSrcDescriptor && scriptSrcDescriptor.set && !scriptSrcDescriptor.set.__officialProxyDevFreeUnlockWrapped) {
      Object.defineProperty(HTMLScriptElement.prototype, "src", {
        get: scriptSrcDescriptor.get,
        set: function (value) {
          var payload = getDevFreeUnlockPayload(value);
          var callbackName = payload && getJsonpCallbackName(value);
          if (payload && callbackName) {
            compatLog("official proxy platform unlock JSONP " + callbackName + " " + value);
            var script = callbackName + "(" + JSON.stringify(payload) + ");";
            return scriptSrcDescriptor.set.call(this, "data:text/javascript;charset=utf-8," + encodeURIComponent(script));
          }
          return scriptSrcDescriptor.set.call(this, value);
        }
      });
      Object.getOwnPropertyDescriptor(HTMLScriptElement.prototype, "src").set.__officialProxyDevFreeUnlockWrapped = true;
      compatLog("official proxy platform unlock JSONP patch enabled");
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
    var ok = false;
    function run(name, fn) {
      try {
        ok = fn() || ok;
      } catch (error) {
        compatLog("official proxy " + name + " patch skipped: " + (error && (error.stack || error.message) || error));
      }
    }
    run("DButton padding", installButtonPaddingPatch);
    run("DSystem/CUI", installNewDSystemPatch);
    run("platform unlock", installDevFreeUnlockPatch);
    run("free-time", installFreeTimeBypass);
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
