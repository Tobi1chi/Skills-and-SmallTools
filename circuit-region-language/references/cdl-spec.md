# CDL Language Specification

Version: 2.0

## Overview

CDL (Circuit Description Language) is a human-AI co-design intermediate language
for describing circuits at component level. It uses a concise, line-oriented syntax
with three connection operators and structured block decomposition.

Design goals:

- Human-readable without tooling.
- AI-parseable without ambiguity.
- Mirrors the net-label paradigm used in KiCad / JLCEDA / Altium.
- Separates *understanding* (why) from *connections* (what) when needed.
- Produces a logical netlist that can be mapped to EDA imports.

---

## Formal Grammar

```
file         ::= header? block*
header       ::= "# " text NEWLINE
block        ::= block_header rail_decl* comp_decl* NEWLINE conn_stmt* param_stmt*
block_header ::= "## [" label "] " text NEWLINE
rail_decl    ::= "rail:" rail_name "=" voltage_v "@" current_ma
                 ("from:" refdes)? ("seq:" integer)? NEWLINE
comp_decl    ::= refdes WS partvalue (WS "(" package ")")? (WS '"' note '"')? NEWLINE
conn_stmt    ::= mount_stmt | signal_stmt | power_stmt
mount_stmt   ::= pin_ref WS "~~" WS net_name (WS '"' note '"')? NEWLINE
signal_stmt  ::= pin_ref WS "-->" WS pin_ref (WS "[" net_name "]")? (WS '"' note '"')? NEWLINE
power_stmt   ::= pin_ref WS "==" WS rail_name (WS '"' note '"')? NEWLINE
param_stmt   ::= refdes WS ":" WS param_list NEWLINE
special_stmt ::= refdes WS "!" WS special_kw (WS '"' note '"')? NEWLINE

pin_ref      ::= refdes "." pin_name
param_list   ::= param ("," WS param)*
param        ::= key "=" value
special_kw   ::= "NC" | "DNP" | "TP" | "OPT"

refdes       ::= [A-Za-z][A-Za-z0-9_]*
pin_name     ::= [A-Za-z0-9_/+-]+      # allows PA9, IN+, OUT-, SWDIO
net_name     ::= [A-Za-z][A-Za-z0-9_]* # no spaces, no special chars
rail_name    ::= [A-Za-z][A-Za-z0-9_V]* # GND, 3V3, VBUS, AGND, etc.
partvalue    ::= non-whitespace-string  # 100nF, AMS1117-3.3, STM32F103C8T6
package      ::= non-paren-string       # 0402, SOT-223, LQFP-48
label        ::= non-bracket-string     # 电源管理, MCU核心, 传感器
text         ::= any text to end of line
note         ::= any text excluding "
comment      ::= "//" any text to end of line   # full-line or end-of-line
```

### Character Rules

- Net names: start with letter, alphanumeric + underscore only. No spaces.
  Good: `I2C1_SCL`, `UART1_TX`, `OSC32_IN`. Bad: `I2C SCL`, `uart-tx`.
- Pin names: alphanumeric + `_`, `/`, `+`, `-`. Enables `IN+`, `OUT-`, `PA9`, `SWDIO`.
- PartValue: no spaces. Use `-` for multi-word parts: `AMS1117-3.3`, `ESP-12F`.
- Comments: `//` anywhere on a line. Rest of line is ignored.
- Blank lines: allowed anywhere, ignored by parser.

---

## Component Declarations

```
<RefDes>  <PartValue>  (<Package>)  "<Note>"
```

| Field | Required | Rules |
|---|---|---|
| RefDes | Yes | Standard designator: U1, C3, R12, Y1, J2, TP1 |
| PartValue | Yes | Value or MPN, no spaces |
| Package | No | Footprint hint for human reference |
| Note | No | Design **intent** — why, not what |

Notes capture intent, not description:
- Good: `"上拉，默认使能"` `"防MCU启动前误触发"` `"整条I2C总线唯一上拉"`
- Bad: `"10k电阻"` `"去耦电容"` `"NPN三极管"`

---

## Power Rail Declarations

```
rail: <RailName> = <voltage>V @ <current>mA  from: <RefDes>  seq: <n>
```

Declares a named power rail with its source, rating, and power-up sequence.
Use inside `[电源管理]` blocks. All other blocks reference the rail by name only.

