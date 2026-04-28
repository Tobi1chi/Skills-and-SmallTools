# Analog Circuit Guide for CDL

## Table of Contents

1. [When This Guide Applies](#when-this-guide-applies)
2. [The Understanding Layer Is Mandatory](#the-understanding-layer-is-mandatory)
3. [Node Dictionary Best Practices](#node-dictionary-best-practices)
4. [Path Tracing](#path-tracing)
5. [Feedback Loop Documentation](#feedback-loop-documentation)
6. [Functional Cell Decomposition](#functional-cell-decomposition)
7. [Operating Point Estimation](#operating-point-estimation)
8. [Common Analog Region Patterns](#common-analog-region-patterns)
9. [Pitfalls and Anti-Patterns](#pitfalls-and-anti-patterns)

---

## When This Guide Applies

Read this guide whenever the region involves any of:

- Operational amplifiers (op-amps, instrumentation amps, comparators)
- Voltage references or precision bias networks
- Sensor signal conditioning (thermistor, strain gauge, photodiode, etc.)
- Analog filters (RC, active, Sallen-Key, etc.)
- Feedback networks (gain-setting, regulation, AGC)
- Compensation networks (frequency response shaping)
- Current mirrors or current sources
- Differential signal chains
- ADC/DAC analog front-ends or back-ends
- Any circuit where DC operating point, impedance, or bandwidth matter

For purely digital regions (GPIO, I2C, SPI, UART, reset logic), this guide
does not apply — use the simplified format from the language spec.

---

## The Understanding Layer Is Mandatory

For analog and mixed-signal regions, **never skip directly to the connection table.**

The purpose of CDL is to make the circuit understandable, not just parseable.
A connection table alone — even a correct one — does not help a reader understand
why a circuit works, how to verify it, or what happens if a component changes.

Required sections for analog regions:

1. **Node Dictionary** — what each internal node is and why it exists.
2. **Paths** — how signals, bias, and references flow through the circuit.
3. **Loops** — what feedback or control loops exist and what they control.
4. **Cells** — what functional sub-groups exist.
5. **Operating Points** — what voltages and currents to expect at quiescence.

Only after these sections does the Connection table appear.

---

## Node Dictionary Best Practices

### What to include

Every node that has a name, a purpose, or a non-obvious voltage:

| Include | Example |
|---|---|
| Bias points | VMID = Vcc/2 for single-supply AC coupling |
| Virtual grounds | Op-amp summing junction held at VREF by feedback |
| Feedback nodes | The node where the feedback resistor meets the inverting input |
| High-impedance nodes | Photodiode cathode, MOSFET gate bias |
| Reference voltages | VREF from a bandgap, divided reference |
| Summing junctions | Where multiple signals combine |
| Filter nodes | RC junction between filter stages |

### What NOT to include

- Power rails (they belong in Boundary Nodes / Rails)
- Ground (obvious, unless multiple ground domains)
- Simple component-to-component midpoints that have no design significance

### Format

```
| Node | Role | Expected Value | Impedance | Notes |
|------|------|----------------|-----------|-------|
| VMID | mid-rail bias | VCC/2 = 1.65V | low (set by divider) | decoupled by C3 |
| FB_SUM | feedback summing point | ≈ VREF | high (op-amp input) | HIGH-Z, guard |
| FILT_OUT | RC filter output | AC signal, DC = VMID | R1 output impedance | |
```

---

## Path Tracing

### Signal Path

Trace the main signal from input boundary to output boundary. Include every
component the signal passes through, in reading order.

```
- name: main_signal
  type: signal
  trace: SENSOR_IN → R_series → C_ac → FILT_OUT → U1.IN+(3) → U1.OUT(1) → R_out → AFE_OUT
  note: Sensor voltage, series-limited, AC-coupled, low-pass filtered,
        amplified by U1 in non-inverting configuration, output-buffered.
```

The `→` arrow means "reading order", NOT electrical current direction. In a
feedback amplifier, current flows both ways through the feedback resistor —
but the path still reads left to right for clarity.

### Bias Path

Trace how DC bias voltages are established:

```
- name: mid_bias
  type: bias
  trace: 3V3A → R3 → VMID → R4 → AGND
  note: Resistor divider sets VMID = VCC/2 = 1.65V. C3 decouples VMID
        to suppress noise. VMID biases the non-inverting input for
        single-supply operation.
```

### Reference Path

```
- name: voltage_ref
  type: reference
  trace: U2.OUT(VREF) → R_ref → VREF_LOCAL → C_ref → AGND
  note: U2 provides 1.250V reference. R_ref + C_ref filter high-frequency
        noise. VREF_LOCAL used by ADC and feedback divider.
```

### Protection Path

```
- name: input_clamp
  type: protection
  trace: SENSOR_RAW → D1(TVS, cathode to rail, anode to GND) → R_limit → SENSOR_IN
  note: D1 clamps voltage transients. R_limit restricts fault current to < 10mA.
```

### Compensation Path

```
- name: miller_comp
  type: compensation
  trace: U1.OUT(1) → C_comp → U1.IN-(2)
  note: Miller compensation capacitor. Reduces bandwidth to ensure phase
        margin > 45° with capacitive load.
```

### Do NOT use arrows for analog direction

Wrong:
```
SENSOR_IN ← R1 ← C1 ← U1.OUT    (implies current direction — misleading)
```

Right:
```
trace: SENSOR_IN → R1 → C1 → U1.IN+ → U1.OUT → AFE_OUT
note: Signal enters at SENSOR_IN, is filtered by R1+C1, amplified by U1.
```

---

## Feedback Loop Documentation

### Required fields

```
- name: <descriptive name>
  type: negative feedback | positive feedback | compensation | oscillation
  trace: <circular path>
  polarity: negative | positive
  sets: <what parameter is controlled>
  stability: <phase margin concern, compensation, dominant pole>
```

### Negative feedback (most common)

```
- name: gain_setting
  type: negative feedback
  trace: U1.OUT(1) → R_fb(R2) → FB_SUM → U1.IN-(2) → U1.OUT(1)
  polarity: negative (signal returns to inverting input)
  sets: closed-loop gain = 1 + R_fb/R_g = 1 + 100k/10k = 11 V/V
  stability: Unity-gain stable op-amp. No compensation needed for Av=11.
```

### Positive feedback (hysteresis, latch)

```
- name: comparator_hysteresis
  type: positive feedback
  trace: U1.OUT(1) → R_hyst(R5) → U1.IN+(3) → U1.OUT(1)
  polarity: positive (signal returns to non-inverting input)
  sets: hysteresis window = VCC × R_low / (R_hyst + R_low)
  stability: Intentionally regenerative — snap action.
```

### Regulator feedback

```
- name: ldo_regulation
  type: negative feedback
  trace: VOUT → R_upper(R1) → FB_NODE → R_lower(R2) → GND; FB_NODE → U1.FB(4)
  polarity: negative (rising VOUT raises FB, reduces drive)
  sets: VOUT = VREF × (1 + R1/R2)
  stability: Output capacitor ESR provides a zero. Check U1 datasheet for
             min/max ESR range and required Cout.
```

---

## Functional Cell Decomposition

Break the region into cells that a reader can understand independently.

### Good cells

| Cell name | Components | Function |
|---|---|---|
| input_filter | R1, C1 | RC low-pass, fc = 1/(2π×R1×C1) |
| bias_divider | R3, R4, C3 | Sets VMID = VCC/2, decoupled |
| gain_stage | U1, R2, R5 | Non-inverting amp, Av = 1 + R2/R5 |
| output_buffer | R_out, C_out | Output series resistor + DC block |

### Bad cells (too vague)

| Cell name | Components | Function |
|---|---|---|
| analog_stuff | U1, R1-R5, C1-C3 | Does the analog things |
| passives | R1, R2, R3, R4, R5 | All the resistors |

Cells should map to recognizable circuit patterns. If you can't name the
pattern, the cell boundary is probably wrong.

---

## Operating Point Estimation

State expected DC conditions at quiescence (no signal, steady state).

### What to include

```
| Location | Parameter | Value | Condition |
|----------|-----------|-------|-----------|
| VMID | voltage | 1.65V | VCC = 3.3V, no signal |
| U1.IN+ (pin 3) | voltage | 1.65V | Biased by VMID divider |
| U1.IN- (pin 2) | voltage | 1.65V | Virtual short from feedback |
| U1.OUT (pin 1) | voltage | 1.65V | No signal, output at bias point |
| U1 | supply current | 1.0 mA typ | From datasheet |
| R3 (bias) | current | 1.65V/100kΩ = 16.5µA | Through bias divider |
```

### When operating points matter

- Single-supply op-amp circuits (VMID matters).
- Sensor bias circuits (excitation current matters).
- Reference dividers (divider current vs load current).
- Current mirrors (reference leg current sets output).
- Regulators (quiescent current, dropout headroom).

---

## Common Analog Region Patterns

### Non-inverting amplifier with single supply

Cells: bias divider, AC coupling, gain stage, output coupling.
Key nodes: VMID, AC_IN, FB_SUM.
Loop: gain feedback (negative, sets Av).

### Inverting amplifier (dual supply)

Cells: input resistor, feedback resistor, summing junction.
Key nodes: SUM_JUNCTION (virtual ground at 0V).
Loop: gain feedback (negative, sets Av = -Rf/Rin).

### Sensor front-end (thermistor / RTD)

Cells: excitation source, sensor element (external), voltage divider or bridge,
amplifier, filter.
Key nodes: sensor node (varies with measurement), reference node.
Paths: excitation path, measurement path.
Constraints: excitation current (self-heating), input impedance, linearization.

### Voltage reference with filter

Cells: reference IC, RC filter, decoupling.
Key nodes: VREF_RAW (before filter), VREF_CLEAN (after filter).
Path: reference path from IC output through filter.
Constraints: load current budget, settling time, noise floor.

### Active low-pass filter (Sallen-Key)

Cells: input network (R, C), feedback capacitor, unity-gain buffer.
Key nodes: filter intermediate node.
Loop: positive feedback (sets Q and resonance).
Constraints: component matching for Q accuracy.

---

## Pitfalls and Anti-Patterns

### Anti-pattern: Connection table only

Wrong:
```
R1.1 → VCC, R1.2 → NODE_A, R2.1 → NODE_A, R2.2 → GND,
U1.3 → NODE_A, U1.1 → NODE_B, R3.1 → NODE_B, R3.2 → U1.2,
R4.1 → U1.2, R4.2 → NODE_A
```

This is technically complete but conveys zero understanding. The reader must
mentally simulate the circuit to figure out what it does.

### Anti-pattern: Directional arrows on analog nodes

Wrong:
```
VMID → U1.IN+     (implies VMID drives U1; actually both are at the same potential)
U1.OUT → R_fb → U1.IN-  (implies signal flows one way; actually feedback is bidirectional)
```

Right: Use arrows for reading order in paths, and state direction in the note.

### Anti-pattern: Fabricated pin numbers

Wrong:
```
U1.PIN_A → VCC    (made-up pin name because datasheet wasn't checked)
```

Right:
```
U1.?(V+) → VCC    CHECK: verify V+ pin number from datasheet
```

### Anti-pattern: Missing bias explanation

Wrong:
```
R3 = 100kΩ between VCC and U1.IN+
R4 = 100kΩ between U1.IN+ and GND
```

Right:
```
Bias divider (R3 + R4) sets VMID = VCC/2 = 1.65V at U1.IN+.
This provides the DC operating point for single-supply operation.
C3 (100nF) decouples VMID to reject power supply noise.
```

### Anti-pattern: Ignoring high-impedance nodes

Any node connected to an op-amp input, MOSFET gate, or ADC input with
impedance > 10kΩ should be noted as HIGH-Z. These nodes are sensitive to:
- PCB leakage current
- Flux residue
- Guard ring requirements
- Long trace routing

Always annotate: `HIGH-Z` in the node dictionary and connection table.
