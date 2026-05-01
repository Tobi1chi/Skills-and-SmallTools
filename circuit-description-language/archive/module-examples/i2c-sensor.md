# Example: I2C Sensor with Pull-ups

```
## [传感器] MPU-6050 六轴 IMU，I2C 挂载，INT 接 PA0

U4   MPU-6050  (QFN-24)   "六轴 IMU"
R3   4.7k      (0402)     "I2C SCL 上拉，全板唯一，勿在其他块重复"
R4   4.7k      (0402)     "I2C SDA 上拉，全板唯一，勿在其他块重复"

U4.SCL  ~~  I2C1_SCL
R3.2    ~~  I2C1_SCL
R3.1    ==  3V3

U4.SDA  ~~  I2C1_SDA
R4.2    ~~  I2C1_SDA
R4.1    ==  3V3

U4.INT  -->  U1.PA0   [MPU_INT]   "中断，低电平有效"

U4.VCC  ==  3V3
U4.GND  ==  GND
U4.AD0  ==  GND    // I2C address = 0x68

U4  :  i2c_address=0x68, int_polarity=active-low, odr=1kHz
```

## Notes

This example shows:
- `~~` for shared I2C bus (multiple nodes on same net)
- `-->` for interrupt signal (clear driver → receiver)
- `==` for power rail connections
- Pull-up ownership annotated with "全板唯一" to prevent duplicates
- Parameter annotation for firmware-relevant configuration
- AD0 tied to GND with inline comment explaining the address consequence
