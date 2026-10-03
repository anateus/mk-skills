const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const helper = path.join(__dirname, '../../skills/reviewing-code/scripts/prepare-pr-review');
function run(cwd, executable, args, env = process.env) {
  return spawnSync(executable, args, { cwd, env, encoding: 'utf8', timeout: 30000 });
}
function git(cwd, ...args) {
  const result = run(cwd, 'git', args);
  assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim();
}
function fixture(t) {
  const temp = process.env.JCODE_SCRATCH_DIR || os.tmpdir();
  const root = fs.mkdtempSync(path.join(temp, 'prepare-pr-test-'));
  const out = path.join(root, 'output');
  const repo = path.join(root, 'repo');
  fs.mkdirSync(repo);
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  git(repo, 'init', '-b', 'main');
  git(repo, 'config', 'user.name', 'Test');
  git(repo, 'config', 'user.email', 'test@example.test');
  git(repo, 'remote', 'add', 'origin', 'https://github.com/owner/repo.git');
  const commit = (message) => {
    git(repo, 'add', '-A');
    git(repo, 'commit', '-m', message);
    return git(repo, 'rev-parse', 'HEAD');
  };
  fs.writeFileSync(path.join(repo, 'delete.txt'), 'delete me\n');
  fs.writeFileSync(path.join(repo, 'rename-old.txt'), 'same\n');
  fs.writeFileSync(path.join(repo, 'large.txt'), 'line\n'.repeat(301));
  fs.writeFileSync(path.join(repo, ':(glob)*'), 'literal path before\n');
  fs.writeFileSync(path.join(repo, 'binary.bin'), Buffer.from([0, 1, 2]));
  fs.writeFileSync(path.join(repo, '.env.secret'), 'FAKE_SECRET_VALUE_NOT_FOR_OUTPUT');
  fs.writeFileSync(path.join(repo, 'package.json'), JSON.stringify({ scripts: { test: 'node --test' } }));
  const base = commit('base');
  git(repo, 'checkout', '-b', 'feature');
  fs.rmSync(path.join(repo, 'delete.txt'));
  fs.renameSync(path.join(repo, 'rename-old.txt'), path.join(repo, 'rename-new.txt'));
  fs.writeFileSync(path.join(repo, 'large.txt'), 'line\n'.repeat(302));
  fs.writeFileSync(path.join(repo, ':(glob)*'), 'literal path after\n');
  fs.writeFileSync(path.join(repo, 'binary.bin'), Buffer.from([0, 2, 0]));
  fs.writeFileSync(path.join(repo, '.env.secret'), 'NEW_FAKE_SECRET_VALUE_NOT_FOR_OUTPUT');
  commit('feature');
  const nested = path.join(root, 'nested');
  fs.mkdirSync(nested);
  git(nested, 'init', '-b', 'main');
  git(nested, 'config', 'user.name', 'Test');
  git(nested, 'config', 'user.email', 'test@example.test');
  fs.writeFileSync(path.join(nested, 'nested.txt'), 'nested');
  git(nested, 'add', '.');
  git(nested, 'commit', '-m', 'nested');
  git(repo, 'update-index', '--add', '--cacheinfo', `160000,${git(nested, 'rev-parse', 'HEAD')},submodule`);
  git(repo, 'commit', '-m', 'submodule entry');
  const head = git(repo, 'rev-parse', 'HEAD');
  git(repo, 'checkout', 'main');
  fs.writeFileSync(path.join(root, 'AGENTS.md'), 'Original workspace review guidance.\n');
  const requirements = path.join(root, 'requirements');
  fs.mkdirSync(requirements);
  fs.writeFileSync(path.join(requirements, 'DOM-7862.md'), 'Synthetic exported requirements.\n');
  const pr = { number: 7, title: 'DOM-7862 prep', body: 'DOM-7862', html_url: 'https://github.com/owner/repo/pull/7', base: { sha: base, repo: { full_name: 'owner/repo' } }, head: { sha: head } };
  const data = {
    'repos/owner/repo/pulls/7': pr,
    'repos/owner/repo/issues/7/comments?per_page=100&page=1': Array.from({ length: 100 }, (_, id) => ({ id })),
    'repos/owner/repo/issues/7/comments?per_page=100&page=2': [{ id: 100 }],
    'repos/owner/repo/pulls/7/reviews?per_page=100&page=1': [],
    'repos/owner/repo/pulls/7/comments?per_page=100&page=1': [],
    threads: { data: { repository: { pullRequest: { reviewThreads: { pageInfo: { hasNextPage: false, endCursor: null }, nodes: [{ id: 'T1', isResolved: true, isOutdated: false, path: 'large.txt', comments: { pageInfo: { hasNextPage: true, endCursor: 'inner-cursor' }, nodes: [{ id: 'C1', body: 'first comment' }] } }] } } } } },
    inner: { data: { node: { comments: { pageInfo: { hasNextPage: false, endCursor: null }, nodes: [{ id: 'C2', body: 'second comment' }] } } } },
  };
  const dataPath = path.join(root, 'github.json');
  fs.writeFileSync(dataPath, JSON.stringify(data));
  fs.writeFileSync(path.join(root, 'gh'), `#!${process.execPath}
const fs = require('fs');
const args = process.argv.slice(2);
const data = JSON.parse(fs.readFileSync(process.env.GH_FIXTURE));
let result;
if (args[0] === 'api' && args[1] === 'graphql') {
  const query = args.find(x => x.startsWith('query=')) || '';
  if (args.includes('commentCursor=inner-cursor')) {
    if (!query.includes('node(id:$threadId)') || !query.includes('comments(first:100,after:$commentCursor)') || !args.includes('threadId=T1')) process.exit(93);
    result = data.inner;
  } else {
    if (!query.includes('reviewThreads(first:100,after:$cursor)')) process.exit(94);
    result = args.includes('cursor=outer-cursor') ? data.next_threads : data.threads;
  }
} else {
  const endpoint = args.find(x => x.startsWith('repos/')) || '';
  if (!(endpoint in data)) process.exit(95);
  result = data[endpoint];
}
if (result && result.fixture_error) { console.error(result.fixture_error); process.exit(2); }
process.stdout.write(JSON.stringify(result));
`, { mode: 0o755 });
  const env = { ...process.env, PATH: `${root}:${process.env.PATH}`, GH_FIXTURE: dataPath };
  const url = pr.html_url;
  const args = [url, '--repos-root', root, '--output', out, '--requirements-dir', requirements];
  return { root, repo, out, head, base, requirements, data, dataPath, env, url, args, capture: path.join(out, 'owner-repo-pr-7') };
}

