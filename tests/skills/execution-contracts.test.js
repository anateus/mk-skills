const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const readSkill = (name) => fs.readFileSync(
  path.join(__dirname, '..', '..', 'skills', name, 'SKILL.md'),
  'utf8',
);

const scenarios = {
  behaviorChange: 'Add retry behavior observable through the client API.',
  mechanicalRename: 'Rename an internal symbol without changing behavior.',
  generatedUpdate: 'Regenerate checked-in output from its source schema.',
  reproducibleBug: 'A focused command reliably reproduces the wrong response.',
  nonReproducibleBug: 'The reported failure cannot be reproduced in this environment.',
};

const prohibitedRequirements = [
  /(?:must|required to|always) commit/i,
  /(?:must|required to|always) (?:create|use) (?:a )?worktree/i,
  /(?:must|required to|always) (?:publish|create|update) (?:a )?(?:tracker|ticket|issue)/i,
  /(?:must|required to|always) (?:dispatch|use) (?:peers|peer agents|subagents)/i,
  /(?:must|required to|always) (?:open|create) (?:a )?(?:pull request|PR)/i,
];

test('TDD contract uses observable behavior and preserves proportional exceptions', () => {
  const skill = readSkill('test-driven-development');
  assert.ok(scenarios.behaviorChange);
  assert.match(skill, /public (?:behavior )?seam|behavior.*public seam/is);
  assert.match(skill, /independent expected values/i);
  assert.match(skill, /red evidence/i);
  assert.match(skill, /minimal green change/i);
  assert.match(skill, /narrow (?:vertical )?(?:red-green )?slice/i);
  assert.match(skill, /fresh verification/i);

  for (const scenario of ['mechanical rename', 'generated', 'configuration-only']) {
    assert.match(skill, new RegExp(scenario, 'i'));
  }
  assert.match(skill, /preserv(?:e|ing) public behavior/i);
  assert.ok(scenarios.mechanicalRename && scenarios.generatedUpdate);
});

test('debugging contract distinguishes reproducible and non-reproducible bugs', () => {
  const skill = readSkill('diagnosing-bugs');
  assert.ok(scenarios.reproducibleBug && scenarios.nonReproducibleBug);
  assert.match(skill, /tight (?:feedback )?loop/i);
  assert.match(skill, /reproduc/i);
  assert.match(skill, /minimi[sz](?:e|ed).*evidence/is);
  assert.match(skill, /competing hypotheses/i);
  assert.match(skill, /discriminating evidence/i);
  assert.match(skill, /cause-level fix|fix the cause/i);
  assert.match(skill, /regression protection/i);
  assert.match(skill, /document(?:ed)? limitation/i);
});

test('implementation contract is a risk-scaled router without lifecycle ownership', () => {
  const skill = readSkill('implementing-work');
  assert.match(skill, /request, specification, or plan/i);
  assert.match(skill, /applicable skills/i);
  assert.match(skill, /coherent slices/i);
  assert.match(skill, /verification.*risk|risk.*verification/is);
  assert.match(skill, /review.*risk|risk.*review/is);
  assert.match(skill, /does not own|outside.*ownership/is);
  for (const lifecycle of ['commits', 'pull requests', 'trackers', 'worktrees']) {
    assert.match(skill, new RegExp(lifecycle, 'i'));
  }
});

test('execution skills do not impose external workflow ceremony', () => {
  for (const name of ['test-driven-development', 'diagnosing-bugs', 'implementing-work']) {
    const skill = readSkill(name);
    for (const prohibition of prohibitedRequirements) {
      assert.doesNotMatch(skill, prohibition, `${name} must not match ${prohibition}`);
    }
  }
});
