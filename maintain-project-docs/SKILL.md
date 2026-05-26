---
name: maintain-project-docs
description: Maintain current project documentation from useful conversation context. Use when the user asks Codex to write newly discovered facts, decisions, commands, conventions, troubleshooting notes, or agent instructions into README, AGENTS.md, docs/, ADRs, runbooks, or project memory; when the user says to preserve, document, remember in docs, update docs from this discussion, or keep project documentation in sync with what was just learned.
---

# Maintain Project Docs

## Purpose

Keep project documentation current by extracting durable information from the conversation and writing it into the right project document with small, reviewable edits. Treat documentation as a maintained product, not a transcript.

## What Belongs In Docs

Preserve information when it is stable, project-specific, and useful to future contributors or agents:

- Confirmed build, test, lint, run, deployment, flashing, release, or debugging commands.
- Architecture decisions, module responsibilities, data flow, API contracts, schemas, protocols, and integration boundaries.
- Project conventions, coding patterns, naming rules, branch habits, review expectations, and local tool constraints.
- Environment assumptions, dependency versions, hardware requirements, service endpoints without secrets, and setup gotchas.
- Troubleshooting conclusions that were verified or strongly evidenced.
- User instructions that should persist for this project, especially when the user says to remember, document, or use it going forward.

Do not write:

- Raw chat summaries, temporary status, brainstorming that has not become a decision, or one-off debugging noise.
- Secrets, tokens, cookies, private keys, personal email/calendar content, account identifiers, or credentials.
- Guesses presented as fact. Mark uncertain items as `Needs verification` only when they are still valuable.
- Broad preferences that belong in global instructions rather than the current project.

## Workflow

1. Identify candidate facts from the latest conversation.
   - Extract only durable facts, decisions, commands, constraints, and caveats.
   - Separate verified facts from assumptions and open questions.

2. Inspect existing documentation.
   - Use `rg --files` first.
   - Look for `AGENTS.md`, `README*`, `docs/`, `CONTRIBUTING*`, `CHANGELOG*`, `adr/`, `decisions/`, runbooks, setup guides, and project memory files.
   - Read the smallest relevant documents before editing.

3. Route each fact to the correct document.
   - `AGENTS.md`: agent behavior rules, project-specific instructions, tool constraints, and collaboration expectations.
   - `README.md`: project purpose, quick start, common commands, installation, and basic usage.
   - `CONTRIBUTING.md`: contributor workflows, test expectations, review norms, commit conventions.
   - `docs/architecture.md`: structure, module boundaries, data flow, protocols, and system design.
   - `docs/runbook.md` or `docs/troubleshooting.md`: operational procedures, deployment, recurring failures, recovery steps.
   - `docs/decisions/ADR-YYYYMMDD-title.md`: important decisions with context, decision, consequences, and alternatives.
   - `~/.codex/project-memory/*.md`: agent-oriented working memory that should not become formal project documentation.

4. Edit conservatively.
   - Preserve the document's existing tone, headings, and level of detail.
   - Prefer adding to an existing relevant section over creating a new file.
   - Create a new document only when no appropriate target exists and the information is clearly durable.
   - Use small patches; do not rewrite whole documents unless explicitly asked.
   - Avoid duplicate content. If a fact already exists, refine it instead of adding another copy.

5. Validate the update.
   - Re-read the changed section.
   - Check links and heading anchors when changed.
   - Run formatting or documentation checks if the project already defines them and they are cheap.
   - If validation was not run, say that in the final response.

## Decision Rules

Ask the user before editing when:

- The target document is ambiguous and multiple locations would be reasonable.
- The update would create a new public-facing policy, design decision, or contributor requirement.
- The conversation contains sensitive or personal material that may need redaction.
- The edit would touch many files or restructure documentation.

Proceed without asking when:

- The user explicitly requested documentation maintenance.
- The target file is obvious.
- The edit is small, reversible, and based on clearly confirmed facts.

## ADR Shape

When creating an ADR, use this concise structure:

```markdown
# ADR YYYY-MM-DD: <Decision Title>

## Context
- What situation forced the decision.

## Decision
- The chosen approach.

## Consequences
- Expected benefits, tradeoffs, and follow-up work.

## Alternatives Considered
- Short notes only when alternatives were actually discussed.
```

## Final Response

Report:

- Which facts were preserved.
- Which files were changed.
- Anything intentionally skipped and why.
- Validation performed or not performed.
