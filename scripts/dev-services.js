'use strict';

const net = require('node:net');
const path = require('node:path');
const { spawn } = require('node:child_process');

const repoRoot = path.resolve(__dirname, '..');

function usage() {
  console.log(`Usage:
  node scripts/dev-services.js [options]

Options:
  --official-only           Start only the v2 official-player proxy
  --modern-only             Start only the modern player
  --host <host>             Listen host (default: 127.0.0.1)
  --official-port <port>    Official proxy port (default: 8766)
  --modern-port <port>      Modern player port (default: 8788)
  --python <command>        Python executable (default: PYTHON, python/python3)
  --platform-unlock         Enable platform unlock explicitly
  --no-platform-unlock      Disable platform unlock
  --smoke-test              Start, verify both selected ports, then stop
  --help                    Show this help`);
}

function positivePort(value, name) {
  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(`${name} must be a valid port`);
  return port;
}

function parseArgs(argv) {
  const options = {
    host: '127.0.0.1',
    officialPort: 8766,
    modernPort: 8788,
    python: process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3'),
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') options.help = true;
    else if (arg === '--official-only') options.officialOnly = true;
    else if (arg === '--modern-only') options.modernOnly = true;
    else if (arg === '--host') options.host = argv[++index];
    else if (arg === '--official-port') options.officialPort = positivePort(argv[++index], '--official-port');
    else if (arg === '--modern-port') options.modernPort = positivePort(argv[++index], '--modern-port');
    else if (arg === '--python') options.python = argv[++index];
    else if (arg === '--platform-unlock' || arg === '--dev-free-unlock') options.platformUnlock = true;
    else if (arg === '--no-platform-unlock') options.noPlatformUnlock = true;
    else if (arg === '--smoke-test') options.smokeTest = true;
    else throw new Error(`Unknown argument: ${arg}`);
  }
  if (options.officialOnly && options.modernOnly) throw new Error('--official-only and --modern-only are mutually exclusive');
  if (options.platformUnlock && options.noPlatformUnlock) throw new Error('unlock flags are mutually exclusive');
  return options;
}

function waitForPort(host, port, timeoutMs = 15_000) {
  const startedAt = Date.now();
  return new Promise((resolve, reject) => {
    function attempt() {
      const socket = net.createConnection({ host, port });
      socket.once('connect', () => {
        socket.destroy();
        resolve();
      });
      socket.once('error', () => {
        socket.destroy();
        if (Date.now() - startedAt >= timeoutMs) reject(new Error(`Timed out waiting for ${host}:${port}`));
        else setTimeout(attempt, 120);
      });
    }
    attempt();
  });
}

function startService(options, name, scriptName, port, extraArgs = []) {
  const args = [
    path.join(repoRoot, scriptName),
    '--host', options.host,
    '--port', String(port),
    '--root', repoRoot,
    ...extraArgs,
  ];
  const child = spawn(options.python, args, {
    cwd: repoRoot,
    stdio: 'inherit',
    windowsHide: true,
  });
  child.serviceName = name;
  child.once('error', (error) => {
    console.error(`${name} failed to start: ${error.message}`);
  });
  return child;
}

async function stopChildren(children) {
  for (const child of children) {
    if (child.exitCode === null && child.signalCode === null) child.kill();
  }
  await Promise.race([
    Promise.all(children.map((child) => new Promise((resolve) => {
      if (child.exitCode !== null || child.signalCode !== null) resolve();
      else child.once('close', resolve);
    }))),
    new Promise((resolve) => setTimeout(resolve, 3_000)),
  ]);
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    usage();
    return;
  }

  const children = [];
  const ports = [];
  const startOfficial = !options.modernOnly;
  const startModern = !options.officialOnly;
  if (startOfficial) {
    const unlockArgs = [];
    if (options.noPlatformUnlock) unlockArgs.push('--no-platform-unlock');
    if (options.platformUnlock) unlockArgs.push('--platform-unlock');
    children.push(startService(options, 'official-player proxy', 'official_player_proxy.py', options.officialPort, unlockArgs));
    ports.push(options.officialPort);
  }
  if (startModern) {
    children.push(startService(options, 'modern player', 'modern_player_server.py', options.modernPort));
    ports.push(options.modernPort);
  }

  let stopping = false;
  const shutdown = async (exitCode = 0) => {
    if (stopping) return;
    stopping = true;
    await stopChildren(children);
    process.exitCode = exitCode;
  };
  process.once('SIGINT', () => { shutdown(130); });
  process.once('SIGTERM', () => { shutdown(143); });

  if (options.smokeTest) {
    try {
      await Promise.all(ports.map((port) => waitForPort(options.host, port)));
      console.log(`service smoke test passed: ${ports.map((port) => `${options.host}:${port}`).join(', ')}`);
      await shutdown(0);
    } catch (error) {
      console.error(error.message);
      await shutdown(1);
    }
    return;
  }

  console.log(`player services running: ${ports.map((port) => `${options.host}:${port}`).join(', ')}`);
  await new Promise((resolve) => {
    let exited = 0;
    const handleExit = async (child, code, signal) => {
      exited += 1;
      if (!stopping) {
        console.error(`${child.serviceName} exited (${code ?? signal ?? 'unknown'})`);
        await shutdown(code || 1);
      }
      if (exited === children.length) resolve();
    };
    for (const child of children) {
      if (child.exitCode !== null || child.signalCode !== null) {
        queueMicrotask(() => { handleExit(child, child.exitCode, child.signalCode); });
      } else child.once('close', (code, signal) => { handleExit(child, code, signal); });
    }
  });
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error.stack || error.message || error);
    process.exitCode = 1;
  });
}

module.exports = { parseArgs, waitForPort };
