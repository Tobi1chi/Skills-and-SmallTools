---
name: rewrite-by-example
description: Use when the user wants to calibrate an AI-style cleanup of their own manuscript by first hand-rewriting a small set of selected sentences, so the rewrite of the rest of the document follows the user's personal style instead of generic de-AI rules. Trigger on requests like "let me show you how I write by fixing a few sentences myself", "learn my writing style from my own edits", "pick some sentences for me to rewrite first then match that style", or "I want to teach you my voice before you touch the rest". Do NOT trigger when the user only wants a fast automatic polish, a one-shot de-AI pass, or a diagnosis without interaction — use `de-ai-academic-prose` for those.
---

# Rewrite by Example

## Overview

Use this skill when a manuscript sounds AI-generated and the user is willing to
hand-rewrite a small number of carefully chosen sentences so that their
personal writing style can be extracted and applied to the rest of the
document. The skill treats the user's rewrites as a small calibration sample
and compares its statistics against the original document to build a
quantitative style fingerprint, which then drives the full rewrite.

This skill is interactive by design. It has mandatory pause points where the
user must act before the workflow continues. Do not skip these pauses.

This skill shares its diagnostic vocabulary with the `de-ai-academic-prose`
skill. Reuse the tags and severity levels defined there rather than inventing
new ones. When this file references `markers.md` or `genres.md`, load them
from `/mnt/skills/user/de-ai-academic-prose/references/` so the two skills
stay consistent.

Read `/mnt/skills/user/de-ai-academic-prose/references/markers.md` for the
diagnostic tag list and severity scale.

Read `/mnt/skills/user/de-ai-academic-prose/references/genres.md` when the
passage genre affects sentence selection or rewrite pressure.

For whole-document statistics, reuse
`/mnt/skills/user/de-ai-academic-prose/scripts/analyze_academic_prose.py` for
the baseline pass, and use `scripts/compare_style.py` (in this skill) for the
delta pass between baseline and user rewrites.

## When this skill is the right fit

Use this skill when:

- the user explicitly wants to teach their style through their own edits;
- the user is willing to rewrite at least three sentences by hand;
- the manuscript is long enough that extracting a fingerprint is worth the
  overhead (roughly 1500+ words);
- a previous automatic de-AI pass felt generic or wrong in voice.

Do not use this skill when:

- the user wants a one-shot automatic cleanup;
- the manuscript is a short excerpt where selection has no room to breathe;
- the user refuses to write anything themselves;
- the task is diagnosis only.

In those cases hand off to `de-ai-academic-prose` instead.

## Workflow

The workflow has six steps and two mandatory pause points. Do not merge steps,
do not skip pauses, and do not proceed past a pause without an explicit user
response.

### Step 1. Confirm scope and run the baseline analysis

Before selecting any sentences, confirm:

- which file or passage is in scope;
- whether the user wants the whole document rewritten at the end, or only
  specific sections;
- how many calibration sentences the user is willing to rewrite (default: 6,
  minimum: 3, maximum: 8);
- whether the user wants a `minimal`, `medium`, or `aggressive` final rewrite
  once the fingerprint is extracted (default: `medium`);
- whether to enable `cross_sentence_mode` (default: `off`).

`cross_sentence_mode` controls whether the skill also tries to learn the
user's style at the level of sentence-to-sentence logic, paragraph structure,
and argument flow. When it is `off`, the skill only calibrates sentence-level
style (word choice, cadence, sentence shape). When it is `on`, the skill
additionally asks the user to rewrite one or two whole paragraphs, and
performs a qualitative comparison of argument structure in addition to the
quantitative sentence-level delta.

Explain the trade-off to the user before they decide. Paragraph rewrites
take noticeably more effort than sentence rewrites, and the cross-sentence
signal is qualitative rather than quantitative — it relies on reading, not
on the compare script. Recommend `on` only when the user has already
noticed that AI prose fails them at the paragraph level (broken logic,
pseudo progression, forced symmetry, drifting topics), not just at the
sentence level. For most users `off` is the right default.

Do not ask these questions if the user already answered them. Infer when
inference is safe; ask only when guessing would materially change the result.

Then run the baseline analysis script from the `de-ai-academic-prose` skill:

```bash
uv run python /mnt/skills/user/de-ai-academic-prose/scripts/analyze_academic_prose.py \
  /path/to/manuscript.tex \
  --emit-markdown /tmp/baseline_extracted.md \
  --emit-report /tmp/baseline_report.md
```

Use the report to understand which sections are AI-heaviest, which markers
dominate, and where the candidate sentences should come from.

When `cross_sentence_mode` is `on`, also read the extracted Markdown
yourself and note 3–5 paragraphs where the suspected problem lives at the
cross-sentence level — for example, where `broken connector logic`,
`pseudo progression`, `circular paragraph`, `forced symmetry`,
`weak evidence link`, or `paragraph drift` seem to apply. These are not in
the script output; you must read for them. See the Cross-sentence tags
section in
`/mnt/skills/user/de-ai-academic-prose/references/markers.md` for
definitions and examples.

### Step 2. Select calibration sentences

Selection depends on `cross_sentence_mode`.

#### Step 2a. Default mode (`cross_sentence_mode: off`)

Choose 5–8 sentences from the manuscript for the user to rewrite. Selection
is the most important step in this skill. A bad selection wastes the user's
effort and produces a useless fingerprint.

Selection rules:

1. **Marker coverage**: the selected set must cover at least three different
   diagnostic tags from `markers.md`. Do not pick five sentences that all
   suffer from `template transitions` — the fingerprint would only learn
   connector preferences.
2. **Severity**: prefer sentences tagged `medium` or `high`. `low` sentences
   give the user too little to work with.
3. **Self-contained meaning**: the user must be able to read and rewrite the
   sentence without flipping back to context. Skip sentences that only make
   sense inside a long argument chain.
4. **Length band**: roughly 15–40 words. Shorter sentences carry too little
   signal; longer sentences are hard to rewrite and produce noisy deltas.
5. **Genre spread**: if the document has multiple genres (e.g. introduction +
   methods + discussion), draw from at least two of them. Methods sentences
   often have different style norms than discussion sentences, and the
   fingerprint should reflect that.
6. **Avoid notation-heavy sentences**: sentences whose shape is dictated by
   equations, symbol definitions, or fixed technical phrasing are not good
   calibration targets. They cannot be rewritten stylistically.

#### Step 2b. Cross-sentence mode (`cross_sentence_mode: on`)

Choose 3–5 individual sentences AND 1–2 whole paragraphs. The sentences
follow the rules in Step 2a. The paragraphs follow these additional rules:

1. **One cross-sentence tag per paragraph, minimum**: each selected
   paragraph must clearly exhibit at least one cross-sentence tag
   (`broken connector logic`, `pseudo progression`, `circular paragraph`,
   `forced symmetry`, `weak evidence link`, or `paragraph drift`). Do not
   pick a paragraph just because it "reads AI-ish" — name the specific
   cross-sentence problem.
2. **Paragraph length band**: 4–8 sentences. Shorter paragraphs give the
   user nothing to restructure; longer paragraphs are exhausting to
   rewrite and may contain multiple overlapping problems.
3. **Distinct problems across paragraphs**: if selecting two paragraphs,
   they should illustrate different cross-sentence tags. One circular
   paragraph plus one pseudo-progression paragraph is more informative
   than two circular paragraphs.
4. **Self-contained argument**: the paragraph's point should be
   understandable without the surrounding context. Paragraphs that depend
   on a long upstream argument are bad calibration targets.
5. **No notation-heavy paragraphs**: same rule as for sentences.

Warn the user that rewriting a paragraph is significantly more effort
than rewriting a sentence. Offer them the option to drop to sentence-only
mode if they change their mind after seeing the selection.

#### Presenting the selection

Present everything to the user in a numbered list. For each item, include:

- the sentence or paragraph itself;
- its source section reference;
- 1–2 diagnostic tags explaining why it was picked (including
  cross-sentence tags where relevant);
- a short hint about what the problem is. For sentences: `"this sentence
  is flagged for abstract drift and flat cadence"`. For paragraphs:
  `"this paragraph is flagged for pseudo progression — the three
  enumerated points are parallel, not progressive"`.

Do not tell the user how to rewrite. The hints name the problem, not the
fix. The whole point is that the user's own choices become the signal.
This is especially important for paragraph rewrites — do not suggest how
to restructure, because the restructuring is exactly what you want to
learn from.

