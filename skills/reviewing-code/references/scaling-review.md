# Scaling a review

Scale passes to size and risk. Say which review level you used and what justified any extra passes or readers.

## Baseline

One reviewer reads the fixed comparison once, checks each axis, and notes coverage in the report. That is the whole review for a small, local, reversible change. A wording-only change needs only a check that nothing else changed.

With no specification, state the change's intent from the request, commits, and PR description before judging it, and ask only if it stays unclear. Findings are judged against that intent.

Two rules hold at every level:

- **Confirm before reporting.** Check each candidate finding against the fixed comparison yourself, whether it came from you, another reviewer, or a tool. For a behavioral claim, re-run its command or test, or walk the failing path in the code; it is a defect when the failure shows and breaks the intended behavior. A behavioral candidate you could not reproduce is an unverified risk. A design or maintainability finding needs no failing run: confirm that the burden it names is in the changed code, per [design checks](design-review.md). Say which candidates you dropped and why.
- **Hold the change responsible for what it changed.** A defect already in the base blocks only when the change copies it or newly reaches it. Report other existing problems separately.

## Signals

Judge by the kind of change, not by a line count. Add effort for:

- a consequential behavior change, redesign, or changed contract, public interface, or wire or storage format;
- persistence, migration, authorization, money, concurrency, deletion, or rollback;
- consumers outside the edited code, or several subsystems in one change;
- a diff too large to read with full attention in one pass;
- a change you wrote, or one whose author's reasoning you carry from the same conversation;
- a first pass that turned up evidence of a wider problem, or a safety assumption you could not prove.

Spend less on a rebase or conflict resolution that left the patch unchanged (see [diff provenance](diff-provenance.md)) and on a small fix to an earlier finding. Those need the changed hunks and what depends on them, not another full review.

## Levels

Each level adds to the one before it.

1. **Separate passes.** Take the axes one at a time over the same comparison instead of holding them all in one read, and keep a coverage manifest. When safety depends on code outside the diff, use [cross-boundary safety checks](cross-boundary-safety.md).
2. **A fresh reader.** When you wrote the change or hold the author's rationale, you check what the change meant to do. A reviewer without that history checks what it says. Give that reviewer the fixed comparison, the complete change content, and the specification or stated intent. Withhold the conversation, the author's justification, and the findings you expect. Ask for a statement, in the reviewer's own words, of what the change does before any findings. A restatement that differs from the intent is a lead: either a defect or a change that does not explain itself. If no separate context is available, review in place and say in the report that the review was not independent.
3. **Several reviewers.** When one reader cannot hold the change, split it by axis or by non-overlapping area. Pick the lenses this change needs; a second reviewer with the same lens adds little. Give each reviewer the same fixed comparison and context, and ask each for locations, evidence, and what it did not cover. Reviewers do not start further reviewers unless asked.
4. **Review and fix rounds.** For high-stakes work, review again after fixes, with a fresh reader each round.

## Merging several reviewers

- A reviewer that failed, timed out, or returned nothing did not review. Record it as not run and its area as unreviewed. Never count it as zero findings.
- Merge the results into one list and group findings that share a root cause.
- Settle disagreements by checking the code. Agreement between reviewers does not confirm a finding, and a finding only one reviewer raised is not weaker for that.
- Keep output that is evidence in itself, such as a fresh reader's restatement, instead of reducing it to a findings list.

## Rounds that converge

Fresh readers sample differently, so a later round often raises something new even when the work has improved. Zero findings is the wrong stopping rule, and one clean round is weaker evidence than it looks.

- **Settled.** A finding disproved with evidence, or one the user accepted as a risk, is settled. Keep the settled list across rounds. Do not re-open an entry because a new reader raises the same issue at the same place without new evidence.
- **Fixed is not settled.** If a later reader raises the same issue at the same place, the fix failed or a later edit brought the problem back. Re-open it. Before closing a finding, re-run its original reproduction against the new head.
- **Clean round.** A round is clean when it raises no blocking finding that is not settled and no reviewer is recorded as not run. Decide this before applying that round's fixes. On high-risk work, confirm a clean round with one more fresh reader before relying on it.
- **Churn.** A new finding sits where a fix was applied, and reverting that fix would resolve it. Stop and take the conflict to the user.
- **No progress.** When successive fixes fail the same check, write down the assumption they share and test it directly before trying another fix.

There is no round limit. When rounds stop making progress, report the open findings by severity and let the user decide whether to accept them, continue, or rework the change. Unresolved defects stay open whichever they choose.

## Testing changes to this guidance

Before trusting an edit to these rules, [replay past findings](replaying-findings.md): run the old and the new guidance against defects real reviewers found on real PRs.
