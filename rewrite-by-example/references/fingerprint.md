# Style Fingerprint Dimensions

This document defines the dimensions that `scripts/compare_style.py` reports
in its delta JSON, how to interpret each one, and when to trust or discard a
signal. Read this file after running the compare script and before writing
the human-readable fingerprint for the user.

## Delta JSON shape

Each dimension in the delta JSON follows the same structure:

```json
{
  "dimension_name": {
    "baseline": 0.08,
    "sample": 0.01,
    "absolute_delta": -0.07,
    "relative_delta": -0.875,
    "confidence": "high",
    "note": "optional human-readable context"
  }
}
```

- `baseline` is measured on the unselected portion of the original document.
- `sample` is measured on the user's rewrites.
- `relative_delta` is `(sample - baseline) / baseline`, except for variance
  and count-based dimensions where the formula is documented per dimension.
- `confidence` is one of `high`, `medium`, `low`, based on sample size and
  dimension stability rules defined below.

## Confidence rules

A dimension is only worth trusting when the sample gives it enough data.
Use these defaults unless overridden:

- `high`: sample has at least 100 tokens for token-based dimensions, or at
  least 6 sentences for sentence-based dimensions, and the relative delta
  exceeds 30%.
- `medium`: sample meets the size threshold but the relative delta is
  between 15% and 30%, or the size is slightly below threshold but the
  delta is very large (>50%).
- `low`: sample is too small for the dimension to be meaningful, or the
  relative delta is below 15%. Low-confidence dimensions should be dropped
  from the fingerprint by default.

Drop a dimension entirely (not just mark it low) when the baseline value is
zero and the sample value is also zero — there is no signal to report.

## Dimensions

### sentence_length_mean

Average sentence length in the user's rewrites vs the unselected baseline.

- Interpretation: a large negative delta means the user prefers shorter
  sentences; positive means longer.
- Sample size rule: at least 3 sentences for any confidence, at least 6 for
  `high`.
- Common rewrite implication: tighten or loosen default sentence length when
  applying the fingerprint.

### sentence_length_variance

Variance (not standard deviation) of sentence length.

- Interpretation: larger variance means the user breaks uniform rhythm into
  long/short alternation. Smaller variance means the user prefers a steady
  cadence.
- Sample size rule: at least 5 sentences for any confidence. Below 5,
  variance is too noisy — mark `low` regardless of delta magnitude.
- Common rewrite implication: this dimension addresses the `flat cadence`
  marker directly.

### sentence_initial_patterns

Distribution of sentence-initial bigrams in baseline vs sample. Specifically
tracks how often sentences start with the top five baseline patterns (often
`This`, `The`, `It is`, `In`, `These`).

- Interpretation: a sharp drop in a specific pattern means the user avoids
  that opening. Report per pattern, not as a single aggregate number.
- Sample size rule: at least 4 sentences for `medium`, at least 8 for
  `high`.
- Common rewrite implication: rebalance sentence openings when applying the
  fingerprint.

### marker_density

Per-tag marker density for each tag defined in
`de-ai-academic-prose/references/markers.md`:

- `repetitive_framing`
- `meta_writing`
- `template_transitions`
- `over_balanced_contrast`
- `abstract_drift`
- `flat_cadence`
- `generic_recap`

Each is reported as a separate entry (e.g. `marker_density.template_transitions`).
Density is markers per 100 tokens.

- Interpretation: the marker with the largest negative delta is the user's
  strongest dislike. Prioritize it when rewriting.
- Sample size rule: each tag needs at least 2 marker instances in the
  baseline to be comparable. Tags with fewer are dropped.
- Common rewrite implication: directly maps to the tag list the rewrite
  should suppress.

### abstract_noun_density

Density of a fixed abstract-noun list (`framework`, `approach`, `aspect`,
`element`, `notion`, `context`, `dimension`, `perspective`, `paradigm`,
`mechanism` when used non-technically). Measured per 100 tokens.

- Interpretation: a negative delta means the user prefers concrete subjects
  over abstract umbrella nouns.
- Sample size rule: at least 80 tokens in the sample for any confidence.
- Common rewrite implication: push toward concrete actors and objects when
  applying the fingerprint.

### connector_density_total

Total density of discourse connectors (full list in the compare script,
includes `however`, `moreover`, `furthermore`, `therefore`, `thus`,
`consequently`, `additionally`, `nevertheless`, `nonetheless`, `in
addition`, `on the other hand`, `at the same time`).

- Interpretation: the user may not dislike any individual connector but
  still prefer an overall lighter connector density. This dimension catches
  that aggregate preference.
- Sample size rule: at least 100 tokens for any confidence.
- Common rewrite implication: use as a global cap on connectors during
  rewrite, in addition to per-word blacklisting.

### connector_blacklist

List of connectors whose sample count is zero while their baseline density
was non-trivial (at least 0.3 per 100 tokens).

