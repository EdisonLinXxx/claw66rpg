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
      var item = goodsId ? getDevInventoryItem(goodsId) : null;
      return { status: 1, data: goodsId ? (item ? [item] : []) : devInventoryArray() };
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

  function getLocalPlatformApiPayload(url) {
    var payload = getDevFreeUnlockPayload(url);
    if (payload) return payload;

    var lower = String(url || "").toLowerCase();
    if (lower.indexOf("new_get_game_ad_list") !== -1) {
      return {
        status: 1,
        msg: "local platform ad list",
        data: {
          ad: {
            adurl: "",
            imgurl: "",
            mobile_img_url: ""
          }
        }
      };
    }
    if (lower.indexOf("get_game_info") !== -1) {
      return {
        status: 1,
        msg: "local platform game info",
        data: {
          game: {
            first_pub_time: "2026-01-01",
            author_uname: "",
            gname: "",
            month_card: 0
          }
        }
      };
    }
    if (lower.indexOf("get_limit_free_status") !== -1 || lower.indexOf("getlimitfreetime") !== -1) {
      return { status: 1, msg: "local platform free status", data: { status: 0, is_free: 1, time: 0 } };
    }
    if (lower.indexOf("get_orange_flower_color_status") !== -1) {
      return { status: 1, msg: "local platform orange flower status", data: { status: 0 } };
    }
    if (lower.indexOf("check_refund_flower") !== -1) {
      return { status: 1, msg: "local platform refund status", data: { status: 0, have_refund: 0 } };
    }
    if (lower.indexOf("get_status_v3") !== -1) {
      return { status: 1, msg: "local platform light text status", data: { status: 0 } };
    }
    if (lower.indexOf("get_global_cfg") !== -1) {
      return { status: 1, msg: "local platform prop shop config", data: {} };
    }
    if (lower.indexOf("get_goods_list") !== -1) {
      return { status: 1, msg: "local platform prop shop goods", data: [] };
    }
    if (lower.indexOf("cloud_load_ex") !== -1 || lower.indexOf("cloud_save_ex") !== -1) {
      return { status: 1, msg: "ok", data: null };
    }
    if (lower.indexOf("oweb_log.php") !== -1) {
      return { ret: 1 };
    }
    return null;
  }

  function createResolvedAjaxResult(payload) {
    var result = {
      abort: function () {},
      done: function (handler) {
        if (typeof handler === "function") setTimeout(function () { handler(payload, "success", result); }, 0);
        return result;
      },
      fail: function () { return result; },
      always: function (handler) {
        if (typeof handler === "function") setTimeout(function () { handler(result, "success"); }, 0);
        return result;
      },
      status: 200,
      responseJSON: payload,
      responseText: JSON.stringify(payload)
    };
    return result;
  }

  function installLocalRequestPatch() {
    var patched = false;
    if (typeof window.SAL_request === "function" && !window.SAL_request.__officialProxyLocalRequestWrapped) {
      var originalRequest = window.SAL_request;
      window.SAL_request = function (url, method, dataType, callback) {
        var payload = getLocalPlatformApiPayload(url);
        if (payload) {
          compatLog("official proxy local API SAL_request " + url);
          if (typeof callback === "function") setTimeout(function () { callback(200, payload); }, 0);
          return null;
        }
        return originalRequest.apply(this, arguments);
      };
      window.SAL_request.__officialProxyLocalRequestWrapped = true;
      patched = true;
    }

    if (window.$ && $.ajax && !$.ajax.__officialProxyLocalRequestWrapped) {
      var originalAjax = $.ajax;
      $.ajax = function (options) {
        var url = typeof options === "string" ? options : options && options.url;
        var payload = getLocalPlatformApiPayload(url);
        if (payload) {
          compatLog("official proxy local API ajax " + url);
          var result = createResolvedAjaxResult(payload);
          setTimeout(function () {
            if (options && typeof options.success === "function") options.success(payload, "success", result);
            if (options && typeof options.complete === "function") options.complete(result, "success");
          }, 0);
          return result;
        }
        return originalAjax.apply(this, arguments);
      };
      $.ajax.__officialProxyLocalRequestWrapped = true;
      patched = true;
    }

    if (patched) compatLog("official proxy local API patch enabled");
    return patched;
  }

  function isLocalNetworkNoiseToast(value) {
    var text = String(value || "");
    return text.indexOf("网络异常") !== -1 &&
      (text.indexOf("退出重进") !== -1 || text.indexOf("联系客服") !== -1 || text.indexOf("刷新重试") !== -1);
  }

  function hideLocalNetworkNoiseObject(object) {
    if (!object) return object;
    object.__officialProxyHiddenNetworkNoiseToast = true;
    try { object.visible = false; } catch (error) {}
    try { object._visible = false; } catch (error) {}
    try { object._opacity = 0; } catch (error) {}
    try {
      if (typeof object.setVisible === "function") object.setVisible(false);
    } catch (error) {}
    try {
      if (typeof object.setOpacity === "function") object.setOpacity(0);
    } catch (error) {}
    return object;
  }

  function installNetworkNoiseToastFilterPatch() {
    var state = window.__officialProxyNetworkNoiseToastFilter ||
      (window.__officialProxyNetworkNoiseToastFilter = { lastEmptySprite: null, logged: false });
    var patched = false;

    if (typeof window.SALSprite === "function" && !window.SALSprite.__officialProxyNetworkNoiseWrapped) {
      var originalSprite = window.SALSprite;
      window.SALSprite = function (path) {
        var object = originalSprite.apply(this, arguments);
        if (!path) state.lastEmptySprite = { object: object, at: Date.now() };
        return object;
      };
      window.SALSprite.__officialProxyNetworkNoiseWrapped = true;
      patched = true;
    }

    if (typeof window.SALText === "function" && !window.SALText.__officialProxyNetworkNoiseWrapped) {
      var originalText = window.SALText;
      window.SALText = function (text) {
        var args = Array.prototype.slice.call(arguments);
        var isNoise = isLocalNetworkNoiseToast(text);
        if (isNoise) {
          args[0] = "";
          var last = state.lastEmptySprite;
          if (last && Date.now() - last.at < 1000) hideLocalNetworkNoiseObject(last.object);
        }
        var object = originalText.apply(this, args);
        if (isNoise) {
          hideLocalNetworkNoiseObject(object);
          if (!state.logged) {
            state.logged = true;
            compatLog("official proxy suppressed local network toast");
          }
        }
        return object;
      };
      window.SALText.__officialProxyNetworkNoiseWrapped = true;
      patched = true;
    }

    if (typeof window.SAL_addElement === "function" && !window.SAL_addElement.__officialProxyNetworkNoiseWrapped) {
      var originalAddElement = window.SAL_addElement;
      window.SAL_addElement = function (parent, child) {
        if (child && child.__officialProxyHiddenNetworkNoiseToast) hideLocalNetworkNoiseObject(child);
        var result = originalAddElement.apply(this, arguments);
        if (child && child.__officialProxyHiddenNetworkNoiseToast) hideLocalNetworkNoiseObject(child);
        return result;
      };
      window.SAL_addElement.__officialProxyNetworkNoiseWrapped = true;
      patched = true;
    }

    if (typeof window.SAL_setElementOpacity === "function" && !window.SAL_setElementOpacity.__officialProxyNetworkNoiseWrapped) {
      var originalSetOpacity = window.SAL_setElementOpacity;
      window.SAL_setElementOpacity = function (object, opacity) {
        if (object && object.__officialProxyHiddenNetworkNoiseToast) {
          var args = Array.prototype.slice.call(arguments);
          args[1] = 0;
          return originalSetOpacity.apply(this, args);
        }
        return originalSetOpacity.apply(this, arguments);
      };
      window.SAL_setElementOpacity.__officialProxyNetworkNoiseWrapped = true;
      patched = true;
    }

    if (typeof window.SAL_setElementVisible === "function" && !window.SAL_setElementVisible.__officialProxyNetworkNoiseWrapped) {
      var originalSetVisible = window.SAL_setElementVisible;
      window.SAL_setElementVisible = function (object, visible) {
        if (object && object.__officialProxyHiddenNetworkNoiseToast) {
          var args = Array.prototype.slice.call(arguments);
          args[1] = false;
          return originalSetVisible.apply(this, args);
        }
        return originalSetVisible.apply(this, arguments);
      };
      window.SAL_setElementVisible.__officialProxyNetworkNoiseWrapped = true;
      patched = true;
    }

    if (typeof window.SAL_runAction === "function" && !window.SAL_runAction.__officialProxyNetworkNoiseWrapped) {
      var originalRunAction = window.SAL_runAction;
      window.SAL_runAction = function (object, action, callback) {
        if (object && object.__officialProxyHiddenNetworkNoiseToast) {
          hideLocalNetworkNoiseObject(object);
          if (typeof callback === "function") setTimeout(callback, 0);
          return null;
        }
        return originalRunAction.apply(this, arguments);
      };
      window.SAL_runAction.__officialProxyNetworkNoiseWrapped = true;
      patched = true;
    }

    if (patched) compatLog("official proxy network toast filter patch enabled");
    return patched;
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

  registerCompatPatch("platform unlock", 40, installDevFreeUnlockPatch);
  registerCompatPatch("local API", 50, installLocalRequestPatch);
  registerCompatPatch("network toast filter", 60, installNetworkNoiseToastFilterPatch);
