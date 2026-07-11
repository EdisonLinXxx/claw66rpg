'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const repoRoot = path.resolve(__dirname, '..');

function runNode(args) {
  execFileSync(process.execPath, args, {
    cwd: repoRoot,
    stdio: 'inherit',
  });
}

function main() {
  runNode([path.join(__dirname, 'build-official-player-compat.js'), '--check']);

  const sourceRoot = path.join(repoRoot, 'official_player_compat_src');
  fs.readdirSync(sourceRoot)
    .filter((fileName) => fileName.endsWith('.js') && fileName !== '05-game-profiles.js')
    .forEach((fileName) => {
      const sourceText = fs.readFileSync(path.join(sourceRoot, fileName), 'utf8');
      if (/[0-9a-fA-F]{32}/.test(sourceText)) {
        throw new Error(
          `${fileName} contains a game GUID. Move matching rules into 05-game-profiles.js.`,
        );
      }
    });

  const proxyText = fs.readFileSync(path.join(repoRoot, 'official_player_proxy.html'), 'utf8');
  const policyScriptIndex = proxyText.indexOf('player_render_refresh_policy.js');
  const refreshScriptIndex = proxyText.indexOf('player_render_refresh.js');
  if (policyScriptIndex < 0 || refreshScriptIndex < 0 || policyScriptIndex > refreshScriptIndex) {
    throw new Error('Render policy module must load before player_render_refresh.js.');
  }

  runNode(['--check', path.join(repoRoot, 'official_player_compat.js')]);
  runNode([
    path.join(
      repoRoot,
      '66rpgProjectDropper',
      'validate_official_compat_profiles.js',
    ),
  ]);
  runNode([path.join(__dirname, 'validate-player-render-policy.js')]);

  console.log('official player compatibility validation passed');
}

try {
  main();
} catch (error) {
  if (error && error.message && error.status === undefined) {
    console.error(error.message);
  }
  process.exitCode = 1;
}
