#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def configure_matplotlib():
    workspace = Path.cwd()
    os.environ.setdefault("MPLCONFIGDIR", str((workspace / ".mplconfig").resolve()))
    os.environ.setdefault("XDG_CACHE_HOME", str((workspace / ".cache").resolve()))
    (workspace / ".mplconfig").mkdir(exist_ok=True)
    (workspace / ".cache").mkdir(exist_ok=True)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run ngspice on a .cir file, read the wrdata output it produces, "
            "and generate a matplotlib plot."
        )
    )
    parser.add_argument("cir_file", type=Path, help="Path to the ngspice .cir file")
    parser.add_argument(
        "--output",
        type=Path,
        help="Output image path. Defaults to <cir_file_stem>_plot.png",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Optional plot title. Defaults to the .cir file name.",
    )
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="Keep the wrdata output file after plotting. By default it is deleted.",
    )
    return parser.parse_args()


def parse_wrdata(cir_text: str) -> tuple[str, list[str]]:
    match = re.search(r"^\s*wrdata\s+(\S+)\s+(.+)$", cir_text, flags=re.MULTILINE)
    if not match:
        raise ValueError("No wrdata command found in the .cir file.")

    data_file = match.group(1)
    expressions = match.group(2).strip().split()
    if not expressions:
        raise ValueError("wrdata command does not contain any expressions to plot.")
    return data_file, expressions


def run_ngspice(cir_file: Path) -> None:
    result = subprocess.run(
        ["ngspice", "-b", str(cir_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise RuntimeError(f"ngspice failed with exit code {result.returncode}.")


def load_wrdata_table(data_file: Path, traces: int):
    rows: list[list[float]] = []
    for line in data_file.read_text().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append([float(piece) for piece in stripped.split()])

    if not rows:
        raise ValueError(f"No numeric data found in {data_file}.")

    expected_columns = traces * 2
    bad_rows = [index + 1 for index, row in enumerate(rows) if len(row) != expected_columns]
    if bad_rows:
        raise ValueError(
            f"{data_file} has unexpected column counts on lines {bad_rows[:5]}."
        )

    return rows


def build_plot(rows, expressions, output_path: Path, title: str):
    plt = configure_matplotlib()

    time_values = [row[0] for row in rows]
    time0 = time_values[0]
    time_ms = [(value - time0) * 1000 for value in time_values]

    colors = ["#b55d32", "#2b7a50", "#2457c5", "#7a3db8", "#008b8b", "#8b4513"]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(11, 6), dpi=180)
    fig.patch.set_facecolor("#f5f0e6")
    ax.set_facecolor("#fffdf8")

    for index, expression in enumerate(expressions):
        y_values = [row[index * 2 + 1] for row in rows]
        ax.plot(
            time_ms,
            y_values,
            label=expression,
            linewidth=2.2,
            color=colors[index % len(colors)],
        )

    ax.axhline(0, color="#8c8478", linestyle="--", linewidth=1.0, alpha=0.8)
    ax.set_title(title, fontsize=16, pad=12)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Value")
    ax.legend(frameon=True, facecolor="white", edgecolor="#d7d0c3")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")


def main() -> int:
    args = parse_args()
    cir_file = args.cir_file.resolve()
    if not cir_file.exists():
        raise FileNotFoundError(f"{cir_file} does not exist.")

    cir_text = cir_file.read_text()
    data_file_name, expressions = parse_wrdata(cir_text)
    data_file = (cir_file.parent / data_file_name).resolve()
    output_path = args.output or cir_file.with_name(f"{cir_file.stem}_plot.png")
    title = args.title or f"{cir_file.name} waveforms"

    run_ngspice(cir_file)
    if not data_file.exists():
        raise FileNotFoundError(
            f"ngspice finished, but expected wrdata output was not found: {data_file}"
        )

    rows = load_wrdata_table(data_file, len(expressions))
    build_plot(rows, expressions, output_path, title)

    if not args.keep_data and data_file.exists():
        data_file.unlink()

    if args.keep_data:
        print(f"Simulation data kept: {data_file}")
    else:
        print(f"Simulation data deleted: {data_file}")
    print(f"Plot image: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
