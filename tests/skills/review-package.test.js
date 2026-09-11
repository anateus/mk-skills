const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const script = path.join(__dirname, '..', '..', 'skills', 'reviewing-code', 'scripts', 'review-package');
function git(cwd, ...args) { const r = spawnSync('git', args, { cwd, encoding: 'utf8' }); assert.equal(r.status, 0, r.stderr); return r.stdout.trim(); }

test('review package covers an explicit multi-commit range without changing the repo', (t) => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'review-package-repo-')); t.after(() => fs.rmSync(repo, { recursive: true, force: true }));
  git(repo, 'init', '-b', 'main'); git(repo, 'config', 'user.name', 'Test'); git(repo, 'config', 'user.email', 'test@example.test');
  fs.writeFileSync(path.join(repo, 'one.txt'), Array.from({ length: 30 }, (_, i) => `line ${i}\n`).join(''));
  git(repo, 'add', '.'); git(repo, 'commit', '-m', 'base'); const base = git(repo, 'rev-parse', 'HEAD');
  fs.appendFileSync(path.join(repo, 'one.txt'), 'first change\n'); git(repo, 'add', '.'); git(repo, 'commit', '-m', 'first subject');
  fs.writeFileSync(path.join(repo, 'two.txt'), 'second change\n'); git(repo, 'add', '.'); git(repo, 'commit', '-m', 'second subject'); const head = git(repo, 'rev-parse', 'HEAD');
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'review-package-output-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const options = { cwd: repo, encoding: 'utf8', env: { ...process.env, TMPDIR: temp } };
  const result = spawnSync(script, [base, head], options); assert.equal(result.status, 0, result.stderr || result.error?.message);
  const packagePath = result.stdout.trim(); t.after(() => fs.rmSync(packagePath, { force: true }));
  assert.equal(result.stdout, `${packagePath}\n`); assert.equal(path.dirname(packagePath) === repo, false);
  const source = fs.readFileSync(packagePath, 'utf8');
  const repeated = spawnSync(script, [base, head], options);
  assert.equal(repeated.status, 0, repeated.stderr);
  assert.notEqual(repeated.stdout.trim(), packagePath, 'each invocation gets its own artifact');
  assert.equal(fs.readFileSync(repeated.stdout.trim(), 'utf8'), source);
  for (const value of [base, head, 'first subject', 'second subject', 'one.txt', 'two.txt', 'Diff stat', 'line 20']) assert.match(source, new RegExp(value));
  assert.equal(git(repo, 'status', '--porcelain'), '');
});

test('invalid and non-ancestor revisions fail without a package path', (t) => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'review-package-invalid-')); t.after(() => fs.rmSync(repo, { recursive: true, force: true }));
  git(repo, 'init', '-b', 'main'); git(repo, 'config', 'user.name', 'Test'); git(repo, 'config', 'user.email', 'test@example.test');
  fs.writeFileSync(path.join(repo, 'a'), 'a'); git(repo, 'add', '.'); git(repo, 'commit', '-m', 'a'); const first = git(repo, 'rev-parse', 'HEAD');
  fs.writeFileSync(path.join(repo, 'a'), 'b'); git(repo, 'commit', '-am', 'b'); const second = git(repo, 'rev-parse', 'HEAD');
  for (const args of [['missing', second], [second, first]]) { const r = spawnSync(script, args, { cwd: repo, encoding: 'utf8' }); assert.notEqual(r.status, 0); assert.equal(r.stdout || '', ''); }
});

const checker = path.join(path.dirname(script), 'review-coverage');

function fixture(t) {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'review-coverage-'));
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'review-coverage-output-'));
  t.after(() => { fs.rmSync(repo, { recursive: true, force: true }); fs.rmSync(temp, { recursive: true, force: true }); });
  git(repo, 'init', '-b', 'main'); git(repo, 'config', 'user.name', 'Test'); git(repo, 'config', 'user.email', 'test@example.test');
  const write = (name, content) => fs.writeFileSync(path.join(repo, name), content);
  const commit = (message) => { git(repo, 'add', '.'); git(repo, 'commit', '-m', message); return git(repo, 'rev-parse', 'HEAD'); };
  const options = { cwd: repo, encoding: 'utf8', env: { ...process.env, TMPDIR: temp } };
  return { repo, temp, write, commit, options };
}

