from __future__ import annotations

import argparse
import json
from pathlib import Path

from prg_tools import read_prg, validate_operation_block_links


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that operation blocks only connect to other operation blocks through exactly one intermediate block."
    )
    parser.add_argument("project", type=Path, help="Path to the .prg file")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")
    args = parser.parse_args()

    result = validate_operation_block_links(read_prg(args.project))
    print(json.dumps(result, ensure_ascii=False, indent=args.indent))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
