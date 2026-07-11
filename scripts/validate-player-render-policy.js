'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');

const policy = require(path.resolve(__dirname, '..', 'player_render_refresh_policy.js'));

const legacyPolicy = {
  id: 'legacy-forced-repaint',
  forceRepaintLevel: true,
  recache: true,
};

assert.deepEqual(policy.resolve(null), legacyPolicy);
assert.deepEqual(policy.resolve({ hasCapability() { return false; } }), legacyPolicy);
assert.deepEqual(
  policy.resolve({ hasCapability(capability) {
    return capability === 'render-public-repaint-only';
  } }),
  {
    id: 'public-repaint-only',
    forceRepaintLevel: false,
    recache: false,
  },
);

console.log('player render policy validation passed');
