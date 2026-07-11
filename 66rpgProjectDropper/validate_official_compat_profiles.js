const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "..");
const bundle = fs.readFileSync(path.join(repoRoot, "official_player_compat.js"), "utf8");

function resolveProfile(guid, version) {
  const window = {
    __officialProxyGuid: guid,
    __officialProxyVersion: version,
    __officialProxyDevFreeUnlock: false,
    location: { search: "" },
    console: { log() {} },
  };
  const context = {
    window,
    console: window.console,
    setInterval() { return 1; },
    clearInterval() {},
  };
  vm.runInNewContext(bundle, context, { filename: "official_player_compat.js" });
  return {
    profiles: Array.from(window.__officialProxyCompatRegistry.activeProfileIds()),
    capabilities: Array.from(window.__officialProxyCompatRegistry.activeCapabilities()).sort(),
  };
}

function resolveGameIndexAfterConfig({ guid, version, gameId, runtimeIndex, userIndex }) {
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
  const context = {
    window,
    console: window.console,
    commonPlayer,
    GloableData,
    Main,
    setInterval() { return 1; },
    clearInterval() {},
  };
  vm.runInNewContext(bundle, context, { filename: "official_player_compat.js" });
  new Main().setGameConfig();
  return {
    runtimeIndex: gameData.gameInfo.gIndex,
    userIndex: commonPlayer.userInfos.gindex,
  };
}

assert.deepEqual(resolveProfile("0a235c54f16c431ab5736c92997edb47", "364"), {
  profiles: ["66rpg-1569947-legacy-v2"],
  capabilities: ["extended-dsystem", "padded-dbutton"],
});
assert.deepEqual(resolveProfile("468fe16ef100b2f24215e6874783ad66", "1544"), {
  profiles: ["66rpg-1683317-v1544"],
  capabilities: ["extended-dsystem", "jump-story-v2063", "native-v108-sized-cui"],
});
assert.deepEqual(resolveProfile("468fe16ef100b2f24215e6874783ad66", "1543"), {
  profiles: [],
  capabilities: [],
});
assert.deepEqual(resolveProfile("9076a69f88f6c963ec508dabe224a73e", "56"), {
  profiles: ["66rpg-1692665-v56"],
  capabilities: ["extended-dsystem", "jump-story-v2063", "native-v108-sized-cui"],
});
assert.deepEqual(resolveProfile("544d66fdeb58b5219cb5e3adb543e6aa", "28"), {
  profiles: ["66rpg-1693705-v28"],
  capabilities: [
    "cui-capability-inventory",
    "extended-dsystem",
    "native-v108-sized-cui",
    "proxy-query-game-index",
  ],
});
assert.deepEqual(resolveProfile("544d66fdeb58b5219cb5e3adb543e6aa", "27"), {
  profiles: [],
  capabilities: [],
});
assert.deepEqual(resolveProfile("00000000000000000000000000000000", "1"), {
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
