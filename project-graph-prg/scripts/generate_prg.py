from __future__ import annotations

import argparse
import json
from pathlib import Path

from geometry_prg_tools import generate_prg_from_spec, write_prg


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Project Graph .prg file from JSON.")
    parser.add_argument("spec", type=Path, help="Path to the intermediate JSON spec")
    parser.add_argument("output", type=Path, help="Path to the output .prg file")
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    stage, attachments, metadata, tags, references = generate_prg_from_spec(spec)
    write_prg(
        args.output,
        stage=stage,
        attachments=attachments,
        metadata=metadata,
        tags=tags,
        references=references,
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "object_count": len(stage),
                "attachment_count": len(attachments),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
