#!/usr/bin/env python3
"""
compare_style.py — delta comparison between a baseline text and a small
user-rewrite sample, for the rewrite-by-example skill.

This script is a SKELETON. The dimension definitions and confidence rules
are authoritative and match references/fingerprint.md. The statistical
implementations marked TODO need to be filled in before the skill can run
end to end.

Usage:
    uv run python scripts/compare_style.py \
        --baseline /tmp/baseline_unselected.md \
        --sample /tmp/sample_rewrites.md \
        --emit-delta /tmp/delta.json

Inputs:
    --baseline  Path to a Markdown file containing the ORIGINAL document
                with the selected calibration sentences REMOVED. This is
                important: passing the full original as baseline will
                inflate deltas due to selection bias.
    --sample    Path to a Markdown file containing only the user's
                rewritten versions of the selected sentences.

Outputs:
    --emit-delta  Path to write the delta JSON described in
                  references/fingerprint.md.

Exit codes:
    0   Success.
    1   Input file missing or unreadable.
    2   Sample too small for any dimension to be meaningful.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


# --- Shared word lists ------------------------------------------------------
# Keep these in sync with references/fingerprint.md. The de-ai-academic-prose
# skill uses overlapping lists; if you change either list, reconcile both.

CONNECTORS = [
    "however", "moreover", "furthermore", "therefore", "thus",
    "consequently", "additionally", "nevertheless", "nonetheless",
    "in addition", "on the other hand", "at the same time",
]

ABSTRACT_NOUNS = [
    "framework", "approach", "aspect", "element", "notion", "context",
    "dimension", "perspective", "paradigm", "mechanism",
]

NOMINALIZATION_SUFFIXES = ["tion", "ment", "ance", "ence", "ity", "ization"]


# --- Confidence thresholds --------------------------------------------------

MIN_TOKENS_HIGH = 100
MIN_SENTENCES_HIGH = 6
MIN_SENTENCES_ANY = 3
MIN_RELATIVE_DELTA_HIGH = 0.30
MIN_RELATIVE_DELTA_MEDIUM = 0.15


@dataclass
class DimensionResult:
    baseline: float
    sample: float
    absolute_delta: float
    relative_delta: float
    confidence: str  # "high" | "medium" | "low"
    note: str = ""


def read_text(path: Path) -> str:
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path.read_text(encoding="utf-8")


def tokenize(text: str) -> list[str]:
    """Naive whitespace + punctuation tokenizer. Replace with a better
    tokenizer if the de-ai-academic-prose script uses one — prefer reusing
    that over introducing a second tokenization rule."""
    # TODO: reuse tokenizer from analyze_academic_prose.py for consistency
    import re
    return re.findall(r"\b[\w'-]+\b", text.lower())


def split_sentences(text: str) -> list[str]:
    """Naive sentence splitter. Same note as tokenize — reuse the existing
    splitter from analyze_academic_prose.py if one is available."""
    # TODO: reuse sentence splitter from analyze_academic_prose.py
    import re
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def classify_confidence(
    relative_delta: float,
    sample_tokens: int,
    sample_sentences: int,
    min_tokens: int = MIN_TOKENS_HIGH,
    min_sentences: int = MIN_SENTENCES_HIGH,
) -> str:
    """Apply the rules from references/fingerprint.md."""
    abs_delta = abs(relative_delta)
    size_ok = sample_tokens >= min_tokens and sample_sentences >= min_sentences
    if size_ok and abs_delta >= MIN_RELATIVE_DELTA_HIGH:
        return "high"
    if abs_delta >= MIN_RELATIVE_DELTA_MEDIUM:
        return "medium"
    return "low"


def safe_relative_delta(baseline: float, sample: float) -> float:
    if baseline == 0:
        return 0.0 if sample == 0 else float("inf")
    return (sample - baseline) / baseline


# --- Dimension computations ------------------------------------------------
# Each function returns a DimensionResult. All are TODO stubs that currently
# return a zero result so the script runs end to end.

def dim_sentence_length_mean(
    baseline_sents: list[str], sample_sents: list[str]
) -> DimensionResult:
    def mean_len(sents):
        if not sents:
            return 0.0
        return sum(len(tokenize(s)) for s in sents) / len(sents)

    b = mean_len(baseline_sents)
    s = mean_len(sample_sents)
    rel = safe_relative_delta(b, s)
    conf = classify_confidence(
        rel,
        sample_tokens=sum(len(tokenize(x)) for x in sample_sents),
        sample_sentences=len(sample_sents),
        min_sentences=MIN_SENTENCES_HIGH,
    )
    return DimensionResult(b, s, s - b, rel, conf)


def dim_sentence_length_variance(
    baseline_sents: list[str], sample_sents: list[str]
) -> DimensionResult:
    # TODO: compute population variance of sentence lengths
    # Confidence rule: require at least 5 sample sentences for any confidence.
    return DimensionResult(0.0, 0.0, 0.0, 0.0, "low", "TODO: not yet implemented")


def dim_marker_density(
    baseline_text: str, sample_text: str
) -> dict[str, DimensionResult]:
    # TODO: for each tag in markers.md, count markers per 100 tokens in
    # baseline and sample, return one DimensionResult per tag.
    # Tags to cover:
    #   repetitive_framing, meta_writing, template_transitions,
    #   over_balanced_contrast, abstract_drift, flat_cadence, generic_recap
    return {}


def dim_abstract_noun_density(
    baseline_text: str, sample_text: str
) -> DimensionResult:
    # TODO: count occurrences of ABSTRACT_NOUNS per 100 tokens
    return DimensionResult(0.0, 0.0, 0.0, 0.0, "low", "TODO: not yet implemented")


def dim_connector_density_total(
    baseline_text: str, sample_text: str
) -> DimensionResult:
    # TODO: total density of CONNECTORS per 100 tokens
    return DimensionResult(0.0, 0.0, 0.0, 0.0, "low", "TODO: not yet implemented")


def dim_connector_blacklist(
    baseline_text: str, sample_text: str
) -> list[str]:
    # TODO: return connectors whose sample count is zero AND whose baseline
    # density is at least 0.3 per 100 tokens. Requires sample >= 100 tokens.
    return []


def dim_word_blacklist(
    baseline_text: str, sample_text: str
) -> list[str]:
    # TODO: top 20 content words in baseline that are absent from sample
    return []


def dim_word_whitelist(
    baseline_text: str, sample_text: str
) -> list[str]:
    # TODO: content words in sample that are absent or very rare in baseline
    return []


def dim_sentence_initial_patterns(
    baseline_sents: list[str], sample_sents: list[str]
) -> dict[str, DimensionResult]:
    # TODO: track top 5 baseline sentence-initial bigrams, report per-pattern
    # deltas in the sample.
    return {}


def dim_passive_to_active_ratio(
    baseline_text: str, sample_text: str
) -> DimensionResult:
    # TODO: approximate passive voice detection. Requires POS tagging or
    # heuristics (be + past participle). Flag confidence medium at best.
    return DimensionResult(0.0, 0.0, 0.0, 0.0, "low", "TODO: not yet implemented")


def dim_nominalization_density(
    baseline_text: str, sample_text: str
) -> DimensionResult:
    # TODO: count words ending in NOMINALIZATION_SUFFIXES, per 100 tokens.
    # This is a rough heuristic — expect false positives.
    return DimensionResult(0.0, 0.0, 0.0, 0.0, "low", "TODO: not yet implemented")


# --- Main -------------------------------------------------------------------

def build_delta(baseline_path: Path, sample_path: Path) -> dict[str, Any]:
    baseline_text = read_text(baseline_path)
    sample_text = read_text(sample_path)

    baseline_sents = split_sentences(baseline_text)
    sample_sents = split_sentences(sample_text)
    sample_tokens = len(tokenize(sample_text))

    if len(sample_sents) < MIN_SENTENCES_ANY:
        print(
            f"error: sample has only {len(sample_sents)} sentences; "
            f"minimum is {MIN_SENTENCES_ANY}",
            file=sys.stderr,
        )
        sys.exit(2)

    delta: dict[str, Any] = {
        "meta": {
            "baseline_tokens": len(tokenize(baseline_text)),
            "baseline_sentences": len(baseline_sents),
            "sample_tokens": sample_tokens,
            "sample_sentences": len(sample_sents),
        },
        "sentence_length_mean": asdict(
            dim_sentence_length_mean(baseline_sents, sample_sents)
        ),
        "sentence_length_variance": asdict(
            dim_sentence_length_variance(baseline_sents, sample_sents)
        ),
        "abstract_noun_density": asdict(
            dim_abstract_noun_density(baseline_text, sample_text)
        ),
        "connector_density_total": asdict(
            dim_connector_density_total(baseline_text, sample_text)
        ),
        "connector_blacklist": dim_connector_blacklist(baseline_text, sample_text),
        "word_blacklist": dim_word_blacklist(baseline_text, sample_text),
        "word_whitelist": dim_word_whitelist(baseline_text, sample_text),
        "passive_to_active_ratio": asdict(
            dim_passive_to_active_ratio(baseline_text, sample_text)
        ),
        "nominalization_density": asdict(
            dim_nominalization_density(baseline_text, sample_text)
        ),
    }

    # Nested per-tag dimensions
    marker_density = dim_marker_density(baseline_text, sample_text)
    delta["marker_density"] = {k: asdict(v) for k, v in marker_density.items()}

    sentence_initial = dim_sentence_initial_patterns(baseline_sents, sample_sents)
    delta["sentence_initial_patterns"] = {
        k: asdict(v) for k, v in sentence_initial.items()
    }

    return delta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--emit-delta", type=Path, required=True)
    args = parser.parse_args()

    delta = build_delta(args.baseline, args.sample)
    args.emit_delta.write_text(json.dumps(delta, indent=2), encoding="utf-8")
    print(f"wrote delta to {args.emit_delta}")


if __name__ == "__main__":
    main()
