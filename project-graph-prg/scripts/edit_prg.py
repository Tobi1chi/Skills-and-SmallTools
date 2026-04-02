from __future__ import annotations

import argparse
import json
from pathlib import Path

from prg_tools import edit_document, read_prg, write_prg


def main() -> int:
    parser = argparse.ArgumentParser(description="Edit an existing Project Graph .prg file using a JSON patch.")
    parser.add_argument("input", type=Path, help="Path to the input .prg file")
    parser.add_argument("patch", type=Path, help="Path to the JSON edit patch")
    parser.add_argument("output", type=Path, nargs="?", help="Path to the output .prg file; defaults to input path")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")
    args = parser.parse_args()

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
    print(
        json.dumps(
            {
                "input": str(args.input.resolve()),
                "patch": str(args.patch.resolve()),
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