function readJson(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }

test('captures all Git paths, paginates comments, and replays unchanged context without network tools', (t) => {
  const f = fixture(t);
  const first = run(f.root, helper, f.args, f.env);
  assert.equal(first.status, 0, first.stderr);
  const manifest = readJson(path.join(f.capture, 'coverage-manifest.json'));
  assert.equal(manifest.files.length, 7);
  assert.ok(manifest.files.some(x => x.change === 'D'));
  assert.ok(manifest.files.some(x => x.change.startsWith('R')));
  assert.ok(manifest.files.some(x => x.new_mode === '160000'));
  assert.ok(manifest.files.every(x => x.coverage === 'unreviewed'));
  assert.equal(readJson(path.join(f.capture, 'raw/issue-comments.json')).length, 101);
  const thread = readJson(path.join(f.capture, 'raw/review-threads.json'))[0];
  assert.equal(thread.isResolved, true);
  assert.deepEqual(thread.comments.nodes.map(x => x.id), ['C1', 'C2']);
  const files = fs.readdirSync(path.join(f.capture, 'files'));
  const chunks = files.filter(x => /large\.txt\.(before|after)\.\d{4}\.txt$/.test(x));
  assert.ok(chunks.length >= 4);
  for (const file of chunks) assert.ok(fs.readFileSync(path.join(f.capture, 'files', file), 'utf8').split('\n').filter(x => /^\d+:/.test(x)).length <= 150);
  for (const file of files.filter(x => x.endsWith('.diff'))) assert.doesNotMatch(fs.readFileSync(path.join(f.capture, 'files', file), 'utf8'), /FAKE_SECRET_VALUE/);
  const magic = files.find(x => x.includes('_glob_') && x.endsWith('.diff'));
  assert.ok(magic, 'literal magic-named file has its own diff');
  const magicDiff = fs.readFileSync(path.join(f.capture, 'files', magic), 'utf8');
  assert.match(magicDiff, /literal path after/);
  assert.doesNotMatch(magicDiff, /large\.txt|FAKE_SECRET_VALUE/);
  assert.doesNotMatch(fs.readFileSync(path.join(f.capture, 'diff-package.txt'), 'utf8'), /FAKE_SECRET_VALUE/);
  assert.match(fs.readFileSync(path.join(f.capture, 'test-commands.txt'), 'utf8'), /node --test/);
  const hashes = fs.readFileSync(path.join(f.capture, 'capture-hashes.json'));
  const tickets = fs.readFileSync(path.join(f.capture, 'tickets.json'));
  const guidance = fs.readdirSync(path.join(f.capture, 'guidance'));
  fs.writeFileSync(path.join(f.root, 'AGENTS.md'), 'Changed after capture.\n');
  fs.writeFileSync(path.join(f.repo, 'AGENTS.md'), 'NEW_GUIDANCE_AFTER_CAPTURE');
  fs.rmSync(f.requirements, { recursive: true });
  fs.rmSync(path.join(f.root, 'gh'));
  for (let i = 0; i < 2; i++) {
    const replay = run(f.root, helper, [f.url, '--repos-root', f.root, '--output', f.out, '--reuse'], { ...f.env, PATH: '/usr/bin:/bin' });
    assert.equal(replay.status, 0, replay.stderr);
  }
  const replays = fs.readdirSync(f.out).filter(x => x.startsWith('owner-repo-pr-7-reuse'));
  assert.equal(replays.length, 2);
  for (const replay of replays) {
    assert.deepEqual(fs.readFileSync(path.join(f.out, replay, 'tickets.json')), tickets);
    for (const file of guidance) assert.deepEqual(fs.readFileSync(path.join(f.out, replay, 'guidance', file)), fs.readFileSync(path.join(f.capture, 'guidance', file)));
    assert.deepEqual(fs.readdirSync(path.join(f.out, replay, 'guidance')).sort(), [...guidance].sort());
  }
  assert.deepEqual(fs.readFileSync(path.join(f.capture, 'capture-hashes.json')), hashes);
  const collision = run(f.root, helper, [f.url, '--repos-root', f.root, '--output', f.out], f.env);
  assert.notEqual(collision.status, 0);
  assert.deepEqual(fs.readFileSync(path.join(f.capture, 'capture-hashes.json')), hashes);
});

