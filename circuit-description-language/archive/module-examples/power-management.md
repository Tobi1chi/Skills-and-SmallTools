# Example: Power Management

```
## [电源管理] USB 5V 经 LDO 降至 3.3V，单轨供全板

rail: VBUS  = 5.0V @ 500mA   from: J1   seq: 0
rail: 3V3   = 3.3V @ 300mA   from: U2   seq: 1

U2   AMS1117-3.3  (SOT-223)   "主 LDO"
C1   100nF        (0402)      "VBUS 入口去耦"
C2   10uF         (0805)      "LDO 输出滤波，提升瞬态响应"
C3   100nF        (0402)      "MCU VDD 本地去耦"

U2.IN   ==  VBUS
U2.GND  ==  GND
U2.OUT  ==  3V3
C1.1    ==  VBUS
C1.2    ==  GND
C2.1    ==  3V3
C2.2    ==  GND
C3.1    ==  3V3
C3.2    ==  GND
```

## Notes

This example shows:
- `rail:` declarations with voltage, current, source, and sequencing
- All connections use `==` since they connect to power rails
- Intent notes on capacitors explain *why* (去耦, 滤波), not *what* (100nF)
- `seq: 0` for input (first), `seq: 1` for regulated output (second)
