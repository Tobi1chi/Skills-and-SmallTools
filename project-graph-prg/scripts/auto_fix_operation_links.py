from __future__ import annotations

import argparse
import json
from pathlib import Path

from prg_tools import auto_fix_operation_block_links, read_prg, write_prg


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-fix direct operation-block links by inserting exactly one blank intermediate register node."
    )
    parser.add_argument("input", type=Path, help="Path to the input .prg file")
    parser.add_argument("output", type=Path, nargs="?", help="Path to the output .prg file; defaults to input path")
    parser.add_argument("--label", default="", help="Text used for inserted intermediate register nodes; keep blank by default")
    parser.add_argument("--width", type=float, default=100.0, help="Width of inserted intermediate register nodes")
    parser.add_argument("--height", type=float, default=76.0, help="Height of inserted intermediate blocks")
    parser.add_argument("--vertical-offset", type=float, default=140.0, help="Vertical offset for inserted intermediate blocks")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")
    args = parser.parse_args()

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