### PAUSE POINT 1 — wait for the user's rewrites

After presenting the selection, stop. Do not continue the workflow. Do not
start rewriting anything else. Wait for the user to post their rewrites.

If the user posts fewer than three rewrites, tell them the fingerprint will
be unreliable and ask whether they want to rewrite more or proceed with low
confidence. If they choose to proceed, mark the entire fingerprint as
`low confidence` in the delta report.

If the user's rewrites violate academic guardrails (introduced casual tone,
removed necessary hedging, invented content, broke citations), flag this
explicitly before moving on. Ask whether those changes were intentional style
choices or mistakes. Do not silently learn from edits that break the
manuscript's integrity.

### Step 3. Run the delta comparison

Once you have the user's rewrites, construct two files:

- `/tmp/sample_rewrites.md`: the user's rewritten versions only, one per
  line or paragraph;
- `/tmp/baseline_unselected.md`: the original document **with the selected
  sentences and paragraphs removed**. This is the critical detail — the
  baseline for comparison must be the unselected portion of the original,
  not the whole original. The selected items were picked *because* they
  were outliers, so including them in the baseline would inflate the
  apparent delta and make the fingerprint overfit to selection bias.

Then run:

```bash
uv run python scripts/compare_style.py \
  --baseline /tmp/baseline_unselected.md \
  --sample /tmp/sample_rewrites.md \
  --emit-delta /tmp/delta.json
```

The script output is a JSON document with per-dimension baseline values,
sample values, absolute and relative deltas, and a confidence flag. See
`references/fingerprint.md` for the full list of dimensions and how to read
the output.

When `cross_sentence_mode` is `on`, also perform a qualitative comparison
for each rewritten paragraph. The compare script does not measure
cross-sentence structure — you must read each before/after pair yourself
and record, in prose:

- **Connector logic**: did the user change, remove, or replace connectors,
  and if so, did they do it in a way that fixes `broken connector logic`?
  Which connectors did they add, remove, or replace?
- **Progression structure**: if the original paragraph used progression
  markers (`first`, `second`, `finally`, `more importantly`), did the
  user preserve them, remove them, or replace them with something else?
  Did they collapse pseudo-progression into parallel structure?
- **Opening and closing alignment**: compare the first and last sentences
  of the original paragraph to the first and last sentences of the user's
  rewrite. Did the user break a circular paragraph by giving it a
  different endpoint than its starting point?
- **Symmetry**: if the original had a balanced two-sided structure, did
  the user preserve the balance or lean toward one side?
- **Evidence-claim linkage**: did the user strengthen, weaken, or
  restructure the link between claims and their supporting evidence?
- **Topic continuity**: did the user's rewrite stay on one topic or
  follow a different trajectory than the original?

Record these observations as a short structured note per paragraph. These
are the inputs to the qualitative half of the fingerprint in Step 4.

### Step 4. Translate the delta into a human-readable fingerprint

Do not apply the raw delta directly. Translate it into a short natural-language
fingerprint that the user can read and verify.

#### Quantitative part (always)

The quantitative fingerprint should cover:

- sentence length mean and variance changes;
- marker density changes, one line per affected tag from `markers.md`;
- connector and transition density changes;
- abstract/concrete ratio changes;
- sentence-initial pattern changes;
- a word blacklist (high-frequency original words that the user's rewrites
  avoided entirely);
- a word whitelist (words the user introduced that were rare or absent in the
  original), only when the signal is strong enough to trust.

Drop any dimension whose confidence flag is `low` unless the user explicitly
wants to see low-confidence signals. Low confidence usually means the sample
was too small for that dimension to be meaningful.

Do not pad the fingerprint with dimensions that showed no real change. If
only three dimensions moved meaningfully, the fingerprint has three rules.
A short accurate fingerprint is better than a long padded one.

#### Qualitative part (only when `cross_sentence_mode` is `on`)

Add a second section to the fingerprint containing cross-sentence rules
derived from the paragraph observations in Step 3. Each rule should be
one sentence, stated as a principle the rewrite will follow, not as a
description of what the user did. Examples:

- "Keep connectors only when the logical relationship they name is
  actually present. Remove scaffolding connectors that do not add
  logical content."
