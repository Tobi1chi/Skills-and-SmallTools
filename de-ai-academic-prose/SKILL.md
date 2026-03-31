---
name: de-ai-academic-prose
description: Use when the user wants academic writing rewritten or diagnosed to reduce obvious AI-generated style while preserving meaning, citations, technical accuracy, and formal tone. Trigger on requests like "remove AI tone", "make this sound human", "rewrite this thesis section naturally", "check whether this sounds AI-written", or "analyze this Markdown/LaTeX report for AI tone".
---

# De-AI Academic Prose

## Overview

Use this skill when academic text is technically correct but sounds overly
generated, templated, or mechanically balanced. The goal is to preserve the
claims, evidence, and formal register while reducing obvious AI-style prose
patterns.

This skill also supports whole-document triage for Markdown and LaTeX
manuscripts when the user wants structural statistics before rewriting.

Read [references/markers.md](references/markers.md) when you need a concrete
checklist of AI-style markers, diagnostic tags, severity levels, or output
mode guidance.

Read [references/genres.md](references/genres.md) when the passage belongs to a
specific genre such as an abstract, introduction, literature review,
methodology, discussion, conclusion, proposal, or statement.

Read [references/variance.md](references/variance.md) when the user wants the
rewrite to consider whether the prose needs more authored irregularity,
variation, or anti-detection texture.

For long documents or `.tex` inputs, use
[`scripts/analyze_academic_prose.py`](scripts/analyze_academic_prose.py) to:

- extract section content from LaTeX into normalized Markdown;
- compute whole-document and per-section word-frequency statistics;
- compute `section priority` and `marker density` for rewrite planning;
- generate a `rewrite queue` ordered by likely payoff;
- rank candidate AI-heavy sentences before rewriting;
- save a reusable Markdown or JSON report when the user wants artifacts.

## Workflow

### -1. Confirm screening parameters before analysis

Before running the analysis or assigning diagnostic tags, confirm the user's
preferences for de-AI work. If the user already stated these preferences in
the conversation, do not ask again; carry them into the next steps.

At minimum confirm or infer:

- scope: whole document, selected sections, or sentence-level cleanup;
- rewrite pressure: light, medium, or aggressive;
- tolerance for signposted academic English;
- soft discourse marker cap per paragraph;
- variance setting: `off`, `light`, or `moderate`;
- whether the user wants only diagnosis, a rewrite queue, or direct edits.

Keep this preference intake short. In Default mode, ask concise plain-text
questions only when the parameters are not already clear and guessing would
materially change the outcome.

Do not move on to rewriting when the user's intended meaning is still
ambiguous in a way that would materially affect style. If "remove AI tone"
could plausibly mean either light cleanup or aggressive de-templating, ask
first and wait for the answer instead of silently picking one.

These are blocking parameters for direct edits when unclear:

- how much signposting or connective language the user wants to keep;
- whether the user prefers authored smoothness or more compressed prose;
- whether the user wants diagnosis first or immediate rewriting.

Default assumptions when the user does not specify:

- rewrite pressure: `medium`
- variance: `off`
- signposted-English tolerance: `preserve comfortable signposting`
- soft discourse marker cap: `2` per paragraph
- mode: `diagnose-only` until rewrite preferences are clear

### 0. Start with data analysis

Default to document analysis before diagnosis whenever the input is more than a
short excerpt. Use the confirmed preference profile from Step `-1` to set the
analysis thresholds before you run the script or begin mental triage.

Use the script before diagnosis or rewriting when the input is:

- a whole report, dissertation chapter, or proposal;
- a `.tex` source file;
- a Markdown manuscript with multiple sections;
- a request for statistics, hotspots, or "which parts sound AI-written?"

Typical command pattern:

```bash
uv run python scripts/analyze_academic_prose.py /path/to/file.tex \
  --emit-markdown /tmp/extracted.md \
  --emit-report /tmp/analysis.md
```

If the environment does not use `uv`, run the script with the local Python
launcher required by that environment.

Use the report to decide:

