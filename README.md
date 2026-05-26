# SmallTools Skills

This repository collects small Codex skills and related setup tools. Most
top-level folders are installable skills with a `SKILL.md`; a few folders are
supporting guides or templates.

## Included Skills

| Skill | Purpose |
| --- | --- |
| `academic-paper-review` | Review engineering and quantitative academic manuscripts for structure, logic, evidence, and expression without rewriting the paper. |
| `circuit-description-language` | Create, review, explain, and convert Circuit Description Language (CDL) blocks for schematic description workflows. |
| `de-ai-academic-prose` | Diagnose or rewrite academic prose to reduce obvious AI-generated style while preserving technical meaning and citations. |
| `fix-review-loop` | Iterate through reproduce, fix, verify, and re-review cycles until a code issue is clean or a real decision point appears. |
| `generate-project-memory` | Generate or update durable project memory files for future agents, usually under `~/.codex/project-memory/`. |
| `ha-docker-yaml-sync` | Safely edit Home Assistant YAML files stored inside a running Docker container and copy them back. |
| `jlc-part-search` | Search JLC/LCSC/SZLCSC/JLCPCB/EasyEDA catalog data with a two-stage candidate/detail workflow. |
| `jlceda-enet-parser` | Parse JLCEDA Pro / EasyEDA Pro `.enet` netlists into component, BOM, network, power, and connectivity summaries. |
| `keats-course-downloader` | Download KEATS/Moodle course materials into section folders from a course URL plus cookie or Playwright auth-state file. |
| `maintain-project-docs` | Preserve useful conversation context in project docs such as `README.md`, `AGENTS.md`, `docs/`, runbooks, ADRs, or project memory. |
| `ngspice-matplotlib-plot` | Run `ngspice` `.cir` netlists and generate waveform plots from `wrdata` output with matplotlib. |
| `profile-writing-style` | Analyze writing samples and produce a reusable Markdown profile of the author's prose habits. |
| `project-graph-prg` | Generate, inspect, validate, edit, layout-check, and repair Project Graph `.prg` files. |
| `rewrite-by-example` | Calibrate academic de-AI rewriting from user-rewritten example sentences before applying the style to the rest of a manuscript. |
| `ssh-control` | Operate remote Linux/Unix hosts over SSH, including commands, persistent shells, and SFTP transfers. |
| `stm32-macos-makefile` | Configure or repair macOS STM32 Makefile workflows with clangd, OpenOCD, ST-Link, and helper shell setup. |

## Other Tools

| Folder | Purpose |
| --- | --- |
| `codex-new-machine-setup` | Structured macOS/Windows bootstrap guide and templates for preparing a new computer for daily Codex work. |

## Structure

Installable skills follow this layout:

- `SKILL.md` for trigger rules and workflow instructions.
- `agents/openai.yaml` for UI metadata when provided.
- `references/` for detailed docs that should be loaded only when needed.
- `scripts/` for deterministic helpers. Python helpers should be run with `uv`.
- `assets/` or `examples/` only when the skill needs reusable files.

## Install

Install a skill from this repository with the `skills` CLI:

```bash
npx skills add https://github.com/Tobi1chi/Skills-and-SmallTools --skill fix-review-loop
```

Replace `fix-review-loop` with any skill folder listed above.
