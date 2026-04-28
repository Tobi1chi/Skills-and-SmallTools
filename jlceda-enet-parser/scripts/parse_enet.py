#!/usr/bin/env python3
"""
嘉立创EDA专业版 .enet 网表文件解析器
JLCEDA Pro .enet Netlist Parser

用途: 解析 .enet 文件并输出适合 AI 理解的结构化摘要。
Usage: python parse_enet.py <file.enet> [options]

Options:
  --mode summary       输出完整设计摘要（默认）
  --mode bom           输出物料清单（BOM）
  --mode nets          仅输出网络连接信息
  --mode components    仅输出元件列表
  --mode power         输出电源网络分析
  --mode ai            输出专为 AI 优化的简洁格式
  --mode connectivity  输出元件间连接关系矩阵
  --json               以 JSON 格式输出
  --filter-net <名称>  只显示特定网络
  --filter-comp <标识符> 只显示特定元件
  --lcsc               输出嘉立创元件编号汇总
"""

import json
import sys
import argparse
from collections import defaultdict
from typing import Any


def load_enet(filepath: str) -> dict:
    """加载并解析 .enet 文件（JSON 格式）"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError as e:
        print(f"[错误] 文件格式无效，不是合法的 JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"[错误] 找不到文件: {filepath}", file=sys.stderr)
        sys.exit(1)


def get_nets(data: dict) -> list:
    return data.get("nets", [])


def get_components(data: dict) -> list:
    return data.get("components", [])


def build_component_index(components: list) -> dict:
    """以 designator 为 key 建立元件索引"""
    return {c["designator"]: c for c in components}


def build_net_index(nets: list) -> dict:
    """以 net name 为 key 建立网络索引"""
    return {n["name"]: n for n in nets}


def component_nets(nets: list) -> dict[str, list[str]]:
    """返回每个元件连接的网络列表: {designator: [net_name, ...]}"""
    result = defaultdict(list)
    for net in nets:
        for pin in net.get("pins", []):
            result[pin["component"]].append(net["name"])
    return dict(result)


# ─── 输出模式 ──────────────────────────────────────────────────────────────


def mode_summary(data: dict) -> str:
    nets = get_nets(data)
    components = get_components(data)
    comp_idx = build_component_index(components)
    comp_net_map = component_nets(nets)

    lines = []
    lines.append("=" * 60)
    lines.append("  嘉立创EDA 网表摘要 / JLCEDA Netlist Summary")
    lines.append("=" * 60)
    lines.append(f"版本 (Version)  : {data.get('version', 'N/A')}")
    lines.append(f"元件总数        : {len(components)}")
    lines.append(f"网络总数        : {len(nets)}")

    # 统计元件类型
    type_count = defaultdict(int)
    for c in components:
        prefix = "".join(filter(str.isalpha, c["designator"]))
        type_count[prefix] += 1
    lines.append("\n【元件类型统计】")
    for prefix, count in sorted(type_count.items()):
        lines.append(f"  {prefix:<8}: {count} 个")

    # 电源网络识别
    power_keywords = {"GND", "VCC", "VDD", "VSS", "3V3", "5V", "12V", "VBAT", "VREF", "AGND", "DGND", "PGND"}
    power_nets = [n["name"] for n in nets if any(kw in n["name"].upper() for kw in power_keywords)]
    if power_nets:
        lines.append(f"\n【识别到的电源网络】")
        for pn in power_nets:
            pin_count = len([n for n in nets if n["name"] == pn][0].get("pins", []))
            lines.append(f"  {pn:<20} ({pin_count} 个引脚连接)")

    # 元件详情
    lines.append("\n【元件列表】")
    lines.append(f"  {'位号':<8} {'名称':<24} {'封装':<30} {'值'}")
    lines.append("  " + "-" * 80)
    for c in sorted(components, key=lambda x: x["designator"]):
        lines.append(f"  {c['designator']:<8} {c['name']:<24} {c.get('footprint',''):<30} {c.get('value','')}")

    # 网络详情
    lines.append("\n【网络连接】")
    for net in sorted(nets, key=lambda x: x["name"]):
        pins = net.get("pins", [])
        pin_str = ", ".join(f"{p['component']}.{p['pin']}" for p in pins)
        lines.append(f"  {net['name']:<24} → {pin_str}")

    return "\n".join(lines)


def mode_bom(data: dict) -> str:
    components = get_components(data)

    # 按 name+footprint+value 合并
    bom: dict[tuple, list] = defaultdict(list)
    for c in components:
        key = (c["name"], c.get("footprint", ""), c.get("value", ""))
        bom[key].append(c)

    lines = []
    lines.append("BOM (物料清单) — 嘉立创EDA 网表")
    lines.append("-" * 70)
    lines.append(f"{'数量':<6} {'名称':<22} {'值':<12} {'封装':<28} {'LCSC编号':<12} {'位号'}")
    lines.append("-" * 70)

    for (name, footprint, value), comps in sorted(bom.items()):
        designators = ", ".join(c["designator"] for c in sorted(comps, key=lambda x: x["designator"]))
        lcsc = comps[0].get("attributes", {}).get("LCSC", "")
        lines.append(f"{len(comps):<6} {name:<22} {value:<12} {footprint:<28} {lcsc:<12} {designators}")

    lines.append(f"\n合计: {len(components)} 个元件，{len(bom)} 种规格")
    return "\n".join(lines)


def mode_nets_only(data: dict, filter_net: str = None) -> str:
    nets = get_nets(data)
    if filter_net:
        nets = [n for n in nets if filter_net.lower() in n["name"].lower()]

    lines = ["网络连接详情 / Net Connection Details", "-" * 60]
    for net in sorted(nets, key=lambda x: x["name"]):
        pins = net.get("pins", [])
        lines.append(f"\n网络: {net['name']}  ({len(pins)} 个引脚)")
        for p in pins:
            lines.append(f"    {p['component']}.pin{p['pin']}")
    return "\n".join(lines)


def mode_components_only(data: dict, filter_comp: str = None) -> str:
    components = get_components(data)
    if filter_comp:
        components = [c for c in components if filter_comp.lower() in c["designator"].lower()]
    nets = get_nets(data)
    comp_net_map = component_nets(nets)

    lines = ["元件详情 / Component Details", "-" * 60]
    for c in sorted(components, key=lambda x: x["designator"]):
        lines.append(f"\n{c['designator']} — {c['name']}")
        lines.append(f"  值 (Value)   : {c.get('value', 'N/A')}")
        lines.append(f"  封装          : {c.get('footprint', 'N/A')}")
        attrs = c.get("attributes", {})
        if attrs.get("LCSC"):
            lines.append(f"  LCSC 编号    : {attrs['LCSC']}")
        if attrs.get("Manufacturer"):
            lines.append(f"  制造商        : {attrs['Manufacturer']}")
        if attrs.get("Description"):
            lines.append(f"  描述          : {attrs['Description']}")
        connected = comp_net_map.get(c["designator"], [])
        if connected:
            lines.append(f"  连接网络      : {', '.join(connected)}")
    return "\n".join(lines)


def mode_power(data: dict) -> str:
    nets = get_nets(data)
    power_keywords = {"GND", "VCC", "VDD", "VSS", "3V3", "5V", "12V",
                      "VBAT", "VREF", "AGND", "DGND", "PGND", "PWR", "AVCC"}

    lines = ["电源网络分析 / Power Net Analysis", "-" * 60]
    found = False
    for net in sorted(nets, key=lambda x: x["name"]):
        if any(kw in net["name"].upper() for kw in power_keywords):
            found = True
            pins = net.get("pins", [])
            lines.append(f"\n▶ {net['name']}  ({len(pins)} connections)")
            for p in pins:
                lines.append(f"    {p['component']}.{p['pin']}")
    if not found:
        lines.append("(未识别到电源网络)")
    return "\n".join(lines)


def mode_ai(data: dict) -> str:
    """输出专为 AI 阅读优化的简洁文本"""
    nets = get_nets(data)
    components = get_components(data)
    comp_net_map = component_nets(nets)
    power_keywords = {"GND", "VCC", "VDD", "VSS", "3V3", "5V", "12V", "VBAT", "VREF", "AGND", "DGND", "PGND"}

    lines = []
    lines.append("# 嘉立创EDA网表摘要（AI分析格式）")
    lines.append(f"元件数: {len(components)}  网络数: {len(nets)}")

    # 分类
    passives = [c for c in components if c["designator"][0] in ("R", "C", "L")]
    ics = [c for c in components if c["designator"][0] in ("U", "IC")]
    connectors = [c for c in components if c["designator"][0] in ("J", "CN", "P")]
    others = [c for c in components if c not in passives + ics + connectors]

    def fmt_comp(c):
        return f"{c['designator']}({c.get('value', c['name'])})"

    if ics:
        lines.append(f"\n## 主要芯片 ({len(ics)})")
        for c in ics:
            desc = c.get("attributes", {}).get("Description", c["name"])
            nets_list = ", ".join(comp_net_map.get(c["designator"], []))
            lines.append(f"- {c['designator']}: {c['name']} / {desc}")
            lines.append(f"  封装: {c.get('footprint','')}  连接网络: {nets_list}")

    if passives:
        lines.append(f"\n## 无源元件 ({len(passives)})")
        lines.append(", ".join(fmt_comp(c) for c in passives))

    if connectors:
        lines.append(f"\n## 连接器 ({len(connectors)})")
        lines.append(", ".join(fmt_comp(c) for c in connectors))

    if others:
        lines.append(f"\n## 其他 ({len(others)})")
        lines.append(", ".join(fmt_comp(c) for c in others))

    pnets = [n for n in nets if any(kw in n["name"].upper() for kw in power_keywords)]
    sig_nets = [n for n in nets if n not in pnets]

    if pnets:
        lines.append(f"\n## 电源网络 ({len(pnets)})")
        for n in pnets:
            pins = [f"{p['component']}.{p['pin']}" for p in n.get("pins", [])]
            lines.append(f"- {n['name']}: {', '.join(pins)}")

    if sig_nets:
        lines.append(f"\n## 信号网络 ({len(sig_nets)})")
        for n in sig_nets:
            pins = [f"{p['component']}.{p['pin']}" for p in n.get("pins", [])]
            lines.append(f"- {n['name']}: {', '.join(pins)}")

    return "\n".join(lines)


def mode_connectivity(data: dict) -> str:
    """元件间连接关系：哪些元件直接相连"""
    nets = get_nets(data)
    connections: dict[tuple, list[str]] = defaultdict(list)

    for net in nets:
        pins = net.get("pins", [])
        comps = list({p["component"] for p in pins})
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                key = tuple(sorted([comps[i], comps[j]]))
                connections[key].append(net["name"])

    lines = ["元件间直接连接关系 / Component Connectivity", "-" * 60]
    for (a, b), shared_nets in sorted(connections.items()):
        lines.append(f"  {a} ↔ {b}  via: {', '.join(shared_nets)}")
    return "\n".join(lines)


def mode_lcsc(data: dict) -> str:
    components = get_components(data)
    lines = ["嘉立创LCSC元件编号汇总", "-" * 50]
    lines.append(f"{'位号':<10} {'LCSC编号':<14} {'名称':<22} {'值'}")
    lines.append("-" * 60)
    for c in sorted(components, key=lambda x: x["designator"]):
        lcsc = c.get("attributes", {}).get("LCSC", "—")
        lines.append(f"{c['designator']:<10} {lcsc:<14} {c['name']:<22} {c.get('value','')}")
    return "\n".join(lines)


# ─── 主程序 ───────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="嘉立创EDA .enet 网表解析器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("file", help=".enet 文件路径")
    parser.add_argument("--mode", default="summary",
                        choices=["summary", "bom", "nets", "components", "power", "ai", "connectivity", "lcsc"],
                        help="输出模式")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出原始数据")
    parser.add_argument("--filter-net", metavar="NAME", help="过滤网络名称（模糊匹配）")
    parser.add_argument("--filter-comp", metavar="DESIGNATOR", help="过滤元件位号（模糊匹配）")
    args = parser.parse_args()

    data = load_enet(args.file)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    mode_map = {
        "summary": lambda: mode_summary(data),
        "bom": lambda: mode_bom(data),
        "nets": lambda: mode_nets_only(data, args.filter_net),
        "components": lambda: mode_components_only(data, args.filter_comp),
        "power": lambda: mode_power(data),
        "ai": lambda: mode_ai(data),
        "connectivity": lambda: mode_connectivity(data),
        "lcsc": lambda: mode_lcsc(data),
    }

    output = mode_map[args.mode]()
    print(output)


if __name__ == "__main__":
    main()
