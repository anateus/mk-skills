const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { skillsRoot, parseSkill, skillDirectories, markdownReferences } = require('../helpers/skills');

function markdownLinks(source) { return [...source.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)].map((match) => match[1]); }

test('every skill has valid matching frontmatter and stays within its budget', () => {
  for (const directory of skillDirectories()) {
    const file = path.join(skillsRoot, directory, 'SKILL.md');
    assert.ok(fs.existsSync(file), `${directory} contains SKILL.md`);
    const { fields, body } = parseSkill(file);
    assert.deepEqual(Object.keys(fields).sort(), ['description', 'name']);
    assert.equal(fields.name, directory);
    assert.match(fields.name, /^[a-z0-9]+(?:-[a-z0-9]+)*$/);
    assert.ok(fields.description.trim() && !fields.description.includes('\n'));
    const words = body.trim().split(/\s+/).length;
    assert.ok(words <= (directory === 'zellij-agent-herder' ? 800 : 500), `${directory} has ${words} body words`);
  }
});

test('every reference is reachable from its entry and all local Markdown links resolve', () => {
  for (const name of skillDirectories()) {
    const base = path.join(skillsRoot, name, 'SKILL.md');
    const references = markdownReferences(name);
    const edges = new Map();
    for (const file of [base, ...references]) {
      const source = fs.readFileSync(file, 'utf8');
      edges.set(file, []);
      for (const link of markdownLinks(source)) {
        const target = link.split('#', 1)[0];
        if (!target || /^[a-z][a-z+.-]*:/i.test(target) || target.startsWith('#')) continue;
        assert.ok(fs.existsSync(path.resolve(path.dirname(file), target)), `${file} links to ${target}`);
        edges.get(file).push(path.resolve(path.dirname(file), target));
      }
    }
    const seen = new Set();
    const pending = [base];
    while (pending.length) {
      const file = pending.pop();
      if (seen.has(file)) continue;
      seen.add(file);
      pending.push(...(edges.get(file) || []));
    }
    for (const reference of references) assert.ok(seen.has(reference), `${name}: unreachable ${reference}`);
  }
});