- "Do not use three-step progression markers unless the three points
  genuinely escalate in strength."
- "Paragraphs should end somewhere different from where they started.
  Avoid summary sentences that restate the opening claim."
- "When comparing two options, lean toward one. Do not default to
  symmetric two-sided structure."

Only include a cross-sentence rule when the evidence from the paragraph
rewrites is clear. One strong paragraph rewrite can justify one rule; do
not invent cross-sentence rules when the user's paragraph edits were
mostly sentence-level. Mark each cross-sentence rule as "cross-sentence"
so the user knows which rules came from paragraph observations and which
came from the statistical delta.

If the user's paragraph rewrites contradict each other (e.g. one
paragraph removed progression markers but another added them), surface
the contradiction as an open question for Pause Point 2 rather than
forcing it into a single rule.

### PAUSE POINT 2 — confirm the fingerprint with the user

Present the fingerprint and ask the user to confirm, correct, or reject each
rule. Use wording like:

> Based on your rewrites, here is the style fingerprint I extracted. Before I
> apply it to the rest of the document, please tell me which rules are
> accurate and which I misread. Any rule you reject will be dropped.

Wait for the user's response. Do not proceed to the full rewrite with
unconfirmed rules. If the user rejects a rule, remove it from the fingerprint
entirely — do not argue, and do not apply it in weakened form.

If the user adds a rule the delta did not detect, accept it as a manual
override and treat it with the same weight as the detected rules.

### Step 5. Rewrite the rest of the document

Apply the confirmed fingerprint to the parts of the document the user wants
rewritten. Follow these rules:

- the fingerprint is a **constraint**, not a template. Do not copy the exact
  phrasing from the user's rewrites into other sentences;
- keep all non-negotiables from `de-ai-academic-prose`: technical meaning,
  notation, citations, claim strength, hedging, formal register;
- match the rewrite intensity the user selected in Step 1 (`minimal`,
  `medium`, or `aggressive`);
- when a sentence in the document would require breaking a fingerprint rule
  to stay technically correct, keep it technically correct and note the
  exception;
- do not rewrite notation-heavy method passages unless the fingerprint
  specifically targets them;
- do not rewrite passages the user excluded from scope in Step 1.

When the rewrite is done, produce output in `before/after + rationale` mode
by default unless the user asked for something else. The rationale should
reference the specific fingerprint rules applied, so the user can audit
whether their own style was honored.

### Step 6. Offer a second calibration round

After delivering the rewrite, offer (but do not force) a second calibration
round: the user picks any rewritten passage they dislike, edits it, and the
skill updates the fingerprint from the new delta. This is optional and only
worth doing if the user reports that the first-pass fingerprint missed
something important.

## Red lines

All red lines from `de-ai-academic-prose` apply. In addition:

- Do not skip either pause point. The skill is useless without the user's
  actual input at both stages.
- Do not learn from user edits that broke academic integrity. Flag them and
  ask first.
- Do not use the whole original document as the comparison baseline. Use the
  unselected portion only.
- Do not apply low-confidence fingerprint rules silently. Either drop them or
  show them clearly marked as low-confidence.
- Do not copy phrases verbatim from the user's rewrites into other sentences.
  Learn the pattern, not the text.
- Do not pad the fingerprint with dimensions that did not actually move.
- Do not argue when the user rejects a fingerprint rule.
- Do not generate cross-sentence fingerprint rules when
  `cross_sentence_mode` is `off`. Those rules require paragraph-level
  rewrites as evidence; without them, any cross-sentence rule would be
  guessed rather than learned.
- When `cross_sentence_mode` is `on`, do not suggest how the user should
  restructure a paragraph before they rewrite it. The restructuring is
  what you are trying to learn.

## Output pattern

Unless the user asks for something else, structure the final response as:

1. baseline analysis summary (from Step 1);
2. the selected calibration sentences with tags and hints (Step 2);
3. [pause 1];
4. the delta report with confidence flags (Step 3);
5. the human-readable fingerprint (Step 4);
6. [pause 2];
7. the rewritten document or sections with before/after pairs and rationale
   tied to fingerprint rules (Step 5);
8. an optional offer for a second calibration round (Step 6).

Keep each step's output short and focused. The user should be able to act on
each step without rereading earlier ones.
