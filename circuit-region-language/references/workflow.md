# CDL Workflows

## Mode A — Design from Scratch

Use when: the user provides a natural-language requirement and wants a complete
circuit description.

### Step 1: Four Framing Questions

AI asks:
1. Where does power enter? (→ `[电源输入]`)
2. How many voltage rails? (→ `[电源管理]` complexity)
3. What does the MCU talk to? (→ peripheral blocks)
4. Where do signals ultimately go? (→ `[执行输出]`, `[对外连接器]`)

### Step 2: Decompose into Blocks

Use the standard block map and three decomposition rules (see cdl-spec.md).
Each subsystem → one `## [Label]` block.

### Step 3: Draft CDL per Block

For each block:
1. Write `rail:` declarations (power blocks).
2. List all component declarations with intent notes.
3. Write connection statements using `~~`, `-->`, `==`.
4. Add parameter annotations where relevant.
5. Mark special components with `!` annotations.

### Step 4: Analog Understanding Layer (if applicable)

For analog/mixed-signal blocks, add understanding sections:
- Node Dictionary — what each internal node is
- Functional Paths — signal/bias flow
- Feedback Loops — polarity, what they control
- Functional Cells — component sub-groups
- Operating Points — expected DC conditions

### Step 5: Human Review per Block

AI drafts CDL → human reviews → correct and confirm.

### Step 6: Cross-Block Consistency

Verify:
- Net names are consistent across all blocks (same signal = same string)
- No duplicate pull-ups on shared buses
- Power rails referenced in `==` are declared in `[电源管理]`
- Every `-->` net can be joined by `~~` from other blocks

### Step 7: Pre-Conversion Checklist

Run the five-point pre-conversion checklist (see cdl-spec.md) before
generating a logical netlist.

---

## Mode B — Describe Existing Schematic

Use when: the user shares a schematic image or verbal description and wants
CDL output.

### Step 1: Identify Subsystems

Look for visual groupings, dashed boxes, or functional areas in the schematic.
Map each to a `## [Label]` block.

### Step 2: Extract Components

For each block, list every component with designator, value, package, and
intent note. If values are not readable, mark with `// CHECK`.

### Step 3: Write Connections

Trace nets from the schematic:
- Shared nets → `~~` operator
- Driver-receiver pairs → `-->` operator
- Power/ground → `==` operator

### Step 4: Verify

Human checks:
- All components listed
- Net names match labels in schematic
- Operator choices (`~~` vs `-->`) match topology
- No missing connections

### Step 5: Iterate Until Agreed

---

## Mode C — Review CDL

Use when: the user provides CDL and wants it checked for completeness,
correctness, and consistency.

AI checks for:

### Errors (must fix)
- Undeclared components referenced in connections
- `-->` net name inconsistency with associated `~~` lines
- Net name conflicts across blocks (same signal, different names)
- `seq:` conflicts: a rail with seq N depends on a rail with seq > N

### Warnings (likely problems)
- Single-node nets (floating signal)
- Missing decoupling on MCU VDD pins
- I2C/1-Wire bus without pull-up
- Multiple pull-ups on same I2C bus
- Power rail used in `==` but not declared via `rail:`

### Suggestions (improvements)
- Missing intent notes on components
- Missing `! NC` on unused pins
- Block exceeding 20-component ceiling
- Missing parameter annotations for configurable ICs

### Output Format

Produce a review report with three categories:
- **Errors** — must fix before this description can be used.
- **Warnings** — likely problems that need attention.
- **Suggestions** — improvements for clarity or completeness.
