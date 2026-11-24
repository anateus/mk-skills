---
name: test-driven-development
description: Implement behavior through narrow red-green cycles at public seams. Use for test-first or TDD work, or behavior changes with a useful test seam; choose proportional alternatives elsewhere.
---

# Test-Driven Development

Drive behavior through evidence, not implementation shape. Work in narrow red-green slices so each test proves one useful outcome and each production change has a reason to exist.

## Behavior cycle

1. Load [`designing-tests`](../designing-tests/SKILL.md) to choose the behavior seam, fixture, and assertions for one narrow slice.
2. Add the focused test and run it. Capture red evidence showing the intended assertion fails for the expected behavioral reason. Setup errors and unrelated failures are not a valid red state.
3. Make the minimal green change that satisfies that behavior while preserving public behavior outside the requested change.
4. Run the focused test, then proportional affected checks. Record fresh verification before claiming the slice works.
5. Refactor only while green, then start the next narrow vertical slice.

## Proportional alternatives

Use the cycle when it provides useful behavioral confidence. If the change has no valuable behavior seam, use the nearest reliable evidence instead: compiler or reference checks for a mechanical rename, generator reproducibility for generated files, or validation for configuration with no behavioral change. Explain why the alternative gives better evidence.

Existing untested code is not itself an exception when the requested behavior can be characterized safely.

## Outcome

Report the behavior proved and relevant evidence or limitations. Include the red-green detail when it helps assess the change.
