const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const zlib = require('node:zlib');

const root = path.join(__dirname, '..', '..');
const source = path.join(root, 'skills', 'personal-writing-style', 'scripts', 'writing-corpus.go');
const installer = path.join(root, 'skills', 'personal-writing-style', 'scripts', 'install-guidance.py');

function writeJsonl(file, rows) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${rows.map((row) => JSON.stringify(row)).join('\n')}\n`);
}

function sqlite(db, statements) {
  const result = spawnSync('sqlite3', [db], { input: statements, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
}

test('writing-corpus extracts only authored text from supported sources', (t) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'writing-corpus-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));

  const claude = path.join(dir, 'claude');
  writeJsonl(path.join(claude, 'project', 'session.jsonl'), [
    { type: 'user', timestamp: '2026-01-01T01:00:00Z', userType: 'external', isSidechain: false, message: { role: 'user', content: 'Claude words from me.' } },
    { type: 'user', timestamp: '2026-01-01T01:00:30Z', userType: 'external', isSidechain: false, message: { role: 'user', content: [{ type: 'text', text: 'Claude image prompt from me.' }, { type: 'image', source: {} }] } },
    { type: 'user', timestamp: '2026-01-01T01:01:00Z', userType: 'external', isSidechain: false, sourceToolAssistantUUID: 'tool', message: { role: 'user', content: [{ type: 'tool_result', content: 'secret tool output' }] } },
    { type: 'assistant', timestamp: '2026-01-01T01:02:00Z', message: { role: 'assistant', content: 'assistant prose' } },
  ]);
  writeJsonl(path.join(claude, 'project', 'subagents', 'agent.jsonl'), [
    { type: 'user', timestamp: '2026-01-01T01:03:00Z', userType: 'external', message: { role: 'user', content: 'delegated prompt' } },
  ]);

  const codex = path.join(dir, 'codex');
  writeJsonl(path.join(codex, '2026', '01', '01', 'rollout.jsonl'), [
    { type: 'response_item', timestamp: '2026-01-02T01:00:00Z', payload: { type: 'message', role: 'user', content: [
      { type: 'input_text', text: '# AGENTS.md instructions\n<INSTRUCTIONS>generated context</INSTRUCTIONS>' },
      { type: 'input_text', text: 'Codex words from me.\n<environment_context>generated context</environment_context>' },
    ] } },
    { type: 'response_item', timestamp: '2026-01-02T01:01:00Z', payload: { type: 'message', role: 'assistant', content: [{ type: 'output_text', text: 'assistant prose' }] } },
  ]);

  const messages = path.join(dir, 'chat.db');
  sqlite(messages, `
    create table message (date integer, text text, attributedBody blob, is_from_me integer, item_type integer, associated_message_type integer);
    insert into message values (788918400000000000, 'iMessage words from me.', null, 1, 0, 0);
    insert into message values (788918401000000000, 'received prose', null, 0, 0, 0);
    insert into message values (788918402000000000, null, x'00', 1, 0, 0);
  `);

  const mail = path.join(dir, 'mail.sqlite');
  sqlite(mail, `
    create table ZMESSAGE (Z_PK integer primary key, ZISSENT integer, ZDATESENT real);
    create table ZMESSAGECONTENT (ZMESSAGE integer, ZBODYTEXT text);
    insert into ZMESSAGE values (1, 1, 788918400);
    insert into ZMESSAGECONTENT values (1, 'Email words from me.\n\nOn Jan 1, Someone wrote:\nquoted prose');
    insert into ZMESSAGE values (2, 0, 788918401);
    insert into ZMESSAGECONTENT values (2, 'received email');
    insert into ZMESSAGE values (3, 1, 788918402);
    insert into ZMESSAGECONTENT values (3, null);
    alter table ZMESSAGECONTENT add column ZBODYHTML text;
    update ZMESSAGECONTENT set ZBODYHTML='<p>Email HTML from me.</p><blockquote>quoted prose</blockquote>' where ZMESSAGE=3;
  `);

  const slack = path.join(dir, 'slack');
  writeJsonl(path.join(slack, 'general', '2026-01-01.json'), []);
  fs.writeFileSync(path.join(slack, 'general', 'messages.json'), JSON.stringify([
    { type: 'message', user: 'U-ME', ts: '1767225600.000000', text: 'Slack words from me.' },
    { type: 'message', user: 'U-OTHER', ts: '1767225601.000000', text: 'coworker prose' },
  ]));

  const output = path.join(dir, 'corpus.jsonl.gz');
  const binary = path.join(dir, 'writing-corpus');
  let result = spawnSync('go', ['build', '-o', binary, source], { cwd: root, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  result = spawnSync(binary, [
    '--output', output,
    '--max-per-source', '0',
    '--min-chars', '1',
    '--claude-dir', claude,
    '--codex-dir', codex,
    '--imessage-db', messages,
    '--mimestream-db', mail,
    '--slack-export', slack,
    '--slack-user-id', 'U-ME',
  ], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);

  const compressed = fs.readFileSync(output);
  assert.deepEqual([...compressed.subarray(0, 2)], [0x1f, 0x8b]);
  const rows = zlib.gunzipSync(compressed).toString('utf8').trim().split('\n').map(JSON.parse);
  assert.deepEqual(rows.map(({ source, text }) => [source, text]), [
    ['claude', 'Claude words from me.'],
    ['claude', 'Claude image prompt from me.'],
    ['codex', 'Codex words from me.'],
    ['imessage', 'iMessage words from me.'],
    ['mimestream', 'Email words from me.'],
    ['mimestream', 'Email HTML from me.'],
    ['slack', 'Slack words from me.'],
  ]);
  assert.ok(rows.every((row) => Object.keys(row).sort().join(',') === 'id,source,text,timestamp,word_count'));
  assert.deepEqual(rows.map((row) => row.word_count), [4, 5, 4, 4, 4, 4, 4]);
  assert.equal(fs.statSync(output).mode & 0o777, 0o600);
  const stats = JSON.parse(result.stderr);
  assert.equal(stats.imessage.skipped_attributed_body, 1);
  assert.equal(stats.claude.emitted, 2);
});

test('profile guidance installer safely manages both global host files', (t) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'writing-guidance-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const agents = path.join(dir, '.agents', 'AGENTS.md');
  const claude = path.join(dir, '.claude', 'CLAUDE.md');
  fs.mkdirSync(path.dirname(agents), { recursive: true });
  fs.mkdirSync(path.dirname(claude), { recursive: true });
  fs.writeFileSync(agents, '# Existing agents guidance\n');
  fs.writeFileSync(claude, '# Existing Claude guidance\n');
  const profile = path.join(dir, 'profiles', 'style-profile.md');
  fs.mkdirSync(path.dirname(profile), { recursive: true });
  fs.writeFileSync(profile, '# Profile\n');
  const env = { ...process.env, HOME: dir };
  const args = ['--all-global', '--profile', profile];

  let result = spawnSync('python3', [installer, ...args], { encoding: 'utf8', env });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Dry-run only/);
  assert.equal(fs.readFileSync(agents, 'utf8'), '# Existing agents guidance\n');
  assert.equal(fs.readFileSync(claude, 'utf8'), '# Existing Claude guidance\n');

  result = spawnSync('python3', [installer, ...args, '--apply'], { encoding: 'utf8', env });
  assert.equal(result.status, 0, result.stderr);
  for (const target of [agents, claude]) {
    const installed = fs.readFileSync(target, 'utf8');
    assert.match(installed, /^# Existing/);
    assert.equal((installed.match(/BEGIN personal-writing-style:profile/g) || []).length, 1);
    assert.equal((installed.match(/## Personal writing style/g) || []).length, 1);
    assert.match(installed, new RegExp(profile.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    assert.match(installed, /Use `personal-writing-style` and read the profile/);
    assert.match(installed, /Do not read the raw corpus unless/);
    assert.equal(fs.readFileSync(`${target}.bak`, 'utf8'), target === agents ? '# Existing agents guidance\n' : '# Existing Claude guidance\n');
  }

  const afterFirstApply = [fs.readFileSync(agents), fs.readFileSync(claude)];
  result = spawnSync('python3', [installer, ...args, '--apply'], { encoding: 'utf8', env });
  assert.equal(result.status, 0, result.stderr);
  assert.equal((result.stdout.match(/up to date:/g) || []).length, 2);
  assert.deepEqual([fs.readFileSync(agents), fs.readFileSync(claude)], afterFirstApply);

  const replacement = path.join(dir, 'profiles', 'replacement.md');
  result = spawnSync('python3', [installer, '--all-global', '--profile', replacement, '--apply'], { encoding: 'utf8', env });
  assert.equal(result.status, 0, result.stderr);
  for (const target of [agents, claude]) {
    const installed = fs.readFileSync(target, 'utf8');
    assert.match(installed, new RegExp(replacement.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    assert.doesNotMatch(installed, new RegExp(profile.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    assert.equal((installed.match(/BEGIN personal-writing-style:profile/g) || []).length, 1);
  }
});

test('all-global avoids duplicating guidance when Claude imports AGENTS.md', (t) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'writing-guidance-import-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const agents = path.join(dir, '.agents', 'AGENTS.md');
  const claude = path.join(dir, '.claude', 'CLAUDE.md');
  fs.mkdirSync(path.dirname(agents), { recursive: true });
  fs.mkdirSync(path.dirname(claude), { recursive: true });
  fs.writeFileSync(agents, '# Shared guidance\n');
  fs.writeFileSync(claude, `# Claude\n@${agents}\n`);

  const result = spawnSync('python3', [installer, '--all-global', '--apply'], {
    encoding: 'utf8',
    env: { ...process.env, HOME: dir },
  });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /inherits profile guidance/);
  assert.match(fs.readFileSync(agents, 'utf8'), /BEGIN personal-writing-style:profile/);
  assert.equal(fs.readFileSync(claude, 'utf8'), `# Claude\n@${agents}\n`);
  assert.equal(fs.existsSync(`${claude}.bak`), false);
});
