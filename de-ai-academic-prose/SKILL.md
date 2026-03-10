---
name: de-ai-academic-prose
description: Use when the user wants academic writing rewritten to reduce obvious AI-generated style while preserving meaning, citations, technical accuracy, and formal tone. Trigger on requests like "remove AI tone", "make this sound human", "rewrite this thesis section naturally", or "check whether this sounds AI-written".
---

# De-AI Academic Prose

## Overview

Use this skill when academic text is technically correct but sounds overly
generated, templated, or mechanically balanced. The goal is to preserve the
claims, evidence, and formal register while reducing obvious AI-style prose
patterns.

Read [references/markers.md](references/markers.md) when the text is long or
when you need a concrete checklist of common AI-style markers and rewrite
strategies.

## Workflow

### 1. Diagnose before rewriting

Identify whether the problem is actually "AI tone" rather than weak content,
poor structure, or missing evidence. Focus on passages with:

- repeated framing phrases such as `this project`, `the present project`,
  `this framework`, `this means`, `therefore`, `however`;
- excessive meta-writing about the purpose of the text rather than direct
  argument;
- repetitive `not X but Y` or `rather than` constructions;
- uniformly balanced paragraph rhythm with low variation in sentence length;
- abstract nouns replacing concrete claims or specific objects;
- low-information summary sentences at the ends of paragraphs.

### 2. Preserve the non-negotiables

Do not change:

- technical meaning;
- mathematical notation or symbol definitions unless the user asks for it;
- citations, unless they are plainly wrong or missing;
- the strength of the claim, especially where hedging is deliberate;
- discipline-appropriate academic tone.

The task is not to make the writing casual. The task is to make it sound like
a real author wrote it.

### 3. Rewrite toward specificity

Prefer:

- concrete subjects over meta subjects;
- direct claims over self-explanation;
- specific system conditions, variables, constraints, and results over abstract
  umbrella nouns;
- varied sentence lengths and paragraph cadence;
- fewer transition words when logic is already clear.

Useful rewrite moves:

- Replace `This project / the present study` with the actual subject.
- Replace `This framework allows...` with a direct statement of what the model,
  method, or result does.
- Delete throat-clearing phrases such as `it is important to note that`.
- Delete paragraph-ending recap sentences that add no new information.
- Merge or split sentences to avoid a flat rhythm.

### 4. Keep the rewrite grounded

If the text is a literature review, preserve distinctions among cited works and
do not homogenize them into generic summary prose.

If the text is a modelling section, keep the notation and claim precision
intact. In technical sections, AI tone often comes from surrounding exposition,
not from the equations themselves.

If the text is a discussion or conclusion, be especially careful not to turn
conditional claims into broader claims than the evidence supports.

## Output Pattern

Unless the user asks for rewrite-only output:

1. Point out the strongest AI-style markers.
2. Rewrite the passage.
3. Briefly note what changed if that helps the user evaluate the edit.

When editing files directly, prefer local rewrites over whole-section
replacement unless the section is uniformly affected.

## Red Lines

- Do not introduce conversational or journalistic style.
- Do not add motivational filler or rhetorical flourish.
- Do not invent examples, results, or literature support.
- Do not remove necessary methodological caution.
