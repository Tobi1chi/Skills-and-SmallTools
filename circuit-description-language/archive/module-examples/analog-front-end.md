# Example: Analog Front-End (Sensor + Op-Amp)

This example demonstrates CDL with the optional analog understanding layer.

```
## [模拟前端] 热电偶信号放大，单端输入，10倍增益，送 ADC

U1   OPA333   (SOT-23-5)   "零漂移运放，适合热电偶低频信号"
R1   10k      (0402)       "反馈上臂，与 R2 配合设置增益"
R2   1.1k     (0402)       "反馈下臂，G = 1 + R1/R2 ≈ 10"
R3   100k     (0402)       "输入限流，保护运放输入"
C1   100nF    (0402)       "输入滤波，与 R3 构成 ~16Hz 低通"
C2   100nF    (0402)       "运放电源去耦"
R4   100k     (0402)       "VMID 上臂，与 R5 构成中点偏置"
R5   100k     (0402)       "VMID 下臂"
C3   10uF     (0805)       "VMID 去耦，降低偏置噪声"

// 输入滤波
R3.1    ~~  SENSOR_IN
R3.2    ~~  AFE_FILT
C1.1    ~~  AFE_FILT
C1.2    ==  AGND

// 运放连接
U1.IN+  ~~  AFE_FILT
U1.IN-  ~~  FB_NODE
U1.OUT  ~~  AFE_OUT
U1.V+   ==  3V3A
U1.V-   ==  AGND

// 反馈网络
R1.1    ~~  AFE_OUT
R1.2    ~~  FB_NODE
R2.1    ~~  FB_NODE
R2.2    ~~  VMID

// 中点偏置
R4.1    ==  3V3A
R4.2    ~~  VMID
R5.1    ~~  VMID
R5.2    ==  AGND
C3.1    ~~  VMID
C3.2    ==  AGND

// 电源去耦
C2.1    ==  3V3A
C2.2    ==  AGND
```

## Analog Understanding Layer

### Node Dictionary

| Node | Role | Expected Value |
|------|------|----------------|
| SENSOR_IN | boundary input, raw thermocouple signal | 0–50 mV |
| AFE_FILT | filtered input, after RC low-pass | tracks SENSOR_IN, fc ≈ 16 Hz |
| FB_NODE | feedback summing point | ~VMID + (SENSOR_IN × G/(G+1)) |
| VMID | mid-rail bias, single-supply virtual ground | 1.65 V |
| AFE_OUT | amplified output to ADC | VMID + (SENSOR_IN × 10) |

### Paths

- **signal_main**: SENSOR_IN → R3 → AFE_FILT → U1.IN+ → U1.OUT → AFE_OUT
  Single-ended sensor signal, low-pass filtered, gained ×10 by U1.

- **bias_vmid**: 3V3A → R4 → VMID → R5 → AGND
  Resistive divider sets mid-rail bias for single-supply operation.

- **feedback**: U1.OUT → R1 → FB_NODE → R2 → VMID
  Negative feedback sets gain = 1 + R1/R2 ≈ 10.

### Loops

- **gain_feedback**: U1.OUT → R1 → FB_NODE (U1.IN-) → U1.OUT
  Type: negative feedback. Sets voltage gain ≈ 10.
  Polarity: negative (returns to inverting input).

### Cells

- **input_filter** [R3, C1]: First-order low-pass, fc = 1/(2π×100k×100n) ≈ 16 Hz.
- **gain_stage** [U1, R1, R2]: Non-inverting amplifier, G = 1 + 10k/1.1k ≈ 10.
- **bias_generator** [R4, R5, C3]: Mid-rail reference, VMID = 3V3A/2 = 1.65V.

### Operating Points

| Location | Parameter | Value |
|----------|-----------|-------|
| VMID | voltage | 1.65 V |
| AFE_OUT (quiescent) | voltage | 1.65 V |
| U1 | supply current | ~25 µA |
| R4-R5 divider | bias current | ~16.5 µA |

## Notes

This example shows how CDL handles analog circuits:
- All connections use `~~` (analog paths have no single driver)
- `==` only for power rail connections
- Understanding layer added after CDL block as structured prose
- Node Dictionary explains *every* significant internal node
- Paths trace signal flow in reading order (not electrical current direction)
- Feedback loop identified with polarity
- Operating points verify consistency (VMID = 3V3A/2 = 1.65V ✓)
