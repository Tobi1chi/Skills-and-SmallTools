---
name: circuit-description-language
description: >
  Creates, explains, reviews, and converts human-readable text descriptions of
  circuits using CDL (Circuit Description Language). Use when the user wants to
  express circuit requirements or schematic information as CDL, decompose a
  circuit description into CDL blocks, review CDL syntax and completeness,
  convert CDL into a logical netlist, or generate the synchronized CSV BOM that
  mirrors the CDL component declarations. Also trigger on "describe this
  circuit", "write CDL", "convert CDL to netlist", "review my CDL", "check my
  circuit description", or when a schematic image needs a component-level text
  representation. This skill teaches CDL syntax and workflow only; it does not
  provide circuit design templates or prescribe how to implement specific
  modules. Do NOT trigger for parsing .enet files, product-level schematic
  design review, PCB layout, SPICE simulation, procurement, or EDA library
  mapping tasks.
---

# CDL — Circuit Description Language

CDL is a human-AI co-design intermediate language for circuit descriptions. It
sits between natural-language intent and EDA entry:

```
Natural language intent
        ↓
      CDL              ← this skill operates here
        ↓
Logical netlist        ← component list + net topology
        ↓
EDA import             ← requires symbol/pin/footprint mapping outside CDL
```

This skill defines CDL syntax and workflow only. It does not provide circuit
design templates, reference module implementations, component selection rules,
or product-level schematic review. When a task creates or updates a CDL file,
also create or update a synchronized CSV BOM unless the user explicitly declines
it.

## Read Order

- For syntax, operators, declarations, annotations, and netlist mapping, read
  `references/cdl-spec.md`.
- For task flow, decomposition, schematic extraction, review, and conversion,
  read `references/workflow.md`.
- Before finalizing or reviewing CDL, read `references/review-checklists.md`.
- For explanatory analog or mixed-signal descriptions, read
  `references/analog-circuit-guide.md`.
- For minimal syntax-only snippets, read `references/syntax-examples.md`.

## Scope

Use CDL to:

1. Turn requirements, schematic observations, or user discussion into a
   component-level text description.
2. Organize a circuit description into functional CDL blocks.
3. Represent connections with CDL operators and named nets.
4. Mark unresolved information explicitly with `// CHECK`.
5. Review CDL for syntax, consistency, and representational completeness.
6. Convert CDL into a logical netlist using human-readable pin names.
7. Generate a CSV BOM whose component rows are derived directly from CDL
   component declarations and whose `RefDes` values match the CDL exactly.

Do not use CDL to:

- Decide the correct circuit topology for a product.
- Replace datasheet work, domain engineering review, or `schematic-review`.
- Generate KiCad, Altium, JLCEDA, or other EDA project files.
- Produce PCB layout constraints or routing rules.
- Produce SPICE simulation netlists.
- Resolve symbol pin numbers, footprints, or library mappings.
- Choose purchasable part numbers, prices, suppliers, or procurement status for
  the synchronized BOM unless another skill or source supplies that information.
- Parse `.enet` files; use `jlceda-enet-parser` for that.

## Operating Rules

- Treat `references/cdl-spec.md` as the only authority for CDL syntax.
- Treat `references/workflow.md` as the authority for how to apply CDL in a
  task.
- When writing or changing CDL, keep the synchronized CSV BOM aligned with the
  final CDL component declarations: one row per CDL component RefDes, no merged
  RefDes cells, and variant/DNP/OPT status captured in fields rather than by
  omitting the component.
- If a circuit decision is not provided by the user, schematic, datasheet, or a
  separate domain review, mark it as `// CHECK` instead of inventing a module
  implementation.
- Never copy archived module examples as design templates. Archived examples
  are historical material only and are not part of the active skill path.
