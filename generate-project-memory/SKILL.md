---
name: generate-project-memory
description: Generate or update a durable project memory file for the current repository or workspace. Use when the user asks Codex to create project memory, summarize a codebase for future agents, capture repository conventions, write a memory file under ~/.codex/project-memory, refresh an existing project notes file, or preserve important context across projects.
---

# Generate Project Memory

## Purpose

Create a compact, durable Markdown memory file that future agents can read before working on the project. The memory should capture stable facts, conventions, workflows, and known caveats rather than a one-time task summary.

## Default Location

Prefer the global memory folder:

```text
~/.codex/project-memory/
```

Use `~/.codex/project-memory/index.md` as an index when it exists or when creating the first memory file. Name project files with lowercase hyphen-case, such as `mic-esp32.md` or `home-assistant-ai-agent.md`.

If the user explicitly asks for a project-local file, write to a local path such as `AGENT_MEMORY.md` or `docs/agent-memory.md`.

## Workflow

1. Identify the project root.
   - Use the current working directory by default.
   - Prefer the Git root when inside a Git repository.
   - Record the absolute path and repository remote if available.

2. Inspect project facts.
   - Read lightweight metadata first: `AGENTS.md`, `README*`, package manifests, build files, config files, CI files, docs indexes, and source tree names.
   - Use `rg --files` for file discovery.
   - Avoid reading large generated outputs, dependency folders, build artifacts, binary files, secrets, credentials, and `.env` files.

3. Run the helper script when useful.
   - Use `uv run <skill-dir>/scripts/scan_project_memory.py --project <path> --out <draft.md>`.
   - The script produces a draft from filesystem and Git metadata; review and improve it before presenting it as final.

4. Write or update the memory file.
   - Preserve still-valid information from an existing memory file.
   - Remove stale claims when the codebase contradicts them.
   - Mark uncertain items as `Needs verification` instead of guessing.
   - Keep the final memory concise enough to be read at the start of future tasks.

5. Update the index.
   - If writing under `~/.codex/project-memory/`, ensure `index.md` links the project name, path, and memory file.
   - Do not duplicate the whole memory in the index.

## Memory File Shape

Use this structure unless the project suggests something better:

```markdown
# Project Memory: <project name>

Last updated: YYYY-MM-DD
Project path: /absolute/path
Repository: <remote or "not detected">

## What This Project Is
- Stable one-paragraph description.

## How To Work Here
- Build, test, lint, run, and deploy commands.
- Required environment assumptions.

## Architecture Notes
- Main directories and responsibilities.
- Important data flows or integration points.

## Conventions
- Coding style, framework patterns, naming, branch/test habits.
- Instructions from AGENTS.md or other local guidance.

## Known Risks And Caveats
- Fragile areas, generated files, hardware/service assumptions, migration traps.

## Useful Entry Points
- Key files with short reasons.

## Open Questions
- Things future agents should verify before relying on them.
```

## Quality Bar

- Prefer facts that will still matter weeks from now.
- Do not include secrets, tokens, private keys, cookies, personal email contents, or raw credentials.
- Do not over-index on file listings; explain why files matter.
- Include exact commands only when discovered from project files or verified locally.
- If tests or commands were not run, say so in the memory or final response.
- Keep generated memory readable by another agent in under two minutes.
