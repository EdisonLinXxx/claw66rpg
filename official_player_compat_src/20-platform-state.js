  function readDevInventory() {
    try {
      var raw = window.localStorage && localStorage.getItem(getDevInventoryKey());
      var parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (error) {
      return {};
    }
  }

  function writeDevInventory(inventory) {
    try {
      if (window.localStorage) localStorage.setItem(getDevInventoryKey(), JSON.stringify(inventory));
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

  function getDevInventoryItem(goodsId) {
    if (!goodsId || goodsId <= 0) return null;
    var inventory = readDevInventory();
    var key = String(goodsId);
    var usingNum = parseInt(inventory[key], 10) || 0;
    return usingNum > 0 ? { goods_id: goodsId, using_num: usingNum } : null;
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
