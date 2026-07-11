const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "..");
const bundle = fs.readFileSync(path.join(repoRoot, "official_player_compat.js"), "utf8");
const profileRoot = path.join(repoRoot, "official_player_game_profiles");

function loadProfile(context, gameId) {
  if (!/^\d+$/.test(String(gameId || ""))) return false;
  const profilePath = path.join(profileRoot, `${gameId}.js`);
  if (!fs.existsSync(profilePath)) return false;
  vm.runInContext(fs.readFileSync(profilePath, "utf8"), context, {
    filename: `official_player_game_profiles/${gameId}.js`,
  });
  return true;
}

function createContext(window, globals = {}) {
  return vm.createContext({
    window,
    console: window.console,
    setInterval() { return 1; },
    clearInterval() {},
    ...globals,
  });
}

function resolveProfile(gameId, guid, version) {
  const window = {
    __officialProxyGuid: guid,
    __officialProxyVersion: version,
    __officialProxyDevFreeUnlock: false,
    location: { search: "" },
    console: { log() {} },
  };
  const context = createContext(window);
  vm.runInContext(bundle, context, { filename: "official_player_compat.js" });
  loadProfile(context, gameId);
  return {
    profiles: Array.from(window.__officialProxyCompatRegistry.activeProfileIds()),
    capabilities: Array.from(window.__officialProxyCompatRegistry.activeCapabilities()).sort(),
  };
}

function resolveGameIndexAfterConfig({
  profileGameId,
  guid,
  version,
  gameId,
  runtimeIndex,
  userIndex,
}) {
  const gameData = { gameInfo: { gIndex: runtimeIndex } };
  const commonPlayer = { userInfos: { gindex: userIndex } };
  const GloableData = { getInstance() { return gameData; } };
  function Main() {}
  Main.prototype.setGameConfig = function () {
    gameData.gameInfo.gIndex = runtimeIndex;
    commonPlayer.userInfos.gindex = userIndex;
  };

  const window = {
    __officialProxyGuid: guid,
    __officialProxyVersion: version,
    __officialProxyGameId: gameId,
    __officialProxyDevFreeUnlock: false,
    location: { search: "" },
    console: { log() {} },
    commonPlayer,
    GloableData,
    Main,
  };
  const context = createContext(window, { commonPlayer, GloableData, Main });
  vm.runInContext(bundle, context, { filename: "official_player_compat.js" });
  loadProfile(context, profileGameId || gameId);
  new Main().setGameConfig();
  return {
    runtimeIndex: gameData.gameInfo.gIndex,
    userIndex: commonPlayer.userInfos.gindex,
  };
}

assert.deepEqual(resolveProfile("1569947", "0a235c54f16c431ab5736c92997edb47", "364"), {
  profiles: ["66rpg-1569947-legacy-v2"],
  capabilities: ["extended-dsystem", "padded-dbutton"],
});
assert.deepEqual(resolveProfile("1683317", "468fe16ef100b2f24215e6874783ad66", "1544"), {
  profiles: ["66rpg-1683317-v1544"],
  capabilities: ["extended-dsystem", "jump-story-v2063", "native-v108-sized-cui"],
});
assert.deepEqual(resolveProfile("1683317", "468fe16ef100b2f24215e6874783ad66", "1543"), {
  profiles: [],
  capabilities: [],
});
assert.deepEqual(resolveProfile("1692665", "9076a69f88f6c963ec508dabe224a73e", "56"), {
  profiles: ["66rpg-1692665-v56"],
  capabilities: ["extended-dsystem", "jump-story-v2063", "native-v108-sized-cui"],
});
assert.deepEqual(resolveProfile("1692785", "7978ad977a004863319a5b8fb970653d", "52"), {
  profiles: ["66rpg-1692785-v52-unverified"],
  capabilities: [],
});
assert.deepEqual(resolveProfile("1693705", "544d66fdeb58b5219cb5e3adb543e6aa", "28"), {
  profiles: ["66rpg-1693705-v28"],
  capabilities: [
    "cui-capability-inventory",
    "extended-dsystem",
    "native-v108-sized-cui",
    "proxy-query-game-index",
  ],
});
assert.deepEqual(resolveProfile("1693705", "544d66fdeb58b5219cb5e3adb543e6aa", "27"), {
  profiles: [],
  capabilities: [],
});
assert.deepEqual(resolveProfile("1692665", "544d66fdeb58b5219cb5e3adb543e6aa", "28"), {
  profiles: [],
  capabilities: [],
});
assert.deepEqual(resolveProfile("0000000", "00000000000000000000000000000000", "1"), {
  profiles: [],
  capabilities: [],
});

assert.deepEqual(resolveGameIndexAfterConfig({
  guid: "544d66fdeb58b5219cb5e3adb543e6aa",
  version: "28",
  gameId: "1693705",
  runtimeIndex: Number.NaN,
  userIndex: "",
}), {
  runtimeIndex: 1693705,
  userIndex: "1693705",
});
assert.deepEqual(resolveGameIndexAfterConfig({
  guid: "544d66fdeb58b5219cb5e3adb543e6aa",
  version: "28",
  gameId: "1693705",
  runtimeIndex: 1569947,
  userIndex: "1569947",
}), {
  runtimeIndex: 1569947,
  userIndex: "1569947",
});
assert.deepEqual(resolveGameIndexAfterConfig({
  guid: "9076a69f88f6c963ec508dabe224a73e",
  version: "56",
  gameId: "1692665",
  runtimeIndex: Number.NaN,
  userIndex: "",
}), {
  runtimeIndex: Number.NaN,
  userIndex: "",
});
assert.deepEqual(resolveGameIndexAfterConfig({
  profileGameId: "1693705",
  guid: "544d66fdeb58b5219cb5e3adb543e6aa",
  version: "28",
  gameId: "1693705-not-valid",
  runtimeIndex: Number.NaN,
  userIndex: "",
}), {
  runtimeIndex: Number.NaN,
  userIndex: "",
});

console.log("official compatibility profiles passed");
