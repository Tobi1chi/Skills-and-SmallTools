# Prompt Templates

Use these patterns when applying the skill.

Assume the current working directory is the skill directory or the target project directory. Prefer relative paths in commands and artifacts. Use Unicode text in content and UTF-8 for all JSON/Markdown/script I/O.

Current CLI surface:

- `prg_cli.py inspect`
- `prg_cli.py generate`
- `prg_cli.py edit`
- `prg_cli.py validate`
- `prg_cli.py validate-op`
- `prg_cli.py overlap`
- `prg_cli.py fix-op-links`
- `prg_cli.py fix-layout`

## Generate From Requirements

```text
Use $project-graph-prg to generate a Project Graph .prg file from these requirements.
Output path: <output>.prg
Requirements:
- <requirement 1>
- <requirement 2>
- <requirement 3>

Workflow:
1. Build a UTF-8 JSON spec.
2. Generate the .prg with `prg_cli.py generate`.
3. Run `prg_cli.py validate`.
4. If the graph contains logic operators like #ADD# or #DIV#, run `prg_cli.py validate-op`.
5. Read the structural and logic validation results.
6. If needed, run `prg_cli.py fix-op-links` and re-run logic validation.
7. Run `prg_cli.py overlap` last.
8. If needed, run `prg_cli.py fix-layout` and re-run overlap validation.

Constraints:
- Keep all labels Unicode-safe.
- Do not leave any overlapping blocks, including containment overlap.
- Default to `200px` edge-to-edge clearance. If the user requires a different clearance such as `300px around each unit`, run `prg_cli.py overlap --min-gap 300`.
- The model must decide whether repair is safe before calling `prg_cli.py fix-op-links` or `prg_cli.py fix-layout`.
- Return the generated `.prg` path and the validation command sequence.
```

## Generate From Reference Image

```text
Use $project-graph-prg to recreate the logical structure of this reference image as a Project Graph .prg.
Output path: <output>.prg
Requirements:
- Preserve node labels and edge labels
- Approximate the original layout
- Keep text content as Unicode

Workflow:
1. Reconstruct the graph structure into a UTF-8 JSON spec.
2. Generate the .prg with `prg_cli.py generate`.
3. Run `prg_cli.py validate`.
4. If the graph contains logic operators like #ADD# or #DIV#, run `prg_cli.py validate-op`.
5. Read the structural and logic validation results.
6. If needed, run `prg_cli.py fix-op-links` and re-run logic validation.
7. Run `prg_cli.py overlap` last.
8. If needed, run `prg_cli.py fix-layout` and re-run overlap validation.

State clearly that the result is a logical reconstruction, not a pixel-perfect import.
The model must decide whether repair is safe before calling `prg_cli.py fix-op-links` or `prg_cli.py fix-layout`.
Return the generated `.prg` path and the validation command sequence.
```

## Modify Existing PRG

```text
Use $project-graph-prg to modify this existing .prg file: <input>.prg
Requested changes:
- <change 1>
- <change 2>

Workflow:
1. Inspect the current file first.
2. Build a UTF-8 edit patch JSON when the change can be expressed as semantic edits.
3. Prefer `prg_cli.py edit` over rebuilding the entire file when a local patch is safer.
4. Run `prg_cli.py validate`.
5. If the graph contains logic operators like #ADD# or #DIV#, run `prg_cli.py validate-op`.
6. Read the structural and logic validation results.
7. If needed, run `prg_cli.py fix-op-links` and re-run logic validation.
8. Run `prg_cli.py overlap` last.
9. If needed, run `prg_cli.py fix-layout` and re-run overlap validation.

Decision rule:
- Do not call repair commands automatically just because validation failed.
- Read the validation output first.
- Prefer `prg_cli.py edit` for local semantic edits and regeneration from spec for structural rewrites.
- Prefer regeneration from spec over unsafe repair when semantics may be damaged.
```

## Patch-First Edit

```text
Use $project-graph-prg to apply semantic edits to this existing .prg file: <input>.prg
Output path: <output>.prg
Requested changes:
- <change 1>
- <change 2>

Workflow:
1. Inspect the current `.prg` with `prg_cli.py inspect`.
2. Build a UTF-8 edit patch JSON that follows `references/edit-patch-format.md`.
3. Run `prg_cli.py edit`.
4. Run `prg_cli.py validate`.
5. If the graph contains logic operators like #ADD# or #DIV#, run `prg_cli.py validate-op`.
6. Read the structural and logic validation results.
7. Only if needed and safe, run `prg_cli.py fix-op-links` and re-run logic validation.
8. Run `prg_cli.py overlap` last.
9. Only if needed and safe, run `prg_cli.py fix-layout` and re-run overlap validation.

Constraints:
- Prefer local semantic edits over full regeneration when the user wants to preserve the existing graph.
- Use selectors that are stable enough to match exactly one intended object when possible.
- Return the patch path, the output `.prg` path, and the validation command sequence.
```

## Inspect Existing PRG

```text
Use $project-graph-prg to inspect this file: <input>.prg
Return:
- object counts
- key nodes and sections
- edge summary
- whether validation passes
- whether any overlap exists
- whether any illegal direct operator-to-operator links exist
```

## Recommended Meta Prompt

```text
Use $project-graph-prg for this task.

Follow this workflow exactly:
1. Inspect or build the UTF-8 JSON/spec input first.
2. Use `prg_cli.py` subcommands, not ad hoc manual archive edits.
3. For edits, prefer a UTF-8 edit patch and `prg_cli.py edit` before considering regeneration.
4. Run structural validation before logic validation.
5. Run logic validation before overlap validation.
6. Keep overlap checking at the end.
7. Never auto-repair blindly. Read validation output first and decide whether repair is safe.
8. If repair would risk changing semantics, adjust the patch/spec and retry instead.
9. Return the final command sequence you ran, the validation status, and the output `.prg` path.
```
