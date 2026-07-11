'use strict';

const assert = require('node:assert/strict');
const prepare = require('./prepare-official-player-game');
const services = require('./dev-services');
const validator = require('./validate-official-proxy-pages');

assert.deepEqual(
  prepare.parseArgs(['--game-url', 'https://www.66rpg.com/game/1693705']),
  {
    gameUrl: 'https://www.66rpg.com/game/1693705',
    downloads: '.dry-run-downloads',
    cdnHosts: [
      'https://dlcdn1.cgyouxi.com',
      'https://c2.cgyouxi.com',
      'https://c3.cgyouxi.com',
      'https://c4.cgyouxi.com',
    ],
  },
);
assert.equal(
  prepare.extractGameInfo("<script>window.GAME_INFO_DATA = {\"gindex\":1693705};</script>", 'test').gindex,
  1693705,
);
assert.equal(
  prepare.extractGameInfo("<script>$('#data').data('game', {\"gindex\":1693705});</script>", 'test').gindex,
  1693705,
);

const serviceOptions = services.parseArgs([
  '--official-only', '--official-port', '18766', '--no-platform-unlock',
]);
assert.equal(serviceOptions.officialOnly, true);
assert.equal(serviceOptions.officialPort, 18766);
assert.equal(serviceOptions.noPlatformUnlock, true);
assert.throws(() => services.parseArgs(['--official-only', '--modern-only']), /mutually exclusive/);

const validatorOptions = validator.parseArgs(['--port', '18766', '--no-start-server']);
assert.equal(validatorOptions.port, 18766);
assert.equal(validatorOptions.noStartServer, true);

console.log('node entrypoint validation passed');
