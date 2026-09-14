# Validating external claims

External sources provide leads, not facts. A claim enters the system analysis or becomes a property premise only after evidence exhibits the behavior through code, a reproduction, logs, a fix, or another primary observation.

Validate what the analysis builds on, not everything you read. The moment a claim would become "the system does X" or support a property is the moment it needs validation.

## Claimed guarantees

Docs, design notes, and comments often state intended behavior such as "acknowledged writes survive failover." Turn the statement into a property and attribute it as a claim. Do not state that it holds. The test exists to find out.

## Bug and incident reports

A report is an interpretation of symptoms. Read the reproduction, logs, code path, fix, maintainer discussion, and resolution. Name a competing explanation before investigating, usually environment, configuration, dependency behavior, or user misunderstanding. Find evidence that distinguishes those explanations from a system defect.

"The issue says split-brain" repeats the claim. "Name resolution fails before any quorum event, and the announced hostnames differ from the names peers resolve" discriminates between a coordination defect and deployment misconfiguration.

If available evidence cannot settle the claim, keep it out of factual findings and property premises. Record it under `Open Questions`, including what evidence is missing. Use the state conventions from [property catalog](property-catalog.md).

## Evidence discipline

- Read past titles and summaries to the primary evidence.
- Check source standing and resolution state, but do not substitute authority for mechanism.
- Cite the path, symbol, revision, log detail, test, or discussion that decides the claim.
- Separate current behavior from fixed history and intended design.
- When a source and code disagree, report the conflict and use current runtime wiring as evidence of current behavior.