test('OCR captures real-shaped rules/version and replay preserves them without invoking OCR', (t) => {
  const f = fixture(t);
  const calls = path.join(f.root, 'ocr-calls');
  fs.writeFileSync(path.join(f.root, 'ocr'), `#!/bin/sh
printf '%s\\n' "$*" >> "$OCR_CALLS"
case "$1 $2" in
  'version '|'--version ') printf '%s\\n' 'open-code-review 1.12.11 test' ;;
  'delegate preview') printf '%s\\n' '{"schema_version":"1","reviewable_files":[{"path":"large.txt","status":"modified","insertions":1,"deletions":0,"background":"DROP"}],"excluded_files":[]}' ;;
  'delegate rule') printf '%s\\n' '{"schema_version":"1","groups":[{"rule":"Rule text","files":["large.txt"]}]}' ;;
  *) exit 91 ;;
esac
`, { mode: 0o755 });
  const result = run(f.root, helper, [...f.args, '--ocr'], { ...f.env, OCR_CALLS: calls });
  assert.equal(result.status, 0, result.stderr);
  assert.doesNotMatch(fs.readFileSync(path.join(f.capture, 'ocr-preview.json'), 'utf8'), /DROP/);
  assert.match(fs.readFileSync(path.join(f.capture, 'ocr-rules.json'), 'utf8'), /Rule text/);
  assert.match(readJson(path.join(f.capture, 'pr.json')).ocr.version, /1\.12\.11/);
  assert.doesNotMatch(fs.readFileSync(calls, 'utf8'), /(^|\n)(review|scan|llm|delegate review)\b/);
  fs.rmSync(path.join(f.root, 'ocr'));
  fs.rmSync(path.join(f.root, 'gh'));
  const replay = run(f.root, helper, [f.url, '--repos-root', f.root, '--output', f.out, '--reuse', '--ocr'], { ...f.env, PATH: '/usr/bin:/bin' });
  assert.equal(replay.status, 0, replay.stderr);
  const replayDir = path.join(f.out, fs.readdirSync(f.out).find(x => x.startsWith('owner-repo-pr-7-reuse')));
  assert.deepEqual(readJson(path.join(replayDir, 'pr.json')).ocr, readJson(path.join(f.capture, 'pr.json')).ocr);
  assert.deepEqual(fs.readFileSync(path.join(replayDir, 'ocr-rules.json')), fs.readFileSync(path.join(f.capture, 'ocr-rules.json')));
});

