---
name: test-driven-development
description: Implement behavior through narrow red-green cycles at public seams. Use for test-first or TDD work, or behavior changes with a useful test seam; choose proportional alternatives elsewhere.
---

# Test-Driven Development

Drive behavior through evidence, not implementation shape. Work in narrow red-green slices so each test proves one useful outcome and each production change has a reason to exist.

## Behavior cycle

1. Identify a public behavior seam: an API, command, rendered result, persisted state, or integration boundary a consumer can observe.
2. Derive independent expected values from the requirement, protocol, or a worked example. Do not copy the implementation's calculation.
3. Add one focused test and run it. Capture red evidence showing the intended assertion fails for the expected behavioral reason; setup errors and unrelated failures are not a valid red state.
4. Make the minimal green change that satisfies that behavior while preserving public behavior outside the requested change.
5. Run the focused test, then proportional affected checks. Record fresh verification before claiming the slice works.
6. Refactor only while green, then start the next narrow vertical slice.

Prefer public seams over private calls, snapshots without meaningful assertions, or mocks that merely restate collaborators. A test should survive harmless internal refactoring.

Name the wrong production change each test would catch. For agent instructions, evaluate behavior on realistic requests; wording checks prove only structural contracts. Interaction assertions are useful when the interaction itself is the contract.

## Proportional alternatives

Use the cycle when it provides useful behavioral confidence. For a mechanical rename with unchanged behavior, generated file update, configuration-only change, or another case with no valuable test seam, use the nearest reliable evidence instead: compiler or reference checks, generator reproducibility, configuration validation, or focused smoke tests. Explain the chosen seam or the reason an alternative is higher value.

Existing untested code is not itself an exception when the requested behavior can be characterized safely.

## Outcome

Report the behavior proved and relevant evidence or limitations. Include the red-green detail when it helps assess the change.
