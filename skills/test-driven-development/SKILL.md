---
name: test-driven-development
description: Implement observable behavior changes through narrow red-green cycles at public seams, with proportional alternatives when a test adds little value. Use when the user asks for test-first or TDD work, or when implementing a behavior change or defect fix that has a useful observable seam.
---

# Test-Driven Development

Drive behavior through evidence, not implementation shape. Work in narrow red-green slices so each test proves one useful outcome and each production change has a reason to exist.

## Behavior cycle

1. Identify a public behavior seam: an API, command, rendered result, persisted state, or integration boundary a consumer can observe.
2. State independent expected values derived from the requirement, protocol, or worked example—not copied from the implementation's calculation.
3. Add one focused test and run it. Capture red evidence showing the intended assertion fails for the expected behavioral reason; setup errors and unrelated failures are not a valid red state.
4. Make the minimal green change that satisfies that behavior while preserving public behavior outside the requested change.
5. Run the focused test, then proportional affected checks. Record fresh verification before claiming the slice works.
6. Refactor only while green, then start the next narrow vertical slice.

Prefer public seams over private calls, snapshots without meaningful assertions, or mocks that merely restate collaborators. A test should survive harmless internal refactoring.

## Proportional alternatives

Use the cycle when it provides useful behavioral confidence. For a mechanical rename with unchanged behavior, generated file update, configuration-only change, or another case with no valuable test seam, use the nearest reliable evidence instead: compiler or reference checks, generator reproducibility, configuration validation, or focused smoke tests. Explain the chosen seam or the reason an alternative is higher value.

Existing untested code is not itself an exception when the requested behavior can be characterized safely.

## Outcome

Report the behavior seam, red evidence, minimal green change, and fresh verification when applicable. For an alternative, report the evidence used and its limitations.
