# Journey map contract

Keep an index linking each feature recipe. A recipe describes behavior from the user's point of view rather than implementation internals. Use these fields, adapting headings to the repository's conventions:

- Feature and user-visible result, with distinct entry points and sub-journeys.
- Preconditions: build, fixture state, authentication, entitlement, operating system, and required external boundaries.
- Exact user action through the chosen runner, with stable selectors or commands and expected immediate feedback.
- Independent resulting-state and side-effect observations, their evidence artifact paths, and a reset or cleanup step.
- Gotchas, particularly inaccessible paths and prerequisites the local fixture cannot supply.

For each run, record source-reviewed and actually driven entry points separately. A recipe is not proof. An inaccessible path needs the attempted action and concrete unmet prerequisite. A successful alternate entry point does not verify an unexercised one. Keep evidence outside the run's disposable directory and identify which artifacts belong to each feature and entry point.

Maintain the index against actual recipe files and source-visible user entry points. When the product changes, distinguish an intended new behavior that needs a map update from a product regression that must remain visible. Do not remove a broken journey just to make the coverage report pass.