- Interpretation: the user actively avoided these specific connectors.
- Sample size rule: applies only when the sample is at least 100 tokens,
  otherwise zero-count is not meaningful.
- Common rewrite implication: hard blacklist these words in the rewrite.

### word_blacklist

Non-connector content words with high baseline frequency (top 20 content
words) that the sample never used.

- Interpretation: candidate words the user dislikes. Weaker signal than
  connector blacklist because content words are topic-driven.
- Sample size rule: always `medium` at best. Never trust as `high` — too
  topic-dependent. Show to the user for confirmation before applying.
- Common rewrite implication: suggest alternatives but do not hard-ban.

### word_whitelist

Words in the sample that are absent or very rare in the baseline. Report
only content words, not function words.

- Interpretation: vocabulary the user introduced. Usually a weaker signal
  than the blacklist because a short sample can introduce new words for
  purely local reasons.
- Sample size rule: always `low` or `medium`. Present to the user as a
  suggestion, not a rule.

### passive_to_active_ratio

Ratio of passive-voice verbs to active-voice verbs in baseline vs sample.

- Interpretation: a large negative delta means the user converts passive to
  active. Common in non-methods genres.
- Sample size rule: at least 8 finite verbs in the sample.
- Common rewrite implication: bias the rewrite toward active voice in
  non-methods sections. Do not force active voice in methods sections where
  passive is the genre norm.

### nominalization_density

Density of nominalizations (verbs turned into abstract nouns:
`implementation`, `optimization`, `utilization`, `consideration`,
`examination`). Measured per 100 tokens.

- Interpretation: a negative delta means the user verbalizes actions instead
  of nominalizing them. Very common de-AI move.
- Sample size rule: at least 80 tokens in the sample.
- Common rewrite implication: convert nominalizations back to verbs where
  grammatically possible.

## Selection bias guard

The compare script assumes the baseline is the *unselected* portion of the
original document, not the full original. If the full original is passed as
baseline, the deltas will be inflated because the selected sentences were
chosen precisely because they were AI-heavy outliers.

Always construct the baseline file by removing the selected sentences from
the original before running compare. The SKILL workflow enforces this in
Step 3 — do not shortcut it.

## How to turn the delta into the human-readable fingerprint

For each dimension with `high` or `medium` confidence, write one line in
plain language. Drop `low` confidence dimensions unless the user asked to
see them.

Example transformation:

```
"marker_density.template_transitions": {
  "baseline": 0.081,
  "sample": 0.008,
  "relative_delta": -0.90,
  "confidence": "high"
}
```

becomes:

> Template transitions dropped from 8.1 to 0.8 per 100 words (−90%): you
> strongly prefer prose without moreover / however / therefore scaffolding.

Do not show raw JSON to the user. Do not show every dimension — only the
ones that moved. Keep each line to one sentence.

## When the fingerprint contradicts itself

Occasionally the delta will show contradictory signals — for example, the
sample has lower connector density but also uses a connector the baseline
never used. When this happens, present both observations to the user in
Pause Point 2 and let the user resolve the contradiction. Do not try to
reconcile it automatically.

## Cross-sentence dimensions (qualitative only)

When `cross_sentence_mode` is `on` in the SKILL workflow, the fingerprint
has a second section that is not produced by `compare_style.py`. The
compare script only measures things that can be counted — word
frequencies, densities, sentence lengths, marker hits. It cannot tell
whether two sentences actually stand in a contrast relation, whether a
three-step progression actually progresses, or whether a paragraph ends
where it started.

Those judgments come from reading the user's paragraph rewrites side by
side with the original paragraphs and writing a short structured
observation per paragraph. The SKILL.md Step 3 workflow lists the
specific observations to record (connector logic, progression structure,
opening/closing alignment, symmetry, evidence-claim linkage, topic
continuity).

Treat cross-sentence rules differently from quantitative rules in three
ways:

1. **No confidence flag from statistics.** Cross-sentence rules are
   either supported by a clear paragraph rewrite or they are not
   included. There is no "medium confidence" cross-sentence rule —
   either the user demonstrated the pattern or they did not.
2. **One paragraph can justify one rule.** Do not aggregate evidence
   across paragraphs. If the user demonstrated "fix broken connector
   logic" in one paragraph and "collapse pseudo progression" in
   another, those are two separate rules, each tied to its source
   paragraph.
3. **Mark them explicitly.** When presenting the fingerprint to the
   user in Pause Point 2, label cross-sentence rules as
   `cross-sentence` so the user can audit quantitative and qualitative
   rules separately. The user should be able to accept the sentence
   rules while rejecting a cross-sentence rule, or vice versa.

Do not generate cross-sentence rules when `cross_sentence_mode` is
`off`. Without paragraph rewrites, any cross-sentence rule would be a
guess dressed up as a finding.