test('rejects mismatched origins before any capture', (t) => {
  const f = fixture(t);
  git(f.repo, 'remote', 'set-url', 'origin', 'https://FAKE_PRIVATE_TOKEN@unrelated.test/owner/repo.git');
  const result = run(f.root, helper, f.args, f.env);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /origin mismatch/);
  assert.doesNotMatch(result.stderr, /FAKE_PRIVATE_TOKEN/);
  assert.equal(fs.existsSync(f.capture), false);
});

test('records partial API failure and never relays command error bodies', (t) => {
  const f = fixture(t);
  f.data['repos/owner/repo/pulls/7/reviews?per_page=100&page=1'] = { fixture_error: 'FAKE_PRIVATE_ERROR_SECRET' };
  fs.writeFileSync(f.dataPath, JSON.stringify(f.data));
  const result = run(f.root, helper, f.args, f.env);
  assert.notEqual(result.status, 0);
  assert.equal(readJson(path.join(f.capture, 'capture-failure.json')).incomplete, true);
  assert.doesNotMatch(result.stderr, /FAKE_PRIVATE_ERROR_SECRET/);
  assert.doesNotMatch(fs.readFileSync(path.join(f.capture, 'capture-failure.json'), 'utf8'), /FAKE_PRIVATE_ERROR_SECRET/);
});

test('rejects tampered raw captures before offline replay', (t) => {
  const f = fixture(t);
  assert.equal(run(f.root, helper, f.args, f.env).status, 0);
  fs.appendFileSync(path.join(f.capture, 'raw/issue-comments.json'), ' ');
  const originalEntries = fs.readdirSync(f.capture).sort();
  const result = run(f.root, helper, [f.url, '--repos-root', f.root, '--output', f.out, '--reuse'], { ...f.env, PATH: '/usr/bin:/bin' });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /hash mismatch/);
  assert.equal(fs.readdirSync(f.out).some(x => x.startsWith('owner-repo-pr-7-reuse')), false);
  assert.deepEqual(fs.readdirSync(f.capture).sort(), originalEntries);
});

