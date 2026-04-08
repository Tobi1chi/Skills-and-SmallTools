# AI-Style Markers

Use this checklist when the user asks whether academic prose sounds generated
or when you need a more concrete basis for rewriting.

## Diagnostic tags

Assign 2-4 tags before rewriting.

- `repetitive framing`: repeated phrases such as `this project`, `this study`,
  `the present work`, `this framework`
- `meta-writing`: prose about what the text intends to do instead of direct
  claims
- `template transitions`: repeated `however`, `therefore`, `moreover`, `at the
  same time` when the logic is already clear
- `over-balanced contrast`: repeated `not X but Y`, `rather than`, or parallel
  contrast templates
- `abstract drift`: abstract umbrella nouns replacing concrete actors,
  systems, variables, or results
- `flat cadence`: sentence lengths and rhythms are too uniform across the
  paragraph
- `generic recap`: low-information paragraph endings or summary lines

## Cross-sentence tags

These tags describe problems that live in the relationships between
sentences or across a whole paragraph, not inside any single sentence.
A script cannot detect them — they require reading the text and judging
whether the logic actually holds. Use them only when you have read the
passage, not when you are only looking at statistics.

- `broken connector logic`: a connector like `however`, `therefore`, or
  `moreover` is present, but the relationship between the sentences it
  joins is not actually contrast, causation, or addition. The connector
  marks a logical relation the content does not support. Example:
  "The dataset contains 1200 samples. However, we also used a validation
  split." — there is no contrast, only addition.

- `pseudo progression`: the prose uses progression markers (`first`,
  `second`, `finally`, `more importantly`, `furthermore`) to stage a
  sequence of points, but the later points are not actually stronger,
  deeper, or more consequential than the earlier ones. The sequence is
  parallel content wearing a staircase.

- `circular paragraph`: the paragraph opens with a claim, expands it in
  the middle, and closes by restating the same claim in different words.
  Information gain across the paragraph is close to zero. Distinguish
  from `generic recap` — `generic recap` is about a low-information
  closing sentence; `circular paragraph` is about the whole paragraph
  going nowhere.

- `forced symmetry`: two things are compared in a perfectly balanced
  two-sided structure (`on one hand... on the other hand`, `while X...,
  Y...`, `both X and Y share...`) when the actual evidence or argument
  is not symmetric. Real analyses usually lean toward one side; AI
  defaults to balance.

- `weak evidence link`: a sentence presents evidence or a citation to
  support a claim, but the evidence is only topically adjacent to the
  claim rather than actually supporting it. Phrases like `as shown by`,
  `building on`, `in line with` followed by a reference that does not
  really entail the current point.

- `paragraph drift`: the paragraph starts on topic A, gradually slides
  to topic B in the middle, and ends on topic C, without the author
  acknowledging the drift. The sentence-to-sentence transitions feel
  smooth, which is exactly why it is hard to catch — each hop is small.

When using these tags, name the specific sentence or sentence pair that
exhibits the problem, not just the paragraph. The user needs to see
where the broken relationship is, not just that something is off.

## Severity scale

- `low`: one or two markers are present, but the prose still feels mostly
  authored
- `medium`: several markers stack together and the generated feel is visible
- `high`: the passage reads persistently formulaic, over-smoothed, or synthetic

## High-signal markers

- repeated self-framing such as `this project`, `the present project`,
  `this study`, `this framework`;
- repeated balancing templates such as `not X but Y`, `rather than`, `at the
  same time`, `however`, `therefore`;
- over-explanation of intent instead of direct argument;
- abstract summary language that avoids naming the concrete object;
- similar sentence length across an entire paragraph;
- every paragraph ending in a generic takeaway sentence;
- prose that is always polished but rarely surprising in phrasing.

## Common rewrites

- `The present project aims to identify...`
  -> `The analysis identifies...`

- `This framework allows the comparison of...`
  -> `The model compares...`

- `It is important to note that...`
  -> delete in most cases

- `This means that...`
  -> state the consequence directly

- `Rather than claiming X, the project seeks to show Y.`
  -> `The study tests Y under ...`

## Output modes

- `rewrite-only`: revised prose only
- `diagnose-only`: genre, severity, tags, and brief explanation
- `diagnose + rewrite`: default mode
- `before/after + rationale`: useful when the user wants transparency
- `minimal edit`: smallest viable cleanup
- `aggressive rewrite`: stronger restructuring for high-severity passages
- `line-by-line edit notes`: teaching mode for repeated patterns

## Optional controls

- `variance: off`: default
- `variance: light`: mild authored irregularity
- `variance: moderate`: stronger anti-template variation with formal tone

## Academic guardrails

- Keep formal syntax.
- Keep citations attached to the same claims unless they are misused.
- Keep hedging where evidence is conditional.
- Prefer precision over stylistic novelty.

## When not to over-correct

Do not aggressively de-template:

- notation-heavy modelling sections where standard phrasing is expected;
- method descriptions that need consistent terminology;
- passages already grounded in concrete results or case details.

The goal is not originality for its own sake. The goal is prose that sounds
authored rather than generated.
