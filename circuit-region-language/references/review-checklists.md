# CDL Review Checklists

Use these checklists to verify a CDL document before finalizing.

---

## General Checks (all circuits)

- [ ] Every `## [Label]` block has a one-sentence intent description.
- [ ] Every component declaration has RefDes and PartValue.
- [ ] Every component referenced in connection statements is declared in its block.
- [ ] No component pin appears on two different nets (would mean a short circuit).
- [ ] Every named net appears in at least 2 `~~` / `-->` statements.
- [ ] Net names are consistent across all blocks (same signal = same string).
- [ ] Every `-->` net name matches any `~~` lines for the same net.
- [ ] Power rails used in `==` are either standard names or declared via `rail:`.
- [ ] Every `// CHECK` comment has a corresponding entry in open questions.
- [ ] Intent notes describe *why*, not *what* (design intent, not component description).

---

## Power Checks

- [ ] `rail:` declarations present for all non-standard rails.
- [ ] Input rail source is identified (`from:` field).
- [ ] Output rail voltage and current are documented.
- [ ] `seq:` ordering is consistent (no circular dependencies).
- [ ] Input/output capacitors are present with appropriate values.
- [ ] Enable (EN) pin default state documented.
- [ ] Feedback divider resistor values match intended output voltage.
- [ ] Thermal concerns noted if LDO has large dropout × current.

---

## Digital / Interface Checks

- [ ] `-->` used for signals with clear driver → receiver relationship.
- [ ] `~~` used for shared buses and passive loads.
- [ ] Open-drain signals (SDA, SCL, INT#) have pull-up with ownership noted.
- [ ] I2C nets: exactly one pull-up per line, annotated "全板唯一".
- [ ] Reset and enable pins: default state documented via pull-up/pull-down.
- [ ] Strap / configuration pins: default configuration stated.
- [ ] Decoupling capacitors present for every IC.
- [ ] UART: TX/RX labeling is from perspective of owning component.
- [ ] No two push-pull outputs drive the same net.

---

## Analog Checks

- [ ] Node Dictionary covers all non-trivial internal nodes.
- [ ] At least one signal path documented in Paths section.
- [ ] Feedback loops identified with polarity and what they control.
- [ ] Functional cells defined for major component groups.
- [ ] Operating points listed for bias nodes and active components.
- [ ] Operating points consistent with component values and rail voltages.
- [ ] High-impedance nodes annotated.
- [ ] Compensation components explained if present.
- [ ] No analog path uses `-->` to imply current direction (use `~~` for analog).

---

## Decomposition Checks

- [ ] Each block stays under 20-component ceiling.
- [ ] Blocks follow independent replaceability rule.
- [ ] Cross-block signal count ≤6 per block (excluding power rails).
- [ ] Power rails are global and not counted as cross-block signals.

---

## Special Annotation Checks

- [ ] All intentionally unconnected pins marked with `! NC`.
- [ ] DNP components have explanation of when/why to populate.
- [ ] Test points (`! TP`) placed on important nets.
- [ ] Optional components (`! OPT`) document conditions for population.

---

## Using These Checklists

### When designing (Mode A):
Run General + type-specific + Decomposition checks before finalizing.

### When describing (Mode B):
Run General + type-specific checks. Decomposition checks are advisory.

### When reviewing (Mode C):
Run ALL applicable checklists. Report findings as Errors, Warnings, or Suggestions.

| Finding type | Meaning |
|---|---|
| Error | Must fix. The document cannot be used as-is. |
| Warning | Likely problem. Should be investigated and resolved. |
| Suggestion | Would improve clarity or completeness, but not blocking. |
