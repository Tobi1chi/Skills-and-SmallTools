from __future__ import annotations

import argparse
import json
from pathlib import Path

from geometry_prg_tools import (
    detect_edge_block_crossings,
    insert_connect_points_for_crossing_edges,
    read_prg,
    write_prg,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect edge-through-block crossings and insert ConnectPoint detours.")
    parser.add_argument("project", type=Path, help="Path to the source .prg file")
    parser.add_argument("output", type=Path, help="Path to the rewritten .prg file")
    parser.add_argument("--include-sections", action="store_true", help="Also treat Section bounds as blocking geometry")
    parser.add_argument("--clearance", type=float, default=48.0, help="Routing clearance outside the crossed block")
    parser.add_argument("--point-size", type=float, default=30.0, help="Inserted ConnectPoint square size")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")
    args = parser.parse_args()

    document = read_prg(args.project)
    before = detect_edge_block_crossings(document, include_sections=args.include_sections)
    fix = insert_connect_points_for_crossing_edges(
        document.stage,
        clearance=args.clearance,
        point_size=args.point_size,
        include_sections=args.include_sections,
    )
    write_prg(
        args.output,
        stage=document.stage,
        metadata=document.metadata,
        tags=document.tags,
        references=document.references,
        attachments=document.attachments,
    )
    after = detect_edge_block_crossings(read_prg(args.output), include_sections=args.include_sections)
    result = {
        "input": str(args.project.resolve()),
        "output": str(args.output.resolve()),
        "before": before,
        "fix": fix,
        "after": after,
    }
    print(json.dumps(result, ensure_ascii=False, indent=args.indent))
    return 0 if after["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
