# Test topology

Design the least expensive execution shape that can create each property's preconditions and observe its oracle. "Topology" may mean one function call, an in-process model, several processes, containers, or a production-like distributed environment.

## Choose from the property backward

For each property, identify:

- code and state that must execute;
- clients or workload drivers;
- required real dependencies versus fakes or models;
- process, thread, storage, clock, and network boundaries;
- required replicas and version combinations;
- observation and instrumentation points;
- setup, stabilization, cleanup, and reproducibility needs;
- framework-specific constraints and costs.

Prefer the smallest shape that preserves the behavior under test. A fake is useful only if it preserves the relevant contract. An in-process test cannot cover a process crash. Two services in one fault unit cannot experience independent process or network faults. Conversely, a containerized distributed environment is wasteful for a pure parser invariant.

## Common shapes

### Direct or model-based

```text
generated or fixed input -> public API -> result
          model/oracle -----------------> compare
```

Use for unit, differential, metamorphic, and many fast-check properties.

### Stateful sequence

```text
command generator -> system state
                 -> model state -> compare after each command
```

Use when operation order and preconditions matter.

### Service integration

```text
workload client -> service under test -> real or compatible dependency
```

Use when serialization, persistence, protocol, or lifecycle boundaries are part of the property.

### Distributed fault environment

```text
workload clients -> service replicas <-> storage or coordination dependencies
                           ^
                     fault controller
```

Use only when properties require cross-process interleavings, restarts, partitions, or topology changes. Justify every component and replica.

## Tool selection

Choose the mechanism after the semantic catalog exists. A project may route deterministic cases to its ordinary runner, generated input properties to fast-check, stateful or system exploration to Hegel, and process or network faults to Antithesis. Do not assume one framework must consume the whole catalog.

When Antithesis is selected, verify current container, test-template, readiness, SDK, and fault requirements from official documentation. When another tool is selected, verify its current APIs and runtime constraints from its primary documentation.

## Output

Write `docs/code-analysis/test-topology.md` with provenance from [workspace and provenance](workspace.md). For each layer or component, document its role, launch source, state, connections, replicas, fault boundary, observation points, and the properties it enables.
