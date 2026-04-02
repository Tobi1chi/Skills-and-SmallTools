from __future__ import annotations

import argparse
import json
from pathlib import Path

from prg_tools import find_overlaps, find_spacing_violations, read_prg


def main() -> int:
    parser = argparse.ArgumentParser(description="Check rectangle overlaps in a Project Graph .prg file.")
    parser.add_argument("project", type=Path, help="Path to the .prg file")
    parser.add_argument("--include-points", action="store_true", help="Include ConnectPoint objects in overlap checks")
    parser.add_argument("--exclude-sections", action="store_true", help="Exclude Section bounds from overlap checks")
    parser.add_argument("--min-area", type=float, default=1.0, help="Minimum overlap area to report")
    parser.add_argument("--min-gap", type=float, default=200.0, help="Minimum required edge-to-edge spacing between blocks")
    parser.add_argument("--ignore-containment", action="store_true", help="Ignore full containment and only report partial overlaps")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")
    args = parser.parse_args()

    document = read_prg(args.project)
    overlap_result = find_overlaps(
        document,
        include_sections=not args.exclude_sections,
        include_points=args.include_points,
        min_overlap_area=args.min_area,
        ignore_containment=args.ignore_containment,
    )
    spacing_result = None
    if args.min_gap > 0:
        spacing_result = find_spacing_violations(
            document,
            include_sections=not args.exclude_sections,
            include_points=args.include_points,
            min_gap=args.min_gap,
            ignore_containment=args.ignore_containment,
        )
    result = {
        "ok": overlap_result["ok"] and (spacing_result["ok"] if spacing_result else True),
        "overlap": overlap_result,
        "spacing": spacing_result,
    }
    print(json.dumps(result, ensure_ascii=False, indent=args.indent))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
