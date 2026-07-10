(function () {
  "use strict";

  var params = new URLSearchParams(window.location.search);
  var pathGameId = (window.location.pathname.match(/\/(\d+)\/?$/) || [])[1];
  var gameId = params.get("gameId") || pathGameId || "1692579";
  var guid = params.get("guid") || "fbb2a8717f628920e662bdba3b89b418";
  var version = params.get("version") || "18";
  var quality = params.get("quality") || "32";
  var screenMode = params.get("screenMode") || "1";
  var statusNode = document.getElementById("player-status");
  var statusLines = [];
  var traceEnabled = params.get("trace") === "1";

  if (!traceEnabled) {
    statusNode.style.display = "none";
  } else {
    statusNode.style.pointerEvents = "none";
  }

  function writeStatus(message, detail) {
    var line = "[modern-player] " + message;
    if (detail !== undefined) {
      if (typeof detail === "string") {
        line += " " + detail;
      } else {
        try {
          line += " " + JSON.stringify(detail);
        } catch (_) {
          line += " " + String(detail);
        }
      }
    }
    if (traceEnabled) {
      statusLines.push(line);
      statusLines = statusLines.slice(-80);
      statusNode.textContent = statusLines.join("\n");
    }
    console.log(line);
  }

  window.__modernPlayerLog = writeStatus;
  window.addEventListener("error", function (event) {
    writeStatus("window error", {
      message: event.message,
      source: event.filename,
      line: event.lineno,
      column: event.colno,
      stack: event.error && event.error.stack
    });
  });
  window.addEventListener("unhandledrejection", function (event) {
    writeStatus("unhandled rejection", String(event.reason && (event.reason.stack || event.reason)));
  });

  function fileContext(byte, position) {
    var view = new Uint8Array(byte.buffer, Math.max(0, position - 16), Math.min(48, byte.buffer.byteLength - Math.max(0, position - 16)));
    return Array.prototype.map.call(view, function (value) {
      return value.toString(16).padStart(2, "0");
    }).join(" ");
  }

  function installBinaryTrace() {
    if (!window.GameByte || !GameByte.prototype.readStringE) {
      throw new Error("GameByte runtime is unavailable");
    }
    var originalGetInt32 = GameByte.prototype.getInt32;
    var originalReadString = GameByte.prototype.readStringE;
    var isTargetGame = guid === "fbb2a8717f628920e662bdba3b89b418" && version === "18";
    var parsingSystem = false;
    var parsingPopMessage = false;
    GameByte.prototype.getInt32 = function () {
      if (isTargetGame && parsingSystem && GloableData.getInstance().gameInfo.ver === 110 && this.pos === 2038) {
        writeStatus("v110 setting extension skipped", {
          from: this.pos,
          to: 2050,
          bytes: 12
        });
        this.pos = 2050;
      }
      if (isTargetGame && parsingPopMessage && GloableData.getInstance().gameInfo.ver === 110 && this.pos === 2580312) {
        writeStatus("v110 pop-message version skipped", {
          from: this.pos,
          to: 2580316,
          bytes: 4
        });
        this.pos = 2580316;
      }
      return originalGetInt32.call(this);
    };
    GameByte.prototype.readStringE = function () {
      var start = this.pos;
      var extensionEnd = {
        451: 493,
        969: 1014,
        1278: 1328
      }[start];
      if (isTargetGame && parsingSystem && GloableData.getInstance().gameInfo.ver === 110 && extensionEnd) {
        this.pos = extensionEnd;
        writeStatus("v110 extension skipped", {
          from: start,
          to: extensionEnd,
          bytes: extensionEnd - start
        });
        return originalReadString.call(this);
      }
      var available = this.bytesAvailable;
      var length = this.getInt32();
      this.pos = start;
      if (length < 0 || length > available - 4 || length > 65536) {
        writeStatus("invalid string boundary", {
          position: start,
          length: length,
          available: available,
          context: fileContext(this, start),
          stack: new Error("binary trace").stack
        });
      }
      return originalReadString.call(this);
    };

    var OriginalSystem = org_data.DSystem;
    org_data.DSystem = function (byte) {
      writeStatus("DSystem start", { position: byte.pos });
      parsingSystem = true;
      try {
        var system = new OriginalSystem(byte);
        writeStatus("DSystem complete", { position: byte.pos });
        return system;
      } finally {
        parsingSystem = false;
      }
    };
    org_data.DSystem.prototype = OriginalSystem.prototype;

    var OriginalPopMsg = org_data.DPopMsg;
    org_data.DPopMsg = function (byte) {
      writeStatus("DPopMsg start", { position: byte.pos });
      parsingPopMessage = true;
      try {
        var popMsg = new OriginalPopMsg(byte);
        writeStatus("DPopMsg complete", { position: byte.pos });
        return popMsg;
      } finally {
        parsingPopMessage = false;
      }
    };
    org_data.DPopMsg.prototype = OriginalPopMsg.prototype;

    var originalDataToVar = org_event.TextDifUtil.dataToVar;
    org_event.TextDifUtil.dataToVar = function (value) {
      var fields = value instanceof Array ? value : String(value).split(",");
      var condition = originalDataToVar.call(this, value);
      var marker = fields.length > 6 ? String(fields[6] || "") : "";
      // The current v2 runtime treats every extended v110 condition without a
      // task marker as task type 6, which never completes in IFEvent.
      if (
        isTargetGame &&
        fields.length > 6 &&
        marker.indexOf("TA") === -1 &&
        marker.indexOf("AS") === -1 &&
        condition.type === 6
      ) {
        condition.clean();
        condition.type = 0;
        condition.id = parseInt(fields[0], 10);
        condition.op = parseInt(fields[1], 10);
        condition.otherVar = parseInt(fields[2], 10);
        condition.idOrValue = parseInt(fields[3], 10);
        condition.haveElse = parseInt(fields[4], 10) !== 0;
        if (traceEnabled) {
          writeStatus("v110 standard condition restored", {
            id: condition.id,
            op: condition.op,
            otherVar: condition.otherVar,
            value: condition.idOrValue,
            currentValue: condition.type === 0
              ? GloableData.getInstance().dGameSystem.vars.getVar(condition.id)
              : GloableData.getInstance().dGameSystem.varsEx.getVar(condition.id),
            haveElse: condition.haveElse
          });
        }
      }
      if (traceEnabled && isTargetGame && condition.type === 3) {
        writeStatus("flower condition", {
          op: condition.op,
          value: condition.idOrValue,
          currentValue: GloableData.getInstance().flowerHua,
          haveElse: condition.haveElse
        });
      }
      if (traceEnabled && isTargetGame && condition.type === 8) {
        var ownedItem = GloableData.getInstance().getItemById(condition.id);
        writeStatus("inventory condition", {
          goodsId: condition.id,
          usingNum: ownedItem ? ownedItem.max : 0,
          haveElse: condition.haveElse
        });
      }
      if (isTargetGame && condition.type === 8) {
        var productConditionHaveElse = condition.haveElse;
        condition.clean();
        condition.type = 3;
        condition.op = 1;
        condition.otherVar = 0;
        condition.idOrValue = 0;
        condition.haveElse = productConditionHaveElse;
      }
      return condition;
    };

    // These variables are server-issued access credentials in the original
    // game. Keep their real stored values untouched, but expose the standalone
    // entitlement to every condition engine (story IF and custom UI alike).
    var originalGetGameVariable = org_data.DGameVariables.prototype.getVar;
    var standaloneVariableMinimums = {
      26: 999999,
      234: 1,
      235: 1
    };
    org_data.DGameVariables.prototype.getVar = function (variableId) {
      var value = originalGetGameVariable.apply(this, arguments);
      var data = GloableData.getInstance();
      if (isTargetGame && data.dGameSystem && this === data.dGameSystem.vars) {
        var standaloneMinimum = standaloneVariableMinimums[variableId];
        if (standaloneMinimum !== undefined) {
          return Math.max(standaloneMinimum, Number(value) || 0);
        }
      }
      return value;
    };

    var originalSetGameVariable = org_data.DGameVariables.prototype.setVar;
    var standaloneAutoSaveTimer = 0;
    org_data.DGameVariables.prototype.setVar = function () {
      var result = originalSetGameVariable.apply(this, arguments);
      var data = GloableData.getInstance();
      var main = data.iMain;
      var storyId = main && (main.storyId || (main.mainLine && main.mainLine.storyId));
      if (isTargetGame && data.dGameSystem && this === data.dGameSystem.vars && storyId > 0) {
        window.clearTimeout(standaloneAutoSaveTimer);
        standaloneAutoSaveTimer = window.setTimeout(function () {
          try {
            data.snap(data.autoSaveIndex - 1, true);
            writeStatus("standalone variable changes auto-saved");
          } catch (error) {
            writeStatus("standalone variable auto-save failed", String(error && error.message || error));
          }
        }, 1200);
      }
      return result;
    };

    var originalGetCumulativeFlower = OrgWeb.prototype.getFlowrHuaNum;
    OrgWeb.prototype.getFlowrHuaNum = function () {
      var value = originalGetCumulativeFlower.apply(this, arguments);
      return isTargetGame ? Math.max(999999, Number(value) || 0) : value;
    };
    var originalGetSpendableFlower = OrgWeb.prototype.getReWidFlower;
    OrgWeb.prototype.getReWidFlower = function () {
      var value = originalGetSpendableFlower.apply(this, arguments);
      return isTargetGame ? Math.max(999999, Number(value) || 0) : value;
    };

    var originalCheckIIF = org_event.TextDifUtil.checkIIF;
    org_event.TextDifUtil.checkIIF = function (event, taskIds, autoSaveFlags) {
      var result = originalCheckIIF.apply(this, arguments);
      var inlineType = event && event.Argv && String(event.Argv[0] || "");
      // ST conditions are account-owned product credentials. The standalone
      // player has no 66RPG account inventory, so make those gates available
      // without altering ordinary mall purchases or reward inventory.
      if (isTargetGame && inlineType.indexOf("ST") > -1) {
        result = true;
      }
      if (
        traceEnabled &&
        isTargetGame &&
        event &&
        event.Argv &&
        inlineType.indexOf("MO") === -1
      ) {
        writeStatus("inline condition", {
          args: Array.prototype.slice.call(event.Argv, 0, 8),
          result: result
        });
      }
      return result;
    };

    // v110 added periodic custom-UI buttons (type 6), but the public v2
    // runtime only creates controls 0-4. These four buttons cover daily,
    // weekly and monthly sign-in plus the daily fortune action in this game.
    // Preserve the intended period limit locally and use image1 as the
    // already-claimed state, matching the data authored by the game.
    var standalonePeriodicButtons = {
      128: "day",
      129: "week",
      130: "month",
      273: "day"
    };
    var standalonePeriodicMemory = {};

    function resolveCustomUIButtonIndex(control) {
      var index = control.isUserIndex
        ? GloableData.getInstance().dGameSystem.vars.getVar(control.index) - 1
        : control.index;
      var buttons = GloableData.getInstance().gameMainData.System.Buttons;
      if (index < 0 || index >= buttons.length) {
        index = 0;
      }
      return index;
    }

    function standalonePeriodKey(period) {
      var now = new Date();
      var year = now.getFullYear();
      var month = String(now.getMonth() + 1).padStart(2, "0");
      var day = String(now.getDate()).padStart(2, "0");
      if (period === "month") {
        return year + "-" + month;
      }
      if (period === "week") {
        var weekStart = new Date(year, now.getMonth(), now.getDate());
        var weekday = weekStart.getDay() || 7;
        weekStart.setDate(weekStart.getDate() - weekday + 1);
        return [
          weekStart.getFullYear(),
          String(weekStart.getMonth() + 1).padStart(2, "0"),
          String(weekStart.getDate()).padStart(2, "0")
        ].join("-");
      }
      return [year, month, day].join("-");
    }

    function standalonePeriodicStorageKey(buttonIndex) {
      var period = standalonePeriodicButtons[buttonIndex];
      return [
        "modern-player-periodic-control",
        guid,
        version,
        buttonIndex,
        standalonePeriodKey(period)
      ].join(":");
    }

    function hasClaimedStandalonePeriodicButton(buttonIndex) {
      var key = standalonePeriodicStorageKey(buttonIndex);
      try {
        return window.localStorage && localStorage.getItem(key) === "1";
      } catch (_) {
        return standalonePeriodicMemory[key] === true;
      }
    }

    function markStandalonePeriodicButtonClaimed(buttonIndex) {
      var key = standalonePeriodicStorageKey(buttonIndex);
      standalonePeriodicMemory[key] = true;
      try {
        if (window.localStorage) {
          localStorage.setItem(key, "1");
        }
      } catch (_) {}
    }

    function normalizeCustomUIImage(path) {
      return String(path || "").replace(/\\/g, "/").replace(/\/{2,}/g, "/");
    }

    if (window.view && view.SCustomUI && view.SCustomUI.prototype.loadControls) {
      var originalLoadCustomUIControl = view.SCustomUI.prototype.loadControls;
      view.SCustomUI.prototype.loadControls = function (control) {
        if (!isTargetGame || !control || control.type !== 6) {
          return originalLoadCustomUIControl.apply(this, arguments);
        }

        var buttonIndex = resolveCustomUIButtonIndex(control);
        var period = standalonePeriodicButtons[buttonIndex];
        if (!period) {
          writeStatus("unsupported v110 periodic button", { buttonIndex: buttonIndex });
          return originalLoadCustomUIControl.apply(this, arguments);
        }

        var component;
        var position = this.getControlPoint(control);
        if (hasClaimedStandalonePeriodicButton(buttonIndex)) {
          var claimedImage = normalizeCustomUIImage(control.image1);
          component = new ImageComponent();
          component.pixelHitTest = false;
          component.mouseEnabled = false;
          component.updateURL(this._sp_url + claimedImage, -1, 1, this.clickImage, this);
          component.x = position.x;
          component.y = position.y;
        } else {
          var buttonData = GloableData.getInstance().gameMainData.System.Buttons[buttonIndex];
          var normalImage = buttonData.image1 && buttonData.image1.name
            ? this._btn_url + buttonData.image1
            : "";
          var hoverImage = buttonData.image2 && buttonData.image2.name
            ? this._btn_url + buttonData.image2
            : "";
          component = new ORGButton(normalImage, hoverImage, GameEventConstant.CLICK_SCUI_BUTTON);
          component.pixelHitTest = true;
          component.visible = true;
          component.index = control.index;
          component.postion = position;
        }

        component.tag = control;
        component.__standalonePeriodicButtonIndex = buttonIndex;
        this.addChild(component);
        this.controlsArr.push(component);
      };
    }

    if (window.view && view.SCustomUIMediator && view.SCustomUIMediator.prototype.onSelect) {
      var originalCustomUISelect = view.SCustomUIMediator.prototype.onSelect;
      view.SCustomUIMediator.prototype.onSelect = function (button) {
        if (traceEnabled && isTargetGame) {
          var buttonData = GloableData.getInstance().gameMainData.System.Buttons[button && button.index];
          writeStatus("custom UI button", {
            cuiIndex: view.SCustomUI && view.SCustomUI.F_Index,
            buttonIndex: button && button.index,
            image1: buttonData && buttonData.image1 && buttonData.image1.name,
            events: button && button.tag && button.tag.event && button.tag.event.map(function (event) {
              return {
                code: event.Code,
                args: event.Argv && Array.prototype.slice.call(event.Argv, 0, 12)
              };
            })
          });
        }
        var periodicButtonIndex = button && button.__standalonePeriodicButtonIndex;
        var canRunPeriodicButton = periodicButtonIndex !== undefined &&
          (!this.view.buttonInter || this.view.buttonInter.isEnd) &&
          button.tag && button.tag.event && button.tag.event.length > 0;
        if (canRunPeriodicButton) {
          if (hasClaimedStandalonePeriodicButton(periodicButtonIndex)) {
            return;
          }
          button.mouseEnabled = false;
        }

        try {
          var result = originalCustomUISelect.apply(this, arguments);
          if (canRunPeriodicButton) {
            markStandalonePeriodicButtonClaimed(periodicButtonIndex);
            var claimedImage = normalizeCustomUIImage(button.tag.image1);
            if (claimedImage && button.parent) {
              var claimedURL = this.view._sp_url + claimedImage;
              var claimedComponent = new ImageComponent();
              var claimedPosition = this.view.getControlPoint(button.tag);
              claimedComponent.pixelHitTest = false;
              claimedComponent.mouseEnabled = false;
              claimedComponent.tag = button.tag;
              claimedComponent.__standalonePeriodicButtonIndex = periodicButtonIndex;
              claimedComponent.updateURL(claimedURL, -1, 1, this.view.clickImage, this.view);
              claimedComponent.x = claimedPosition.x;
              claimedComponent.y = claimedPosition.y;
              var controlIndex = this.view.controlsArr.indexOf(button);
              if (controlIndex >= 0) {
                this.view.controlsArr.splice(controlIndex, 1);
              }
              button.visible = false;
              this.view.addChild(claimedComponent);
              this.view.controlsArr.push(claimedComponent);
            }
            writeStatus("standalone periodic action claimed", {
              buttonIndex: periodicButtonIndex,
              period: standalonePeriodicButtons[periodicButtonIndex]
            });
          }
          return result;
        } catch (error) {
          if (canRunPeriodicButton) {
            button.mouseEnabled = true;
          }
          throw error;
        }
      };
    }

    if (window.MallProxy && MallProxy.prototype.createOrderComplete) {
      var originalCreateOrderComplete = MallProxy.prototype.createOrderComplete;
      MallProxy.prototype.createOrderComplete = function (event) {
        var result = originalCreateOrderComplete.apply(this, arguments);
        if (isTargetGame && event && event.data && event.data.status === 1) {
          window.setTimeout(function () {
            try {
              var data = GloableData.getInstance();
              data.snap(data.autoSaveIndex - 1, true);
              writeStatus("mall purchase auto-saved", {
                goodsId: event.data.data && event.data.data.goods_id,
                buyNum: event.data.data && event.data.data.buy_num
              });
            } catch (error) {
              writeStatus("mall purchase auto-save failed", String(error && error.message || error));
            }
          }, 0);
        }
        return result;
      };
    }
  }

  function configureLocalRuntime() {
    var basePrefix = window.location.pathname.indexOf("/play-modern/") === 0 ? "/play-modern" : "";
    var localRoot = window.location.origin + basePrefix + "/";
    HttpURL.M_RESOUSE_SERVER_URL = localRoot;
    HttpURL.CGV2_SERVER_URL = localRoot;
    HttpURL.M_M_SERVER_URL = localRoot;
    HttpURL.M_MAll_SERVER_URL = localRoot;
    HttpURL.M_C_SERVER_URL = localRoot;
    HttpURL.REPORT_SERVER_URL = localRoot;
    GloableData.getInstance().serverPath = "https://c2.cgyouxi.com/website/hfplayer/v2/bin/";

    if (window.commonPlayer) {
      commonPlayer.userInfos = {
        uid: "local-player",
        code: "local-player",
        uname: "Local Player",
        gindex: gameId,
        open_id: "",
        channel_type: ""
      };
      commonPlayer.loginStatus = true;
      commonPlayer.channel_id = "";
      commonPlayer.platform = "";
      commonPlayer.flower = Object.assign({}, commonPlayer.flower || {}, {
        // Story flower conditions read this legacy cumulative value instead
        // of the modern mall balance returned by getMyAccountMoney.
        num: 999999,
        fresh_flower_num: 999999,
        wild_flower_num: 0,
        tanhua_flower_num: 0
      });
    }

    writeStatus("standalone entitlements enabled", {
      cumulativeFlower: commonPlayer && commonPlayer.flower && commonPlayer.flower.num
    });
  }

  function installRuntimeTrace() {
    if (!traceEnabled) {
      return;
    }
    var lastState = "";
    window.setInterval(function () {
      try {
        var data = GloableData.getInstance();
        var main = data.iMain;
        var line = main && (main.mainLine || main);
        var currentEvent = line && line.currentEvent;
        var chat = UIManager.getInstance().chat;
        var talkText = chat && chat.talkText;
        var primitiveEventData = {};
        if (currentEvent) {
          Object.keys(currentEvent).forEach(function (key) {
            var value = currentEvent[key];
            if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
              primitiveEventData[key] = value;
            }
          });
        }
        var state = {
          storyId: main && main.storyId,
          lineStoryId: line && line.storyId,
          position: line && line.pos,
          storyLength: line && line.story && line.story.length,
          eventRunFinish: line && line.eventRunFinish,
          paused: line && line.isPause,
          currentEvent: currentEvent && currentEvent.Code,
          eventData: primitiveEventData,
          eventArgs: currentEvent && currentEvent.Argv && Array.prototype.slice.call(currentEvent.Argv, 0, 20),
          chatVisible: chat && chat.visible,
          showingText: talkText && talkText.showingText,
          textComplete: talkText && talkText.isComplete,
          textPaused: talkText && talkText.pause,
          text: talkText && talkText.text
        };
        var serialized = JSON.stringify(state);
        if (serialized !== lastState) {
          lastState = serialized;
          writeStatus("runtime state", state);
        }
      } catch (error) {
        writeStatus("runtime trace unavailable", String(error && error.message || error));
      }
    }, 1000);
  }

  function boot() {
    installBinaryTrace();
    configureLocalRuntime();
    installRuntimeTrace();
    window.gameMain = new Main();
    writeStatus("initGameData", {
      gameId: gameId,
      guid: guid,
      version: version,
      quality: quality,
      screenMode: screenMode
    });
    window.gameMain.initGameData(
      guid,
      version,
      "",
      "",
      quality,
      "",
      screenMode,
      gameId,
      ""
    );
  }

  try {
    boot();
  } catch (error) {
    writeStatus("boot failed", error && (error.stack || error.message || String(error)));
  }
})();
