# Example: UART Communication

```
## [通信] UART1 连接 ESP8266，PB0 控制模块使能

U3   ESP-12F  (SMD)    "WiFi 模块"
R2   10k      (0402)   "EN 上拉，模块上电即工作，无需 MCU 主动拉高"

U1.PA9   -->  U3.RX   [UART1_TX]
U1.PA10  -->  U3.TX   [UART1_RX]
U1.PB0   -->  U3.EN   [ESP_EN]    "MCU 可拉低复位模块"
R2.1     ==   3V3
R2.2     ~~   ESP_EN              // pull-up joins same net as --> above

U3.VCC  ==  3V3
U3.GND  ==  GND

U3  :  baudrate=115200, firmware=AT
```

## Notes

This example shows:
- `-->` for UART signals with clear driver/receiver direction
- `~~` to add pull-up resistor to same net created by `-->`
- Mixed use of `-->` and `~~` on the same net (ESP_EN)
- The `-->` declares intent (MCU controls EN), `~~` extends the net (pull-up)
- Parameter annotation for firmware configuration
