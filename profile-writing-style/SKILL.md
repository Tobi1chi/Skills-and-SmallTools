---
name: profile-writing-style
description: Use when the user wants an AI to analyze one or more text files written by them and summarize their writing style into a Markdown document. Trigger on requests like "summarize my writing style", "analyze these samples and describe how I write", "extract my prose habits from these files", or "create a style profile from my writing".
---

# Profile Writing Style

Use this skill to infer a writer's recurring habits from text they provide and
turn those observations into a concise Markdown style profile. Focus on
describing actual tendencies, not on scoring quality or rewriting the samples
unless the user asks for that separately.

## Workflow

### 1. Build the sample set

- Prefer 3 to 10 files or excerpts written by the same person.
- If the user gives a directory, identify files that contain the writer's own
  prose and ignore generated files, bibliographies, logs, figures, and code.
- If the sample set mixes genres, state that clearly and group observations by
  genre when needed.

### 2. Read for recurring patterns

Look for patterns that repeat across the samples rather than isolated quirks.
Summarize only what is supported by multiple examples.

Check these layers:

- sentence shape: average sentence length, clause density, use of contrast or
  qualification, rhythm variation
- paragraph movement: topic sentence style, buildup, paragraph endings,
  tendency to summarise or restate
- argument style: directness, hedging, evidence handling, how claims are
  limited or framed
- vocabulary: concrete versus abstract nouns, repeated framing words,
  transition words, domain vocabulary
- meta-writing: how often the writer refers to the paper, report, or section
  itself instead of advancing the object-level claim
- tone: restrained, assertive, explanatory, defensive, formal, compressed, or
  expansive

### 3. Distinguish stable style from local noise

- Do not overfit to one chapter, one assignment, or one unusually edited file.
- Separate genuine style from genre constraints. For example, notation-heavy
  technical sections naturally sound more templated than discussion sections.
- If the samples appear heavily AI-assisted or heavily edited, say so as an
  uncertainty instead of pretending the profile is pure.

### 4. Produce a Markdown style profile

Write a Markdown document using the structure in
[references/style-profile-template.md](references/style-profile-template.md).

The profile should include:

- a short overview of the writer's overall prose character
- 5 to 10 concrete stylistic tendencies
- a short list of high-frequency habits or repeated constructions
- tensions or tradeoffs in the style, such as "clear but repetitive" or
  "careful but over-explained"
- a short "Strengths To Preserve" section
- a short "Risks To Watch" section
- optional "Operational Rules" if the user wants the profile reused later

### 5. Keep the output evidence-based

- Ground claims in patterns actually seen across the sample set.
- Use short quoted fragments only when helpful and keep them brief.
- Avoid vague labels like "good academic tone" unless you explain what creates
  that effect in the writing.
- Do not turn the profile into a rewrite request unless the user asks.

## Output Notes

- Default output file name: `writing-style-profile.md` unless the user names a
  different path.
- If the sample size is too small, say what can and cannot be inferred.
- If the user wants a reusable prompt or editing guide derived from the
  profile, add a final `Operational Rules` section.
