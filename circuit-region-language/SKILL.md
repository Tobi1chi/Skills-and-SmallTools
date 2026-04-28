---
name: circuit-region-language
version: 2.0
description: >
  Creates, explains, reviews, and converts human-readable text descriptions of
  circuits using CDL (Circuit Description Language). Use whenever the user wants to:
  design a circuit from requirements, analyze or explain an existing schematic,
  create a text-based circuit description that someone can draw from, generate a
  logical netlist, decompose a complex MCU system into CDL blocks, or review whether
  a circuit description is complete enough to draw. Also trigger when the user says
  "describe this circuit", "write CDL for this schematic", "let's design this
  subcircuit together", "convert my CDL to a netlist", "help me decompose this
  system into CDL blocks", "review my CDL", "check my circuit description",
  or when a user shares a schematic image and wants to produce a text description
  at component level.
  Do NOT trigger for: parsing .enet files (use jlceda-enet-parser instead),
  schematic design review against requirements (use schematic-review instead),
  or BOM/procurement tasks.
---

# CDL — Circuit Description Language

## What CDL Is

CDL is a **human-AI co-design intermediate language** for circuit descriptions.
It sits between natural language discussion and EDA entry:

```
Natural language intent
        ↓
    [CDL]           ← this skill operates here
        ↓
Logical netlist     ← CDL output, requires pin mapping to proceed
        ↓
EDA import          ← requires symbol/footprint library, outside CDL scope
```

CDL produces a **logical netlist**: component list + net topology using
human-readable pin names. Converting to an importable EDA netlist requires
a component pin-map (e.g. `PA9` → pin 30 in LQFP-48). CDL does not
provide or require that mapping — it is the responsibility of the EDA step.

**CDL is not:**
- A PCB layout description
- A SPICE simulation netlist
- A replacement for EDA tools
- A complete library mapping

## When to Use This Skill

1. User asks to **design** a circuit from natural-language requirements.
2. User asks to **describe** an existing schematic in text form.
3. User asks to **decompose** a complex MCU system into CDL blocks.
4. User asks to **review** whether a CDL description is complete and correct.
5. User asks to **convert** CDL into a logical netlist.
6. User shares a schematic image and wants a component-level text description.

## Language Reference

Read `references/cdl-spec.md` for the complete CDL formal grammar, operators,
and all syntax rules.

## Workflow Guide

Read `references/workflow.md` for the three design workflows:

- **Mode A** — Design from scratch
- **Mode B** — Describe existing schematic
- **Mode C** — Review CDL

## Analog Circuit Guide

Read `references/analog-circuit-guide.md` when the circuit involves op-amps,
references, sensor front-ends, feedback networks, compensation, or any
non-trivial analog signal chain. CDL supports an optional understanding layer
(Node Dictionary, Paths, Loops, Cells, Operating Points) for analog regions
that require deeper explanation beyond connections.

## Review Checklists

Read `references/review-checklists.md` before finalizing any CDL output.

## Examples

| Example | File |
|---|---|
| Crystal oscillator | `examples/crystal-oscillator.md` |
| Power management (LDO) | `examples/power-management.md` |
| I2C sensor with pull-ups | `examples/i2c-sensor.md` |
| UART communication | `examples/uart-comm.md` |
| Debug / SWD interface | `examples/debug-swd.md` |
| Analog front-end (sensor + op-amp) | `examples/analog-front-end.md` |

## Core Principles

1. **Use CDL syntax exclusively.** All circuit descriptions use `~~`, `-->`, `==`
   operators and the CDL block structure. Do NOT fall back to SRTL tables.
2. **Understanding first for analog.** Complex analog circuits get a logic layer
   (Node Dictionary, Paths, Loops) before connections. Simple digital can skip it.
3. **Drawable.** Output must be sufficient for a human to draw the complete circuit.
4. **Honest.** Unknown pins, uncertain values → mark with `// CHECK` comments.
5. **Subsystem decomposition.** Use `## [Label]` blocks to organize circuits.

## Behavior Rules

1. All connection descriptions use CDL operators: `~~` (mount to net), `-->` (directed signal), `==` (power rail).
2. Component declarations follow CDL format: `RefDes  PartValue  (Package)  "Note"`.
3. Power rails use `rail:` declarations in power blocks.
4. Parameters use `RefDes : key=value` syntax.
5. Special annotations use `RefDes ! NC/DNP/TP/OPT` syntax.
6. Never use Markdown tables for connection lists — use CDL statements.
7. For analog circuits, provide understanding layer sections as CDL comments or
   as prose sections between CDL blocks.
8. Every `// CHECK` comment should be listed in a final open-questions section.
9. Subsystem blocks follow the 20-component ceiling rule.
10. Net names must be consistent across all blocks (same signal = same string).

## What This Skill Does NOT Do

- Generate KiCad / Altium / JLCEDA project files.
- Produce PCB layout constraints or trace routing rules.
- Replace SPICE simulation.
- Act as a complete component library.
- Parse .enet files (use jlceda-enet-parser skill instead).
- Perform product-level schematic review (use schematic-review skill instead).
