"""Shared boilerplate for pymupdf-based scripts in this project.

Each per-script "work" function (see extractText.py for an example) receives
an already-opened, page-sliced pymupdf.Document, writes its own primary
output via `result_path(...)`, and returns an int exit code. The `run()`
driver handles argparse, logging, input validation, page slicing, the
exception-to-exit-code mapping, and duration reporting.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import pymupdf

ROOT = Path(__file__).resolve().parent

# Recognized short-forms for the PDFs you focus on most. Unknown files fall
# back to a slugified version of the filename stem.
SHORT_FORMS: dict[str, str] = {
    "LAWS-OF-KENYA-BOOKLET.pdf": "lok-booklet",
    "The_Constitution_of_Kenya_2010.pdf": "cok-2010",
}

__all__ = [
    "ROOT",
    "SHORT_FORMS",
    "short_form_for",
    "timestamp",
    "result_path",
    "log_path",
    "setup_logging",
    "open_pdf",
    "parse_pages",
    "run",
]


def short_form_for(pdf_path: Path) -> str:
    if pdf_path.name in SHORT_FORMS:
        return SHORT_FORMS[pdf_path.name]
    slug = re.sub(r"[^a-z0-9]+", "-", pdf_path.stem.lower()).strip("-")
    return slug or "doc"


def timestamp() -> str:
    """Easy-to-digest timestamp with millisecond suffix for near-run uniqueness."""
    now = datetime.now()
    return f"{now:%Y%m%d-%H%M%S}-{now.microsecond // 1000:03d}"


def result_path(output_dir: Path, script_name: str, shortform: str, ext: str = "txt") -> Path:
    """Canonical timestamped result path. The `.{txt,log}` pairing is
    guaranteed by `log_path` calling this with `ext="log"`."""
    return output_dir / f"{script_name}_{shortform}_{timestamp()}.{ext}"


def log_path(output_dir: Path, script_name: str, shortform: str) -> Path:
    return result_path(output_dir, script_name, shortform, ext="log")


def setup_logging(log_path: Path, *, name: str, level: int = logging.INFO) -> logging.Logger:
    """FileHandler (full format) + StreamHandler (terse). Logging happens
    here so the .log file exists on the FileNotFoundError path."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()  # avoid duplicate handlers on repeated in-process runs

    file_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                 datefmt="%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(file_fmt)
    logger.addHandler(fh)

    stream_fmt = logging.Formatter("[%(levelname)s] %(message)s")
    ch = logging.StreamHandler()
    ch.setFormatter(stream_fmt)
    logger.addHandler(ch)

    return logger


def open_pdf(pdf_path: Path) -> pymupdf.Document:
    """Validate and open a PDF. Caller owns the close() (use try/finally)."""
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    return pymupdf.open(pdf_path)


def parse_pages(spec: str, total: int) -> list[int]:
    """Parse a --pages spec into a list of 0-indexed page indices.

    Accepted forms:
        "all"       -> all pages
        "5"         -> single page
        "1-10"      -> inclusive range
        "1,3,5"     -> comma list
        "1-3,7,10"  -> mixed

    Returns a sorted, deduplicated list. 1-indexed in the spec, 0-indexed out.
    """
    s = spec.strip().lower()
    if s in ("", "all"):
        return list(range(total))

    indices: set[int] = set()
    for token in s.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            a, b = token.split("-", 1)
            a_i, b_i = int(a), int(b)
            if a_i > b_i:
                a_i, b_i = b_i, a_i
            for i in range(a_i, b_i + 1):
                _add_page(indices, i, total)
        else:
            _add_page(indices, int(token), total)

    return sorted(indices)


def _add_page(into: set[int], one_indexed: int, total: int) -> None:
    if one_indexed < 1 or one_indexed > total:
        raise ValueError(f"page {one_indexed} out of range 1..{total}")
    into.add(one_indexed - 1)


# Work function contract — what each per-script file supplies.
WorkFn = Callable[..., int]


