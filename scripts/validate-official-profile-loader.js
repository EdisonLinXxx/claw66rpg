'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');

const loader = require(path.resolve(__dirname, '..', 'official_player_profile_loader.js'));

assert.equal(loader.normalizeGameId('1693705'), '1693705');
assert.equal(loader.normalizeGameId('1693705.js'), '');
assert.equal(loader.normalizeGameId('../1693705'), '');
assert.equal(loader.profileUrl('1693705', '28'), 'official_player_game_profiles/1693705.js?v=28');
assert.equal(loader.profileUrl('bad-id', '28'), '');

function fakeTarget({ gameId = '1693705', version = '28', loadStatus = 'loaded' } = {}) {
  const appended = [];
  const target = {
    __officialProxyGameId: gameId,
    __officialProxyVersion: version,
    Promise,
    document: {
      createElement() { return {}; },
      head: {
        appendChild(script) {
          appended.push(script.src);
          queueMicrotask(() => {
            if (loadStatus === 'loaded') script.onload();
            else script.onerror();
          });
        },
      },
    },
    logLine() {},
  };
  return { target, appended };
}

async function main() {
  const loaded = fakeTarget();
  assert.deepEqual(await loader.load(loaded.target), {
    status: 'loaded',
    url: 'official_player_game_profiles/1693705.js?v=28',
  });
  assert.deepEqual(loaded.appended, ['official_player_game_profiles/1693705.js?v=28']);

  const missing = fakeTarget({ gameId: '9999999', loadStatus: 'missing' });
  assert.deepEqual(await loader.load(missing.target), {
    status: 'missing',
    url: 'official_player_game_profiles/9999999.js?v=28',
  });

  const invalid = fakeTarget({ gameId: '../1693705' });
  assert.deepEqual(await loader.load(invalid.target), { status: 'skipped', url: '' });
  assert.deepEqual(invalid.appended, []);

  console.log('official profile loader validation passed');
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
