#!/usr/bin/env python3
"""Create a draft project memory file from lightweight repo metadata."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
from pathlib import Path


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    ".cache",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

IMPORTANT_NAMES = {
    "AGENTS.md",
    "README.md",
    "README.rst",
    "README.txt",
    "pyproject.toml",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "Cargo.toml",
    "go.mod",
    "Makefile",
    "justfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
    ".github/workflows",
}


def run_git(project: Path, args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=project,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def git_root(path: Path) -> Path:
    root = run_git(path, ["rev-parse", "--show-toplevel"])
    return Path(root).resolve() if root else path.resolve()


def is_skipped(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def collect_files(project: Path, limit: int) -> list[Path]:
    files: list[Path] = []
    for root, dirnames, filenames in os.walk(project):
        root_path = Path(root)
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        if is_skipped(root_path.relative_to(project)):
            continue
        for filename in filenames:
            rel = (root_path / filename).relative_to(project)
            if not is_skipped(rel):
                files.append(rel)
                if len(files) >= limit:
                    return sorted(files)
    return sorted(files)


def collect_important(files: list[Path]) -> list[Path]:
    important: list[Path] = []
    for rel in files:
        rel_text = rel.as_posix()
        if rel.name in IMPORTANT_NAMES or rel_text.startswith(".github/workflows/"):
            important.append(rel)
    return important


def top_dirs(files: list[Path]) -> list[str]:
    counts: dict[str, int] = {}
    for rel in files:
        if len(rel.parts) > 1:
            counts[rel.parts[0]] = counts.get(rel.parts[0], 0) + 1
    return [f"{name}/ ({count} files)" for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:12]]


def read_excerpt(project: Path, rel: Path, max_chars: int) -> str | None:
    path = project / rel
    try:
        if path.stat().st_size > 200_000:
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    text = "\n".join(line.rstrip() for line in text.splitlines()[:80])
    return text[:max_chars].strip() or None


def render(project: Path, files: list[Path]) -> str:
    today = dt.date.today().isoformat()
    remote = run_git(project, ["remote", "get-url", "origin"]) or "not detected"
    branch = run_git(project, ["branch", "--show-current"]) or "not detected"
    important = collect_important(files)
    dirs = top_dirs(files)

    lines = [
        f"# Project Memory: {project.name}",
        "",
        f"Last updated: {today}",
        f"Project path: {project}",
        f"Repository: {remote}",
        f"Current branch when scanned: {branch}",
        "",
        "## What This Project Is",
        "- Needs review: summarize the project purpose from README, manifests, and source layout.",
        "",
        "## How To Work Here",
        "- Needs review: add build, test, lint, run, and deploy commands discovered from project files.",
        "",
        "## Architecture Notes",
    ]
    if dirs:
        lines.extend(f"- `{item}`" for item in dirs)
    else:
        lines.append("- Needs review: no source directories detected by the scanner.")

    lines.extend(
        [
            "",
            "## Conventions",
            "- Needs review: capture coding style, framework patterns, naming, and local AGENTS.md instructions.",
            "",
            "## Known Risks And Caveats",
            "- Needs review: add fragile areas, generated files, hardware/service assumptions, and migration traps.",
            "",
            "## Useful Entry Points",
        ]
    )
    if important:
        lines.extend(f"- `{rel.as_posix()}`" for rel in important[:30])
    else:
        lines.append("- Needs review: no standard entry point files detected.")

    lines.extend(["", "## Source Excerpts To Review"])
    for rel in important[:8]:
        excerpt = read_excerpt(project, rel, 2500)
        if not excerpt:
            continue
        lines.extend(
            [
                f"### {rel.as_posix()}",
                "",
                "```text",
                excerpt,
                "```",
                "",
            ]
        )

    lines.extend(
        [
            "## Open Questions",
            "- Verify all commands before relying on them.",
            "- Decide which facts belong in long-term memory versus a task-specific summary.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project directory to scan.")
    parser.add_argument("--out", required=True, help="Markdown draft output path.")
    parser.add_argument("--limit", type=int, default=2000, help="Maximum files to scan.")
    args = parser.parse_args()

    project = git_root(Path(args.project).expanduser())
    files = collect_files(project, args.limit)
    output = Path(args.out).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(project, files), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