test('paginates outer review threads and preserves both thread identities', (t) => {
  const f = fixture(t);
  f.data.threads.data.repository.pullRequest.reviewThreads.pageInfo = { hasNextPage: true, endCursor: 'outer-cursor' };
  f.data.next_threads = { data: { repository: { pullRequest: { reviewThreads: {
    pageInfo: { hasNextPage: false, endCursor: null },
    nodes: [{ id: 'T2', isResolved: false, isOutdated: true, path: 'large.txt', comments: { pageInfo: { hasNextPage: false, endCursor: null }, nodes: [] } }],
  } } } } };
  fs.writeFileSync(f.dataPath, JSON.stringify(f.data));
  const result = run(f.root, helper, f.args, f.env);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(readJson(path.join(f.capture, 'raw/review-threads.json')).map(x => x.id), ['T1', 'T2']);
});

test('rejects a missing outer pagination cursor instead of re-reading the first page', (t) => {
  const f = fixture(t);
  f.data.threads.data.repository.pullRequest.reviewThreads.pageInfo = { hasNextPage: true, endCursor: null };
  fs.writeFileSync(f.dataPath, JSON.stringify(f.data));
  const result = run(f.root, helper, f.args, f.env);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /outer thread pagination cursor/);
});

test('replay rejects unlisted raw files without modifying the original capture', (t) => {
  const f = fixture(t);
  assert.equal(run(f.root, helper, f.args, f.env).status, 0);
  fs.writeFileSync(path.join(f.capture, 'raw/extra.json'), '{"unexpected":"not captured"}');
  const entries = fs.readdirSync(f.capture).sort();
  const result = run(f.root, helper, [f.url, '--repos-root', f.root, '--output', f.out, '--reuse'], f.env);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /inventory mismatch/);
  assert.deepEqual(fs.readdirSync(f.capture).sort(), entries);
});

test('replay rejects hash paths escaping the capture before reading them', (t) => {
  const f = fixture(t);
  assert.equal(run(f.root, helper, f.args, f.env).status, 0);
  const outside = path.join(f.out, 'outside.txt');
  fs.writeFileSync(outside, 'synthetic outside file');
  const hashes = readJson(path.join(f.capture, 'capture-hashes.json'));
  hashes['../outside.txt'] = require('node:crypto').createHash('sha256').update('synthetic outside file').digest('hex');
  fs.writeFileSync(path.join(f.capture, 'capture-hashes.json'), JSON.stringify(hashes));
  const result = run(f.root, helper, [f.url, '--repos-root', f.root, '--output', f.out, '--reuse'], f.env);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /unsafe cached artifact path/);
});

test('materializes a valid Git byte pathname with an escaped readable label', (t) => {
  const f = fixture(t);
  git(f.repo, 'checkout', 'feature');
  const blob = spawnSync('git', ['hash-object', '-w', '--stdin'], { cwd: f.repo, input: 'synthetic byte-path content\n', encoding: 'utf8' });
  assert.equal(blob.status, 0, blob.stderr);
  const indexInput = Buffer.concat([Buffer.from(`100644 ${blob.stdout.trim()}\tbyte-`), Buffer.from([0xff]), Buffer.from('.txt\0')]);
  const indexed = spawnSync('git', ['update-index', '-z', '--index-info'], { cwd: f.repo, input: indexInput });
  assert.equal(indexed.status, 0, indexed.stderr?.toString());
  git(f.repo, 'commit', '-m', 'byte pathname');
  f.data['repos/owner/repo/pulls/7'].head.sha = git(f.repo, 'rev-parse', 'HEAD');
  fs.writeFileSync(f.dataPath, JSON.stringify(f.data));
  const result = run(f.root, helper, f.args, f.env);
  assert.equal(result.status, 0, result.stderr);
  const manifest = readJson(path.join(f.capture, 'coverage-manifest.json'));
  assert.ok(manifest.files.some(x => (x.new_path || '').includes('\udcff')));
  assert.match(fs.readFileSync(path.join(f.capture, 'README.md'), 'utf8'), /byte-/);
});
