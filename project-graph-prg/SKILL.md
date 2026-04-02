---
name: project-graph-prg
description: Generate, inspect, validate, and overlap-check Project Graph `.prg` files from natural-language requirements or reference diagrams. Use when Codex needs to create a new `.prg`, modify an existing `.prg`, inspect a `.prg` archive, validate required nodes/edges/sections, or enforce a no-overlap layout for Project Graph diagrams.
---

# Project Graph PRG

Use this skill to turn user requirements or a reference image into a Project Graph `.prg` file and verify the result with deterministic local scripts.

Use Unicode text in generated content. Write JSON, Markdown, and script I/O as UTF-8.

## Quick Workflow

1. Read the user request and decide whether the task is:
   - inspect an existing `.prg`
   - generate a new `.prg`
   - edit an existing `.prg`
   - validate content expectations
   - check layout overlaps
2. If generating from prose or an image, translate the request into an intermediate JSON spec.
   - Use [references/spec-format.md](references/spec-format.md) for the supported object schema.
3. If editing an existing `.prg`, translate the request into a UTF-8 JSON edit patch.
   - Use [references/edit-patch-format.md](references/edit-patch-format.md) for selectors and edit operations.
   - Use [references/prompt-templates.md](references/prompt-templates.md) for prompt wording and output expectations.
4. Prefer the unified CLI [scripts/prg_cli.py](scripts/prg_cli.py) with `uv run --with msgpack --python 3.12 ...`.
   - The older single-purpose scripts are still available for compatibility.
5. After generation or edit, run validation in this order:
   - `validate_prg.py`
   - `validate_operation_links.py` when the graph contains logic/operator blocks such as `#ADD#` or `#DIV#`
   - `check_overlap.py` last
6. Inspect the validation results and decide whether repair is appropriate.
7. Repair logic before layout.
   - Run `auto_fix_operation_links.py` only for illegal operator-link problems.
   - Run `auto_fix_layout.py` only after logic is settled, because earlier repairs may change layout.
8. If validation still fails after repair, adjust the JSON spec or edit patch and retry instead of hand-editing the binary archive.

## Model Workflow Template

When using this skill, prefer to make the model follow this explicit workflow in the prompt instead of relying on a one-shot command:

1. Build or inspect the UTF-8 JSON/spec context first.
2. Run `prg_cli.py generate`, `prg_cli.py edit`, or `prg_cli.py inspect` as appropriate.
3. Run `prg_cli.py validate`.
4. If the graph contains operator blocks such as `#ADD#`, `#DIV#`, or `#SIN#`, run `prg_cli.py validate-op`.
5. Read the validation output and decide whether logic repair is appropriate.
6. If needed, run `prg_cli.py fix-op-links`, then re-run `prg_cli.py validate-op`.
7. Run `prg_cli.py overlap` last.
8. Read the overlap/spacing output and decide whether layout repair is appropriate.
9. If needed, run `prg_cli.py fix-layout`, then re-run `prg_cli.py overlap`.
10. Report what passed, what failed, and whether the final `.prg` is acceptable.

Do not auto-repair blindly. The model should inspect validation results first, then decide whether repair is safe.

## Scripts

The skill bundles these scripts in [scripts](scripts):

- [prg_cli.py](scripts/prg_cli.py): unified CLI entry point for inspect/generate/validate/overlap/fix flows
- [edit_prg.py](scripts/edit_prg.py): apply a semantic JSON patch to an existing `.prg`
- [generate_prg.py](scripts/generate_prg.py): create a `.prg` from a JSON spec
- [inspect_prg.py](scripts/inspect_prg.py): summarize archive contents, nodes, edges, sections, and drawings
- [validate_prg.py](scripts/validate_prg.py): verify archive structure and optional expected texts/sections/edges
- [check_overlap.py](scripts/check_overlap.py): detect overlapping rectangular blocks
- [auto_fix_layout.py](scripts/auto_fix_layout.py): shift overlapping blocks until no overlap remains or iteration limit is reached
- [validate_operation_links.py](scripts/validate_operation_links.py): enforce that operator blocks only reach other operator blocks through exactly one blank intermediate register node
- [auto_fix_operation_links.py](scripts/auto_fix_operation_links.py): repair direct operator-to-operator links by inserting one blank intermediate register node
- [prg_tools.py](scripts/prg_tools.py): shared `.prg` ZIP/msgpack helpers

Validation scripts and repair scripts are intentionally separate. Use the validation output to decide whether a repair script should run. Do not assume repair is always correct. Keep overlap detection and layout repair at the end of the workflow to avoid wasted layout work caused by earlier logic repairs.

