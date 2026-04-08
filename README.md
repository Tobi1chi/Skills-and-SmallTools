# SmallTools Skills

This repository contains small public-facing Codex skills.

## Included Skills

- `de-ai-academic-prose`
  降低学术文本AI味并保留严谨性。
- `academic-paper-review`
  快速审阅论文结构论证与表达问题。
- `rewrite-by-example`
  参考示例风格重写文本并保持原意。
- `ngspice-matplotlib-plot`
  Run ngspice netlists and generate waveform plots with matplotlib.
- `fix-review-loop`
  Keep iterating on bug fixes with verify-and-review passes until the loop is
  clean or a real route choice requires user input.
- `profile-writing-style`
  Analyze writing samples and generate a reusable Markdown style profile.

## Structure

Each skill lives in its own folder and includes:

- `SKILL.md` for trigger rules and workflow instructions
- `agents/openai.yaml` for UI metadata when provided
- `references/` or `scripts/` only when the skill needs extra material

## Install

Install a skill from this repository with the `skills` CLI, for example:

```bash
npx skills add https://github.com/Tobi1chi/SmallTools --skill fix-review-loop
```
