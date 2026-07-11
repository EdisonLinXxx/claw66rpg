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

assert.deepEqual(resolveProfile("0a235c54f16c431ab5736c92997edb47", "364"), {
  profiles: ["66rpg-1569947-legacy-v2"],
  capabilities: ["extended-dsystem", "padded-dbutton"],
});
assert.deepEqual(resolveProfile("468fe16ef100b2f24215e6874783ad66", "1544"), {
  profiles: ["66rpg-1683317-v1544"],
  capabilities: ["extended-dsystem", "native-v108-sized-cui"],
});
assert.deepEqual(resolveProfile("468fe16ef100b2f24215e6874783ad66", "1543"), {
  profiles: [],
  capabilities: [],
});
assert.deepEqual(resolveProfile("9076a69f88f6c963ec508dabe224a73e", "56"), {
  profiles: ["66rpg-1692665-v56"],
  capabilities: ["extended-dsystem", "native-v108-sized-cui"],
});
assert.deepEqual(resolveProfile("00000000000000000000000000000000", "1"), {
  profiles: [],
  capabilities: [],
});

console.log("official compatibility profiles passed");
