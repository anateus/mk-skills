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
  const result = spawnSync(script, [base, head], { cwd: repo, encoding: 'utf8' }); assert.equal(result.status, 0, result.stderr || result.error?.message);
  const packagePath = result.stdout.trim(); t.after(() => fs.rmSync(packagePath, { force: true }));
  assert.equal(result.stdout, `${packagePath}\n`); assert.equal(path.dirname(packagePath) === repo, false);
  const source = fs.readFileSync(packagePath, 'utf8');
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
