# CDL Language Specification

Version: 2.1

CDL describes circuits at component level with line-oriented text. The language
captures components, named nets, power rails, annotations, and logical netlist
structure. It does not define domain-specific circuit topology.

## Formal Grammar

```
file            ::= header? block*
header          ::= "# " text NEWLINE
block           ::= block_header statement*
block_header    ::= "## [" label "] " text NEWLINE

statement       ::= rail_decl
                  | comp_decl
                  | conn_stmt
                  | param_stmt
                  | special_stmt
                  | comment
                  | blank

rail_decl       ::= "rail:" rail_name "=" voltage_v ("@" current_ma)?
                    ("from:" refdes)? ("seq:" integer)? NEWLINE
comp_decl       ::= refdes WS partvalue (WS "(" package ")")?
                    (WS '"' note '"')? NEWLINE
conn_stmt       ::= mount_stmt | signal_stmt | power_stmt
mount_stmt      ::= pin_ref WS "~~" WS net_name (WS '"' note '"')? NEWLINE
signal_stmt     ::= pin_ref WS "-->" WS pin_ref
                    (WS "[" net_name "]")? (WS '"' note '"')? NEWLINE
power_stmt      ::= pin_ref WS "==" WS rail_name (WS '"' note '"')? NEWLINE
param_stmt      ::= refdes WS ":" WS param_list NEWLINE
special_stmt    ::= special_target WS "!" WS special_kw
                    (WS '"' note '"')? NEWLINE

special_target  ::= refdes | pin_ref
pin_ref         ::= refdes "." pin_name
param_list      ::= param ("," WS param)*
param           ::= key "=" value
special_kw      ::= "NC" | "DNP" | "TP" | "OPT"

refdes          ::= [A-Za-z][A-Za-z0-9_]*
pin_name        ::= [A-Za-z0-9_/+-]+
net_name        ::= [A-Za-z][A-Za-z0-9_]*
rail_name       ::= [A-Za-z][A-Za-z0-9_V]*
partvalue       ::= non-whitespace-string
package         ::= non-paren-string
label           ::= non-bracket-string
text            ::= any text to end of line
note            ::= any text excluding "
comment         ::= "//" any text to end of line
blank           ::= empty line
```

## Character Rules

- Net names start with a letter and use only letters, digits, and `_`.
- Rail names start with a letter and use only letters, digits, `_`, and `V`.
- Pin names may use letters, digits, `_`, `/`, `+`, and `-`.
- Part values are single tokens. Use `-` or `_` when a value needs grouping.
- Comments start with `//`; the rest of the line is ignored by parsers.
- Blank lines are allowed anywhere.

## Component Declarations

```
<RefDes>  <PartValue>  (<Package>)  "Design intent note"
```

Required fields:

- `RefDes`: component designator such as `U1`, `R2`, `C3`, `J1`.
- `PartValue`: value or part identifier with no spaces.

Optional fields:

- `Package`: human footprint hint.
- `Note`: design intent or unresolved context, not a substitute for wiring.

## Power Rail Declarations

```
rail: <RailName> = <Voltage>V @ <Current>mA  from: <RefDes>  seq: <n>
```

Use `rail:` to define named power rails when the CDL needs rail metadata.
Other blocks reference rails by name with `==`.

- `from:` identifies the source component when known.
- `seq:` records power-up order when known; lower values come earlier.
- If voltage, source, current, or sequence is unknown, omit the field or add
  `// CHECK`.

## Connection Operators

### `~~` Mount To Net

```
<RefDes>.<Pin>  ~~  <NetName>  "optional note"
```

Adds one pin to a named net. Multiple `~~` statements with the same net name
form a multi-node net. Use this as the default connection operator when there is
no need to express driver/receiver intent.

### `-->` Directed Signal Intent

```
<SourceRef>.<Pin>  -->  <SinkRef>.<Pin>  [<NetName>]  "optional note"
```

Adds both pins to one net while documenting the primary signal direction. The
direction is intent metadata; it does not mean the net has exactly two nodes.
Additional pins may join the same net with `~~`.

If `[<NetName>]` is omitted, logical netlist conversion creates a generated
name from the source pin. Prefer explicit names when the net crosses blocks.

### `==` Connect To Power Rail

```
<RefDes>.<Pin>  ==  <RailName>  "optional note"
```

Adds the pin to a named power rail. Rails are logical nets with optional metadata
from `rail:` declarations.

## Parameter Annotations

```
<RefDes>  :  key=value, key=value
```

Use parameters for non-topological attributes relevant to integration or review.
Do not use parameters to replace connection statements.

## Special Annotations

```
<RefDes>      !  DNP  "optional note"
<RefDes>.<Pin> !  NC   "optional note"
```

Supported keywords:

- `NC`: intentionally not connected.
- `DNP`: component is not populated by default.
- `TP`: test point or probe point.
- `OPT`: optional variant-dependent component or connection.

Use component-level annotations for component status and pin-level annotations
for pin status.

## Block Decomposition

Each `## [Label]` block describes one coherent functional region. CDL does not
mandate a fixed set of product blocks.

Decompose using neutral rules:

- Put tightly coupled components in the same block.
- Split blocks that become too large to inspect reliably.
- Prefer boundaries where few named nets cross between blocks.
- Keep block labels descriptive but domain-neutral unless the user or schematic
  already provides domain labels.
- A block should normally stay under about 20 components; if it exceeds that,
  split on an actual functional boundary.

## Logical Netlist Mapping

| CDL construct | Logical netlist result |
|---|---|
| Component declaration | Component with RefDes, PartValue, Package, Note |
| `A.pin ~~ NET_X` | Add `A.pin` to net `NET_X` |
| `A.pin --> B.pin [NET_X]` | Add both pins to net `NET_X`; store direction intent |
| `A.pin --> B.pin` | Add both pins to a generated net name |
| `A.pin == RAIL_X` | Add `A.pin` to global net `RAIL_X` |
| `A.pin ! NC` | Mark pin as intentionally unconnected |
| `A ! DNP` | Mark component as not populated by default |
| `A : key=value` | Add component attribute annotation |

Logical netlists use human-readable pin names. EDA import requires symbol pin
mapping and footprint/library resolution outside CDL.

## Common CDL Mistakes

- Referencing a component that has no declaration.
- Placing the same pin on two different nets.
- Using different net names for the same intended signal.
- Leaving unresolved schematic details unmarked instead of adding `// CHECK`.
- Treating `-->` as a two-node-only connection.
- Using Markdown tables for connection lists instead of CDL statements.
- Embedding domain-specific design assumptions that were not supplied by the
  user, schematic, datasheet, or a separate review process.
