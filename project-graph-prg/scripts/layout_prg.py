from __future__ import annotations

import argparse
import json
from pathlib import Path

import geometry_prg_tools as geom
import graph_layout


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-layout an existing Project Graph .prg file.")
    parser.add_argument("input", type=Path, help="Path to the input .prg file")
    parser.add_argument("output", type=Path, help="Path to the output .prg file")
    parser.add_argument("--strategy", default="auto", choices=["auto", *sorted(graph_layout.STRATEGIES)], help="Layout strategy")
    parser.add_argument("--direction", default="right", choices=sorted(graph_layout.DIRECTIONS), help="Main layout direction")
    parser.add_argument("--min-gap", type=float, default=geom.DEFAULT_MIN_GAP, help="Minimum required edge-to-edge spacing between blocks")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic seed for force-like strategies")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")
    args = parser.parse_args()

    document = geom.read_prg(args.input)
    result = graph_layout.apply_layout_to_stage(
        document.stage,
        strategy=args.strategy,
        direction=args.direction,
        min_gap=args.min_gap,
        seed=args.seed,
    )
    geom.write_prg(
        args.output,
        stage=document.stage,
        metadata=document.metadata,
        tags=document.tags,
        references=document.references,
        attachments=document.attachments,
    )
    print(json.dumps({"output": str(args.output.resolve()), **result}, ensure_ascii=False, indent=args.indent))
    return 0 if result.get("geometry", {}).get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
