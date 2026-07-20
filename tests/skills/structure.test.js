const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const skillsRoot = path.join(__dirname, '..', '..', 'skills');
const wordBudgetAllowlist = new Set(['zellij-agent-herder']);

function parseSkill(file) {
  const source = fs.readFileSync(file, 'utf8');
  const match = source.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  assert.ok(match, `${file} has YAML frontmatter`);

  const fields = {};
  for (const line of match[1].split('\n')) {
    const field = line.match(/^([a-z][a-z-]*):\s*(.+)$/);
    assert.ok(field, `${file} has simple key/value frontmatter`);
    fields[field[1]] = field[2].replace(/^(["'])(.*)\1$/, '$2');
  }
  return { fields, body: match[2], source };
}

test('every skill has valid matching frontmatter and stays within its budget', () => {
  const directories = fs.readdirSync(skillsRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name);

  for (const directory of directories) {
    const file = path.join(skillsRoot, directory, 'SKILL.md');
    assert.ok(fs.existsSync(file), `${directory} contains SKILL.md`);
    const { fields, source } = parseSkill(file);
    assert.deepEqual(Object.keys(fields).sort(), ['description', 'name']);
    assert.equal(fields.name, directory, `${directory} matches frontmatter name`);
    assert.match(fields.name, /^[a-z0-9]+(?:-[a-z0-9]+)*$/);
    assert.match(fields.description, /^Use when\b/);

    if (!wordBudgetAllowlist.has(directory)) {
      const words = source.trim().split(/\s+/).length;
      assert.ok(words <= 500, `${directory} has ${words} words (budget: 500)`);
    }
  }
});

test('local Markdown links in skills resolve', () => {
  const files = fs.readdirSync(skillsRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(skillsRoot, entry.name, 'SKILL.md'));

  for (const file of files) {
    const { body } = parseSkill(file);
    for (const match of body.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)) {
      const target = match[1].split('#', 1)[0];
      if (!target || /^[a-z][a-z+.-]*:/i.test(target) || target.startsWith('#')) continue;
      assert.ok(fs.existsSync(path.resolve(path.dirname(file), target)), `${file} links to ${target}`);
    }
  }
});