function packageFor(f, base, head, ...extra) {
  const result = spawnSync(script, [base, head, ...extra], f.options);
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  const packagePath = result.stdout.trim();
  const manifestPath = `${packagePath}.manifest.json`;
  assert.ok(fs.existsSync(manifestPath), 'package must include a JSON coverage manifest');
  return { packagePath, manifestPath, manifest: JSON.parse(fs.readFileSync(manifestPath, 'utf8')) };
}

test('inventory includes deletions, renames, NUL content, modes and unusual paths from any subdirectory', (t) => {
  const f = fixture(t);
  f.write('deleted.txt', 'deleted content\n'); f.write('old name.txt', 'rename this content\n');
  f.write('nul.ts', 'export const marker = "\0old";\n'); f.write('executable.sh', '#!/bin/sh\nexit 0\n');
  const base = f.commit('base');
  fs.rmSync(path.join(f.repo, 'deleted.txt')); fs.renameSync(path.join(f.repo, 'old name.txt'), path.join(f.repo, 'new\nname.txt'));
  f.write('nul.ts', 'export const marker = "\0new";\n'); f.write('added\tfile.md', '# Added\n');
  fs.chmodSync(path.join(f.repo, 'executable.sh'), 0o755);
  const head = f.commit('changes');
  fs.mkdirSync(path.join(f.repo, 'subdir')); f.options.cwd = path.join(f.repo, 'subdir');
  const { manifest: m } = packageFor(f, base, head);
  assert.equal(m.base, base); assert.equal(m.head, head); assert.equal(m.base_tip, null);
  assert.equal(m.repository, fs.realpathSync(f.repo));
  assert.equal(m.files.length, 5);
  const renamed = m.files.find((entry) => entry.old_path === 'old name.txt');
  assert.equal(renamed.new_path, 'new\nname.txt'); assert.match(renamed.change, /^R/);
  assert.equal(renamed.old_oid, git(f.repo, 'rev-parse', `${base}:old name.txt`));
  assert.equal(renamed.old_oid, renamed.new_oid);
  const deleted = m.files.find((entry) => entry.old_path === 'deleted.txt');
  assert.equal(deleted.change, 'D'); assert.equal(deleted.new_path, null); assert.equal(deleted.new_oid, null);
  const added = m.files.find((entry) => entry.new_path === 'added\tfile.md');
  assert.equal(added.change, 'A'); assert.equal(added.old_path, null); assert.equal(added.old_oid, null);
  const nul = m.files.find((entry) => entry.new_path === 'nul.ts');
  assert.equal(nul.new_oid, git(f.repo, 'rev-parse', `${head}:nul.ts`)); assert.notEqual(nul.old_oid, nul.new_oid);
  const mode = m.files.find((entry) => entry.new_path === 'executable.sh');
  assert.equal(mode.old_mode, '100644'); assert.equal(mode.new_mode, '100755'); assert.equal(mode.old_oid, mode.new_oid);
  assert.ok(m.files.every((entry) => entry.coverage === 'unreviewed'));
  assert.equal(git(f.repo, 'status', '--porcelain'), '');
});

test('checker distinguishes declared coverage gaps and review failures from completed inspection', (t) => {
  const f = fixture(t); f.write('a', 'base'); const base = f.commit('base');
  f.write('a', 'change'); const head = f.commit('change');
  const { manifestPath, manifest: m } = packageFor(f, base, head);
  function check(status, pattern) {
    fs.writeFileSync(manifestPath, JSON.stringify(m));
    const result = spawnSync(checker, [manifestPath, base, head], f.options);
    assert.equal(result.status, status, result.stderr || result.error?.message);
    assert.match(result.stdout + result.stderr, pattern);
  }
  check(1, /unreviewed/);
  m.files[0].coverage = 'partial'; m.files[0].reason = 'Only inspected happy path'; check(1, /partial/);
  m.files[0].coverage = 'skipped'; m.files[0].reason = ''; check(2, /reason/);
  m.files[0].reason = 'Generated output; generator reviewed separately'; check(1, /skipped/);
  m.files[0].coverage = 'reviewed'; m.files[0].reason = ''; check(0, /"reviewed": 1/);
  m.review_failures = ['risk pass truncated']; check(1, /risk pass truncated/);
  m.review_failures = []; m.files[0].coverage = 'complete'; check(2, /coverage/);
});

