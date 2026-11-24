---
name: designing-tests
description: Choose consumer seams, fixtures, and assertions when asked to design or strengthen behavioral tests, or when choosing how a test should catch a specific regression. Not for test execution or code review alone.
---

# Designing Tests

Name the plausible wrong implementation the test should catch. Then choose a seam, fixture, and assertions that distinguish it from the required behavior.

## Choose what to observe

- Start with the consumer and what it relies on. Prefer the narrowest public seam that observes the consequence: an API response, command result, rendered output, persisted state, or integration boundary. For a consequential choice, say what the seam catches and what it misses.
- Test through the real path at the boundary that could be broken. Avoid private calls, snapshots without meaningful assertions, or mocks that restate what the implementation does. Assert an interaction when the interaction itself is the contract. The test should survive harmless internal refactoring.
- Decide whether a seam is useful based on behavior, not file type. Configuration can change routing, permissions, initialization, exposure, or persisted state. Where relevant, observe rendered defaults, supported overrides, and committed environment inputs. For agent instructions, use realistic requests to observe behavior; wording checks establish only structural contracts.

## Make the wrong outcome visible

- Derive expected values from the requirement, protocol, or a worked example, not the implementation. Use distinct IDs and values so the wrong record, stale value, or missing field cannot produce the expected result by accident.
- Assert the specific result the consumer needs. A success flag, aggregate count, or later read can hide a wrong result. For collections or multiple consumers, ask whether one missing result could hide among successful ones; assert the affected member by identity.
- For recovery, observe a new successful result after the fault clears. Make it distinguishable from a result that existed before the fault. If the effect is asynchronous, wait at the observation point with a bound.

## Two regression patterns

**Locked reconciliation.** Make the pre-lock read differ from the value a concurrent writer commits before lock acquisition. Control the ordering to make the stale read deterministic. For example, a request to reserve up to 5 units reads 5 available, then another writer reduces availability to 2 before the request acquires the lock. Assert that the first response reports 2 units reserved and the stored reservation holds 2. Neither assertion proves the other.

**Record replacement.** Seed a record with distinct, non-default values in the fields that must survive. Change only the intended field through the normal update path. For example, update a profile's display name without resending its locale or time zone. Read back the new name and the unchanged locale and time zone. Then assert that the consumer uses the updated record, such as a profile view showing the new name and a date formatted using the retained settings. A successful update or a check of only the changed field can miss a replacement that drops the rest of the record.
