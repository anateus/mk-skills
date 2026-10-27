# Document/code drift audit

Use this bounded mode when the user asks whether selected documentation matches current implementation. It is a pilot, not a routine repository-entry step or a mandate to audit every document.

1. Define the scope: document(s), claims, relevant code paths, revision, and evidence available. Inventory the claims in scope before comparing; do not imply unexamined coverage.
2. For each claim, record the document location and classify it as a claim about current behavior, future/intended behavior, or historical behavior. Treat these as distinct temporal states, not interchangeable evidence.
3. Trace current claims through the reachable implementation and relevant configuration, callers, and tests. Exercise a representative public path when practical. Record the command or source evidence and observed result; static reachability is not an executed behavior claim.
4. Compare future intent with what is implemented now without calling the proposed path current. Compare historical claims against a named revision or other dated primary evidence; historical behavior does not prove current behavior.
5. Report each checked claim as confirmed, drift, intent/unimplemented, historical-only, or unverified, with concise evidence and scope. State material gaps and paths not checked. If code, documents, and runtime disagree, describe the conflict instead of guessing which source is authoritative.

Keep the report proportional to the requested scope. Do not change documents or implementation unless separately asked.