- whether the problem is local or document-wide;
- which sections have the densest template language;
- which sections should be rewritten first;
- which sentences are best candidates for targeted rewriting;
- whether the section balance or sentence cadence looks suspiciously uniform.

Treat soft discourse markers more leniently than stronger template signals.
This includes words and phrases such as `however`, `moreover`, `overall`,
`therefore`, `furthermore`, `additionally`, `consequently`, `thus`,
`nevertheless`, `nonetheless`, `in addition`, and `on the other hand`.
Do not flag them just because they appear once. Instead, use the script's
paragraph-level cap and only treat them as a style problem when a paragraph
exceeds the configured limit. The default cap is two soft discourse markers
per paragraph, unless the user prefers an even more signposted style.

For short excerpts, still do a lightweight analysis mentally before assigning
diagnostic tags: note repeated phrases, sentence-shape uniformity, and whether
the paragraph ends in generic recap language.

### 1. Diagnose after the analysis pass

Use the analysis results to decide whether the problem is actually "AI tone"
rather than weak content, poor structure, or missing evidence.

Assign 2-4 diagnostic tags before you rewrite. Reuse the tag names from
[references/markers.md](references/markers.md). Typical tags include:

- `repetitive framing`
- `meta-writing`
- `template transitions`
- `abstract drift`
- `flat cadence`
- `generic recap`
- `over-balanced contrast`

Then assign a severity level based on both the local prose and the document
statistics:

- `low`: locally templated, but the passage mostly sounds authored;
- `medium`: the generated feel is noticeable across multiple sentences;
- `high`: the paragraph or section reads persistently formulaic or synthetic.

Focus on passages with:

- repeated framing phrases such as `this project`, `the present project`,
  `this framework`, `this means`, `therefore`, `however`;
- excessive meta-writing about the purpose of the text rather than direct
  argument;
- repetitive `not X but Y` or `rather than` constructions;
- uniformly balanced paragraph rhythm with low variation in sentence length;
- abstract nouns replacing concrete claims or specific objects;
- low-information summary sentences at the ends of paragraphs.

For this whole class of discourse markers, only escalate when the paragraph
frequency is high relative to the configured cap. A single well-placed use is
usually acceptable in academic prose, especially when the author naturally
prefers a more signposted English style.

### 2. Preserve the non-negotiables

Do not change:

- technical meaning;
- mathematical notation or symbol definitions unless the user asks for it;
- citations, unless they are plainly wrong or missing;
- the strength of the claim, especially where hedging is deliberate;
- discipline-appropriate academic tone.

The task is not to make the writing casual. The task is to make it sound like
a real author wrote it.

### 3. Identify the genre before choosing rewrite pressure

Determine the genre or closest local function of the passage. Use
[references/genres.md](references/genres.md) when the answer is not obvious.

At minimum distinguish among:

- abstract;
- introduction;
- literature review;
- methodology or modelling section;
- results;
- discussion or conclusion;
- proposal, statement, or application materials.

Adjust rewrite pressure to the genre:

- preserve standard phrasing more aggressively in methods and notation-heavy
  sections;
- preserve distinctions among cited works in literature reviews;
- keep scope, contribution claims, and evidence boundaries tight in abstracts,
  discussions, and conclusions;
- reduce polished-template rhetoric more aggressively in proposals and
  statements, while keeping formal tone.

### 4. Decide whether to add controlled variance

Treat variance as optional. Only apply it when the user asks for it directly,
when anti-detection concerns are explicit, or when the passage still feels too
uniform after a normal rewrite.

Use one of these settings:

- `off`: no deliberate irregularity beyond normal good writing;
- `light`: small cadence variation and a few less-predictable phrasings;
- `moderate`: more visible sentence-shape variation and stronger reduction of
  smooth template flow.

Do not use a stronger setting unless the user explicitly asks for it. Follow
[references/variance.md](references/variance.md) for allowed and forbidden
forms of variance.

When variance is enabled, prefer concrete anti-template moves over vague
"randomness":

- break overly even sentence rhythm;
- convert some noun-heavy lists into more natural phrasing;
- allow an occasional brief explanatory bridge sentence when it clarifies why a
  comparison or modelling choice matters;
