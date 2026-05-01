# CDL Workflows

Use these workflows to apply CDL without turning the skill into a circuit design
cookbook. Domain-specific implementation choices must come from the user,
schematic evidence, datasheets, normal engineering reasoning, or a separate
schematic/design-review skill. CDL supplies representation and process.

## Mode A — Requirements To CDL

Use when the user describes a desired circuit or product and wants a CDL
description.

1. Capture requirements and known boundaries:
   - What external inputs, outputs, supplies, signals, and constraints are known?
   - Which parts, pins, rails, values, and interfaces are already specified?
   - Which details are unknown and need `// CHECK`?
2. Decompose into neutral functional blocks:
   - Use the user's product structure, schematic hierarchy, or actual coupling.
   - Do not impose a canned product block map.
   - Keep blocks small enough to review; split large blocks on real boundaries.
3. Draft CDL per block:
   - Declare rails only when rail metadata is known or useful.
   - Declare components with known values or mark unknowns with `// CHECK`.
   - Write connections using `~~`, `-->`, and `==` from `cdl-spec.md`.
   - Add parameters and special annotations only when they describe known facts.
4. Track unresolved choices:
   - Do not invent topology, values, pin names, part numbers, or module details.
   - Add a final open-questions list for every `// CHECK`.
5. Validate with `review-checklists.md` before finalizing.

## Mode B — Existing Schematic Or Description To CDL

Use when the user provides a schematic image, net description, or verbal circuit
description and wants CDL output.

1. Identify visible or stated blocks from the source material.
2. Extract components with designators, values, packages, and notes when visible.
3. Trace named nets and pin-level connections from the source.
4. Convert source evidence into CDL statements:
   - Shared nets use `~~`.
   - Directional signal intent uses `-->` only when direction is explicit or
     strongly implied by source context.
   - Power and reference rails use `==`.
5. Mark unreadable or uncertain information with `// CHECK`.
6. Produce open questions for unresolved items.

Do not fill gaps by copying historical examples or generic module patterns.

## Mode C — Review CDL

Use when the user provides CDL and wants it checked.

Review for CDL-level issues:

- Syntax and grammar conformance.
- Undeclared components referenced by connections.
- Pins assigned to conflicting nets.
- Single-node nets that may indicate omissions.
- Net naming consistency across blocks.
- Rail references missing declarations when rail metadata is required.
- Missing `// CHECK` tracking in open questions.
- Unclear or missing annotations for intentionally absent connections.
- Blocks that are too large or ambiguously scoped.

Do not perform product-level schematic review unless explicitly requested with a
separate review skill or domain-review scope. If the CDL reveals an electrical
risk, label it as a handoff item rather than making CDL syntax responsible for
the design decision.

## Mode D — CDL To Logical Netlist

Use when the user asks to convert CDL into a logical netlist.

1. Parse component declarations into a component list.
2. Convert `~~`, `-->`, and `==` statements into named nets.
3. Preserve direction intent from `-->` as metadata.
4. Preserve parameters and special annotations.
5. Report unresolved `// CHECK` items.
6. Stop at human-readable logical nets; do not resolve symbol pin numbers,
   footprints, or EDA library identifiers.

## Output Expectations

- CDL output should use CDL statements, not Markdown tables for connections.
- If the task is design-oriented, include open questions for unknown decisions.
- If the task is review-oriented, report Errors, Warnings, Suggestions, and
  Domain Review Handoffs where applicable.
- If the task is conversion-oriented, separate Components, Nets, Annotations,
  and Unresolved Items.
