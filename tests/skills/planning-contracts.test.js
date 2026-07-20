const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const readSkill = (name) => fs.readFileSync(
  path.join(__dirname, '..', '..', 'skills', name, 'SKILL.md'),
  'utf8',
);

const prohibitedRequirements = [
  /(?:must|required to|always) (?:interview|ask the user)/i,
  /(?:must|required to|always) commit/i,
  /(?:must|required to|always) (?:create|use) (?:a )?worktree/i,
  /(?:must|required to|always) (?:publish|create) (?:a )?(?:tracker|ticket|issue)/i,
  /(?:must|required to|always) (?:dispatch|use) (?:peers|peer agents|subagents)/i,
];

test('clarifying-work asks only material questions and covers integration risk', () => {
  const skill = readSkill('clarifying-work');
  assert.match(skill, /discover(?:able)? facts|inspect.*locally/is);
  assert.match(skill, /rework risk/i);
  assert.match(skill, /one material question at a time/i);
  for (const concern of [
    'consumers', 'failure modes', 'schema propagation', 'lifecycle',
    'authorization', 'dependency scope', 'configuration', 'edge cases',
  ]) assert.match(skill, new RegExp(concern, 'i'));
  assert.match(skill, /integration map/i);
});

test('specifying-work defines a synthesis-first reviewable contract', () => {
  const skill = readSkill('specifying-work');
  for (const section of [
    'problem', 'behavior', 'constraints', 'acceptance criteria', 'seams', 'non-goals',
  ]) assert.match(skill, new RegExp(section, 'i'));
  assert.match(skill, /synthesi[sz]e/i);
  assert.match(skill, /approval.*material unresolved|material unresolved.*approval/is);
});

test('planning-work creates peer-ready vertical slices without requiring peers', () => {
  const skill = readSkill('planning-work');
  assert.match(skill, /vertical (?:tracer-bullet )?slices|tracer-bullet/i);
  for (const element of ['dependencies', 'expected outputs', 'verification']) {
    assert.match(skill, new RegExp(element, 'i'));
  }
  assert.match(skill, /peer-ready/i);
  assert.match(skill, /inline/i);
  assert.match(skill, /zellij.*optional|optional.*zellij/is);
  assert.match(skill, /peers?.*optional|optional.*peers?/is);
});

test('front-end skills do not impose external workflow ceremony', () => {
  for (const name of ['clarifying-work', 'specifying-work', 'planning-work']) {
    const skill = readSkill(name);
    for (const prohibition of prohibitedRequirements) {
      assert.doesNotMatch(skill, prohibition, `${name} must not match ${prohibition}`);
    }
  }
});
