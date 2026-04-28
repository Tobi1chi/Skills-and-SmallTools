# 嘉立创EDA Pro .enet 网表格式说明

## 概述

`.enet` 是嘉立创EDA（JLCEDA）专业版导出的专有网表格式，本质上是 **JSON 文件**。
导出路径：顶部菜单 → 文件 → 导出网表 → 类型选 `easyEDA Pro(.enet)`

---

## 顶层结构

```json
{
  "version": "1.0.0",
  "nets": [ ... ],
  "components": [ ... ]
}
```

| 字段         | 类型   | 说明                        |
|------------|------|-----------------------------|
| `version`  | 字符串 | 格式版本                    |
| `nets`     | 数组  | 网络连接列表                |
| `components` | 数组 | 元件列表                    |

---

## nets（网络）字段

每个 net 对象：
```json
{
  "name": "GND",
  "pins": [
    { "component": "U1", "pin": "7" },
    { "component": "C1", "pin": "2" }
  ]
}
```

| 字段      | 说明                                    |
|---------|-----------------------------------------|
| `name`  | 网络名（如 GND、VCC、NET_xxx 等）        |
| `pins`  | 连接到本网络的引脚列表                   |
| `pins[].component` | 元件位号（Designator），如 U1、R1 |
| `pins[].pin` | 引脚编号（字符串）                  |

常见电源网络命名规律：
- `GND` / `AGND` / `DGND` / `PGND` — 地
- `VCC` / `VDD` / `3V3` / `5V` / `12V` — 电源
- `VBAT` / `VREF` / `AVCC` — 特殊电源
- `NET_xxx` — EDA 自动生成的未命名网络

---

## components（元件）字段

```json
{
  "designator": "U1",
  "name": "STM32F103C8T6",
  "footprint": "LQFP-48_7x7mm_P0.5mm",
  "value": "STM32F103C8T6",
  "attributes": {
    "Manufacturer": "STMicroelectronics",
    "LCSC": "C8734",
    "Description": "32-bit ARM Cortex-M3 MCU"
  }
}
```

| 字段            | 说明                                          |
|---------------|-----------------------------------------------|
| `designator`  | 位号（Ref Des），如 U1、R1、C2                 |
| `name`        | 器件名（Device Name）                          |
| `footprint`   | PCB 封装名                                    |
| `value`       | 元件值（阻值、容值、型号等）                   |
| `attributes`  | 扩展属性，可选                                |
| `attributes.LCSC` | 嘉立创商城物料编号，以 C 开头             |
| `attributes.Manufacturer` | 制造商名称                       |
| `attributes.Description`  | 元件描述                         |

### 位号前缀约定（IPC 标准）

| 前缀 | 类型         | 示例            |
|------|------------|-----------------|
| R    | 电阻        | R1, R2          |
| C    | 电容        | C1, C3          |
| L    | 电感/磁珠  | L1              |
| U / IC | 芯片/IC  | U1, IC2         |
| J / CN / P | 连接器 | J1, CN2       |
| D    | 二极管      | D1              |
| Q    | 三极管/MOS  | Q1              |
| SW   | 开关        | SW1             |
| TP   | 测试点      | TP1             |
| FB   | 磁珠        | FB1             |
| Y / X | 晶振       | Y1              |

---

## 使用场景

1. **PCB 导入**：导出后导入 PCB，自动生成元件和飞线
2. **AI 辅助设计审查**：通过解析工具生成适合 AI 分析的文本摘要
3. **BOM 生成**：提取 LCSC 编号汇总采购清单
4. **连接检查**：验证网络连接是否符合预期

---

## 注意事项

- `.enet` 是嘉立创EDA**专业版**格式，与标准版 JSON 格式不同
- 部分旧版文件可能结构略有差异，解析时需容错
- `attributes` 是可选字段，不同导出设置下内容会有差异
- `pin` 字段始终是字符串类型（即使看起来是数字）
