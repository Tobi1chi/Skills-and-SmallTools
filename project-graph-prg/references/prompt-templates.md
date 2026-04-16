# Prompt Templates

Use these patterns when applying the skill.

Assume the current working directory is the skill directory or the target project directory. Prefer relative paths in commands and artifacts. Use Unicode text in content and UTF-8 for all JSON/Markdown/script I/O.

Current CLI surface:

- `prg_cli.py inspect`
- `prg_cli.py classify`
- `prg_cli.py generate`
- `prg_cli.py layout`
- `prg_cli.py edit`
- `prg_cli.py validate`
- `prg_cli.py validate-op`
- `prg_cli.py overlap`
- `prg_cli.py fix-op-links`
- `prg_cli.py fix-layout`
- `prg_cli.py route-edge-crossings`

## Generate From Requirements

```text
Use $project-graph-prg to generate a Project Graph .prg file from these requirements.
Output path: <output>.prg
Requirements:
- <requirement 1>
- <requirement 2>
- <requirement 3>

Workflow:
1. Classify graph type before extracting nodes and edges. Write `graphIntent` with `primaryType`, `confidence`, `evidence`, `extractionFocus`, and `fallbackType`.
2. Use `graphIntent` to decide what entities, groups, and edge semantics to extract.
3. Build a UTF-8 JSON spec with `layoutPlan`.
4. Run `prg_cli.py classify spec.json` and compare script metrics with `graphIntent`.
5. If `hasCycles`, `density`, `component_count`, or `root_count` contradicts `graphIntent`, update `graphIntent/layoutPlan` and re-run classify.
6. Generate the .prg with `prg_cli.py generate` using the default `--layout auto`.
7. Run `prg_cli.py validate`.
8. If the graph contains logic operators like #ADD# or #DIV#, run `prg_cli.py validate-op`.
9. Read the structural and logic validation results.
10. If needed, run `prg_cli.py fix-op-links` and re-run logic validation.
11. Run `prg_cli.py overlap` last for geometry validation.
12. If needed, run `prg_cli.py fix-layout --min-gap 200` and re-run overlap validation.
13. After overlap passes, run `prg_cli.py route-edge-crossings` only if the user wants ConnectPoint-based edge routing or `routingPlan.insertConnectPoints` is true.

Constraints:
- Keep all labels Unicode-safe.
- Do not build objects first and infer layout later; `graphIntent` must guide extraction, grouping, edge semantics, and `layoutPlan`.
- Do not leave any overlapping blocks, including containment overlap.
- Default to `200px` edge-to-edge clearance. If the user requires a different clearance such as `300px around each unit`, run `prg_cli.py overlap --min-gap 300`.
- Treat generated text-node size as derived from text content. Do not trust placeholder width and height from the initial draft spec.
- Treat Section bounds as real geometry during the final overlap pass unless the user explicitly asks to exclude them.
- After overlap passes, check whether ConnectPoint insertion is enabled. If disabled, skip `prg_cli.py route-edge-crossings` and state that straight edge-through-block routing was intentionally not enforced.
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
1. Classify graph type before extracting nodes and edges. Write `graphIntent` with `primaryType`, `confidence`, `evidence`, `extractionFocus`, and `fallbackType`.
2. Use `graphIntent` to reconstruct the graph structure into a UTF-8 JSON spec with `layoutPlan`.
3. Run `prg_cli.py classify spec.json` and compare script metrics with `graphIntent`.
4. If `hasCycles`, `density`, `component_count`, or `root_count` contradicts `graphIntent`, update `graphIntent/layoutPlan` and re-run classify.
5. Generate the .prg with `prg_cli.py generate` using the default `--layout auto`.
6. Run `prg_cli.py validate`.
7. If the graph contains logic operators like #ADD# or #DIV#, run `prg_cli.py validate-op`.
8. Read the structural and logic validation results.
9. If needed, run `prg_cli.py fix-op-links` and re-run logic validation.
10. Run `prg_cli.py overlap` last for geometry validation.
11. If needed, run `prg_cli.py fix-layout --min-gap 200` and re-run overlap validation.
12. After overlap passes, run `prg_cli.py route-edge-crossings` only if the user wants ConnectPoint-based edge routing or `routingPlan.insertConnectPoints` is true.

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
8. Run `prg_cli.py overlap` last for geometry validation.
9. If needed, run `prg_cli.py fix-layout` and re-run overlap validation.
10. After overlap passes, run `prg_cli.py route-edge-crossings` only if the user wants ConnectPoint-based edge routing.

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
8. Run `prg_cli.py overlap` last for geometry validation.
9. Only if needed and safe, run `prg_cli.py fix-layout` and re-run overlap validation.
10. After overlap passes, run `prg_cli.py route-edge-crossings` only if the user wants ConnectPoint-based edge routing.

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
- whether any Section-bound overlap or spacing violation exists
- whether any straight `LineEdge` fully passes through a block
- whether any illegal direct operator-to-operator links exist
```

## Recommended Meta Prompt

```text
Use $project-graph-prg for this task.

Follow this workflow exactly:
1. For generation, classify graph type before extracting nodes and edges, then build `graphIntent`, typed extraction, `layoutPlan`, and `objects` in that order.
2. Run `prg_cli.py classify` on generated specs and reconcile metric conflicts before generation.
3. Use `prg_cli.py` subcommands, not ad hoc manual archive edits.
4. For edits, prefer a UTF-8 edit patch and `prg_cli.py edit` before considering regeneration.
5. Run structural validation before logic validation.
6. Run logic validation before overlap validation.
7. Keep overlap checking near the end, after structure and logic are stable.
8. After overlap passes, check whether ConnectPoint insertion is enabled before routing edge-through-block crossings.
9. Never auto-repair blindly. Read validation output first and decide whether repair is safe.
10. If repair would risk changing semantics, adjust the patch/spec and retry instead.
11. Return the final command sequence you ran, the validation status, and the output `.prg` path.
```
