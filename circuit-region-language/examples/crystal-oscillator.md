# Example: Crystal Oscillator

```
## [时钟] 双晶振——16MHz 主时钟 + 32.768kHz RTC

X4   16MHz      (OSC-4P)   "主时钟晶振，确认引脚4为VCC非信号"
X1   32.768kHz  (C2-2P)    "RTC低速晶振"
C7   15pF       (0402)     "OSC_IN 负载电容"
C8   15pF       (0402)     "OSC_OUT 负载电容"
C9   15pF       (0402)     "OSC32_OUT 负载电容"
C10  15pF       (0402)     "OSC32_IN 负载电容"

// 16MHz 主时钟
X4.3  ~~  OSC_IN
C7.1  ~~  OSC_IN
X4.4  ~~  OSC_OUT
C8.1  ~~  OSC_OUT
C7.2  ==  GND
C8.2  ==  GND
X4.1  ==  GND
X4.2  ==  GND      // CHECK: confirm pin 2 = GND or OE#?

// 32.768kHz RTC 时钟
X1.1  ~~  OSC32_IN
C10.1 ~~  OSC32_IN
X1.2  ~~  OSC32_OUT
C9.1  ~~  OSC32_OUT
C10.2 ==  GND
C9.2  ==  GND
```

## Notes

This example shows:
- Two crystal oscillator sub-circuits in one block
- `~~` operator for all connections (crystals are passive, no driver/receiver)
- Load capacitors sharing nets with crystal pins via net names
- `// CHECK` comment for uncertain pin assignment
- Intent notes explaining design choices, not restating component values
