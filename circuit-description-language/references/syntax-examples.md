# CDL Syntax Examples

These examples demonstrate syntax only. They are not circuit design templates.
If this file conflicts with `cdl-spec.md`, `cdl-spec.md` wins.

## Block And Component

```cdl
## [BlockA] Neutral functional region with known components

U1  PART_A  (PKG_A)  "known role or intent"
R1  VALUE_A (PKG_B)  "known role or // CHECK"
```

## Rail Declaration And Power Connection

```cdl
rail: RAIL_MAIN = 3.3V @ 100mA  from: U1  seq: 1

U1.VDD  ==  RAIL_MAIN
U1.VSS  ==  RAIL_RETURN
```

## Mount To Shared Net

```cdl
U1.PIN_A  ~~  NET_A
R1.1      ~~  NET_A
J1.1      ~~  NET_A
```

## Directed Signal Intent

```cdl
U1.OUT  -->  U2.IN  [SIGNAL_OUT]  "direction intent only"
J1.2    ~~   SIGNAL_OUT           "additional node on the same net"
```

## Parameters

```cdl
U1  :  mode=MODE_A, address=VALUE_A
```

## Special Annotations

```cdl
U1.PIN_UNUSED  !  NC   "intentionally unconnected"
R2             !  DNP  "not populated by default"
TP1            !  TP   "probe point"
R3             !  OPT  "variant-dependent"
```

## Unknowns

```cdl
U3  PART_UNKNOWN  (PKG_UNKNOWN)  "function known, exact part // CHECK"
U3.PIN_X  ~~  NET_UNKNOWN        // CHECK: verify source pin name
```
