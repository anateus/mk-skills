#!/usr/bin/env node

const fs = require('node:fs');
const path = require('node:path');

const scriptPath = fs.realpathSync(__filename);
const skillRoot = path.resolve(path.dirname(scriptPath), '..');
const configPath = path.join(skillRoot, 'config', 'artifact-discipline.json');
const libraryPath = path.join(skillRoot, 'lib', 'artifact-discipline');

function emit(output) {
  process.stdout.write(`${JSON.stringify(output)}\n`);
}

function diagnostic(message) {
  return { systemMessage: `Artifact discipline: ${message}. Allowing subagent lifecycle.` };
}

function handle(event, config, discipline) {
  if (process.env.MK_SKILLS_ARTIFACT_DISCIPLINE === 'off') return {};
  if (!event || !['SubagentStart', 'SubagentStop'].includes(event.hook_event_name)) return {};

  let location;
  try {
    location = discipline.artifactLocation(event, { config });
  } catch (error) {
    return diagnostic(error.message);
  }

  if (event.hook_event_name === 'SubagentStart') {
    try {
      discipline.prepareDirectory(location.directory);
    } catch (error) {
      return diagnostic('could not prepare artifact directory');
    }
    return {
      hookSpecificOutput: {
        hookEventName: 'SubagentStart',
        additionalContext: discipline.renderContext(config, location.artifactPath),
      },
    };
  }

  const inspected = discipline.inspectArtifact(location.artifactPath);
  if (inspected.state === 'complete') return {};
  if (inspected.state === 'unexpected' || inspected.state === 'error') {
    return diagnostic('could not safely inspect artifact path');
  }

  if (typeof event.last_assistant_message === 'string' && event.last_assistant_message.trim() !== '') {
    try {
      discipline.writeAtomically(
        location.artifactPath,
        event.last_assistant_message,
        config.maxFallbackBytes,
      );
      return {};
    } catch (error) {
      return diagnostic('could not persist fallback result');
    }
  }

  if (event.stop_hook_active === true) {
    try {
      discipline.writeAtomically(
        location.artifactPath,
        discipline.EMPTY_PLACEHOLDER,
        config.maxFallbackBytes,
      );
      return {};
    } catch (error) {
      return diagnostic('could not record missing artifact');
    }
  }

  return {
    decision: 'block',
    reason: `Before stopping, write detailed findings to ${location.artifactPath}. If no writing tool is available, return the full findings in your final response.`,
  };
}

let config;
let discipline;
try {
  config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  discipline = require(libraryPath);
  if (!discipline.validateConfig(config)) throw new Error('invalid artifact configuration');
} catch (error) {
  emit(diagnostic('configuration unavailable'));
  process.exit(0);
}

let input = '';
let inputBytes = 0;
let exceeded = false;
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  inputBytes += Buffer.byteLength(chunk, 'utf8');
  if (inputBytes > config.maxInputBytes) {
    exceeded = true;
    return;
  }
  input += chunk;
});
process.stdin.on('end', () => {
  if (exceeded) {
    emit(diagnostic('hook input exceeded byte limit'));
    return;
  }
  let event;
  try {
    event = JSON.parse(input);
  } catch (error) {
    emit(diagnostic('malformed hook input'));
    return;
  }
  emit(handle(event, config, discipline));
});
