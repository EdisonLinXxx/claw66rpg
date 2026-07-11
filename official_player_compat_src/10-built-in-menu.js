  var cuiCompatibilityInstalled = false;

  function showBuiltinNameEditor(event, argv) {
    var gameData = window.GloableData && GloableData.getInstance && GloableData.getInstance();
    var strings = gameData && gameData.dGameSystem && gameData.dGameSystem.dGameString;
    if (!strings || typeof strings.setVar !== "function") return false;

    var rawFields = String(argv && argv[3] || "").split(",");
    var declaredCount = parseInt(argv && argv[4], 10);
    var fieldCount = !isNaN(declaredCount) && declaredCount > 0 ? declaredCount : Math.floor(rawFields.length / 3);
    var fields = [];
    for (var index = 0; index < fieldCount; index++) {
      var offset = index * 3;
      var variableIndex = parseInt(rawFields[offset + 2], 10);
      if (isNaN(variableIndex)) continue;
      fields.push({
        label: String(rawFields[offset] || "名称"),
        variableIndex: variableIndex
      });
    }
    if (!fields.length) return false;

    var existing = document.getElementById("official-proxy-name-editor");
    if (existing) existing.remove();

    var overlay = document.createElement("div");
    overlay.id = "official-proxy-name-editor";
    overlay.style.cssText = "position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(24,20,22,.58);font-family:'Microsoft YaHei',sans-serif;box-sizing:border-box";

    var form = document.createElement("form");
    form.style.cssText = "width:min(520px,92vw);max-height:90vh;overflow:auto;padding:24px 26px;border:1px solid rgba(255,255,255,.75);border-radius:18px;background:rgba(255,252,248,.98);box-shadow:0 18px 50px rgba(45,26,34,.28);box-sizing:border-box";

    var title = document.createElement("h2");
    title.textContent = "填写角色名称";
    title.style.cssText = "margin:0;color:#4d383f;text-align:center;font-size:24px;font-weight:700";
    form.appendChild(title);

    var hint = document.createElement("p");
    hint.textContent = "这些名称会用于后续剧情，请填写后继续。";
    hint.style.cssText = "margin:8px 0 20px;color:#8a717a;text-align:center;font-size:14px";
    form.appendChild(hint);

    var inputs = [];
    fields.forEach(function (field, fieldIndex) {
      var row = document.createElement("label");
      row.style.cssText = "display:block;margin-top:13px;color:#624b54;font-size:14px;font-weight:600";
      row.textContent = field.label === "自定义" ? "自定义名称 " + (fieldIndex + 1) : field.label;

      var input = document.createElement("input");
      input.type = "text";
      input.required = true;
      input.maxLength = 20;
      input.autocomplete = "off";
      input.placeholder = "请输入" + row.textContent;
      try {
        var currentValue = typeof strings.getVar === "function" ? strings.getVar(field.variableIndex) : "";
        input.value = currentValue == null ? "" : String(currentValue);
      } catch (error) {}
      input.style.cssText = "display:block;width:100%;height:42px;margin-top:6px;padding:0 12px;border:1px solid #decbd2;border-radius:10px;outline:none;background:#fff;color:#4e3b42;font-size:16px;box-sizing:border-box";
      input.addEventListener("focus", function () { input.style.borderColor = "#e85f8e"; });
      input.addEventListener("blur", function () { input.style.borderColor = "#decbd2"; });
      row.appendChild(input);
      form.appendChild(row);
      inputs.push({ input: input, variableIndex: field.variableIndex });
    });

    var validation = document.createElement("p");
    validation.style.cssText = "display:none;margin:12px 0 0;color:#d94c71;text-align:center;font-size:13px";
    validation.textContent = "请填写全部名称。";
    form.appendChild(validation);

    var submit = document.createElement("button");
    submit.type = "submit";
    submit.textContent = "确认并继续";
    submit.style.cssText = "display:block;width:100%;height:44px;margin-top:20px;border:0;border-radius:11px;background:#e94d80;color:#fff;font-size:16px;font-weight:700;cursor:pointer";
    form.appendChild(submit);

    ["mousedown", "mouseup", "click", "touchstart", "touchend", "keydown"].forEach(function (eventName) {
      overlay.addEventListener(eventName, function (domEvent) { domEvent.stopPropagation(); });
    });

    form.addEventListener("submit", function (domEvent) {
      domEvent.preventDefault();
      domEvent.stopPropagation();
      var values = inputs.map(function (item) { return item.input.value.trim(); });
      if (values.some(function (value) { return !value; })) {
        validation.style.display = "block";
        return;
      }
      inputs.forEach(function (item, inputIndex) {
        strings.setVar(item.variableIndex, values[inputIndex]);
      });
      overlay.remove();
      var ui = window.UIManager && UIManager.getInstance && UIManager.getInstance();
      if (ui) {
        ui.isSCUIShow = false;
        if (ui.gameSystemUILayer && typeof ui.gameSystemUILayer.setMenuVisible === "function") {
          ui.gameSystemUILayer.setMenuVisible(true);
        }
      }
      if (gameData) gameData.CUIFromIndex = -1;
      event.isSuiFinish = true;
      event.finish();
    });

    overlay.appendChild(form);
    document.body.appendChild(overlay);
    var ui = window.UIManager && UIManager.getInstance && UIManager.getInstance();
    if (ui) {
      ui.isSCUIShow = true;
      if (ui.gameSystemUILayer && typeof ui.gameSystemUILayer.setMenuVisible === "function") {
        ui.gameSystemUILayer.setMenuVisible(false);
      }
    }
    if (gameData) gameData.CUIFromIndex = 10014;
    window.setTimeout(function () { if (inputs[0]) inputs[0].input.focus(); }, 0);
    compatLog("official proxy built-in name editor opened fields=" + fields.length);
    return true;
  }

  function installCuiCompatibilityPatch() {
    if (
      cuiCompatibilityInstalled ||
      !window.org_event ||
      !org_event.CallMenuEvent ||
      !org_event.CallMenuEvent.prototype ||
      typeof org_event.CallMenuEvent.prototype.init !== "function"
    ) return false;

    var originalCallMenuInit = org_event.CallMenuEvent.prototype.init;
    org_event.CallMenuEvent.prototype.init = function () {
      var argv = this.data && this.data.Argv;
      if (parseInt(argv && argv[0], 10) === 10014 && showBuiltinNameEditor(this, argv)) {
        this.index = 10014;
        return;
      }
      return originalCallMenuInit.apply(this, arguments);
    };
    org_event.CallMenuEvent.prototype.init.__officialProxyCuiCompatibilityWrapped = true;
    cuiCompatibilityInstalled = true;
    compatLog("official proxy built-in CUI compatibility enabled");
    return true;
  }

  registerCompatPatch("built-in CUI", 30, installCuiCompatibilityPatch);
