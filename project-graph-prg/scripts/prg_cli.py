from __future__ import annotations

import argparse
import json
from pathlib import Path

import geometry_prg_tools as geom
import graph_layout
from prg_tools import (
    auto_fix_operation_block_links,
    edit_document,
    inspect_document,
    read_prg,
    validate_document,
    validate_operation_block_links,
    write_prg,
)


def add_common_indent_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")


def print_json(payload: object, indent: int) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=indent))


def cmd_inspect(args: argparse.Namespace) -> int:
    summary = inspect_document(read_prg(args.project), sample_limit=args.limit)
    print_json(summary, args.indent)
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    stage, attachments, metadata, tags, references = geom.generate_prg_from_spec(spec, layout=args.layout)
    write_prg(
        args.output,
        stage=stage,
        attachments=attachments,
        metadata=metadata,
        tags=tags,
        references=references,
    )
    print_json(
        {
            "output": str(args.output.resolve()),
            "object_count": len(stage),
            "attachment_count": len(attachments),
        },
        args.indent,
    )
    return 0


def cmd_classify(args: argparse.Namespace) -> int:
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    print_json(graph_layout.classify_spec(spec), args.indent)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    expected = json.loads(args.expect.read_text(encoding="utf-8")) if args.expect else None
    result = validate_document(read_prg(args.project), expected=expected)
    print_json(result, args.indent)
    return 0 if result["ok"] else 1


def cmd_overlap(args: argparse.Namespace) -> int:
    result = geom.find_overlaps(
        geom.read_prg(args.project),
        include_sections=not args.exclude_sections,
        include_points=args.include_points,
        min_overlap_area=args.min_area,
        ignore_containment=args.ignore_containment,
        min_gap=args.min_gap,
    )
    print_json(result, args.indent)
    return 0 if result["ok"] else 1


def cmd_validate_op(args: argparse.Namespace) -> int:
    result = validate_operation_block_links(read_prg(args.project))
    print_json(result, args.indent)
    return 0 if result["ok"] else 1


def cmd_fix_layout(args: argparse.Namespace) -> int:
    document = geom.read_prg(args.input)
    before = geom.find_overlaps(
        document,
        include_sections=args.include_sections,
        include_points=args.include_points,
        min_overlap_area=args.min_area,
        min_gap=args.min_gap,
    )
    layout = graph_layout.apply_layout_to_stage(
        document.stage,
        strategy=args.strategy,
        direction=args.direction,
        min_gap=args.min_gap,
        seed=args.seed,
    )
    after = geom.find_overlaps(
        document,
        include_sections=args.include_sections,
        include_points=args.include_points,
        min_overlap_area=args.min_area,
        min_gap=args.min_gap,
    )
    output_path = (args.output or args.input).resolve()
    write_prg(
        output_path,
        stage=document.stage,
        metadata=document.metadata,
        tags=document.tags,
        references=document.references,
        attachments=document.attachments,
    )
    print_json(
        {
            "input": str(args.input.resolve()),
            "output": str(output_path),
            "before": before,
            "layout": layout,
            "after": after,
            "ok": after["ok"],
        },
        args.indent,
    )
    return 0 if after["ok"] else 1


def cmd_layout(args: argparse.Namespace) -> int:
    document = geom.read_prg(args.input)
    result = graph_layout.apply_layout_to_stage(
        document.stage,
        strategy=args.strategy,
        direction=args.direction,
        min_gap=args.min_gap,
        seed=args.seed,
    )
    output_path = args.output.resolve()
    write_prg(
        output_path,
        stage=document.stage,
        metadata=document.metadata,
        tags=document.tags,
        references=document.references,
        attachments=document.attachments,
    )
    print_json(
        {
            "input": str(args.input.resolve()),
            "output": str(output_path),
            **result,
        },
        args.indent,
    )
    return 0 if result.get("geometry", {}).get("ok", True) else 1


def cmd_fix_op_links(args: argparse.Namespace) -> int:
    document = read_prg(args.input)
    result = auto_fix_operation_block_links(
        document,
        intermediate_label=args.label,
        intermediate_width=args.width,
        intermediate_height=args.height,
        vertical_offset=args.vertical_offset,
    )
    output_path = (args.output or args.input).resolve()
    write_prg(
        output_path,
        stage=document.stage,
        metadata=document.metadata,
        tags=document.tags,
        references=document.references,
        attachments=document.attachments,
    )
    print_json(
        {
            "input": str(args.input.resolve()),
            "output": str(output_path),
            **result,
        },
        args.indent,
    )
    return 0 if result["ok"] else 1


