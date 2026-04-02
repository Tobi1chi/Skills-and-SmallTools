from __future__ import annotations

import argparse
import json
from pathlib import Path

from prg_tools import read_prg, validate_document


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Project Graph .prg file.")
    parser.add_argument("project", type=Path, help="Path to the .prg file")
    parser.add_argument("--expect", type=Path, help="Optional expected-content JSON")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")
    args = parser.parse_args()

    expected = json.loads(args.expect.read_text(encoding="utf-8")) if args.expect else None
    result = validate_document(read_prg(args.project), expected=expected)
    print(json.dumps(result, ensure_ascii=False, indent=args.indent))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
