const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const readSkill = (name) => fs.readFileSync(
  path.join(__dirname, '..', '..', 'skills', name, 'SKILL.md'),
  'utf8',
);

const prohibitedRequirements = [
  /(?:must|required to|always) commit/i,
  /(?:must|required to|always) (?:create|use) (?:a )?worktree/i,
  /(?:must|required to|always) (?:publish|create|update) (?:a )?(?:tracker|ticket|issue)/i,
  /(?:must|required to|always) (?:dispatch|use) (?:peers|peer agents|subagents)/i,
  /(?:must|required to|always) (?:open|create) (?:a )?(?:pull request|PR)/i,
];

test('reviewing-code fixes diff provenance and separates review axes', () => {
  const skill = readSkill('reviewing-code');
  assert.match(skill, /fixed comparison point/i);
  assert.match(skill, /diff provenance/i);
  assert.match(skill, /optional specification|specification.*when (?:one )?exists/is);
  assert.match(skill, /correctness and risk/i);
  assert.match(skill, /specification compliance/i);
  assert.match(skill, /repository standards/i);
  assert.match(skill, /findings.*severity|severity.*findings/is);
  assert.match(skill, /diff size or risk|size.*risk/is);
  assert.match(skill, /peers?.*optional|optional.*peers?/is);
  assert.match(skill, /primary (?:agent )?verification/i);
  assert.doesNotMatch(skill, /GitHub/i);
});

test('handling-review-feedback evaluates and classifies every item', () => {
  const skill = readSkill('handling-review-feedback');
  assert.match(skill, /technically evaluate|technical evaluation/i);
  assert.match(skill, /code and requirements/i);
  for (const classification of ['accepted', 'rejected with evidence', 'clarification-needed']) {
    assert.match(skill, new RegExp(classification, 'i'));
  }
  assert.match(skill, /verify.*accepted|accepted.*verify/is);
});

test('verifying-work maps each claim to fresh relevant evidence and stays compact', () => {
  const skill = readSkill('verifying-work');
  assert.match(skill, /each (?:completion )?claim/i);
  assert.match(skill, /fresh.*evidence|evidence.*fresh/is);
  assert.match(skill, /relevant evidence/i);
  assert.match(skill, /limitations/i);
  assert.ok(skill.trim().split(/\s+/).length < 300, 'verifying-work is under 300 words');
});

test('handing-off-work creates a temporary redacted summary using references', () => {
  const skill = readSkill('handing-off-work');
  assert.match(skill, /temporary (?:location|file|summary)/i);
  assert.match(skill, /redact.*secrets|secrets.*redact/is);
  assert.match(skill, /reference.*durable artifacts|durable artifacts.*reference/is);
  assert.match(skill, /rather than duplicat/i);
  for (const field of ['current state', 'remaining work', 'verified facts', 'blockers', 'suggested skills']) {
    assert.match(skill, new RegExp(field, 'i'));
  }
});

test('review skills do not impose external workflow ceremony', () => {
  for (const name of [
    'reviewing-code', 'handling-review-feedback', 'verifying-work', 'handing-off-work',
  ]) {
    const skill = readSkill(name);
    for (const prohibition of prohibitedRequirements) {
      assert.doesNotMatch(skill, prohibition, `${name} must not match ${prohibition}`);
    }
  }
});
