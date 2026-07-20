const fs = require('node:fs');

const MODES = new Set(['strict', 'selective', 'off']);
const FALLBACK_POLICY = Object.freeze({
  version: 1,
  defaultMode: 'selective',
  modelRules: [],
  contexts: {
    selective: 'Use skills when their trigger clearly matches the task. Scale process to uncertainty and risk, and verify material claims with fresh evidence.',
    strict: '',
  },
});

function policyIsValid(policy) {
  return Boolean(
    policy
      && policy.version === 1
      && MODES.has(policy.defaultMode)
      && Array.isArray(policy.modelRules)
      && policy.modelRules.every((rule) => (
        rule
          && typeof rule === 'object'
          && !Array.isArray(rule)
          && typeof rule.pattern === 'string'
          && MODES.has(rule.mode)
      ))
      && policy.contexts
      && typeof policy.contexts.selective === 'string'
      && typeof policy.contexts.strict === 'string',
  );
}

function loadPolicy(policyPath) {
  const diagnostics = [];
  try {
    const policy = JSON.parse(fs.readFileSync(policyPath, 'utf8'));
    if (!policyIsValid(policy)) {
      diagnostics.push(`Invalid mode policy at ${policyPath}; using selective fallback.`);
      return { policy: FALLBACK_POLICY, diagnostics };
    }
    return { policy, diagnostics };
  } catch (error) {
    diagnostics.push(`Could not load mode policy at ${policyPath}; using selective fallback.`);
    return { policy: FALLBACK_POLICY, diagnostics };
  }
}

function selectMode({ model = '', override, policy = FALLBACK_POLICY }) {
  const diagnostics = [];
  if (override !== undefined && override !== '') {
    if (MODES.has(override)) return { mode: override, reason: 'override', diagnostics };
    diagnostics.push(`Ignoring invalid MK_SKILLS_MODE value "${override}"; using selective mode.`);
    return { mode: 'selective', reason: 'invalid-override', diagnostics };
  }

  for (const rule of policy.modelRules || []) {
    if (!rule || !MODES.has(rule.mode) || typeof rule.pattern !== 'string') continue;
    try {
      if (new RegExp(rule.pattern).test(model)) {
        return { mode: rule.mode, reason: `model:${rule.pattern}`, diagnostics };
      }
    } catch (error) {
      diagnostics.push(`Ignoring invalid model pattern "${rule.pattern}".`);
    }
  }

  const mode = MODES.has(policy.defaultMode) ? policy.defaultMode : 'selective';
  return { mode, reason: 'default', diagnostics };
}

function renderContext({ mode, policy = FALLBACK_POLICY }) {
  if (mode === 'off') return '';
  if (!MODES.has(mode)) return policy.contexts.selective || FALLBACK_POLICY.contexts.selective;
  return policy.contexts[mode] || FALLBACK_POLICY.contexts.selective;
}

module.exports = {
  FALLBACK_POLICY,
  loadPolicy,
  renderContext,
  selectMode,
};