def _build_argparser(script_name: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=script_name,
        description=f"Run {script_name} against a PDF with the standard ke_katiba_digest workflow.",
    )
    p.add_argument("--input", type=Path, default=None,
                   help="Path to input PDF (default: data/LAWS-OF-KENYA-BOOKLET.pdf).")
    p.add_argument("--output-dir", type=Path, default=None,
                   help="Directory for result and log files (default: output/).")
    p.add_argument("--pages", default="all",
                   help='Page spec: "all", "5", "1-10", "1,3,5" (1-indexed, default: all).')
    p.add_argument("--log-level", default="INFO",
                   help="Logging level (default: INFO). Case-insensitive.")
    return p


def _resolve_input_path(args: argparse.Namespace) -> Path:
    if args.input is not None:
        return args.input
    return ROOT / "data" / "LAWS-OF-KENYA-BOOKLET.pdf"


def _resolve_output_dir(args: argparse.Namespace) -> Path:
    return args.output_dir if args.output_dir is not None else (ROOT / "output")


def run(
    work: WorkFn,
    *,
    input_path: Path | None = None,
    output_dir: Path | None = None,
    output_ext: str = "txt",
    shortform: str | None = None,
    log_level: int | str | None = None,
    page_range: str | None = None,
    script_name: str | None = None,
) -> int:
    """Drive a per-script work function. Returns a process exit code.

    CLI form (`python3 my_script.py --input ... --pages 1-3 ...`) and
    programmatic form (pass kwargs directly) are both supported. CLI
    values override programmatic defaults.
    """
    script_name = script_name or Path(sys.argv[0]).stem

    # 1. Parse CLI. We always parse so the --help/--pages ergonomics are
    #    uniform; programmatic callers that pass all kwargs explicitly
    #    just get the same defaults as if they had omitted the flags.
    parser = _build_argparser(script_name)
    args = parser.parse_args()

    eff_input = input_path if input_path is not None else _resolve_input_path(args)
    eff_output_dir = output_dir if output_dir is not None else _resolve_output_dir(args)
    eff_pages = page_range if page_range is not None else args.pages
    eff_log_level = log_level if log_level is not None else args.log_level

    if isinstance(eff_log_level, str):
        eff_log_level = logging.getLevelName(eff_log_level.upper())
        if not isinstance(eff_log_level, int):
            print(f"error: unknown log level {eff_log_level!r}", file=sys.stderr)
            return 1

    # 2. Ensure output dir + log file exist BEFORE checking the input.
    #    The log must survive the FileNotFoundError path for post-mortem.
    eff_output_dir.mkdir(parents=True, exist_ok=True)
    sf = shortform if shortform is not None else short_form_for(eff_input)
    log_p = log_path(eff_output_dir, script_name, sf)
    logger = setup_logging(log_p, name=script_name, level=eff_log_level)

    start = time.monotonic()
    logger.info("start: %s on %s", script_name, eff_input.name)
    try:
        if not eff_input.is_file():
            raise FileNotFoundError(f"PDF not found: {eff_input}")
        logger.info("input: %s (%.1f KB)", eff_input, eff_input.stat().st_size / 1024)

        doc = open_pdf(eff_input)
        try:
            total = doc.page_count
            pages = parse_pages(eff_pages, total)
            primary = result_path(eff_output_dir, script_name, sf, ext=output_ext)
            logger.info("primary: %s", primary)

            rc = work(
                doc,
                input_path=eff_input,
                output_dir=eff_output_dir,
                script_name=script_name,
                shortform=sf,
                pages=pages,
                logger=logger,
            )
            if not isinstance(rc, int):
                rc = 0
            return rc
        finally:
            doc.close()
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1
    except (pymupdf.PyMuPDFError, ValueError) as exc:
        logger.error("extraction failed: %s", exc)
        return 1
    except OSError as exc:
        logger.error("could not write output file: %s", exc)
        return 1
    finally:
        logger.info("duration: %.2fs", time.monotonic() - start)
        logger.info("log: %s", log_p)
