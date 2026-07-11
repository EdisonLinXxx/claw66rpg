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

  const parserModule = path.join(
    repoRoot,
    'official_player_compat_src',
    '50-binary-parser.js',
  );
  const parserText = fs.readFileSync(parserModule, 'utf8');
  if (/[0-9a-fA-F]{32}/.test(parserText)) {
    throw new Error(
      'Binary parser module contains a game GUID. Move matching rules into 05-game-profiles.js.',
    );
  }

  runNode(['--check', path.join(repoRoot, 'official_player_compat.js')]);
  runNode([
    path.join(
      repoRoot,
      '66rpgProjectDropper',
      'validate_official_compat_profiles.js',
    ),
  ]);

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
