'use strict';

const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const repoRoot = path.resolve(__dirname, '..');

function usage() {
  console.log(`Usage:
  node scripts/validate-official-proxy-pages.js [options]

Options:
  --python <command>     Python executable
  --host <host>         Proxy host (default: 127.0.0.1)
  --port <port>         Proxy port (default: 8766)
  --out <directory>     Evidence output directory
  --no-start-server     Reuse an already running proxy
  --headed              Show the validation browser
  --help                Show this help`);
}

function parseArgs(argv) {
  const options = {
    python: process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3'),
    host: '127.0.0.1',
    port: 8766,
    out: path.join(os.tmpdir(), 'official_proxy_main_pages'),
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') options.help = true;
    else if (arg === '--python') options.python = argv[++index];
    else if (arg === '--host') options.host = argv[++index];
    else if (arg === '--port') options.port = Number(argv[++index]);
    else if (arg === '--out') options.out = path.resolve(argv[++index]);
    else if (arg === '--no-start-server') options.noStartServer = true;
    else if (arg === '--headed') options.headed = true;
    else throw new Error(`Unknown argument: ${arg}`);
  }
  if (!Number.isInteger(options.port) || options.port < 1 || options.port > 65535) {
    throw new Error('--port must be a valid port');
  }
  return options;
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    usage();
    return;
  }
  const args = [
    path.join(repoRoot, '66rpgProjectDropper', 'validate_official_proxy_pages.py'),
    '--root', repoRoot,
    '--out', options.out,
    '--host', options.host,
    '--port', String(options.port),
    '--python', options.python,
  ];
  if (options.noStartServer) args.push('--no-start-server');
  if (options.headed) args.push('--headed');
  const result = spawnSync(options.python, args, {
    cwd: repoRoot,
    stdio: 'inherit',
    windowsHide: true,
  });
  if (result.error) throw result.error;
  process.exitCode = result.status ?? 1;
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error(error.message || error);
    process.exitCode = 1;
  }
}

module.exports = { parseArgs };
