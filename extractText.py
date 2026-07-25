#!/usr/bin/env python3
"""Extract text from a PDF in data/ and write a result file + log to output/.

Default input: data/LAWS-OF-KENYA-BOOKLET.pdf
Usage:         python3 extractText.py [--input PATH] [--pages SPEC] [--output-dir PATH] [--log-level LEVEL]
"""
import sys

from pdf_utils import ROOT, result_path, run

DEFAULT_PDF = ROOT / "data" / "LAWS-OF-KENYA-BOOKLET.pdf"


def work(doc, *, input_path, output_dir, script_name, shortform, pages, logger):
    text = [doc[i].get_text() for i in pages]
    if not text:
        raise ValueError(f"No text extracted from {input_path}")
    out = result_path(output_dir, script_name, shortform, ext="txt")
    out.write_text("\n".join(text), encoding="utf-8")
    logger.info("pages: %d", len(pages))
    logger.info("output: %s (%.1f KB)", out, out.stat().st_size / 1024)
    return 0


if __name__ == "__main__":
    sys.exit(run(work, input_path=DEFAULT_PDF, output_dir=ROOT / "output", output_ext="txt"))
