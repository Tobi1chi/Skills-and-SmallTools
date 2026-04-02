from __future__ import annotations

import argparse
import json
from pathlib import Path

from geometry_prg_tools import DEFAULT_MIN_GAP, find_overlaps, read_prg


def main() -> int:
    parser = argparse.ArgumentParser(description="Check block overlaps and spacing in a Project Graph .prg file.")
    parser.add_argument("project", type=Path, help="Path to the .prg file")
    parser.add_argument("--include-points", action="store_true", help="Include ConnectPoint objects in overlap checks")
    parser.add_argument("--exclude-sections", action="store_true", help="Exclude Section bounds from overlap checks")
    parser.add_argument("--min-area", type=float, default=1.0, help="Minimum overlap area to report")
    parser.add_argument("--min-gap", type=float, default=DEFAULT_MIN_GAP, help="Required minimum edge-to-edge gap")
    parser.add_argument("--ignore-containment", action="store_true", help="Ignore full containment and only report partial overlaps")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")
    args = parser.parse_args()

    result = find_overlaps(
        read_prg(args.project),
        include_sections=not args.exclude_sections,
        include_points=args.include_points,
        min_overlap_area=args.min_area,
        ignore_containment=args.ignore_containment,
        min_gap=args.min_gap,
    )
    print(json.dumps(result, ensure_ascii=False, indent=args.indent))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