```
rail: 3V3   = 3.3V @ 500mA   from: U2   seq: 1
rail: VBUS  = 5.0V @ 2000mA  from: J1   seq: 0   // USB input, seq 0 = first
rail: AGND  = 0V              from: GND  seq: 0   // analog ground island
```

`seq:` defines power-up order. Lower number = earlier. Used by review tools
to check sequencing constraints.

---

## Connection Operators

### `~~` Mount to Net

```
<RefDes>.<Pin>  ~~  <NetName>  "<Note>"
```

One pin joins a named net. Multiple `~~` lines with the same net name create
a multi-node net. This is the **primary** operator — use it by default.

Mirrors the net-label paradigm in KiCad/JLCEDA: connections are made by
sharing a net name, not by drawing wires between components.

```
X1.1   ~~  OSC32_IN
C10.1  ~~  OSC32_IN    // load capacitor on same net
U1.PC14 ~~ OSC32_IN   // MCU pin also on this net
```

### `-->` Directed Signal Intent

```
<RefDes>.<Pin>  -->  <RefDes>.<Pin>  [<NetName>]  "<Note>"
```

Declares the **primary direction and intent** of a signal. Implicitly creates
a net named `[NetName]` (or auto-named if omitted). Other pins may join the
same net using `~~` — the `-->` just declares which end is the driver.

`-->` answers "who drives this signal and who receives it". It does not mean
the net has exactly two nodes.

```
U1.PA9  -->  U3.RX  [UART1_TX]     // U1 drives, U3 receives
R2.2    ~~   ESP_EN                 // pull-up also on this net — valid
U1.PB0  ~~   ESP_EN                 // MCU also drives — annotate if needed
```

**Decision guide:**
```
Is there a clear driver → receiver relationship?   → use -->
Is it a shared bus / passive load / pull resistor? → use ~~
Are you unsure?                                    → use ~~, always safe
```

### `==` Connect to Power Rail

```
<RefDes>.<Pin>  ==  <RailName>  "<Note>"
```

Connects to a global power rail. Rail names are implicit nets available
everywhere without declaration. Use `rail:` in the power block to define them.

Standard rails: `GND`, `3V3`, `5V`, `VBUS`, `VBAT`, `VDD`, `AGND`, `PGND`

```
U1.VDD   ==  3V3
C1.2     ==  GND
U4.AGND  ==  AGND    // connects to analog ground island, not digital GND
```

---

## Special Component Annotations

```
<RefDes>  !  <keyword>  "<Note>"
```

| Keyword | Meaning |
|---|---|
| `NC` | No Connect — pin intentionally left unconnected |
| `DNP` | Do Not Populate — component on BOM as optional, not assembled by default |
| `TP` | Test Point — node exists for probing, no functional connection needed |
| `OPT` | Optional — component may be omitted depending on variant |

```
U1.PB1   !  NC     "reserved for future use"
R5       !  DNP    "only for debug variant, 0R jumper"
TP1      !  TP     "3V3 rail test point"
R6       !  OPT    "0R, only populate if external pull-up not present"
```

---

## Parameter Annotations

```
<RefDes>  :  <key>=<value>, <key>=<value>
```

Configuration values relevant for firmware or system integration.
Not electrical connections — do not use for pin assignments.

```
U3  :  baudrate=115200, mode=AT-command, firmware=v2.2.1
U4  :  i2c_address=0x68, odr=1kHz, int_polarity=active-low
U5  :  resolution=128x64, protocol=I2C
```

---

## Subsystem Decomposition

Decompose before writing CDL. Each subsystem → one `## [Label]` block.

### Standard Block Map

```
[电源输入]       Entry: connector, reverse protection, fuse, ESD clamp
     ↓ VBUS
[电源管理]       Regulation: LDO/DCDC, rail declarations, decoupling
     ↓ 3V3, GND, ...
[MCU核心]        Minimum system: crystal, reset, debug header, VDD decoupling
     ↓ GPIO, SPI, I2C, UART, ADC...
[传感器输入]     Sensors: I2C/SPI devices, pull-ups, decoupling
[通信接口]       Comms: UART modules, WiFi/BLE, level shifters
[执行输出]       Actuators: LED drivers, relays, motor drivers
[人机交互]       UI: buttons, displays, indicator LEDs
[存储]           Storage: SPI Flash, EEPROM, SD card
[对外连接器]     I/O: external signal/power connectors, ESD protection
```

### Three Decomposition Rules

**Rule 1 — Independent replaceability.**
If swapping A requires changing B, they belong in the same block.
If swapping A leaves B untouched, they are separate blocks.