test('checker rejects missing, duplicate, forged and stale inventory even when outcomes say reviewed', (t) => {
  const f = fixture(t); f.write('a', 'base'); const base = f.commit('base');
  f.write('a', 'change'); const head = f.commit('change');
  const { manifestPath, manifest: m } = packageFor(f, base, head);
  m.files[0].coverage = 'reviewed';
  for (const mutate of [
    (copy) => { copy.files = []; },
    (copy) => { copy.files.push(copy.files[0]); },
    (copy) => { copy.files[0].new_oid = copy.files[0].old_oid; },
    (copy) => { copy.files[0].new_path = 'unrelated'; },
    (copy) => { copy.repository += '-other'; },
  ]) {
    const copy = structuredClone(m); mutate(copy); fs.writeFileSync(manifestPath, JSON.stringify(copy));
    const result = spawnSync(checker, [manifestPath, base, head], f.options);
    assert.equal(result.status, 2, result.stderr || result.error?.message);
  }
  fs.writeFileSync(manifestPath, JSON.stringify(m));
  git(f.repo, 'commit', '--allow-empty', '-m', 'new context with same blobs');
  const moved = git(f.repo, 'rev-parse', 'HEAD');
  assert.equal(spawnSync(checker, [manifestPath, base, moved], f.options).status, 2);
  assert.equal(spawnSync(checker, [manifestPath, head, head], f.options).status, 2);
});

test('PR base-tip movement invalidates coverage even when merge base and head remain unchanged', (t) => {
  const f = fixture(t); f.write('a', 'base'); const base = f.commit('base');
  git(f.repo, 'checkout', '-b', 'feature'); f.write('a', 'feature'); const head = f.commit('feature');
  git(f.repo, 'checkout', 'main'); f.write('unrelated', 'base branch change'); const tip = f.commit('base advanced');
  const { manifestPath, manifest: m } = packageFor(f, base, head, '--base-tip', tip);
  assert.equal(m.base_tip, tip); m.files.forEach((entry) => { entry.coverage = 'reviewed'; });
  fs.writeFileSync(manifestPath, JSON.stringify(m));
  assert.equal(spawnSync(checker, [manifestPath, base, head, '--base-tip', 'main'], f.options).status, 0);
  git(f.repo, 'commit', '--allow-empty', '-m', 'base context moved');
  assert.equal(spawnSync(checker, [manifestPath, base, head, '--base-tip', 'main'], f.options).status, 2);
  assert.equal(spawnSync(checker, [manifestPath, base, head], f.options).status, 2);
});

test('an empty comparison passes, malformed manifests and failed Git operations leave no success artifact', (t) => {
  const f = fixture(t); f.write('a', 'base'); const base = f.commit('base');
  const { manifestPath } = packageFor(f, base, base);
  assert.equal(spawnSync(checker, [manifestPath, base, base], f.options).status, 0);
  fs.writeFileSync(manifestPath, '{invalid');
  assert.equal(spawnSync(checker, [manifestPath, base, base], f.options).status, 2);
  const before = fs.readdirSync(f.temp);
  const result = spawnSync(script, [base, 'missing'], f.options);
  assert.notEqual(result.status, 0); assert.equal(result.stdout, '');
  assert.deepEqual(fs.readdirSync(f.temp), before);
});

test('package generation suppresses external diff helpers and removes artifacts if the patch fails', (t) => {
  const f = fixture(t); f.write('a', 'base'); const base = f.commit('base');
  f.write('a', 'change'); const head = f.commit('change');
  const helper = path.join(f.temp, 'external-diff');
  fs.writeFileSync(helper, '#!/bin/sh\necho "external helper must not run" >&2\nexit 91\n', { mode: 0o755 });
  git(f.repo, 'config', 'diff.external', helper);
  const { packagePath } = packageFor(f, base, head);
  assert.match(fs.readFileSync(packagePath, 'utf8'), /\+change/);

  const realGit = spawnSync('which', ['git'], { encoding: 'utf8' }).stdout.trim();
  const bin = path.join(f.temp, 'bin'); fs.mkdirSync(bin);
  fs.writeFileSync(path.join(bin, 'git'), `#!/usr/bin/env python3\nimport os, sys\nif '--unified=10' in sys.argv:\n    print('synthetic patch failure', file=sys.stderr)\n    sys.exit(92)\nos.execv(${JSON.stringify(realGit)}, ['git', *sys.argv[1:]])\n`, { mode: 0o755 });
  const before = fs.readdirSync(f.temp);
  const result = spawnSync(script, [base, head], { ...f.options, env: { ...f.options.env, PATH: `${bin}:${process.env.PATH}` } });
  assert.equal(result.status, 2); assert.equal(result.stdout, ''); assert.match(result.stderr, /synthetic patch failure/);
  assert.deepEqual(fs.readdirSync(f.temp), before, 'a failed patch must not leave a partial review package');
});
