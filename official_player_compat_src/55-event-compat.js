  function installJumpStoryV2063Patch() {
    if (!hasCompatCapability("jump-story-v2063")) return false;
    if (typeof MainEventLine === "undefined" || !MainEventLine.prototype) return false;
    if (MainEventLine.prototype.__officialProxyJumpStoryV2063Wrapped) return false;

    var originalMakeEvent = MainEventLine.prototype.makeEvent;
    MainEventLine.prototype.makeEvent = function (event) {
      var currentEvent = event || (this.story && this.story.events && this.story.events[this.pos]);
      if (currentEvent && currentEvent.Code === 2063) {
        currentEvent.Code = 206;
        compatLog("official proxy v2063 jump-story compat story=" + currentEvent.Argv[0]);
      }
      return originalMakeEvent.apply(this, arguments);
    };
    MainEventLine.prototype.__officialProxyJumpStoryV2063Wrapped = true;
    compatLog("official proxy v2063 jump-story compat enabled");
    return true;
  }

  registerCompatPatch("v2063 jump-story", 30, installJumpStoryV2063Patch);
