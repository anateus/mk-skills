# Distributed incident evidence

## Locate the symptom in the stack

Separate these layers before proposing a cause:

1. User or business impact
2. Scheduler, queue, and dispatch
3. Concurrency, retry, and resource hold time
4. Application state and normalization
5. Provider integration and request/response body
6. Protocol, network, carrier, or external service

A failure at one layer can amplify another without causing it. For example, long external hold time may explain queue throughput while a separate post-connect failure explains conversion loss.

## Identify actor, clock, and leg

For each event, record:

- who emitted it and who received it;
- the clock and timezone;
- the request, call, or job leg it belongs to;
- the stable correlation identifier;
- whether the timestamp marks creation, send, receive, answer, completion, or persistence.

In packet captures, infer ownership from source/destination and protocol fields, not event order alone. In multi-leg calls or requests, do not compare provider-leg duration with application slot-hold duration as if they were the same clock.

## Make comparisons fair

- Use the same window, timezone, filters, and population.
- Show the denominator and null/unknown rate beside every percentage.
- Compare instrumentation coverage before comparing metadata values.
- Split fresh versus retried entities when repeat behavior can bias results.
- Check whether a schema or enrichment change created an apparent incident boundary.

## Interpret history cautiously

Distinguish commit time, merge time, artifact build, deploy, config write, cache expiry, and symptom onset. An `updated_at` value often records only the last write; it cannot prove that an earlier change and revert never occurred. A nearby deployment is a candidate, not a mechanism.

## Interpret codes at the exact boundary

Resolve status and error codes from the provider, endpoint, and code path that emitted them. Do not transfer semantics from another provider because the numeric code matches. Distinguish transport failure, valid HTTP response with a business decline, normalized internal status, and dashboard label.

## Quantify the mechanism

Pair counts with latency or occupancy. For a fixed slot budget, approximate maximum completion rate as:

```text
completion rate <= available slots / average hold time
```

Validate the approximation against observed concurrency and dispatch buckets. This distinguishes “fewer jobs started” from “the same capacity is held longer.”

## Prefer closer evidence

Prefer raw provider bodies, packet/audio traces, database rows, and reproducible queries over normalized dashboards or prose. Use source code to explain how observed fields are produced, then verify the live path actually invokes that code.
