const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { root } = require('../helpers/skills');

test('session summarizer indexes intent while withholding raw commands, results, and secrets', () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'incident-retro-'));
  const transcript = path.join(temporary, 'session.jsonl');
  const events = [
    { type: 'user', uuid: 'user-1', timestamp: '2026-07-22T00:00:00Z', cwd: '/work', message: { role: 'user', content: 'Investigate TOKEN=supersecret safely' } },
    { type: 'user', uuid: 'user-1', timestamp: '2026-07-22T00:00:00Z', cwd: '/work', message: { role: 'user', content: 'Investigate TOKEN=supersecret safely' } },
    { type: 'assistant', timestamp: '2026-07-22T00:00:01Z', message: { role: 'assistant', content: [
      { type: 'tool_use', name: 'Bash', input: { description: 'Fetch incident details', command: 'curl https://example.invalid?token=supersecret' } },
      { type: 'text', text: 'Correction: the first interpretation was wrong.' },
    ] } },
    { type: 'user', timestamp: '2026-07-22T00:00:02Z', message: { role: 'user', content: [{ type: 'tool_result', content: 'raw-provider-secret' }] } },
  ];
  fs.writeFileSync(transcript, `${events.map((event) => JSON.stringify(event)).join('\n')}\n`);
  const script = path.join(root, 'skills', 'investigating-incidents', 'scripts', 'summarize-claude-sessions.py');
  const result = spawnSync('python3', [script, transcript], { encoding: 'utf8' });
  fs.rmSync(temporary, { recursive: true, force: true });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Fetch incident details/);
  assert.match(result.stdout, /Candidate correction points/);
  assert.match(result.stdout, /TOKEN=<redacted>/);
  assert.equal((result.stdout.match(/Investigate TOKEN=/g) || []).length, 1);
  assert.doesNotMatch(result.stdout, /supersecret|raw-provider-secret|curl https/);
});
