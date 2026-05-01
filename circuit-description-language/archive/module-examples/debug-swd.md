# Example: Debug / SWD Interface

```
## [调试] SWD 接口 + 测试点

J2   SWD_Header  (2.54mm-4P)   "调试烧录口"
TP1  TestPoint   (TP-1.0)      "3V3 电源测试点"
R7   0R          (0402)        "预留跳线，默认不焊"

U1.PA13  -->  J2.SWDIO   [SWDIO]
U1.PA14  -->  J2.SWDCLK  [SWDCLK]
J2.VCC   ==   3V3
J2.GND   ==   GND

TP1  !  TP    "用于量产测试夹具探针"
R7   !  DNP   "默认 DNP，调试时可短接两个子网络"

U1.PB11  !  NC   "该项目未使用，不接"
```

## Notes

This example shows:
- `-->` for debug signals (MCU drives debug header)
- Special annotations: `! TP`, `! DNP`, `! NC`
- Each annotation includes an intent note explaining the purpose
- Test point declared as component but marked `! TP`
- Unused MCU pin explicitly marked `! NC` to distinguish from omission
