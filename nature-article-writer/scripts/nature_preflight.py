\
#!/usr/bin/env python3
"""
Nature-style manuscript preflight checker.

This script performs a lightweight structural and stylistic review of a draft
intended for Nature or Nature Portfolio journals. It uses only the Python
standard library and is designed for non-interactive agent use.

Examples:
  python3 scripts/nature_preflight.py --input draft.md --mode nature-article --format text
  python3 scripts/nature_preflight.py --input draft.md --mode portfolio-article --format json
  cat draft.md | python3 scripts/nature_preflight.py --mode nature-letter
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


SECTION_PATTERNS = {
    "abstract": re.compile(r"^\s{0,3}(?:#+\s*)?abstract\s*$", re.I),
    "summary_paragraph": re.compile(r"^\s{0,3}(?:#+\s*)?(?:summary paragraph|summary)\s*$", re.I),
    "introductory_paragraph": re.compile(r"^\s{0,3}(?:#+\s*)?introductory paragraph\s*$", re.I),
    "introduction": re.compile(r"^\s{0,3}(?:#+\s*)?introduction\s*$", re.I),
    "results": re.compile(r"^\s{0,3}(?:#+\s*)?results\s*$", re.I),
    "discussion": re.compile(r"^\s{0,3}(?:#+\s*)?discussion\s*$", re.I),
    "methods": re.compile(r"^\s{0,3}(?:#+\s*)?(?:online methods|methods)\s*$", re.I),
    "data_availability": re.compile(r"^\s{0,3}(?:#+\s*)?data availability\s*$", re.I),
    "code_availability": re.compile(r"^\s{0,3}(?:#+\s*)?code availability\s*$", re.I),
    "references": re.compile(r"^\s{0,3}(?:#+\s*)?references\s*$", re.I),
    "acknowledgements": re.compile(r"^\s{0,3}(?:#+\s*)?acknowledg(?:e)?ments\s*$", re.I),
    "funding_statement": re.compile(r"^\s{0,3}(?:#+\s*)?funding(?: statement)?\s*$", re.I),
    "author_contributions": re.compile(r"^\s{0,3}(?:#+\s*)?author contributions\s*$", re.I),
    "competing_interests": re.compile(r"^\s{0,3}(?:#+\s*)?(?:competing interests|conflict of interest|conflicts of interest)\s*$", re.I),
    "additional_information": re.compile(r"^\s{0,3}(?:#+\s*)?additional information\s*$", re.I),
    "figure_legends": re.compile(r"^\s{0,3}(?:#+\s*)?figure legends\s*$", re.I),
    "extended_data_legends": re.compile(r"^\s{0,3}(?:#+\s*)?extended data(?: figure| table)? legends\s*$", re.I),
}

MODE_REQUIREMENTS = {
    "nature-article": {
        "opening": "summary_or_first_paragraph",
        "sections_required": ["methods", "data_availability", "references", "figure_legends"],
        "sections_recommended": ["code_availability", "funding_statement", "author_contributions", "competing_interests"],
        "opening_should_be_referenced": True,
        "opening_should_not_have_headings": False,
        "opening_should_avoid_numbers": True,
        "opening_target_words_max": 200,
        "title_chars_max": 75,
        "discussion_expected": False,
        "results_expected": False,
        "main_headings_allowed": True,
    },
    "nature-letter": {
        "opening": "introductory_or_first_paragraph",
        "sections_required": ["methods", "data_availability", "references", "figure_legends"],
        "sections_recommended": ["code_availability", "funding_statement", "author_contributions", "competing_interests"],
        "opening_should_be_referenced": True,
        "opening_should_not_have_headings": True,
        "opening_should_avoid_numbers": False,
        "opening_target_words_max": 200,
        "title_chars_max": 85,
        "discussion_expected": False,
        "results_expected": False,
        "main_headings_allowed": False,
    },
    "portfolio-article": {
        "opening": "abstract_or_first_paragraph",
        "sections_required": ["methods", "data_availability", "references"],
        "sections_recommended": ["results", "discussion", "code_availability", "funding_statement", "author_contributions", "competing_interests", "figure_legends"],
        "opening_should_be_referenced": False,
        "opening_should_not_have_headings": False,
        "opening_should_avoid_numbers": False,
        "opening_target_words_max": 200,
        "title_chars_max": 120,
        "discussion_expected": True,
        "results_expected": True,
        "main_headings_allowed": True,
    },
    "portfolio-letter": {
        "opening": "introductory_or_first_paragraph",
        "sections_required": ["methods", "data_availability", "references"],
        "sections_recommended": ["code_availability", "funding_statement", "author_contributions", "competing_interests", "figure_legends"],
        "opening_should_be_referenced": True,
        "opening_should_not_have_headings": True,
        "opening_should_avoid_numbers": False,
        "opening_target_words_max": 200,
        "title_chars_max": 120,
        "discussion_expected": False,
        "results_expected": False,
        "main_headings_allowed": False,
    },
}

HYPE_WORDS = [
    "novel", "groundbreaking", "transformative", "remarkable", "unprecedented",
    "paradigm-shifting", "robust framework", "game-changing", "exciting", "important findings",
]
AI_TELL_PHRASES = [
    "highlights the importance of",
    "underscores the importance of",
    "plays a crucial role",
    "taken together",
    "in the broader context",
    "opens new avenues",
    "paves the way",
    "it is important to note that",
    "provides valuable insights",
    "state-of-the-art",
    "not only",
    "not merely",
    "in this landscape",
    "interplay",
    "fosters",
    "leverages",
]
TRANSITIONS = [
    "additionally", "moreover", "furthermore", "importantly", "notably", "overall",
    "in summary", "in conclusion", "taken together",
]
BRACKET_CITATION_RE = re.compile(r"\[(?:\d+|\d+\s*[-,]\s*\d+)(?:\s*,\s*\d+)*\]")
REFERENCE_LIKE_RE = re.compile(r"(?:\[\d+\]|(?:^|[^\w])\d{1,3}(?:,\d{1,3})*(?:[^\w]|$)|\^\d+)")
ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9-]{1,}\b")
EM_DASH_RE = re.compile(r"—")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
WORDS_RE = re.compile(r"\b[\w'-]+\b")
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n", re.M)


@dataclass
class Issue:
    severity: str
    code: str
    message: str
    evidence: str = ""


def read_text(input_path: str | None) -> str:
    if input_path:
        p = Path(input_path)
        try:
            return p.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise SystemExit(f"Error: input file not found: {p}")
        except OSError as exc:
            raise SystemExit(f"Error: could not read {p}: {exc}")
    try:
        data = sys.stdin.read()
    except OSError as exc:
        raise SystemExit(f"Error: could not read stdin: {exc}")
    if not data.strip():
        raise SystemExit("Error: no input provided. Use --input FILE or pipe manuscript text via stdin.")
    return data


def clean_text(text: str) -> str:
    # Strip common YAML frontmatter if present.
    if text.startswith("---\n"):
        parts = text.split("\n---\n", 1)
        if len(parts) == 2:
            return parts[1]
    return text


def paragraphs(text: str) -> List[str]:
    raw = [p.strip() for p in PARAGRAPH_SPLIT_RE.split(text) if p.strip()]
    return raw


def word_count(text: str) -> int:
    return len(WORDS_RE.findall(text))


def first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s:
            return s
    return ""


def normalize_title(line: str) -> str:
    if line.startswith("#"):
        return re.sub(r"^#+\s*", "", line).strip()
    return line.strip()


def detect_sections(text: str) -> Dict[str, Tuple[int, int]]:
    lines = text.splitlines()
    matches: List[Tuple[str, int]] = []
    for idx, line in enumerate(lines):
        for name, pattern in SECTION_PATTERNS.items():
            if pattern.match(line):
                matches.append((name, idx))
                break
    section_ranges: Dict[str, Tuple[int, int]] = {}
    for i, (name, start_idx) in enumerate(matches):
        end_idx = len(lines)
        if i + 1 < len(matches):
            end_idx = matches[i + 1][1]
        section_ranges[name] = (start_idx, end_idx)
    return section_ranges


def section_text(text: str, section_ranges: Dict[str, Tuple[int, int]], name: str) -> str:
    if name not in section_ranges:
        return ""
    start, end = section_ranges[name]
    lines = text.splitlines()
    content = "\n".join(lines[start + 1:end]).strip()
    return content


def get_opening_paragraph(text: str, mode: str, sections: Dict[str, Tuple[int, int]]) -> Tuple[str, str]:
    if mode in {"nature-article"} and "summary_paragraph" in sections:
        return "summary_paragraph", section_text(text, sections, "summary_paragraph")
    if mode in {"portfolio-article"} and "abstract" in sections:
        return "abstract", section_text(text, sections, "abstract")
    if mode in {"nature-letter", "portfolio-letter"} and "introductory_paragraph" in sections:
        return "introductory_paragraph", section_text(text, sections, "introductory_paragraph")

    # Fallback: first substantial paragraph after title and author lines.
    paras = paragraphs(text)
    if not paras:
        return "first_paragraph", ""
    title = normalize_title(first_nonempty_line(text))
    filtered: List[str] = []
    for p in paras:
        # Skip paragraph if it is exactly the title or very short author/affiliation blocks.
        if p == title:
            continue
        if word_count(p) < 6:
            continue
        filtered.append(p)
    opening = filtered[0] if filtered else ""
    return "first_paragraph", opening


def sentence_stats(text: str) -> Dict[str, float]:
    parts = [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]
    lengths = [word_count(s) for s in parts if word_count(s) > 0]
    if not lengths:
        return {"count": 0, "mean_words": 0.0, "stdev_words": 0.0}
    if len(lengths) == 1:
        return {"count": 1, "mean_words": float(lengths[0]), "stdev_words": 0.0}
    return {
        "count": len(lengths),
        "mean_words": round(statistics.mean(lengths), 2),
        "stdev_words": round(statistics.pstdev(lengths), 2),
    }


def count_phrases(text: str, phrases: List[str]) -> Dict[str, int]:
    lower = text.lower()
    counts: Dict[str, int] = {}
    for phrase in phrases:
        n = lower.count(phrase.lower())
        if n:
            counts[phrase] = n
    return counts


def detect_transition_openers(text: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for p in paragraphs(text):
        words = WORDS_RE.findall(p.lower())
        if not words:
            continue
        opener = " ".join(words[:2]) if len(words) >= 2 else words[0]
        for t in TRANSITIONS:
            if opener.startswith(t):
                counts[t] = counts.get(t, 0) + 1
    return counts


def detect_main_heading_usage(text: str) -> List[str]:
    bad = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("#"):
            continue
        heading = re.sub(r"^#+\s*", "", s).strip().lower()
        if heading in {"introduction", "results", "discussion"}:
            bad.append(heading)
    return bad


def detect_figure_stats_coverage(legend_text: str) -> Dict[str, bool]:
    lower = legend_text.lower()
    return {
        "has_n": bool(re.search(r"\bn\s*[=:=]", lower)) or bool(re.search(r"\bn\s+\d", lower)),
        "has_p": bool(re.search(r"\bp\s*[<=>]", lower)),
        "has_error_bar": "error bar" in lower or "error bars" in lower or "s.d." in lower or "s.e.m." in lower or "sem" in lower or "sd" in lower,
    }


def analyse(text: str, mode: str) -> Dict[str, object]:
    cfg = MODE_REQUIREMENTS[mode]
    issues: List[Issue] = []
    cleaned = clean_text(text)
    title = normalize_title(first_nonempty_line(cleaned))
    sections = detect_sections(cleaned)
    opening_name, opening_text = get_opening_paragraph(cleaned, mode, sections)
    title_chars = len(title)
    total_words = word_count(cleaned)
    opening_words = word_count(opening_text)
    sentence_info = sentence_stats(cleaned)
    em_dash_count = len(EM_DASH_RE.findall(cleaned))
    hype_counts = count_phrases(cleaned, HYPE_WORDS)
    ai_tell_counts = count_phrases(cleaned, AI_TELL_PHRASES)
    transition_openers = detect_transition_openers(cleaned)
    bracket_citation_hits = BRACKET_CITATION_RE.findall(cleaned)
    acronym_hits = ACRONYM_RE.findall(cleaned)
    acronym_count = len(acronym_hits)

    if not title:
        issues.append(Issue("critical", "missing_title", "No title detected.", "Add a clear manuscript title at the top of the file."))
    elif title_chars > cfg["title_chars_max"]:
        issues.append(Issue("warning", "long_title", f"Title length is {title_chars} characters.", f"Target for mode `{mode}` is about {cfg['title_chars_max']} characters or fewer."))

    if not opening_text:
        issues.append(Issue("critical", "missing_opening", "Could not detect an abstract, summary paragraph, or opening paragraph.", "Add an explicit opening paragraph or a headed Abstract/Summary section."))
    else:
        if opening_words > cfg["opening_target_words_max"] + 30:
            issues.append(Issue("warning", "opening_too_long", f"Opening section is {opening_words} words.", f"Target for mode `{mode}` is roughly {cfg['opening_target_words_max']} words."))
        if cfg["opening_should_be_referenced"]:
            if not REFERENCE_LIKE_RE.search(opening_text):
                issues.append(Issue("warning", "opening_unreferenced", f"Detected opening as `{opening_name}` with no citation-like markers.", "Nature-style summary or introductory paragraphs are usually referenced."))
        else:
            if REFERENCE_LIKE_RE.search(opening_text):
                issues.append(Issue("warning", "abstract_has_citations", f"Detected citation-like markers in `{opening_name}`.", "Many Nature Portfolio abstracts should be unreferenced."))
        if cfg["opening_should_avoid_numbers"] and re.search(r"\d", opening_text):
            issues.append(Issue("advisory", "opening_has_numbers", "Opening paragraph contains digits.", "For main Nature, avoid numbers in the summary paragraph unless essential."))
        if "here we show" not in opening_text.lower() and "here, we show" not in opening_text.lower() and "in this work" not in opening_text.lower():
            issues.append(Issue("advisory", "missing_here_we_show", "Opening paragraph does not use `Here we show`, `Here, we show`, or `In this work`.", "Many Nature-style openings benefit from a single explicit main-conclusion sentence."))

    # Required sections.
    for sec in cfg["sections_required"]:
        if sec not in sections:
            issues.append(Issue("critical", f"missing_{sec}", f"Missing expected section: {sec.replace('_', ' ').title()}.", "Add the section or make a deliberate case for why it is not needed."))
    for sec in cfg["sections_recommended"]:
        if sec not in sections:
            issues.append(Issue("advisory", f"missing_{sec}", f"Missing recommended section: {sec.replace('_', ' ').title()}.", "Check whether the target journal and study type require this section."))

    if cfg["results_expected"] and "results" not in sections:
        issues.append(Issue("warning", "missing_results", "Portfolio-style article mode usually expects a Results section.", "Add Results or confirm that the target journal uses a different structure."))
    if cfg["discussion_expected"] and "discussion" not in sections:
        issues.append(Issue("warning", "missing_discussion", "Portfolio-style article mode usually expects a Discussion section.", "Add Discussion or confirm that interpretation is intentionally merged elsewhere."))

    if not cfg["main_headings_allowed"]:
        bad_headings = detect_main_heading_usage(cleaned)
        if bad_headings:
            issues.append(Issue("warning", "headings_in_letter", f"Detected main headings in a letter mode: {', '.join(sorted(set(bad_headings)))}.", "Nature-style letters usually keep the main text unheaded."))

    if bracket_citation_hits:
        preview = ", ".join(bracket_citation_hits[:5])
        issues.append(Issue("advisory", "bracket_citations", f"Detected bracket citation style: {preview}", "Nature-style manuscripts usually use numbered citations rather than square-bracket citation formatting."))

    if em_dash_count > 2:
        issues.append(Issue("advisory", "emdash_overuse", f"Detected {em_dash_count} em dashes.", "Scientific prose often reads more naturally with fewer em dashes."))

    if sentence_info["count"] >= 6 and sentence_info["stdev_words"] < 4:
        issues.append(Issue("advisory", "flat_rhythm", "Sentence-length variation is low.", "Consider modest variation in sentence length to avoid monotonous prose."))

    for phrase, count in hype_counts.items():
        issues.append(Issue("advisory", "hype_word", f"Detected hype phrase `{phrase}` {count} time(s).", "Check whether the data justify this wording."))
    for phrase, count in ai_tell_counts.items():
        issues.append(Issue("advisory", "ai_tell", f"Detected AI-tell phrase `{phrase}` {count} time(s).", "Replace generic phrasing with the exact implication or mechanism."))

    for trans, count in transition_openers.items():
        if count >= 2:
            issues.append(Issue("advisory", "repeated_transition", f"Paragraphs repeatedly open with `{trans}` ({count} times).", "Vary paragraph openings and remove unnecessary signposts."))

    if acronym_count > max(8, total_words // 150):
        issues.append(Issue("advisory", "acronym_density", f"Detected {acronym_count} all-caps acronym-like tokens.", "Nature-style prose usually benefits from fewer acronyms, especially early in the manuscript."))

    figure_legend_text = section_text(cleaned, sections, "figure_legends")
    if figure_legend_text:
        legend_stats = detect_figure_stats_coverage(figure_legend_text)
        missing_bits = [k for k, present in legend_stats.items() if not present]
        if missing_bits:
            issues.append(Issue(
                "advisory",
                "legend_stats_missing",
                "Figure legends may be missing some statistical details.",
                f"Could not clearly detect: {', '.join(missing_bits)}."
            ))

    # Detect `seeks to`, common weak construction.
    weak_seek_count = len(re.findall(r"\b(?:seek|seeks|sought|aims|aimed)\s+to\b", cleaned, re.I))
    if weak_seek_count:
        issues.append(Issue("advisory", "aims_to_language", f"Detected {weak_seek_count} `seeks to`/`aims to` style constructions.", "Where results already exist, prefer direct statements of what the study shows or finds."))

    metrics = {
        "mode": mode,
        "title": title,
        "title_characters": title_chars,
        "total_words": total_words,
        "opening_detected_as": opening_name,
        "opening_words": opening_words,
        "sentence_count": sentence_info["count"],
        "mean_sentence_words": sentence_info["mean_words"],
        "sentence_word_stdev": sentence_info["stdev_words"],
        "em_dash_count": em_dash_count,
        "acronym_like_token_count": acronym_count,
    }

    section_presence = {name: (name in sections) for name in sorted(set(list(SECTION_PATTERNS.keys())))}

    summary = {
        "critical": sum(1 for i in issues if i.severity == "critical"),
        "warning": sum(1 for i in issues if i.severity == "warning"),
        "advisory": sum(1 for i in issues if i.severity == "advisory"),
        "total": len(issues),
    }

    actions = []
    for issue in issues:
        if issue.code in {"missing_title", "missing_opening", "missing_methods", "missing_data_availability", "missing_references", "missing_figure_legends"}:
            actions.append(issue.message)
        elif issue.severity in {"warning", "advisory"} and len(actions) < 8:
            actions.append(issue.message)

    return {
        "summary": summary,
        "metrics": metrics,
        "section_presence": section_presence,
        "issues": [issue.__dict__ for issue in issues],
        "suggested_actions": actions,
    }


def render_text(report: Dict[str, object]) -> str:
    lines: List[str] = []
    summary = report["summary"]
    metrics = report["metrics"]
    lines.append("Nature-style preflight")
    lines.append("======================")
    lines.append(f"Mode: {metrics['mode']}")
    lines.append(f"Title: {metrics['title'] or '[missing]'}")
    lines.append(f"Title length: {metrics['title_characters']} chars")
    lines.append(f"Total words: {metrics['total_words']}")
    lines.append(f"Opening detected as: {metrics['opening_detected_as']} ({metrics['opening_words']} words)")
    lines.append(
        f"Sentence stats: {metrics['sentence_count']} sentences, mean {metrics['mean_sentence_words']} words, stdev {metrics['sentence_word_stdev']}"
    )
    lines.append(f"Em dashes: {metrics['em_dash_count']}")
    lines.append(f"Acronym-like tokens: {metrics['acronym_like_token_count']}")
    lines.append("")
    lines.append(
        f"Issues: {summary['critical']} critical, {summary['warning']} warning, {summary['advisory']} advisory"
    )
    lines.append("")
    if report["issues"]:
        lines.append("Detailed issues")
        lines.append("---------------")
        for issue in report["issues"]:
            sev = issue["severity"].upper()
            lines.append(f"[{sev}] {issue['message']}")
            if issue.get("evidence"):
                lines.append(f"  Evidence: {issue['evidence']}")
        lines.append("")
    else:
        lines.append("No obvious issues detected by the heuristic checker.")
        lines.append("")

    if report["suggested_actions"]:
        lines.append("Suggested next actions")
        lines.append("----------------------")
        for action in report["suggested_actions"]:
            lines.append(f"- {action}")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check a manuscript draft against Nature-style structural and stylistic heuristics."
    )
    parser.add_argument(
        "--input",
        help="Path to the manuscript file. If omitted, text is read from stdin.",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=sorted(MODE_REQUIREMENTS.keys()),
        help="Target journal mode.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format. Defaults to json.",
    )
    parser.add_argument(
        "--output",
        help="Write the report to this file instead of stdout.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 2 when any critical issue is found.",
    )
    return parser.parse_args(argv)


def write_output(payload: str, output_path: str | None) -> None:
    if output_path:
        p = Path(output_path)
        try:
            p.write_text(payload, encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"Error: could not write {p}: {exc}")
    else:
        sys.stdout.write(payload)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    text = read_text(args.input)
    report = analyse(text, args.mode)
    payload = json.dumps(report, indent=2, ensure_ascii=False) if args.format == "json" else render_text(report)
    write_output(payload + ("" if payload.endswith("\n") else "\n"), args.output)
    if args.strict and report["summary"]["critical"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
