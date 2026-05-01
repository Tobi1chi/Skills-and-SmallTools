# CDL Understanding Layer Guide

The understanding layer is optional for CDL syntax but useful when a circuit
description needs explanation beyond connectivity. Use it when the user asks for
explanatory analog or mixed-signal CDL, when the schematic has non-obvious
behavior, or when review would otherwise require mentally reconstructing the
circuit.

This guide is not a cookbook for analog design. It describes how to document
understanding in CDL-adjacent prose without prescribing a topology.

## Required When Requested

If the user asks for explanatory analog or mixed-signal CDL, include these
sections after the relevant CDL block or between blocks:

1. **Node Dictionary** — what named internal nodes represent.
2. **Paths** — how signals, bias, references, controls, or energy move in
   reading order.
3. **Loops** — feedback or control loops, polarity, and what they regulate or
   influence.
4. **Cells** — local groups of components that form a functional unit.
5. **Operating Points** — expected steady-state voltages, currents, states, or
   conditions when known.

If the user only asks for syntactic CDL or logical netlist conversion, these
sections are not required.

## Node Dictionary

Document nodes that have a purpose, expected state, high impedance, bias role,
reference role, summing role, or other non-obvious meaning.

Suggested format:

| Node | Role | Expected State | Notes |
|---|---|---|---|
| NODE_A | internal named node | `// CHECK` | explain only known facts |

Avoid turning the node dictionary into a design guide. If a node's role is not
known from the source, mark it `// CHECK`.

## Paths

Use paths to explain reading order, not physical current direction.

```
- name: PATH_A
  type: signal | bias | reference | control | protection | other
  trace: BOUNDARY_IN -> NODE_A -> NODE_B -> BOUNDARY_OUT
  note: Known behavior or // CHECK if uncertain.
```

## Loops

Document loops only when the source or user intent makes them identifiable.

```
- name: LOOP_A
  type: feedback | control | timing | protection | other
  trace: NODE_A -> component/path -> NODE_B -> return path
  polarity: positive | negative | unknown
  purpose: known purpose or // CHECK
```

Do not invent loop behavior from a generic circuit pattern.

## Cells

Cells group nearby components by observed or stated function.

```
- CELL_A [R1, C1, U1]: stated or observed function; // CHECK if uncertain
```

Cell names should come from the user's terminology, schematic labels, or clear
observed behavior. Avoid naming cells after assumed standard modules unless that
identity is known.

## Operating Points

Operating points are expected steady-state conditions. Include them only when
given, calculable from stated values, or obvious from source evidence.

| Location | Parameter | Value | Condition |
|---|---|---|---|
| NODE_A | voltage | `// CHECK` | condition unknown |

If a value requires datasheet assumptions or domain analysis not present in the
task, mark it unresolved instead of deriving a design-specific answer.

## Relationship To CDL

- Keep connectivity in CDL statements.
- Keep explanation in understanding-layer prose or tables.
- Do not replace connection statements with Markdown tables.
- Every unresolved explanation should correspond to a `// CHECK` or open
  question when it affects the CDL output.
