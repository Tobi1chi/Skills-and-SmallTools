from __future__ import annotations

import argparse
import json
from pathlib import Path

from prg_tools import inspect_document, read_prg


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a Project Graph .prg file.")
    parser.add_argument("project", type=Path, help="Path to the .prg file")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")
    parser.add_argument("--limit", type=int, default=20, help="Max sampled nodes/edges/sections in output")
    args = parser.parse_args()

    summary = inspect_document(read_prg(args.project), sample_limit=args.limit)
    print(json.dumps(summary, ensure_ascii=False, indent=args.indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