Run them from the skill directory with relative paths.

## Commands

Generate:

```powershell
uv run --with msgpack --python 3.12 .\scripts\prg_cli.py generate spec.json out.prg
```

Edit:

```powershell
uv run --with msgpack --python 3.12 .\scripts\prg_cli.py edit input.prg patch.json edited.prg
```

Inspect:

```powershell
uv run --with msgpack --python 3.12 .\scripts\prg_cli.py inspect out.prg --limit 10
```

Validate:

```powershell
uv run --with msgpack --python 3.12 .\scripts\prg_cli.py validate out.prg
```

Validate expected content:

```powershell
uv run --with msgpack --python 3.12 .\scripts\prg_cli.py validate out.prg --expect expect.json
```

Check overlap after logic validation and any logic repair:

```powershell
uv run --with msgpack --python 3.12 .\scripts\prg_cli.py overlap out.prg --exclude-sections
```

The default clearance rule is `200px`. To make it stricter, for example `300px`:

```powershell
uv run --with msgpack --python 3.12 .\scripts\prg_cli.py overlap out.prg --exclude-sections --min-gap 300
```

Auto-fix layout at the end of the workflow:

```powershell
uv run --with msgpack --python 3.12 .\scripts\prg_cli.py fix-layout out.prg fixed.prg
```

Validate logic operator links:

```powershell
uv run --with msgpack --python 3.12 .\scripts\prg_cli.py validate-op logic.prg
```

Auto-fix logic operator links:

```powershell
uv run --with msgpack --python 3.12 .\scripts\prg_cli.py fix-op-links logic.prg fixed-logic.prg
```

Do not ignore containment overlap. If one block fully contains another block, that still counts as overlap.

## Generation Rules

- Build the `.prg` through the JSON spec, not by mutating msgpack manually.
- Use Unicode for node labels, section titles, and inserted helper text. Store JSON/reference files in UTF-8.
- Keep text blocks separated enough that `check_overlap.py` returns no overlaps.
- Leave overlap detection and layout repair until the end of the workflow, after logic and structural checks.
- If overlap exists at the final layout stage, prefer `auto_fix_layout.py` before manually repositioning objects.
- Prefer `TextNode`, `Section`, and `LineEdge` unless the user clearly needs `UrlNode`, `ImageNode`, `SvgNode`, `ConnectPoint`, `MultiTargetUndirectedEdge`, or `PenStroke`.
- If the user provides a reference image, preserve the logical structure first, then approximate layout.
- After generating from an image, explicitly tell the user the `.prg` is a reconstructed approximation, not a pixel-perfect import.

## Validation Rules

- Treat `validate_prg.py` failure as a hard failure.
- Treat any reported overlap as a layout failure unless the user explicitly allows overlap.
- Treat containment overlap as overlap. Do not disable that behavior.
- By default, treat `200px` edge-to-edge clearance as required. If the user specifies a different clearance rule such as "300px around each unit must stay empty", run `check_overlap.py` with `--min-gap 300` and treat any spacing violation as a failure.
- Treat any direct operator-to-operator link as invalid. Two operator blocks are only legal when they are separated by exactly one blank intermediate register node.
- Let the model decide whether to run `auto_fix_layout.py` or `auto_fix_operation_links.py` after reading validation output. Keep detection and repair as separate steps.
- When the user cares about exact content, create an `expect.json` file and run content validation.

## References

- [references/spec-format.md](references/spec-format.md): supported JSON generation schema
- [references/edit-patch-format.md](references/edit-patch-format.md): supported JSON edit patch schema
- [references/prompt-templates.md](references/prompt-templates.md): reusable prompt patterns for image-to-PRG and requirement-to-PRG tasks

## Portable Ideas From The App's Built-In AI Tools

The app's runtime AI tools live in `app/src/core/service/dataManageService/aiEngine/AITools.tsx`. The most useful ideas to port into this skill are the ones that do not depend on live UI state.

Good candidates for this headless `.prg` skill:

- regex search over text nodes
- parent/child graph queries
- direct connection checks between nodes
- breadth expansion from a node
- depth expansion from a node
- sort/reorder nodes by X or Y axis

Lower-value or non-portable runtime-only tools:

- current selection queries
- viewport queries
- tools that depend on what the user has selected in the open GUI

If you extend this skill further, prefer adding the portable graph-query and graph-edit capabilities before any GUI-state-dependent tool.
