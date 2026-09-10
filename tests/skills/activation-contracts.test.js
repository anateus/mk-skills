const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { root, skillDirectories, markdownReferences } = require('../helpers/skills');

test('activation fixtures use real skills and references with a stable schema', () => {
  const fixture = JSON.parse(fs.readFileSync(path.join(root, 'tests', 'fixtures', 'activation-cases.json'), 'utf8'));
  assert.ok(Array.isArray(fixture) && fixture.length > 0);
  const ids = new Set();
  const skills = new Set(skillDirectories());
  const references = new Set([...skills].flatMap((name) => markdownReferences(name).map((file) => path.relative(root, file).split(path.sep).join('/'))));
  for (const item of fixture) {
    assert.deepEqual(Object.keys(item).sort(), ['expectedReferences', 'expectedSkills', 'forbiddenSkills', 'id', 'prompt', 'rubric']);
    assert.match(item.id, /^[a-z0-9]+(?:-[a-z0-9]+)*$/); assert.equal(ids.has(item.id), false); ids.add(item.id);
    assert.ok(item.prompt.trim()); assert.ok(Array.isArray(item.rubric) && item.rubric.length && item.rubric.every(Boolean));
    for (const field of ['expectedSkills', 'forbiddenSkills', 'expectedReferences']) assert.ok(Array.isArray(item[field]), `${item.id}: ${field}`);
    assert.ok(item.expectedSkills.every((name) => !item.forbiddenSkills.includes(name)), `${item.id}: contradictory expectations`);
    for (const name of [...item.expectedSkills, ...item.forbiddenSkills]) assert.ok(skills.has(name), `${item.id}: ${name}`);
    for (const reference of item.expectedReferences) assert.ok(references.has(reference), `${item.id}: ${reference}`);
  }
});
