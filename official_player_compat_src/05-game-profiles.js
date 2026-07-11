  registerGameProfile({
    id: "66rpg-1569947-legacy-v2",
    guid: "0a235c54f16c431ab5736c92997edb47",
    versions: "*",
    capabilities: ["padded-dbutton", "extended-dsystem"]
  });

  registerGameProfile({
    id: "66rpg-1683317-v1544",
    guid: "468fe16ef100b2f24215e6874783ad66",
    versions: ["1544"],
    capabilities: ["extended-dsystem", "native-v108-sized-cui", "jump-story-v2063"]
  });

  registerGameProfile({
    id: "66rpg-1692665-v56",
    guid: "9076a69f88f6c963ec508dabe224a73e",
    versions: ["56"],
    capabilities: ["extended-dsystem", "native-v108-sized-cui", "jump-story-v2063"]
  });

  registerGameProfile({
    id: "66rpg-1693705-v28",
    guid: "544d66fdeb58b5219cb5e3adb543e6aa",
    versions: ["28"],
    capabilities: ["extended-dsystem", "native-v108-sized-cui"]
  });

  window.__officialProxyCompatRegistry = {
    activeProfileIds: function () {
      return getActiveGameProfiles().map(function (profile) { return profile.id; });
    },
    activeCapabilities: getActiveCompatCapabilities,
    hasCapability: hasCompatCapability
  };