def cmd_edit(args: argparse.Namespace) -> int:
    document = read_prg(args.input)
    patch = json.loads(args.patch.read_text(encoding="utf-8"))
    result = edit_document(document, patch)
    output_path = (args.output or args.input).resolve()
    write_prg(
        output_path,
        stage=document.stage,
        metadata=document.metadata,
        tags=document.tags,
        references=document.references,
        attachments=document.attachments,
    )
    print_json(
        {
            "input": str(args.input.resolve()),
            "patch": str(args.patch.resolve()),
            "output": str(output_path),
            **result,
        },
        args.indent,
    )
    return 0 if result["ok"] else 1


def cmd_route_edge_crossings(args: argparse.Namespace) -> int:
    document = geom.read_prg(args.input)
    before = geom.detect_edge_block_crossings(document, include_sections=args.include_sections)
    fix = geom.insert_connect_points_for_crossing_edges(
        document.stage,
        clearance=args.clearance,
        point_size=args.point_size,
        include_sections=args.include_sections,
    )
    output_path = (args.output or args.input).resolve()
    geom.write_prg(
        output_path,
        stage=document.stage,
        metadata=document.metadata,
        tags=document.tags,
        references=document.references,
        attachments=document.attachments,
    )
    after = geom.detect_edge_block_crossings(geom.read_prg(output_path), include_sections=args.include_sections)
    print_json(
        {
            "input": str(args.input.resolve()),
            "output": str(output_path),
            "before": before,
            "fix": fix,
            "after": after,
        },
        args.indent,
    )
    return 0 if after["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified CLI for Project Graph .prg generation, inspection, editing, validation, and repair.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect a .prg file")
    inspect_parser.add_argument("project", type=Path, help="Path to the .prg file")
    inspect_parser.add_argument("--limit", type=int, default=20, help="Max sampled nodes/edges/sections in output")
    add_common_indent_argument(inspect_parser)
    inspect_parser.set_defaults(func=cmd_inspect)

    generate_parser = subparsers.add_parser("generate", help="Generate a .prg file from a JSON spec")
    generate_parser.add_argument("spec", type=Path, help="Path to the intermediate JSON spec")
    generate_parser.add_argument("output", type=Path, help="Path to the output .prg file")
    generate_parser.add_argument(
        "--layout",
        default="auto",
        choices=["auto", "off", *sorted(graph_layout.STRATEGIES)],
        help="Apply native layout before writing the .prg; use off to preserve input coordinates",
    )
    add_common_indent_argument(generate_parser)
    generate_parser.set_defaults(func=cmd_generate)

    classify_parser = subparsers.add_parser("classify", help="Classify a JSON spec and recommend graphIntent/layoutPlan")
    classify_parser.add_argument("spec", type=Path, help="Path to the intermediate JSON spec")
    add_common_indent_argument(classify_parser)
    classify_parser.set_defaults(func=cmd_classify)

    layout_parser = subparsers.add_parser("layout", help="Re-layout an existing .prg file with native coordinates")
    layout_parser.add_argument("input", type=Path, help="Path to the input .prg file")
    layout_parser.add_argument("output", type=Path, help="Path to the output .prg file")
    layout_parser.add_argument("--strategy", default="auto", choices=["auto", *sorted(graph_layout.STRATEGIES)], help="Layout strategy")
    layout_parser.add_argument("--direction", default="right", choices=sorted(graph_layout.DIRECTIONS), help="Main layout direction")
    layout_parser.add_argument("--min-gap", type=float, default=geom.DEFAULT_MIN_GAP, help="Minimum required edge-to-edge spacing between blocks")
    layout_parser.add_argument("--seed", type=int, default=7, help="Deterministic seed for force-like strategies")
    add_common_indent_argument(layout_parser)
    layout_parser.set_defaults(func=cmd_layout)

    edit_parser = subparsers.add_parser("edit", help="Edit an existing .prg file using a JSON patch")
    edit_parser.add_argument("input", type=Path, help="Path to the input .prg file")
    edit_parser.add_argument("patch", type=Path, help="Path to the JSON edit patch")
    edit_parser.add_argument("output", type=Path, nargs="?", help="Path to the output .prg file; defaults to input path")
    add_common_indent_argument(edit_parser)
    edit_parser.set_defaults(func=cmd_edit)

    validate_parser = subparsers.add_parser("validate", help="Validate a .prg file")
    validate_parser.add_argument("project", type=Path, help="Path to the .prg file")
    validate_parser.add_argument("--expect", type=Path, help="Optional expected-content JSON")
    add_common_indent_argument(validate_parser)
    validate_parser.set_defaults(func=cmd_validate)

    overlap_parser = subparsers.add_parser("overlap", help="Check overlap and spacing rules for a .prg file")
    overlap_parser.add_argument("project", type=Path, help="Path to the .prg file")
    overlap_parser.add_argument("--include-points", action="store_true", help="Include ConnectPoint objects in checks")
    overlap_parser.add_argument("--exclude-sections", action="store_true", help="Exclude Section bounds from checks")
    overlap_parser.add_argument("--min-area", type=float, default=1.0, help="Minimum overlap area to report")
    overlap_parser.add_argument("--min-gap", type=float, default=geom.DEFAULT_MIN_GAP, help="Minimum required edge-to-edge spacing between blocks")
    overlap_parser.add_argument("--ignore-containment", action="store_true", help="Ignore full containment and only report partial overlaps")
    add_common_indent_argument(overlap_parser)
    overlap_parser.set_defaults(func=cmd_overlap)

    validate_op_parser = subparsers.add_parser(
        "validate-op",
        help="Validate that operation blocks only connect through exactly one blank intermediate register node",
    )
    validate_op_parser.add_argument("project", type=Path, help="Path to the .prg file")
    add_common_indent_argument(validate_op_parser)
    validate_op_parser.set_defaults(func=cmd_validate_op)

    fix_layout_parser = subparsers.add_parser("fix-layout", help="Auto-fix overlapping layout blocks in a .prg file")
    fix_layout_parser.add_argument("input", type=Path, help="Path to the input .prg file")
    fix_layout_parser.add_argument("output", type=Path, nargs="?", help="Path to the output .prg file; defaults to input path")
    fix_layout_parser.add_argument("--include-points", action="store_true", help="Include ConnectPoint objects in overlap checks")
    fix_layout_parser.add_argument("--include-sections", action="store_true", help="Include Section bounds in overlap checks")
    fix_layout_parser.add_argument("--min-area", type=float, default=1.0, help="Minimum overlap area to resolve")
    fix_layout_parser.add_argument("--min-gap", type=float, default=geom.DEFAULT_MIN_GAP, help="Minimum required edge-to-edge spacing between blocks")
    fix_layout_parser.add_argument("--strategy", default="auto", choices=["auto", *sorted(graph_layout.STRATEGIES)], help="Layout strategy used when reflowing")
    fix_layout_parser.add_argument("--direction", default="right", choices=sorted(graph_layout.DIRECTIONS), help="Main layout direction")
    fix_layout_parser.add_argument("--seed", type=int, default=7, help="Deterministic seed for force-like strategies")
    fix_layout_parser.add_argument("--padding", type=float, default=24.0, help="Extra spacing added when separating objects")
    fix_layout_parser.add_argument("--max-iterations", type=int, default=50, help="Maximum fix iterations")
    add_common_indent_argument(fix_layout_parser)
    fix_layout_parser.set_defaults(func=cmd_fix_layout)

    fix_op_parser = subparsers.add_parser(
        "fix-op-links",
        help="Auto-fix illegal operation-block links by inserting one blank intermediate register node",
    )
    fix_op_parser.add_argument("input", type=Path, help="Path to the input .prg file")
    fix_op_parser.add_argument("output", type=Path, nargs="?", help="Path to the output .prg file; defaults to input path")
    fix_op_parser.add_argument("--label", default="", help="Text used for inserted intermediate register nodes; keep blank by default")
    fix_op_parser.add_argument("--width", type=float, default=100.0, help="Width of inserted intermediate register nodes")
    fix_op_parser.add_argument("--height", type=float, default=76.0, help="Height of inserted intermediate blocks")
    fix_op_parser.add_argument("--vertical-offset", type=float, default=140.0, help="Vertical offset for inserted intermediate blocks")
    add_common_indent_argument(fix_op_parser)
    fix_op_parser.set_defaults(func=cmd_fix_op_links)

    route_parser = subparsers.add_parser(
        "route-edge-crossings",
        help="Insert ConnectPoint detours when a LineEdge fully passes through a block",
    )
    route_parser.add_argument("input", type=Path, help="Path to the input .prg file")
    route_parser.add_argument("output", type=Path, nargs="?", help="Path to the output .prg file; defaults to input path")
    route_parser.add_argument("--include-sections", action="store_true", help="Also treat Section bounds as blocking geometry")
    route_parser.add_argument("--clearance", type=float, default=48.0, help="Routing clearance outside the crossed block")
    route_parser.add_argument("--point-size", type=float, default=30.0, help="Inserted ConnectPoint square size")
    add_common_indent_argument(route_parser)
    route_parser.set_defaults(func=cmd_route_edge_crossings)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
