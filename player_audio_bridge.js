(function () {
  "use strict";

  if (window.__otomePlayerAudioBridge) return;

  var muted = false;
  var retryTimer = 0;
  var retryCount = 0;

  function getSoundManager() {
    if (window.Laya && window.Laya.SoundManager) return window.Laya.SoundManager;
    if (window.laya && window.laya.media && window.laya.media.SoundManager) {
      return window.laya.media.SoundManager;
    }
    return null;
  }

  function setMediaMuted(value) {
    var mediaElements = document.querySelectorAll("audio, video");
    for (var index = 0; index < mediaElements.length; index += 1) {
      mediaElements[index].muted = value;
    }
  }

  function applyMutedState() {
    var soundManager = getSoundManager();
    if (soundManager) soundManager.muted = muted;
    setMediaMuted(muted);

    document.documentElement.dataset.otomeMuted = muted ? "true" : "false";
    document.documentElement.dataset.otomeAudioManager = soundManager ? "laya" : "media";
    return Boolean(soundManager);
  }

  function notifyParent(applied) {
    if (!window.parent || window.parent === window) return;
    window.parent.postMessage({
      type: "otome-player-audio-state",
      muted: muted,
      applied: applied
    }, window.location.origin);
  }

  function stopRetrying() {
    if (!retryTimer) return;
    window.clearInterval(retryTimer);
    retryTimer = 0;
  }

  function retryUntilPlayerReady() {
    stopRetrying();
    retryCount = 0;
    retryTimer = window.setInterval(function () {
      retryCount += 1;
      var applied = applyMutedState();
      if (applied || retryCount >= 20) {
        stopRetrying();
        notifyParent(applied);
      }
    }, 250);
  }

  function setMuted(value) {
    muted = Boolean(value);
    var applied = applyMutedState();
    notifyParent(applied);
    if (!applied) retryUntilPlayerReady();
    return applied;
  }

  window.__otomePlayerAudioBridge = {
    apply: applyMutedState,
    getMuted: function () { return muted; },
    setMuted: setMuted
  };

  window.addEventListener("message", function (event) {
    if (event.source !== window.parent) return;
    if (event.origin && event.origin !== window.location.origin) return;
    if (!event.data || event.data.type !== "otome-player-audio") return;
    setMuted(event.data.muted);
  });

  if (window.MutationObserver) {
    new window.MutationObserver(function () {
      if (muted) setMediaMuted(true);
    }).observe(document.documentElement, { childList: true, subtree: true });
  }
}());