**Rule 2 — 20-component ceiling.**
Any block exceeding 20 components should be split on functional boundary.
Example: split `[通信]` into `[通信-WiFi]` and `[通信-RS485]`.

**Rule 3 — Minimize cross-block signal count.**
Good decomposition: dense intra-block connections, ≤6 inter-block signals.
Power rails (`3V3`, `GND`) are global — do not count them as cross-block signals.

---

## Netlist Conversion Rules

CDL → logical netlist mapping:

| CDL construct | Logical netlist |
|---|---|
| Component declaration | RefDes + PartValue + Package |
| `A.pin ~~ NetName` | Pin A added to net NetName |
| `A.pin --> B.pin [NetName]` | Both pins added to net NetName |
| `A.pin --> B.pin` (no name) | Both pins added to `NET_A_pin` |
| `A.pin == RailName` | Pin A added to global net RailName |
| `A ! NC` | Pin marked no-connect in netlist |
| `A ! DNP` | Component flagged DNP in BOM |
| `U1 : k=v` | Component attribute annotation |

**Pre-conversion checklist (run before generating netlist):**
1. Every named net appears in at least 2 `~~` / `-->` statements
2. Net names are consistent across all blocks (same signal = same string)
3. No component appears in connections without a declaration
4. Every `-->` net name, if specified, matches any `~~` lines for that net
5. Power rails used in `==` are either standard names or declared via `rail:`

**EDA import note:**
The logical netlist uses human-readable pin names (e.g. `PA9`, `SWDIO`).
Importing into KiCad, JLCEDA, or Altium requires resolving these to
numeric pin numbers via the component's symbol definition. This mapping
is outside CDL scope and must be done at the EDA layer.

---

## Analog Understanding Layer (Optional)

For complex analog circuits, CDL supports optional understanding sections
between or after CDL blocks. These are written as prose or structured
comments and cover:

### Node Dictionary
Explains every significant internal node — what it is, why it exists,
expected voltage/impedance.

### Functional Paths
Traces signal/bias/reference flows through the circuit in reading order.

### Feedback / Control Loops
Identifies circular signal paths, polarity, what they control, stability.

### Functional Cells
Groups components into recognizable sub-functions (RC filter, voltage
divider, non-inverting amplifier).

### Operating Points
States expected DC voltage or current at key nodes under quiescent conditions.

These sections are **required** for analog/mixed-signal circuits and
**optional** for digital/power circuits.

---

## Common Mistakes

**Wrong: chain notation for shared bus**
```
// WRONG — implies two-node chain, hides that SCL is shared
U1.PB6  -->  R3.2
R3.2    -->  U4.SCL

// CORRECT — all three are nodes on the same net
U1.PB6  ~~  I2C1_SCL
R3.2    ~~  I2C1_SCL
U4.SCL  ~~  I2C1_SCL
```

**Wrong: inconsistent net names across blocks**
```
// Block [MCU核心]:    U1.PB6  ~~  I2C_SCL
// Block [传感器]:     U4.SCL  ~~  I2C1_SCL
// Result: two separate nets in netlist. Silent bug.
// Fix: agree on one name before writing, use it everywhere.
```

**Wrong: duplicate pull-ups on I2C bus**
```
// Block [传感器]:  R3  4.7k  ...  R3.2 ~~ I2C1_SCL
// Block [显示]:    R7  4.7k  ...  R7.2 ~~ I2C1_SCL
// Two pull-ups = 2.35k effective = too low for most buses.
// Fix: one pull-up per bus, annotate with "全板唯一".
```

**Wrong: missing NC annotation**
```
// WRONG — reader cannot tell if pin is intentionally unconnected
// or accidentally omitted

// CORRECT
U1.PB11  !  NC   "未使用，预留"
```

---

## Quick Reference

```
# Project name

## [SubsystemLabel] One-sentence intent

rail: RailName = xV @ ymA  from: RefDes  seq: n

RefDes  PartValue  (Package)  "Design intent note"
RefDes  :  param=value, param=value
RefDes  !  NC / DNP / TP / OPT  "note"

RefDes.Pin  ~~   NetName              mount to shared net
RefDes.Pin  -->  RefDes.Pin  [Net]    directed signal (net extensible via ~~)
RefDes.Pin  ==   RailName             connect to power rail

// comment

Standard rails: GND  3V3  5V  VBUS  VBAT  VDD  AGND  PGND
```
