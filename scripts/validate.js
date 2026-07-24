#!/usr/bin/env node

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');

function run(label, command, args, options = {}) {
  process.stdout.write(`\n==> ${label}\n`);
  const result = spawnSync(command, args, {
    cwd: root,
    encoding: 'utf8',
    shell: options.shell || false,
  });
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  if (result.error) {
    process.stderr.write(`${result.error.message}\n`);
    return 1;
  }
  return result.status === null ? 1 : result.status;
}

const checks = [
  ['Hook and skill tests', process.execPath, ['--test', 'tests/hooks/*.test.js', 'tests/skills/*.test.js'], { shell: true }],
  ['Curation tests', 'python3', ['-B', '-m', 'unittest', 'tests.curation.test_review_upstreams', '-v']],
  ['Zellij pane identity', 'python3', ['-B', 'skills/zellij-agent-herder/tests/test-pane-identity.py', '-v']],
  ['Zellij adaptive spawn', 'bash', ['skills/zellij-agent-herder/tests/test-zj-spawn.sh']],
  ['Zellij Hunk focus guard', 'python3', ['-B', 'skills/zellij-agent-herder/tests/test-hunk-focus-guard.py', '-v']],
  ['Zellij Hunk stream', 'bash', ['skills/zellij-agent-herder/tests/test-hunk-stream.sh']],
  ['Zellij hook installer', 'bash', ['skills/zellij-agent-herder/tests/test-install-hooks.sh']],
  ['Zellij shared agent config', 'bash', ['skills/zellij-agent-herder/tests/test-shared-agent-config.sh']],
];

for (const check of checks) {
  const status = run(...check);
  if (status !== 0) process.exit(status);
}

const configuredValidator = process.env.PLUGIN_VALIDATOR;
const systemValidator = path.join(
  os.homedir(), '.codex', 'skills', '.system', 'plugin-creator', 'scripts', 'validate_plugin.py',
);
const pluginValidator = configuredValidator || systemValidator;
const systemDependenciesAvailable = spawnSync(
  'python3', ['-c', 'import yaml'], { cwd: root },
).status === 0;
if (fs.existsSync(pluginValidator) && systemDependenciesAvailable) {
  const status = run('Plugin schema', 'python3', [pluginValidator, '.']);
  if (status !== 0) process.exit(status);
} else {
  const reason = fs.existsSync(pluginValidator)
    ? 'PyYAML unavailable'
    : 'validator file absent';
  process.stdout.write(`\n==> Plugin schema\nSKIP plugin-schema check: ${reason}; set PLUGIN_VALIDATOR to enable it.\n`);
}

process.exit(run('Diff whitespace', 'git', ['diff', '--check']));
