const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..', '..');
const skillsRoot = path.join(root, 'skills');

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
  return { fields, body: match[2], source, file };
}

function readSkill(name) { return parseSkill(path.join(skillsRoot, name, 'SKILL.md')); }
function skillDirectories() {
  return fs.readdirSync(skillsRoot, { withFileTypes: true }).filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort();
}
function markdownReferences(name) {
  const directory = path.join(skillsRoot, name, 'references');
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.md'))
    .map((entry) => path.join(entry.parentPath || entry.path, entry.name));
}

module.exports = { root, skillsRoot, parseSkill, readSkill, skillDirectories, markdownReferences };
