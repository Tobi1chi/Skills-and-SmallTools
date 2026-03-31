#!/usr/bin/env python3
"""Analyze academic Markdown/LaTeX prose for structure and AI-style markers."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "done",
    "during",
    "each",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "his",
    "how",
    "however",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "less",
    "may",
    "might",
    "more",
    "most",
    "my",
    "not",
    "of",
    "on",
    "only",
    "or",
    "other",
    "our",
    "out",
    "over",
    "rather",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "them",
    "themselves",
    "there",
    "therefore",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "under",
    "up",
    "use",
    "used",
    "using",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "within",
    "without",
    "would",
    "you",
    "your",
}


TRANSITION_PATTERNS = {
    "template_transition": re.compile(
        r"\b(in contrast|by contrast)\b",
        re.IGNORECASE,
    ),
    "repetitive_framing": re.compile(
        r"\b(this (project|study|framework|report|section|flow|design|means|"
        r"structure|comparison)|the present (project|study|work))\b",
        re.IGNORECASE,
    ),
    "balanced_contrast": re.compile(
        r"\brather than\b|\bnot\s+[^.]{0,60}\s+but\b",
        re.IGNORECASE,
    ),
    "throat_clearing": re.compile(
        r"\b(it is important to note that|it should be noted that|"
        r"this makes it possible to|this means that|this is useful because)\b",
        re.IGNORECASE,
    ),
}


SOFT_DISCOURSE_MARKERS = (
    "however",
    "moreover",
    "overall",
    "therefore",
    "furthermore",
    "additionally",
    "consequently",
    "thus",
    "nevertheless",
    "nonetheless",
    "meanwhile",
    "instead",
    "similarly",
    "specifically",
    "notably",
    "indeed",
    "alternatively",
    "in addition",
    "in particular",
    "for example",
    "for instance",
    "on the other hand",
)
SOFT_DISCOURSE_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(marker) for marker in sorted(SOFT_DISCOURSE_MARKERS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


ABSTRACT_NOUNS = {
    "analysis",
    "architecture",
    "behaviour",
    "behavior",
    "comparison",
    "capability",
    "context",
    "design",
    "distinction",
    "evidence",
    "flow",
    "framework",
    "implementation",
    "improvement",
    "logic",
    "model",
    "process",
    "project",
    "report",
    "result",
    "section",
    "structure",
    "system",
    "workflow",
}


LATEX_HEADING_MAP = {
    "chapter": 1,
    "section": 2,
    "subsection": 3,
    "subsubsection": 4,
    "paragraph": 5,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract sections from Markdown/LaTeX, compute word-frequency stats, "
            "and rank candidate AI-style sentences."
        )
    )
    parser.add_argument("input", type=Path, help="Path to a .md or .tex file")
    parser.add_argument(
        "--top-words",
        type=int,
        default=25,
        help="Number of content words to show",
    )
    parser.add_argument(
        "--top-sentences",
        type=int,
        default=12,
        help="Number of AI-marker sentences to show",
    )
    parser.add_argument(
        "--top-phrases",
        type=int,
        default=10,
        help="Number of bigrams to show",
    )
    parser.add_argument(
        "--emit-markdown",
        type=Path,
        help="Write extracted/normalized markdown to this path",
    )
    parser.add_argument(
        "--emit-report",
        type=Path,
        help="Write the final report to this path",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format",
    )
    parser.add_argument(
        "--soft-discourse-cap-per-paragraph",
        type=int,
        default=1,
        help=(
            "Allow this many soft discourse markers per paragraph before "
            "flagging overuse"
        ),
    )
    parser.add_argument(
        "--soft-transition-cap-per-paragraph",
        type=int,
        dest="soft_discourse_cap_per_paragraph",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_latex_source(path: Path, seen: set[Path] | None = None) -> str:
    if seen is None:
        seen = set()
    path = path.expanduser().resolve()
    if path in seen:
        return ""
    seen.add(path)
    text = normalize_newlines(path.read_text(encoding="utf-8"))

    def replace_include(match: re.Match[str]) -> str:
        raw_target = match.group(1).strip()
        candidate = Path(raw_target)
        if candidate.suffix.lower() != ".tex":
            candidate = candidate.with_suffix(".tex")
        if not candidate.is_absolute():
            candidate = (path.parent / candidate).resolve()
        if not candidate.exists():
            return ""
        return "\n" + read_latex_source(candidate, seen) + "\n"

    return re.sub(
        r"\\(?:input|include)\{([^{}]+)\}",
        replace_include,
        text,
    )


def strip_latex_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


def collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def latex_to_markdown(text: str) -> str:
    text = normalize_newlines(text)
    document_match = re.search(
        r"\\begin\{document\}(.*)\\end\{document\}",
        text,
        flags=re.S,
    )
    if document_match:
        text = document_match.group(1)
    text = strip_latex_comments(text)
    for env in ("figure", "table", "equation", "align", "lstlisting", "titlepage"):
        text = re.sub(
            rf"\\begin\{{{env}\*?\}}.*?\\end\{{{env}\*?\}}",
            "",
            text,
            flags=re.S,
        )
    text = re.sub(r"\\begin\{itemize\}(.*?)\\end\{itemize\}", lambda m: convert_latex_items(m.group(1), "-"), text, flags=re.S)
    text = re.sub(r"\\begin\{enumerate\}(.*?)\\end\{enumerate\}", lambda m: convert_latex_items(m.group(1), "1."), text, flags=re.S)

    for command, level in LATEX_HEADING_MAP.items():
        pattern = re.compile(
            rf"\\{command}\*?(?:\[[^\]]*\])?\{{([^{{}}]*)\}}",
            re.S,
        )
        text = pattern.sub(lambda m, level=level: "\n\n" + ("#" * level) + " " + clean_inline_latex(m.group(1).strip()) + "\n\n", text)

    # Keep content from common inline commands.
    previous = None
    while previous != text:
        previous = text
        text = re.sub(
            r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}",
            lambda m: clean_inline_latex(m.group(1)),
            text,
        )

    text = re.sub(r"\$\$(.*?)\$\$", " ", text, flags=re.S)
    text = re.sub(r"\$(.*?)\$", " ", text, flags=re.S)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = text.replace("~", " ")
    text = text.replace("\\", " ")
    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = collapse_blank_lines(text)
    heading_match = re.search(r"^#{1,6}\s+", text, flags=re.M)
    if heading_match:
        text = text[heading_match.start() :]
    return collapse_blank_lines(text)


def convert_latex_items(body: str, bullet: str) -> str:
    items = []
    for item in re.split(r"\\item", body):
        cleaned = clean_inline_latex(item).strip()
        if cleaned:
            items.append(f"{bullet} {cleaned}")
    return "\n" + "\n".join(items) + "\n"


def clean_inline_latex(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def markdown_sections(markdown: str) -> list[dict]:
    lines = markdown.splitlines()
    headings = []
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2).strip()))

    if not headings:
        return [
            {
                "level": 1,
                "title": "Document",
                "body": markdown.strip(),
            }
        ]

    sections = []
    for idx, (line_index, level, title) in enumerate(headings):
        end_index = len(lines)
        for next_index in range(idx + 1, len(headings)):
            next_line_index, next_level, _ = headings[next_index]
            if next_level <= level:
                end_index = next_line_index
                break
        body = "\n".join(lines[line_index + 1 : end_index]).strip()
        sections.append({"level": level, "title": title, "body": body})
    return sections


def strip_code_blocks(markdown: str) -> str:
    return re.sub(r"```.*?```", "", markdown, flags=re.S)


def strip_markdown_tables(markdown: str) -> str:
    kept_lines = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            continue
        if stripped.startswith("*Figure"):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines)


def strip_markdown_headings(markdown: str) -> str:
    kept_lines = []
    for line in markdown.splitlines():
        if re.match(r"^\s*#{1,6}\s+", line):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines)


def prose_body(markdown: str) -> str:
    return strip_markdown_headings(
        strip_markdown_tables(strip_code_blocks(markdown))
    )


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9'/-]*", text)


def split_sentences(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return []
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", compact)
        if sentence.strip()
    ]


def split_paragraphs(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]


def section_word_stats(sections: Iterable[dict]) -> list[dict]:
    stats = []
    for section in sections:
        body = prose_body(section["body"])
        body_words = words(body)
        body_sentences = split_sentences(body)
        paragraphs = split_paragraphs(body)
        stats.append(
            {
                "level": section["level"],
                "title": section["title"],
                "words": len(body_words),
                "sentences": len(body_sentences),
                "paragraphs": len(paragraphs),
                "avg_sentence_length": round(
                    len(body_words) / len(body_sentences), 2
                )
                if body_sentences
                else 0.0,
            }
        )
    return stats


def top_content_words(text: str, limit: int) -> list[tuple[str, int]]:
    tokens = [token.lower() for token in words(text)]
    counts = Counter(token for token in tokens if token not in STOPWORDS and len(token) > 2)
    return counts.most_common(limit)


def top_bigrams(text: str, limit: int) -> list[tuple[str, int]]:
    tokens = [token.lower() for token in words(text)]
    bigrams = Counter(zip(tokens, tokens[1:]))
    return [(" ".join(pair), count) for pair, count in bigrams.most_common(limit)]


def score_sentence(sentence: str, *, soft_discourse_overuse: bool = False) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    lower = sentence.lower()
    tokens = [token.lower() for token in words(sentence)]

    for label, pattern in TRANSITION_PATTERNS.items():
        if pattern.search(sentence):
            score += 1
            reasons.append(label)

    abstract_count = sum(1 for token in tokens if token in ABSTRACT_NOUNS)
    if abstract_count >= 2:
        score += 1
        reasons.append("abstract_drift")

    sentence_length = len(tokens)
    if sentence_length >= 28:
        score += 1
        reasons.append("long_sentence")

    if lower.startswith(("this ", "these ", "it ", "the report ", "the repository ")):
        score += 1
        reasons.append("meta_subject")

    if re.search(r"\b(discuss|describe|focuses on|summarizes|shows that the)\b", lower):
        score += 1
        reasons.append("meta_writing")

    if soft_discourse_overuse:
        score += 1
        reasons.append("soft_discourse_overuse")

    return score, reasons


def soft_discourse_stats(body: str, cap_per_paragraph: int) -> dict:
    paragraphs = split_paragraphs(body)
    paragraph_counts = []
    overused_paragraphs = 0
    excess_soft_discourse = 0
    for index, paragraph in enumerate(paragraphs, start=1):
        count = len(SOFT_DISCOURSE_PATTERN.findall(paragraph))
        paragraph_counts.append(
            {"paragraph_index": index, "count": count, "over_cap": count > cap_per_paragraph}
        )
        if count > cap_per_paragraph:
            overused_paragraphs += 1
            excess_soft_discourse += count - cap_per_paragraph
    return {
        "cap_per_paragraph": cap_per_paragraph,
        "paragraph_counts": paragraph_counts,
        "total_soft_discourse_markers": sum(item["count"] for item in paragraph_counts),
        "overused_paragraphs": overused_paragraphs,
        "excess_soft_discourse_markers": excess_soft_discourse,
        "max_per_paragraph": max((item["count"] for item in paragraph_counts), default=0),
    }


def sentence_candidates_for_section(section: dict, soft_discourse_cap_per_paragraph: int) -> list[dict]:
    body = prose_body(section["body"])
    candidates = []
    for paragraph in split_paragraphs(body):
        overused_soft_discourse = (
            len(SOFT_DISCOURSE_PATTERN.findall(paragraph)) > soft_discourse_cap_per_paragraph
        )
        for sentence in split_sentences(paragraph):
            score, reasons = score_sentence(
                sentence,
                soft_discourse_overuse=(
                    overused_soft_discourse and bool(SOFT_DISCOURSE_PATTERN.search(sentence))
                ),
            )
            if score <= 0:
                continue
            candidates.append(
                {
                    "section": section["title"],
                    "level": section["level"],
                    "score": score,
                    "reasons": reasons,
                    "sentence": sentence,
                }
            )
    candidates.sort(key=lambda item: (-item["score"], -len(words(item["sentence"]))))
    return candidates


def ai_heavy_sentences(
    sections: Iterable[dict], limit: int, soft_discourse_cap_per_paragraph: int
) -> list[dict]:
    seen: dict[str, dict] = {}
    for section in sections:
        for candidate in sentence_candidates_for_section(
            section, soft_discourse_cap_per_paragraph
        ):
            sentence = candidate["sentence"]
            existing = seen.get(sentence)
            if existing is None:
                seen[sentence] = candidate
                continue
            if candidate["level"] > existing["level"]:
                seen[sentence] = candidate
                continue
            if candidate["level"] == existing["level"] and candidate["score"] > existing["score"]:
                seen[sentence] = candidate
    results = list(seen.values())
    results.sort(key=lambda item: (-item["score"], -len(words(item["sentence"])), item["section"]))
    return results[:limit]


def marker_counts(text: str) -> dict[str, int]:
    tokens = [token.lower() for token in words(text)]
    counts = Counter(tokens)
    return {
        "this": counts["this"],
        "therefore": counts["therefore"],
        "however": counts["however"],
        "moreover": counts["moreover"],
        "overall": counts["overall"],
        "rather_than": len(re.findall(r"\brather than\b", text, flags=re.IGNORECASE)),
        "while": counts["while"],
        "useful": counts["useful"],
        "clear": counts["clear"],
        "design": counts["design"],
        "pipeline": counts["pipeline"],
        "implementation": counts["implementation"],
        "verification": counts["verification"],
    }


def section_marker_hits(body: str, soft_discourse_cap_per_paragraph: int) -> dict[str, int]:
    soft_stats = soft_discourse_stats(body, soft_discourse_cap_per_paragraph)
    hits = {
        "template_transition": 0,
        "soft_discourse_total": soft_stats["total_soft_discourse_markers"],
        "soft_discourse_overuse_paragraphs": soft_stats["overused_paragraphs"],
        "soft_discourse_excess": soft_stats["excess_soft_discourse_markers"],
        "repetitive_framing": 0,
        "balanced_contrast": 0,
        "throat_clearing": 0,
        "meta_subject_sentences": 0,
        "meta_writing_sentences": 0,
        "abstract_drift_sentences": 0,
        "long_sentences": 0,
        "flagged_sentences": 0,
    }
    for label, pattern in TRANSITION_PATTERNS.items():
        hits[label] = len(pattern.findall(body))

    for paragraph in split_paragraphs(body):
        overused_soft_discourse = (
            len(SOFT_DISCOURSE_PATTERN.findall(paragraph)) > soft_discourse_cap_per_paragraph
        )
        for sentence in split_sentences(paragraph):
            score, reasons = score_sentence(
                sentence,
                soft_discourse_overuse=(
                    overused_soft_discourse and bool(SOFT_DISCOURSE_PATTERN.search(sentence))
                ),
            )
            if score <= 0:
                continue
            hits["flagged_sentences"] += 1
            if "meta_subject" in reasons:
                hits["meta_subject_sentences"] += 1
            if "meta_writing" in reasons:
                hits["meta_writing_sentences"] += 1
            if "abstract_drift" in reasons:
                hits["abstract_drift_sentences"] += 1
            if "long_sentence" in reasons:
                hits["long_sentences"] += 1
    return hits


def classify_priority(priority_score: float, max_sentence_score: int) -> str:
    if max_sentence_score >= 4 or priority_score >= 60:
        return "high"
    if max_sentence_score >= 3 or priority_score >= 30:
        return "medium"
    if priority_score > 0:
        return "low"
    return "minimal"


def recommended_action(priority_label: str) -> str:
    if priority_label == "high":
        return "rewrite this section first; rebuild the highest-scoring sentences"
    if priority_label == "medium":
        return "targeted rewrite; trim framing and rebalance cadence"
    if priority_label == "low":
        return "light cleanup; remove obvious template phrasing only"
    return "leave unchanged unless required for consistency"


def section_analysis(
    sections: Iterable[dict], soft_discourse_cap_per_paragraph: int
) -> list[dict]:
    analysis = []
    for section in sections:
        if section["level"] == 1:
            continue
        body = prose_body(section["body"])
        body_words = words(body)
        word_count = len(body_words)
        sentence_count = len(split_sentences(body))
        if word_count == 0:
            continue

        candidates = sentence_candidates_for_section(
            section, soft_discourse_cap_per_paragraph
        )
        hits = section_marker_hits(body, soft_discourse_cap_per_paragraph)
        soft_stats = soft_discourse_stats(body, soft_discourse_cap_per_paragraph)
        total_marker_hits = sum(
            count
            for marker, count in hits.items()
            if marker != "soft_transition_total"
        )
        marker_density = round((total_marker_hits / word_count) * 1000, 2)
        sentence_scores = [candidate["score"] for candidate in candidates]
        max_sentence_score = max(sentence_scores, default=0)
        flagged_sentence_ratio = round(
            hits["flagged_sentences"] / sentence_count, 3
        ) if sentence_count else 0.0
        priority_score = round(
            marker_density
            + (max_sentence_score * 6)
            + (flagged_sentence_ratio * 20),
            2,
        )
        if word_count < 80:
            priority_score = round(priority_score * 0.45, 2)
        elif word_count < 140:
            priority_score = round(priority_score * 0.75, 2)
        priority_label = classify_priority(priority_score, max_sentence_score)
        if word_count < 50 and priority_label != "minimal":
            priority_label = "low"

        dominant_markers = [
            marker
            for marker, count in sorted(
                hits.items(),
                key=lambda item: (-item[1], item[0]),
            )
            if count > 0
        ][:3]

        analysis.append(
            {
                "level": section["level"],
                "section": section["title"],
                "word_count": word_count,
                "sentence_count": sentence_count,
                "marker_hits": hits,
                "total_marker_hits": total_marker_hits,
                "marker_density": marker_density,
                "flagged_sentence_ratio": flagged_sentence_ratio,
                "flagged_sentence_count": hits["flagged_sentences"],
                "max_sentence_score": max_sentence_score,
                "priority_score": priority_score,
                "priority_label": priority_label,
                "dominant_markers": dominant_markers,
                "recommended_action": recommended_action(priority_label),
                "soft_discourse_cap_per_paragraph": soft_discourse_cap_per_paragraph,
                "soft_discourse_stats": soft_stats,
                "top_examples": candidates[:2],
            }
        )

    analysis.sort(
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2, "minimal": 3}[item["priority_label"]],
            -item["priority_score"],
            item["level"],
            item["section"],
        )
    )
    return analysis


def rewrite_queue(section_analysis_items: list[dict]) -> list[dict]:
    queue = []
    for item in section_analysis_items:
        if item["priority_label"] == "minimal":
            continue
        queue.append(
            {
                "section": item["section"],
                "priority": item["priority_label"],
                "priority_score": item["priority_score"],
                "marker_density": item["marker_density"],
                "focus_markers": item["dominant_markers"],
                "action": item["recommended_action"],
                "sentence_targets": [
                    {
                        "score": example["score"],
                        "reasons": example["reasons"],
                        "sentence": example["sentence"],
                    }
                    for example in item["top_examples"]
                ],
            }
        )
    return queue


def build_report(
    markdown: str,
    source_path: Path,
    top_words_limit: int,
    top_sentences_limit: int,
    top_phrases_limit: int,
    soft_discourse_cap_per_paragraph: int,
) -> dict:
    prose = prose_body(markdown)
    sections = markdown_sections(markdown)
    prose_words = words(prose)
    prose_sentences = split_sentences(prose)
    paragraphs = split_paragraphs(prose)
    analyzed_sections = section_analysis(sections, soft_discourse_cap_per_paragraph)

    return {
        "source": str(source_path),
        "word_count": len(prose_words),
        "sentence_count": len(prose_sentences),
        "paragraph_count": len(paragraphs),
        "soft_discourse_cap_per_paragraph": soft_discourse_cap_per_paragraph,
        "soft_discourse_markers": list(SOFT_DISCOURSE_MARKERS),
        "avg_sentence_length": round(len(prose_words) / len(prose_sentences), 2)
        if prose_sentences
        else 0.0,
        "section_stats": section_word_stats(sections),
        "section_priority": [
            {
                "section": item["section"],
                "priority": item["priority_label"],
                "priority_score": item["priority_score"],
                "marker_density": item["marker_density"],
                "dominant_markers": item["dominant_markers"],
                "flagged_sentence_count": item["flagged_sentence_count"],
            }
            for item in analyzed_sections
        ],
        "marker_density": [
            {
                "section": item["section"],
                "word_count": item["word_count"],
                "marker_density": item["marker_density"],
                "marker_hits": item["marker_hits"],
            }
            for item in analyzed_sections
        ],
        "rewrite_queue": rewrite_queue(analyzed_sections),
        "top_content_words": top_content_words(prose, top_words_limit),
        "top_bigrams": top_bigrams(prose, top_phrases_limit),
        "marker_counts": marker_counts(prose),
        "ai_heavy_sentences": ai_heavy_sentences(
            sections, top_sentences_limit, soft_discourse_cap_per_paragraph
        ),
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Academic Prose Analysis",
        "",
        f"- Source: `{report['source']}`",
        f"- Word count: `{report['word_count']}`",
        f"- Sentence count: `{report['sentence_count']}`",
        f"- Paragraph count: `{report['paragraph_count']}`",
        f"- Average sentence length: `{report['avg_sentence_length']}` words",
        f"- Soft discourse cap per paragraph: `{report['soft_discourse_cap_per_paragraph']}`",
        f"- Soft discourse markers: `{', '.join(report['soft_discourse_markers'])}`",
        "",
        "## Section Stats",
        "",
        "| Level | Section | Words | Sentences | Paragraphs | Avg sentence length |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for section in report["section_stats"]:
        lines.append(
            f"| {section['level']} | {section['title']} | {section['words']} | "
            f"{section['sentences']} | {section['paragraphs']} | "
            f"{section['avg_sentence_length']} |"
        )

    lines.extend(
        [
            "",
            "## Section Priority",
            "",
            "| Section | Priority | Score | Marker density | Flagged sentences | Dominant markers |",
            "| --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for item in report["section_priority"]:
        markers = ", ".join(item["dominant_markers"]) if item["dominant_markers"] else "-"
        lines.append(
            f"| {item['section']} | {item['priority']} | {item['priority_score']} | "
            f"{item['marker_density']} | {item['flagged_sentence_count']} | {markers} |"
        )

    lines.extend(
        [
            "",
            "## Marker Density",
            "",
        ]
    )
    for item in report["marker_density"]:
        marker_hits = ", ".join(
            f"{marker}={count}"
            for marker, count in item["marker_hits"].items()
            if count > 0
        )
        if not marker_hits:
            marker_hits = "no markers"
        lines.append(
            f"- `{item['section']}`: density `{item['marker_density']}` per 1k words "
            f"({marker_hits})"
        )

    lines.extend(
        [
            "",
            "## Rewrite Queue",
            "",
        ]
    )
    if not report["rewrite_queue"]:
        lines.append("- No rewrite queue items generated.")
    else:
        for index, item in enumerate(report["rewrite_queue"], start=1):
            markers = ", ".join(item["focus_markers"]) if item["focus_markers"] else "none"
            lines.append(
                f"{index}. `{item['section']}` [{item['priority']}] score `{item['priority_score']}`, "
                f"density `{item['marker_density']}`. Focus: {markers}. Action: {item['action']}."
            )
            for target in item["sentence_targets"]:
                reasons = ", ".join(target["reasons"])
                lines.append(
                    f"   - Sentence score `{target['score']}` ({reasons}): {target['sentence']}"
                )

    lines.extend(
        [
            "",
            "## Top Content Words",
            "",
        ]
    )
    for word, count in report["top_content_words"]:
        lines.append(f"- `{word}`: {count}")

    lines.extend(
        [
            "",
            "## Top Bigrams",
            "",
        ]
    )
    for phrase, count in report["top_bigrams"]:
        lines.append(f"- `{phrase}`: {count}")

    lines.extend(
        [
            "",
            "## Marker Counts",
            "",
        ]
    )
    for marker, count in report["marker_counts"].items():
        lines.append(f"- `{marker}`: {count}")

    lines.extend(
        [
            "",
            "## Candidate AI-Heavy Sentences",
            "",
        ]
    )
    if not report["ai_heavy_sentences"]:
        lines.append("- No high-signal candidate sentences found.")
    else:
        for item in report["ai_heavy_sentences"]:
            reasons = ", ".join(item["reasons"])
            lines.append(
                f"- Score `{item['score']}` in `{item['section']}` "
                f"({reasons}): {item['sentence']}"
            )

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    source = args.input.expanduser().resolve()
    if source.suffix.lower() == ".tex":
        text = read_latex_source(source)
        markdown = latex_to_markdown(text)
    else:
        text = source.read_text(encoding="utf-8")
        markdown = normalize_newlines(text)

    if args.emit_markdown:
        emit_markdown = args.emit_markdown.expanduser().resolve()
        emit_markdown.write_text(markdown, encoding="utf-8")

    report = build_report(
        markdown=markdown,
        source_path=source,
        top_words_limit=args.top_words,
        top_sentences_limit=args.top_sentences,
        top_phrases_limit=args.top_phrases,
        soft_discourse_cap_per_paragraph=args.soft_discourse_cap_per_paragraph,
    )

    if args.format == "json":
        rendered = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    else:
        rendered = render_markdown(report)

    if args.emit_report:
        emit_report = args.emit_report.expanduser().resolve()
        emit_report.write_text(rendered, encoding="utf-8")

    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
