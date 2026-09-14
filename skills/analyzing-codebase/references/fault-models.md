# Fault models

A fault model states which perturbations the eventual test can create. Confirm actual support in the selected framework and environment before claiming a property will be exercised.

## Fault dimensions

- input corruption, malformed values, boundary sizes, and adversarial sequences;
- exceptions, partial results, dependency errors, and injected return values;
- cancellation, timeouts, delayed completion, reordered callbacks, and paused tasks;
- duplicated, lost, delayed, or reordered messages;
- asymmetric network loss, latency, congestion, and partitions;
- process hang, throttle, graceful stop, crash, and restart;
- lost volatile state, partial writes, disk-full behavior, and slow storage;
- clock jumps, skew, frozen time, and timer drift;
- resource exhaustion, backpressure, overload, and pool depletion;
- runtime configuration, schema, version, or topology changes;
- application-specific faults exposed through supported APIs or test seams.

## Match mechanism to fault

An ordinary test can often inject invalid input, exceptions, time, or dependency outcomes through a public seam. Property-based and stateful tools add generated values and operation sequences. Deterministic schedulers or simulators may control task order, time, storage, or messages. System-level tools may perturb processes, networks, clocks, and containers.

Record whether each fault is built in, requires test-only instrumentation, requires a production-safe hook, or is unavailable. A property depending on an unavailable fault is not implemented by that mechanism, even if its assertion exists.

For Antithesis, verify tenant and launch configuration for process termination, clock, instrumentation-dependent, and custom faults. Record quiet-period or recovery-check needs separately from safety checks during active faults. Use current Antithesis documentation rather than treating this reference as an API contract.

For fast-check or another in-process property framework, distinguish generated data from environmental faults. Generating operation sequences does not itself create process crashes, network partitions, or scheduler interleavings.

## Recovery conditions

State the condition under which liveness is expected: faults stopped, dependency restored, quorum available, retry budget not exhausted, or another explicit assumption. A liveness property without recovery conditions is usually underspecified.

Write required faults, availability, recovery assumptions, and injection points into the property catalog and evidence file.
