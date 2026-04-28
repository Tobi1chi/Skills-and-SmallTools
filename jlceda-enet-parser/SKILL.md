---
name: jlceda-enet-parser
description: 解析嘉立创EDA专业版（JLCEDA Pro / EasyEDA Pro）导出的 .enet 网表文件，提取元件列表、网络连接、BOM、电源分析等信息，并生成适合 AI 理解的结构化摘要。当用户上传或提及 .enet 文件、嘉立创网表、立创EDA网表、或询问 PCB 网络连接、元件清单时，必须使用此 skill。即使用户只说"帮我看一下这个网表"，也应触发此 skill。
---

# 嘉立创EDA .enet 网表解析 Skill

## 用途

帮助 Codex 理解和分析嘉立创EDA专业版（JLCEDA Pro）导出的 `.enet` 网表文件，执行以下任务：

- 提取元件列表与 BOM
- 分析网络连接关系
- 识别电源网络结构
- 生成元件间连接矩阵
- 汇总 LCSC 采购编号
- 生成 AI 友好的设计摘要

---

## 工作流程

### Step 1：读取文件

如果用户上传了 `.enet` 文件，先在当前可访问的工作区或附件目录中找到它。不要假设固定的系统路径。

```bash
find . -name '*.enet' -o -name '*.ENET'
```

如有必要，将文件复制到当前工作目录：
```bash
cp <path-to-file>.enet .
```

### Step 2：运行解析脚本

脚本位于本 skill 的 `scripts/parse_enet.py`

**核心用法：**

```bash
# 完整摘要（默认推荐）
uv run python scripts/parse_enet.py <file.enet> --mode summary

# AI 分析专用格式（简洁，适合后续提问）
uv run python scripts/parse_enet.py <file.enet> --mode ai

# 物料清单
uv run python scripts/parse_enet.py <file.enet> --mode bom

# 网络连接详情
uv run python scripts/parse_enet.py <file.enet> --mode nets

# 元件详情
uv run python scripts/parse_enet.py <file.enet> --mode components

# 电源网络分析
uv run python scripts/parse_enet.py <file.enet> --mode power

# 元件间连接关系
uv run python scripts/parse_enet.py <file.enet> --mode connectivity

# LCSC 编号汇总
uv run python scripts/parse_enet.py <file.enet> --mode lcsc

# 查看原始 JSON
uv run python scripts/parse_enet.py <file.enet> --json

# 过滤特定网络
uv run python scripts/parse_enet.py <file.enet> --mode nets --filter-net GND

# 过滤特定元件
uv run python scripts/parse_enet.py <file.enet> --mode components --filter-comp U1
```

### Step 3：根据用户需求呈现结果

| 用户需求                   | 推荐模式            |
|--------------------------|---------------------|
| 整体了解设计               | `summary` → `ai`    |
| 准备采购 / 备料            | `bom` + `lcsc`      |
| 检查某条网络是否连接正确   | `nets --filter-net` |
| 了解某芯片连了哪些信号      | `components --filter-comp` |
| 分析电源结构               | `power`             |
| 检查元件间连接关系          | `connectivity`      |
| 需要 AI 进一步分析         | `ai` 模式输出全量给当前对话中的模型 |

---

## 格式说明

如需了解 `.enet` 文件格式的详细规范，参阅：
`references/enet-format.md`

示例文件位于：
`assets/sample.enet`

---

## 常见分析任务示例

**Q: 这个设计用了哪些芯片？**
→ 运行 `--mode components`，筛选位号以 U 或 IC 开头的元件

**Q: 帮我生成采购清单**
→ 运行 `--mode bom` + `--mode lcsc`，整合输出

**Q: VCC 网络连到了哪些引脚？**
→ 运行 `--mode nets --filter-net VCC`

**Q: 帮我检查有没有单引脚网络（悬空信号）**
→ 运行 `--mode nets`，查找 `(1 个引脚)` 的网络

**Q: MCU 连到了哪些外设？**
→ 运行 `--mode connectivity --filter-comp U1`（结合 grep）

---

## 注意事项

- `.enet` 是 JSON 格式；如果文件无法解析，提示用户确认是否为嘉立创EDA**专业版**导出（标准版格式不同）
- `attributes` 字段为可选，部分字段（如 LCSC、制造商）可能缺失
- 自动生成的网络名通常以 `NET_` 开头，表示未命名信号
- 脚本依赖 Python 3 标准库，无需安装第三方包
