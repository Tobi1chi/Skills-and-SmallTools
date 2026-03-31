# Controlled Variance

Use this reference when the user wants the rewrite to feel less regular, less
templated, or less detectable as generated text.

## Purpose

The goal is not randomness for its own sake. The goal is to restore authored
texture where the prose remains too smooth, too evenly balanced, or too
predictable after a normal rewrite.

In technical abstracts, the most useful form of variance often comes from
preserving natural engineering-paper asymmetry rather than trying to sound
"creative". Real papers often keep a bit of local heaviness, uneven emphasis,
or implementation detail that makes the prose less uniformly polished.

## Levels

## `off`

- Default.
- Use standard good academic prose only.

## `light`

- Vary sentence length modestly.
- Break a few repeated transition patterns.
- Replace a small number of highly predictable framing moves with more direct
  phrasing.
- Preserve some natural roughness if the prose already contains concrete system
  detail.
- Best for most academic sections.

## `moderate`

- Use stronger sentence-shape variation.
- Reorder some information to avoid machine-smooth progression when meaning is
  preserved.
- Allow slightly more idiosyncratic but still formal phrasing.
- Let some sentences stay denser or more implementation-heavy when that reflects
  normal engineering prose rather than a polished summary template.
- Best reserved for expository prose, proposals, statements, and passages that
  still read too synthetic after a normal rewrite.

## Allowed moves

- Mix shorter and longer sentences.
- Vary clause openings instead of repeatedly front-loading transitions.
- Replace generic transitions with direct logical progression.
- Let one sentence carry more weight while the next stays brief.
- Use concrete nouns and verbs earlier in the sentence.
- Preserve occasional asymmetry when it improves naturalness.
- Split an overly efficient sentence into two when the prose needs more
  burstiness.
- Convert a pure noun list into a mixed phrase pattern when that sounds more
  authored.
- Add one brief explanatory sentence if it clarifies why a modelling choice,
  comparison basis, or result distinction matters.
- Relax rigid three-part conclusion symmetry when the paragraph otherwise reads
  too diagrammatic.
- Keep some concrete implementation markers, such as named test systems, bus
  counts, feeder descriptions, solver classes, or network pairings, when they
  give the prose a more grounded research-paper texture.
- Allow mild local unevenness: one sentence may be short and direct while the
  next is denser and more technical.
- Prefer a few concrete action verbs over a continuous run of abstract
  evaluative nouns.

## Common anti-template moves

- `The model places all three interventions on the same feeder, with shared
  operating assumptions, cost accounting, and evaluation metrics...`
  -> `All three interventions are placed on the same feeder. This keeps the
  comparison on a shared cost and operating basis...`

- `spatial concentration of demand, bottleneck location, travel time...`
  -> `how demand is concentrated spatially, where bottlenecks emerge, and how
  travel time affects dispatch...`

- `Mobile storage..., Fixed storage..., Network expansion...`
  -> allow one item to carry a contrastive setup and another to be stated more
  directly, rather than forcing identical sentence shells.

- A paragraph that is uniformly compressed and polished
  -> let one sentence carry implementation detail or operational setup without
  fully normalizing its rough edges, if those edges are still clear and
  professional.

## Signals from human-written technical abstracts

These are often worth preserving or reintroducing when the prose is becoming
too smooth:

- concrete system descriptors such as feeder size, bus counts, network names,
  or test-system pairings;
- slightly uneven sentence weight across the paragraph;
- direct contrasts that are informative but not perfectly parallel;
- implementation detail that feels a little bulky but still precise;
- wording that is correct and formal without sounding globally optimized.

## Forbidden moves

- Do not invent facts, examples, data, citations, or qualifications.
- Do not add typos, grammar mistakes, or fake awkwardness.
- Do not add slang, chatty tone, or journalistic flourish.
- Do not force novelty into notation-heavy or methods-heavy text.
- Do not make the prose obscure just to avoid regularity.
- Do not erase legitimate technical density when it is part of the genre and
  helps the text read like an actual engineering paper.

## When to avoid variance

- highly technical method descriptions;
- passages with dense notation;
- places where stable terminology matters more than rhythm;
- sections already grounded in specific results and natural sentence variety.

## Decision rule

If the prose is already specific and only mildly polished, keep variance `off`.
If the prose remains obviously over-smoothed after removing the major markers,
use `light`. Use `moderate` only when the user explicitly wants stronger
anti-template texture and the genre can tolerate it.

If a technical abstract already contains grounded system detail, avoid
"improving" it into uniformly elegant summary prose. That kind of polishing can
increase detector-facing signals even when the text becomes cleaner.
