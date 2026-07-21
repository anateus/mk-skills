const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const skillFile = path.join(__dirname, '..', '..', 'skills', 'adversarial-refinement', 'SKILL.md');

test('adversarial refinement defines selective modes, challenge loop, and boundaries', () => {
  const source = fs.readFileSync(skillFile, 'utf8');
  for (const phrase of [
    'Interactive grill', 'Artifact critique', 'discoverable facts', 'steelman',
    'one material question at a time', 'recommended answer', 'assumptions',
    'counterexamples', 'failure modes', 'downstream effects', 'reversibility',
    'opportunity cost', 'strongest materially different alternative', 'residual risks',
    'rejected alternatives', 'unresolved decisions',
  ]) assert.match(source, new RegExp(phrase, 'i'), `contains ${phrase}`);
  assert.match(source, /risk|impact/i);
  assert.match(source, /not own implementation|does not own implementation/i);
  assert.match(source, /external lifecycle actions/i);
  assert.match(source, /\[[^\]]+\]\(references\/challenge-lenses\.md\)/);
  assert.match(source, /(?:read|use)[^.\n]*\[[^\]]+\]\(references\/challenge-lenses\.md\)[^.\n]*(?:consequential|generic challenge)/i);
  assert.doesNotMatch(source, /always (?:invoke|use)|requires? (?:a )?mandatory design document|must commit|must implement|require approval after every section/i);
});

test('base skill stays compact', () => {
  const source = fs.readFileSync(skillFile, 'utf8');
  const body = source.replace(/^---[\s\S]*?---\s*/, '');
  assert.ok(body.trim().split(/\s+/).length < 500);
});
