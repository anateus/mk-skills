# Peer-ready plan

Execution: valid inline and sequentially. Optional `zellij-agent-herder` orchestration may be used when requested, available, and the slices remain independent with non-overlapping ownership.

## Slice A

- Scope: update the parser contract and its focused tests.
- Dependencies: none.
- Expected output: the parser accepts the new field while preserving old input behavior.
- Verification: run the parser contract test.

## Slice B

- Scope: update the independent renderer and its focused tests.
- Dependencies: Slice A's documented contract, not its working tree.
- Expected output: the renderer displays the field and retains the fallback.
- Verification: run the renderer behavior test.

Peer reports and output are evidence to verify, not proof of completion. The responsible agent performs primary verification against integrated changes.

