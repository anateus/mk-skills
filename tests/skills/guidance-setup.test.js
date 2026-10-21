const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const setup = path.join(root, 'skills/mk-skills-setup');
const helper = path.join(setup, 'scripts/merge-guidance.py');
const guidance = fs.readFileSync(path.join(setup, 'assets/agents-guidance.md'), 'utf8').trim();
const begin = '<!-- BEGIN mk-skills:agent-guidance (managed block — edits between the markers are overwritten on re-run) -->';
const end = '<!-- END mk-skills:agent-guidance -->';

function run(target, ...flags) {
  const result = spawnSync('python3', [helper, '--target', target, ...flags], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return result.stdout;
}

function temporaryTarget(t) {
  const directory = fs.mkdtempSync(path.join(process.env.JCODE_SCRATCH_DIR || os.tmpdir(), 'guidance-test-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  return path.join(directory, 'AGENTS.md');
}

test('AgentPlan policy defaults to native plans and gates shared-board work', () => {
  const policy = guidance.match(/<important if="you are choosing how to track or coordinate work">([\s\S]*?)<\/important>/);
  assert.ok(policy, 'selection block exists');
  assert.match(policy[1], /Default to native todos\/plans/);
  assert.match(policy[1], /when requested, resuming an active AgentPlan assignment, or filling a concrete need current tools don't meet/);
  assert.match(policy[1], /Multiple steps, delegation, multiple harnesses, or an old board alone aren't reasons/);
  assert.match(policy[1], /--agent <harness-and-pane> --timeout <seconds>/);
  assert.match(policy[1], /Keep human actions human-owned/);
  assert.match(policy[1], /Preparing context doesn't authorize claiming or completing them/);
  assert.match(policy[1], /don't mirror backlogs or status updates/);
  assert.match(policy[1], /external tracker owns issues and team updates/);
});

test('peer storage and board-write preflight are conditional on choosing AgentPlan', () => {
  const peer = fs.readFileSync(path.join(root, 'skills/zellij-agent-herder/references/peer-agents.md'), 'utf8');
  const section = peer.split('### Codex peers that share AgentPlan\n')[1].split('\n## Workflows')[0];
  assert.match(section, /preflight below only when peers use AgentPlan/);
  assert.match(section, /Skip this section when native plans or another coordinator suffice/);
  assert.ok(section.indexOf('only when peers use AgentPlan') < section.indexOf('agentplan_roots='));
  assert.match(section, /agentplan note <project>/, 'real write preflight remains available after selection');
});

test('setup previews without writing, then replaces only its managed block and converges', (t) => {
  const target = temporaryTarget(t);
  const before = '# Local instructions\n\nKeep this prefix.\n\n';
  const after = '\n## Human questions and actions\n\nKeep this human-view policy.\n';
  const old = `${before}${begin}\nOld mandatory board policy.\n${end}\n${after}`;
  fs.writeFileSync(target, old);

  assert.match(run(target), /Dry-run only/);
  assert.equal(fs.readFileSync(target, 'utf8'), old);
  assert.equal(fs.existsSync(`${target}.bak`), false);

  run(target, '--apply');
  const expected = `${before}${begin}\n${guidance}\n${end}\n${after}`;
  assert.equal(fs.readFileSync(target, 'utf8'), expected);
  assert.equal(fs.readFileSync(`${target}.bak`, 'utf8'), old);
  assert.match(run(target, '--apply'), /up to date/);
  assert.equal(fs.readFileSync(target, 'utf8'), expected);
  assert.equal(fs.readFileSync(`${target}.bak`, 'utf8'), old);
});

test('setup appends selected guidance without changing existing local instructions', (t) => {
  const target = temporaryTarget(t);
  const local = '# Native work\n\nUse the current human view.\n';
  fs.writeFileSync(target, local);
  run(target, '--apply');
  assert.equal(fs.readFileSync(target, 'utf8'), `${local.trimEnd()}\n\n${begin}\n${guidance}\n${end}\n`);
});