- reduce perfectly symmetric conclusion patterns when the evidence does not
  require that symmetry.

### 5. Rewrite toward specificity

Prefer:

- concrete subjects over meta subjects;
- direct claims over self-explanation;
- specific system conditions, variables, constraints, and results over abstract
  umbrella nouns;
- varied sentence lengths and paragraph cadence;
- enough transition words to keep the prose comfortable to read.

Useful rewrite moves:

- Replace `This project / the present study` with the actual subject.
- Replace `This framework allows...` with a direct statement of what the model,
  method, or result does.
- Delete throat-clearing phrases such as `it is important to note that`.
- Delete paragraph-ending recap sentences that add no new information.
- Merge or split sentences to avoid a flat rhythm.
- Keep helpful connective language when it genuinely guides the reader.
- Remove only redundant, stacked, or overly formulaic transitions.

Do not optimize for the fewest possible connectives. The goal is natural,
authored readability, not stripped-down minimalism.

Match the intensity of the rewrite to the severity:

- `low`: make local edits, keep most sentence structure, and remove only the
  clearest markers;
- `medium`: rewrite sentences more directly and vary cadence where multiple
  markers interact;
- `high`: rebuild the paragraph around its actual claims, while preserving all
  evidence, notation, and citation logic.

If variance is enabled, introduce it through rhythm, clause structure,
information order, and selective lexical variation, not through invented
content or fake specificity.

### 6. Keep the rewrite grounded

Apply genre-specific guardrails from
[references/genres.md](references/genres.md). When in doubt, be conservative in
methods and more interventionist in expository prose around the methods.

## Output Pattern

Pick the output mode that best matches the user request. If the user does not
specify one, default to `diagnose + rewrite`.

Supported modes:

1. `rewrite-only`
2. `diagnose-only`
3. `diagnose + rewrite`
4. `before/after + rationale`
5. `minimal edit`
6. `aggressive rewrite`
7. `line-by-line edit notes`
8. `document triage + rewrite plan`

Mode guidance:

- `rewrite-only`: return only the revised passage.
- `diagnose-only`: report the genre, severity, and strongest diagnostic tags
  without rewriting.
- `diagnose + rewrite`: briefly state genre, severity, and 2-4 tags, then
  rewrite.
- `before/after + rationale`: show original and revision, then briefly explain
  the main changes.
- `minimal edit`: keep sentence structure as intact as possible while removing
  high-signal markers.
- `aggressive rewrite`: rebuild the prose more substantially, but keep claims,
  support, and tone stable.
- `line-by-line edit notes`: useful when the user wants to learn the pattern of
  edits rather than just receive a polished rewrite.
- `document triage + rewrite plan`: run the file analysis workflow first, then
  report section stats, recurring markers, and the highest-priority passages to
  rewrite.

Optional controls:

- `variance: off | light | moderate`
- If not specified, default to `off`.
- When variance is enabled, briefly state whether it was applied and at what
  level unless the user asks for rewrite-only output.

Unless the user asks for rewrite-only output, include:

1. analysis summary first;
2. genre;
3. severity;
4. 2-4 diagnostic tags;
5. variance setting when used;
6. the rewrite or analysis requested by the chosen mode.

The analysis summary should lead with:

1. genre;
2. file type (`.md` or `.tex`) when relevant;
3. total word count and main-section balance for long documents;
4. `section priority`, `marker density`, and the top of the `rewrite queue`;
5. the most frequent content words or phrases;
6. the top candidate AI-heavy sentences and why they were flagged.

When the script is used, also include:

1. the path to the generated Markdown extraction when one was produced;
2. the path to the generated report when one was produced.

When editing files directly, prefer local rewrites over whole-section
replacement unless the section is uniformly affected.

## Red Lines

- Do not introduce conversational or journalistic style.
- Do not add motivational filler or rhetorical flourish.
- Do not invent examples, results, or literature support.
- Do not remove necessary methodological caution.
- Do not simulate "human randomness" by adding errors, false citations, or
  unsupported detail.
