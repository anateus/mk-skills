const path = require('node:path');

const pluginRoot = process.env.PLUGIN_ROOT
  || process.env.CLAUDE_PLUGIN_ROOT
  || path.resolve(__dirname, '..');
const {
  loadPolicy,
  renderContext,
  selectMode,
} = require(path.join(pluginRoot, 'lib', 'mode-policy'));

function emit(event, diagnostics, override = process.env.MK_SKILLS_MODE) {
  const { policy, diagnostics: policyDiagnostics } = loadPolicy(
    path.join(pluginRoot, 'config', 'mode-policy.json'),
  );
  const selection = selectMode({
    model: event.model,
    override,
    policy,
  });
  const output = {
    hookSpecificOutput: {
      hookEventName: 'SessionStart',
      additionalContext: renderContext({ mode: selection.mode, policy }),
    },
  };
  const messages = [...diagnostics, ...policyDiagnostics, ...selection.diagnostics];
  if (messages.length > 0) output.systemMessage = messages.join(' ');
  process.stdout.write(`${JSON.stringify(output)}\n`);
}

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  input += chunk;
});
process.stdin.on('end', () => {
  let event = {};
  const diagnostics = [];
  let override;
  try {
    const parsed = JSON.parse(input);
    if (
      !parsed
      || typeof parsed !== 'object'
      || Array.isArray(parsed)
      || parsed.hook_event_name !== 'SessionStart'
      || (parsed.model !== undefined && (
        typeof parsed.model !== 'string' || parsed.model.length === 0
      ))
      || typeof parsed.cwd !== 'string'
    ) throw new Error('invalid');
    event = {
      hook_event_name: parsed.hook_event_name,
      model: parsed.model || '',
      cwd: parsed.cwd,
    };
  } catch (error) {
    diagnostics.push('Malformed hook input; using selective fallback.');
    override = 'selective';
  }
  emit(event, diagnostics, override);
});
