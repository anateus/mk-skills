# Style profiling

Infer habits that help reproduce the user's writing. Do not turn one medium, topic, correspondent, or period into a universal rule.

## Evidence pass

1. Record extraction stats and the corpus date range for each source.
2. Analyze each source separately. Compare sentence and paragraph length, openings, punctuation, capitalization, contractions, transitions, parentheticals, list use, directness, hedging, humor, technical density, greetings, and closings.
3. Look for traits shared across at least two media. Mark a trait as medium-specific when it appears mainly in one source.
4. Distinguish deliberate habits from dictation errors, copied material, quoted reply text, templates, signatures, commands, logs, and one-off phrases.
5. Check the proposed profile against a held-out slice. Remove rules that produce caricature or do not help distinguish the user's writing.

Short messages support claims about chat habits, not long-form structure. Coding prompts support technical collaboration style, not personal email tone. If one source dominates the sample, compare source-level findings without pooling message counts.

## Weighting evidence

Do not give every message one vote. Use `word_count` so a two-word reply contributes fewer style observations than a developed paragraph.

- Estimate token, punctuation, and syntactic rates from their actual opportunities, such as marks per sentence or constructions per word. This naturally gives longer samples more evidence.
- Balance media before combining them. A large iMessage history must not outvote email or technical writing solely through message count.
- For message-level features such as greeting presence, use a saturating length weight. A useful starting family is `n / (n + k)`, where `n` is `word_count` and `k` is chosen and recorded from the corpus length distribution. Validate the choice against held-out writing instead of treating it as fixed truth.
- Use TF-IDF-like weighting only for content-bearing words and phrases when separating recurring voice from recurring topics. Do not apply it blindly to function words, punctuation, or syntax, which often carry the style signal.

Record the weighting rule and source balance in the profile. Keep raw lengths in the corpus so later analysis can recalibrate without another private-data extraction.

## Profile format

```markdown
# Personal writing style

Updated: YYYY-MM-DD

## Evidence
- Source, observed date range, candidates, emitted samples, length weighting, limitations

## Stable traits
- Habit, strength, contexts, confidence

## Medium variants
### Technical collaboration
### Instant messages
### Email
### Slack

## Prefer
- Concrete, reproducible guidance

## Avoid
- Choices the user consistently avoids

## Uncertain
- Plausible traits that need more or better-distributed evidence
```

Keep the profile operational. Describe choices another writer can make. Avoid personality diagnoses and vague labels such as "authentic" or "professional." Do not embed raw private messages by default. If examples materially help, use short redacted excerpts with the user's approval.

Rebuild the profile when the corpus or target medium changes materially. Preserve earlier profile claims only when the new evidence still supports them.
