from __future__ import annotations

import argparse
import json
from pathlib import Path

from prg_tools import auto_fix_layout, read_prg, write_prg


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-fix overlapping layout blocks in a Project Graph .prg file.")
    parser.add_argument("input", type=Path, help="Path to the input .prg file")
    parser.add_argument("output", type=Path, nargs="?", help="Path to the output .prg file; defaults to input path")
    parser.add_argument("--include-points", action="store_true", help="Include ConnectPoint objects in overlap checks")
    parser.add_argument("--include-sections", action="store_true", help="Include Section bounds in overlap checks")
    parser.add_argument("--min-area", type=float, default=1.0, help="Minimum overlap area to resolve")
    parser.add_argument("--padding", type=float, default=24.0, help="Extra spacing added when separating objects")
    parser.add_argument("--max-iterations", type=int, default=50, help="Maximum fix iterations")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")
    args = parser.parse_args()

    document = read_prg(args.input)
    result = auto_fix_layout(
        document,
        include_sections=args.include_sections,
        include_points=args.include_points,
        min_overlap_area=args.min_area,
        padding=args.padding,
        max_iterations=args.max_iterations,
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
    print(
        json.dumps(
            {
                "input": str(args.input.resolve()),
                "output": str(output_path),
                **result,
            },
            ensure_ascii=False,
            indent=args.indent,
        )
    )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
