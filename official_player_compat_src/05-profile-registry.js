  window.__officialProxyCompatRegistry = {
    registerGameProfile: function (profile) {
      registerGameProfile(profile);
      compatLog("official proxy game profile registered " + String(profile && profile.id || "unknown"));
      return installRegisteredCompatPatches();
    },
    activeProfileIds: function () {
      return getActiveGameProfiles().map(function (profile) { return profile.id; });
    },
    activeCapabilities: getActiveCompatCapabilities,
    hasCapability: hasCompatCapability
  };
