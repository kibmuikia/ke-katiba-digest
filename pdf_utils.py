"""Shared boilerplate for PyMuPDF-based scripts in this project."""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import pymupdf

ROOT = Path(__file__).resolve().parent

# Mapping known filenames to short identifiers for output naming
SHORT_FORMS: dict[str, str] = {
    "LAWS-OF-KENYA-BOOKLET.pdf": "lok-bk",
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
    """Generate a clean slug identifier from the PDF filename."""
    if pdf_path.name in SHORT_FORMS:
        return SHORT_FORMS[pdf_path.name]
    slug = re.sub(r"[^a-z0-9]+", "-", pdf_path.stem.lower()).strip("-")
    return slug or "doc"


def timestamp() -> str:
    """Generate human-readable timestamp: YYYY-Mon-DD_h<H>m<M>s<S>-<ms>_<pid> with fallbacks."""
    try:
        now = datetime.now()
        # %b gives locale-dependent abbreviated month (e.g., 'Jul').
        # Fallback safeguard in case locale formatting behaves unexpectedly.
        month_str = now.strftime("%b")
        if not month_str or len(month_str) != 3:
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            month_str = months[now.month - 1]

        return (
            f"{now.year}-{month_str}-{now.day:02d}_"
            f"h{now.hour:02d}m{now.minute:02d}s{now.second:02d}-"
            f"{now.microsecond // 1000:03d}_{os.getpid()}"
        )
    except Exception:
        # Ultimate fallback to ensure logging/file creation never blocks due to formatting errors
        ts = int(time.time() * 1000)
        return f"fallback-{ts}_{os.getpid()}"


def result_path(output_dir: Path, script_name: str, shortform: str, ext: str = "txt") -> Path:
    """Build output file path using script name, PDF slug, and unique timestamp."""
    return output_dir / f"{script_name}_{shortform}_{timestamp()}.{ext}"


def log_path(output_dir: Path, script_name: str, shortform: str) -> Path:
    """Build log file path matching the result_path naming scheme."""
    return result_path(output_dir, script_name, shortform, ext="log")


def setup_logging(log_p: Path, *, name: str, level: int = logging.INFO) -> logging.Logger:
    """Configure file and console loggers; purge stale handlers to prevent duplicate lines."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Detach previous handlers (prevents handler leaks across sequential calls)
    for h in logger.handlers[:]:
        h.close()
        logger.removeHandler(h)

    # Attach file handler (full format)
    fh = logging.FileHandler(log_p, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(fh)

    # Attach console handler (terse format)
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)

    return logger


def open_pdf(pdf_path: Path) -> pymupdf.Document:
    """Validate existence and return an opened PyMuPDF Document instance."""
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    return pymupdf.open(pdf_path)


def parse_pages(spec: str, total: int) -> list[int]:
    """Parse 1-indexed page range specs ("all", "1-10", "1,3,5") to 0-indexed integer list."""
    s = spec.strip().lower()
    if not s or s == "all":
        return list(range(total))

    indices: set[int] = set()
    for token in s.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token and not token.startswith("-"):
            # Handle ranges like "1-10"
            parts = token.split("-")
            if len(parts) != 2:
                raise ValueError(f"Invalid range spec: '{token}'")
            a, b = int(parts[0]), int(parts[1])
            if a > b:
                raise ValueError(f"Range start ({a}) exceeds end ({b})")
            for i in range(a, b + 1):
                _add_page(indices, i, total)
        else:
            # Handle single page number
            _add_page(indices, int(token), total)

    return sorted(indices)


def _add_page(into: set[int], one_indexed: int, total: int) -> None:
    """Validate 1-indexed page bound and add as 0-indexed into target set."""
    if one_indexed < 1 or one_indexed > total:
        raise ValueError(f"Page {one_indexed} out of range 1..{total}")
    into.add(one_indexed - 1)


WorkFn = Callable[..., int]


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
    """Driver harness: handles CLI, logging setup, PDF opening, error handling, and runtime telemetry."""
    script_name = script_name or Path(sys.argv[0]).stem

    # 1. Parse CLI flags
    parser = argparse.ArgumentParser(prog=script_name, description=f"Run {script_name} harness.")
    parser.add_argument("--input", type=Path, help="Path to input PDF.")
    parser.add_argument("--output-dir", type=Path, help="Directory for output results and logs.")
    parser.add_argument("--pages", help='Page range spec e.g. "all", "1-10", "1,3,5".')
    parser.add_argument("--log-level", help="Logging level (DEBUG, INFO, WARNING, ERROR).")

    args, _ = parser.parse_known_args()

    # 2. Resolve precedence: CLI args > programmatic parameters > default paths
    eff_input = args.input or input_path or (ROOT / "data" / "LAWS-OF-KENYA-BOOKLET.pdf")
    eff_output_dir = args.output_dir or output_dir or (ROOT / "output")
    eff_pages = args.pages or page_range or "all"
    eff_log_level = args.log_level or log_level or "INFO"

    if isinstance(eff_log_level, str):
        eff_log_level = logging.getLevelName(eff_log_level.upper())

    # 3. Setup output directory & file logging before PDF execution
    eff_output_dir.mkdir(parents=True, exist_ok=True)
    sf = shortform or short_form_for(eff_input)
    log_p = log_path(eff_output_dir, script_name, sf)
    logger = setup_logging(log_p, name=script_name, level=eff_log_level)

    start = time.monotonic()
    logger.info("start: %s on %s", script_name, eff_input.name)

    doc: pymupdf.Document | None = None
    try:
        # 4. Open PDF document and parse target page indices
        doc = open_pdf(eff_input)
        logger.info("input: %s (%.1f KB)", eff_input, eff_input.stat().st_size / 1024)

        pages = parse_pages(eff_pages, doc.page_count)
        primary = result_path(eff_output_dir, script_name, sf, ext=output_ext)
        logger.info("primary: %s", primary)

        # 5. Execute user-defined script work function
        rc = work(
            doc,
            input_path=eff_input,
            output_dir=eff_output_dir,
            script_name=script_name,
            shortform=sf,
            pages=pages,
            logger=logger,
        )
        return rc if isinstance(rc, int) else 0

    # 6. Central error handling & log reporting
    except FileNotFoundError as exc:
        logger.error("File error: %s", exc)
        return 1
    except (pymupdf.PyMuPDFError, ValueError) as exc:
        logger.error("Processing failed: %s", exc)
        return 1
    except OSError as exc:
        logger.error("I/O write error: %s", exc)
        return 1

    # 7. Telemetry & resource cleanup (always closes document and log handles)
    finally:
        if doc is not None:
            doc.close()
        logger.info("duration: %.2fs", time.monotonic() - start)
        logger.info("log: %s", log_p)
        for h in logger.handlers[:]:
            h.close()
            logger.removeHandler(h)
