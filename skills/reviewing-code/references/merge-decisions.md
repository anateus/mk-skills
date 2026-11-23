# Merge decisions

A review supplies evidence. The caller decides whether a change can merge. A short findings list, an empty findings list, or a particular severity count is not permission to merge unattended.

## Get an independent read when it matters

Use a fresh reader when a change alters an important contract, affects recovery or persistent state, or could break a consumer outside the diff. Give the reader the fixed comparison and the intended behavior. Leave out the author’s rationale, earlier findings, and the outcome you expect. Ask the reader to restate what the change does, trace the paths that could fail, and name what they could not verify. See [scaling a review](scaling-review.md) for how to combine independent reviews.

A small, local, reversible change does not need a second reviewer by default. If independence matters and no fresh reader is available, say that explicitly. A reviewer that failed or timed out leaves a coverage gap, not a clean result.

## Report what would block and why

For each proposed blocker, identify the changed behavior, realistic trigger, and material consequence. Show them with a focused run or a trace through the actual consumer. If it also happens on the base, explain what the change newly exposes; otherwise report it separately. A confirmed lesser defect is still a finding. An assumption you could not check is a verification gap, not a confirmed defect or an approval.

Record the reviewed base and head, checks and their scope, uncovered paths, and unresolved findings. Distinguish checks run on the reviewed head from claims about CI or a different revision. The caller can use this evidence alongside repository policy and required checks. Do not let a severity threshold substitute for either.
