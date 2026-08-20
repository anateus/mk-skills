const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { randomUUID } = require('node:crypto');

const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const TRUNCATION_MARKER = '\n\n[truncated by artifact discipline]\n';
const EMPTY_PLACEHOLDER = [
  '# Artifact unavailable',
  '',
  'The subagent stopped after continuation with no artifact or final response.',
  '',
].join('\n');

function validateConfig(config) {
  return Boolean(
    config
      && config.version === 1
      && Array.isArray(config.defaultSubdirectory)
      && config.defaultSubdirectory.length > 0
      && config.defaultSubdirectory.every((segment) => IDENTIFIER.test(segment))
      && IDENTIFIER.test(config.artifactFilename)
      && Number.isSafeInteger(config.maxInputBytes)
      && config.maxInputBytes > 0
      && Number.isSafeInteger(config.maxFallbackBytes)
      && config.maxFallbackBytes > Buffer.byteLength(TRUNCATION_MARKER)
      && typeof config.contextTemplate === 'string'
      && config.contextTemplate.includes('{{artifact_path}}'),
  );
}

function artifactLocation(event, { config, env = process.env, tmpdir = os.tmpdir() }) {
  if (!event || !IDENTIFIER.test(event.session_id) || !IDENTIFIER.test(event.agent_id)) {
    throw new Error('invalid subagent lifecycle identifiers');
  }
  const configuredRoot = env.MK_SKILLS_ARTIFACT_DIR;
  const root = configuredRoot === undefined || configuredRoot === ''
    ? path.join(tmpdir, ...config.defaultSubdirectory)
    : configuredRoot;
  if (!path.isAbsolute(root)) throw new Error('artifact root must be absolute');
  if (path.resolve(root) === path.parse(path.resolve(root)).root) {
    throw new Error('artifact root cannot be a filesystem root');
  }

  const directory = path.join(root, event.session_id, event.agent_id);
  const artifactPath = path.join(directory, config.artifactFilename);
  const relative = path.relative(root, artifactPath);
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error('artifact path escapes configured root');
  }
  return { root, directory, artifactPath };
}

function prepareDirectory(directory) {
  fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
  try {
    fs.chmodSync(directory, 0o700);
  } catch (error) {
    if (error.code !== 'ENOSYS' && error.code !== 'ENOTSUP') throw error;
  }
}

function inspectArtifact(artifactPath) {
  try {
    const stat = fs.lstatSync(artifactPath);
    if (!stat.isFile()) return { state: 'unexpected' };
    return { state: stat.size > 0 ? 'complete' : 'empty' };
  } catch (error) {
    if (error.code === 'ENOENT') return { state: 'missing' };
    return { state: 'error', error };
  }
}

function truncateUtf8(text, maxBytes) {
  const input = Buffer.from(text, 'utf8');
  if (input.byteLength <= maxBytes) return text;

  const marker = Buffer.from(TRUNCATION_MARKER, 'utf8');
  let end = Math.max(0, maxBytes - marker.byteLength);
  const decoder = new TextDecoder('utf-8', { fatal: true });
  while (end > 0) {
    try {
      return `${decoder.decode(input.subarray(0, end))}${TRUNCATION_MARKER}`;
    } catch (error) {
      end -= 1;
    }
  }
  return TRUNCATION_MARKER.slice(0, maxBytes);
}

function writeAtomically(artifactPath, content, maxBytes) {
  const directory = path.dirname(artifactPath);
  prepareDirectory(directory);
  const bounded = truncateUtf8(content, maxBytes);
  const temporary = path.join(directory, `.${path.basename(artifactPath)}.${process.pid}.${randomUUID()}.tmp`);
  try {
    fs.writeFileSync(temporary, bounded, { encoding: 'utf8', flag: 'wx', mode: 0o600 });
    fs.renameSync(temporary, artifactPath);
  } finally {
    try {
      fs.unlinkSync(temporary);
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
}

function renderContext(config, artifactPath) {
  return config.contextTemplate.replaceAll('{{artifact_path}}', () => artifactPath);
}

module.exports = {
  EMPTY_PLACEHOLDER,
  artifactLocation,
  inspectArtifact,
  prepareDirectory,
  renderContext,
  truncateUtf8,
  validateConfig,
  writeAtomically,
};
