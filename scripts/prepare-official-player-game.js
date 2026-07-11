'use strict';

const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '..');
const defaultCdnHosts = [
  'https://dlcdn1.cgyouxi.com',
  'https://c2.cgyouxi.com',
  'https://c3.cgyouxi.com',
  'https://c4.cgyouxi.com',
];

function usage() {
  console.log(`Usage:
  node scripts/prepare-official-player-game.js --game-url <url> [options]

Options:
  --downloads <directory>  Bundle root relative to the repository (default: .dry-run-downloads)
  --cdn-host <url>          Override CDN host; repeat to provide fallbacks
  --help                    Show this help`);
}

function parseArgs(argv) {
  const options = { downloads: '.dry-run-downloads', cdnHosts: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') options.help = true;
    else if (arg === '--game-url') options.gameUrl = argv[++index];
    else if (arg === '--downloads') options.downloads = argv[++index];
    else if (arg === '--cdn-host') options.cdnHosts.push(argv[++index]);
    else throw new Error(`Unknown argument: ${arg}`);
  }
  if (!options.help && !options.gameUrl) throw new Error('--game-url is required');
  if (!options.cdnHosts.length) options.cdnHosts = defaultCdnHosts;
  return options;
}

async function fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response;
  } finally {
    clearTimeout(timer);
  }
}

function extractGameInfo(html, gameUrl) {
  const patterns = [
    /window\.GAME_INFO_DATA\s*=\s*(\{[\s\S]*?\});/,
    /\$\('#data'\)\.data\('game',\s*(\{[\s\S]*?\})\);/,
  ];
  for (const pattern of patterns) {
    const match = html.match(pattern);
    if (match) return JSON.parse(match[1]);
  }
  throw new Error(`Official game payload was not found in ${gameUrl}`);
}

async function getGameInfo(gameUrl) {
  const response = await fetchWithTimeout(gameUrl, {
    headers: {
      'User-Agent': 'Mozilla/5.0 OfficialPlayerProxyPrep/2.0',
      'Accept-Language': 'zh-CN,zh;q=0.9',
    },
  }, 30_000);
  return extractGameInfo(await response.text(), gameUrl);
}

async function saveFirstAvailable(hosts, relativePath, target) {
  let lastError = 'unknown error';
  for (const host of hosts) {
    const url = `${host.replace(/\/$/, '')}/${relativePath.replace(/^\//, '')}`;
    try {
      const response = await fetchWithTimeout(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 OfficialPlayerProxyPrep/2.0',
          Referer: 'https://www.66rpg.com/',
        },
      }, 60_000);
      const content = Buffer.from(await response.arrayBuffer());
      fs.writeFileSync(target, content);
      return url;
    } catch (error) {
      lastError = error.message;
    }
  }
  throw new Error(`Failed to download ${relativePath}. Last error: ${lastError}`);
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    usage();
    return;
  }

  const info = await getGameInfo(options.gameUrl);
  const gameId = String(info.gindex || '');
  const guid = String(info.guid || '');
  const version = String(info.cur_version || info.version || '');
  if (!gameId || !guid || !version) {
    throw new Error(`Missing game metadata: gameId=${gameId} guid=${guid} version=${version}`);
  }

  const bundleDir = path.resolve(repoRoot, options.downloads, 'games', guid, version);
  fs.mkdirSync(bundleDir, { recursive: true });
  const mapTarget = path.join(bundleDir, 'Map_32.bin');
  const miniTarget = path.join(bundleDir, 'Game_mini.bin');
  const basePath = `web/${guid}/${version}`;
  const mapUrl = await saveFirstAvailable(options.cdnHosts, `${basePath}/Map_32.bin`, mapTarget);
  const miniUrl = await saveFirstAvailable(options.cdnHosts, `${basePath}/Game_mini.bin`, miniTarget);

  console.log(`gameId=${gameId}`);
  console.log(`title=${info.gname || ''}`);
  console.log(`author=${info.author_uname || ''}`);
  console.log(`guid=${guid}`);
  console.log(`version=${version}`);
  console.log(`bundle=${bundleDir}`);
  console.log(`map=${mapTarget}`);
  console.log(`map_url=${mapUrl}`);
  console.log(`game_mini=${miniTarget}`);
  console.log(`game_mini_url=${miniUrl}`);
  console.log(`entry=/play-proxy/official_player_proxy.html?gameId=${gameId}&guid=${guid}&version=${version}`);
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error.message || error);
    process.exitCode = 1;
  });
}

module.exports = { extractGameInfo, getGameInfo, parseArgs, saveFirstAvailable };
