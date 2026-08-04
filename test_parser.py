"""
Smoke test for the chapter/part/article/clause regex patterns used by
build_katiba_digest.py, run against the cleaned markdown output of the
PDF->markdown conversion step.

Usage:
    python test_parser.py
    python test_parser.py --md-file /path/to/convertToMarkdown_....md
    python test_parser.py --search-dir output --log-level DEBUG
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from build_katiba_digest import clean_text
except ImportError as exc:  # build_katiba_digest.py missing or broken
    logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")
    logging.error(
        "Could not import 'clean_text' from build_katiba_digest.py (%s). "
        "Make sure test_parser.py is run from the project root, or that "
        "build_katiba_digest.py is on PYTHONPATH.",
        exc,
    )
    sys.exit(1)

logger = logging.getLogger("test_parser")

# Default location if no --md-file is given. Kept as a constant so a change
# only needs to happen in one place.
DEFAULT_MD_FILE = Path(
    "/Users/kibverse/Projects/scripts/ke_katiba_digest/output/convertToMarkdown_lok-bk_2026-Jul-26_h23m54s15-606_33261.md"
)

# Where to look if DEFAULT_MD_FILE (or a user-supplied path) doesn't exist.
FALLBACK_SEARCH_DIR = Path("output")
FALLBACK_GLOB = "convertToMarkdown_*.md"

CHAPTER_PATTERN = re.compile(
    r"^(?:#+|\*\*)*\s*CHAPTER\s+([A-Z]+)\s*[–—\-]\s*(.*?)(?:\*\*)*$", re.IGNORECASE
)
PART_PATTERN = re.compile(
    r"^(?:#+|\*\*)*\s*PART\s+(\d+)\s*[–—\-]?\s*(.*?)(?:\*\*)*$", re.IGNORECASE
)
ARTICLE_PATTERN = re.compile(r"^(?:#+|\*\*)*\s*(\d+)\.\s+(.*?)(?:\*\*)*$")
CLAUSE_PATTERN = re.compile(r"^\((\d+)\)\s+(.*)")


@dataclass(frozen=True)
class ChapterMatch:
    line_index: int
    raw_line: str
    number_word: str
    title: str


@dataclass(frozen=True)
class ArticleMatch:
    line_index: int
    number: str
    title: str


def resolve_md_file(preferred: Path, search_dir: Path, pattern: str) -> Path:
    """
    Return a markdown file to test against.

    Tries `preferred` first. If it doesn't exist, logs a warning and falls
    back to the most recently modified file matching `pattern` inside
    `search_dir`. Raises FileNotFoundError if neither is available, so the
    caller can decide how to report/exit.
    """
    if preferred.exists():
        logger.info("Using markdown source: %s", preferred)
        return preferred

    logger.warning("Preferred markdown file not found: %s", preferred)
    logger.info("Falling back to search directory: %s (pattern=%s)", search_dir, pattern)

    if not search_dir.exists():
        raise FileNotFoundError(
            f"Neither the preferred file ({preferred}) nor the fallback "
            f"search directory ({search_dir}) exist."
        )

    candidates = sorted(
        search_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not candidates:
        raise FileNotFoundError(
            f"No files matching '{pattern}' found in fallback directory "
            f"({search_dir}), and preferred file was missing."
        )

    chosen = candidates[0]
    logger.warning(
        "Falling back to most recently modified match: %s (%d candidate(s) found)",
        chosen,
        len(candidates),
    )
    return chosen


def load_and_clean(md_file: Path) -> str:
    """Read md_file and run it through clean_text, with targeted error handling."""
    try:
        raw_text = md_file.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(
            f"{md_file} is not valid UTF-8 ({exc}). "
            "Confirm the conversion step wrote UTF-8 output."
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"Could not read {md_file}: {exc}") from exc

    if not raw_text.strip():
        raise RuntimeError(f"{md_file} is empty; nothing to test against.")

    try:
        cleaned_text = clean_text(raw_text)
    except Exception as exc:  # clean_text is third-party to this module
        raise RuntimeError(f"clean_text() raised while processing {md_file}: {exc}") from exc

    if not cleaned_text.strip():
        raise RuntimeError(
            f"clean_text() returned empty output for {md_file}. "
            "Check that the file actually contains the expected body markers."
        )

    return cleaned_text


def find_matches(lines: list[str]) -> tuple[list[ChapterMatch], list[ArticleMatch]]:
    chapters: list[ChapterMatch] = []
    articles: list[ArticleMatch] = []

    for idx, line in enumerate(lines):
        ch_m = CHAPTER_PATTERN.match(line)
        if ch_m:
            chapters.append(ChapterMatch(idx, line, ch_m.group(1), ch_m.group(2)))

        art_m = ARTICLE_PATTERN.match(line)
        if art_m:
            articles.append(ArticleMatch(idx, art_m.group(1), art_m.group(2)))

    return chapters, articles


def report(lines: list[str], chapters: list[ChapterMatch], articles: list[ArticleMatch]) -> None:
    logger.info("Total lines: %d", len(lines))

    logger.info("Chapters found: %d", len(chapters))
    for c in chapters[:5]:
        logger.info("  Chapter: line=%d word=%s title=%r", c.line_index, c.number_word, c.title)
    if not chapters:
        logger.warning("No chapters matched — CHAPTER_PATTERN may be out of sync with the source.")

    logger.info("Articles found: %d", len(articles))
    for a in articles[:10]:
        logger.info("  Article: line=%d number=%s title=%r", a.line_index, a.number, a.title)
    if not articles:
        logger.warning("No articles matched — ARTICLE_PATTERN may be out of sync with the source.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--md-file",
        type=Path,
        default=DEFAULT_MD_FILE,
        help="Path to the converted markdown file to test against.",
    )
    parser.add_argument(
        "--search-dir",
        type=Path,
        default=FALLBACK_SEARCH_DIR,
        help="Directory to search for a fallback markdown file if --md-file is missing.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(levelname)s: %(message)s")

    try:
        md_file = resolve_md_file(args.md_file, args.search_dir, FALLBACK_GLOB)
        cleaned_text = load_and_clean(md_file)
    except FileNotFoundError as exc:
        logger.error("No usable markdown source found: %s", exc)
        return 1
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1

    lines = [l.strip() for l in cleaned_text.split("\n") if l.strip()]
    chapters, articles = find_matches(lines)
    report(lines, chapters, articles)

    return 0


if __name__ == "__main__":
    sys.exit(main())
