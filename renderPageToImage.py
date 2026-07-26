#!/usr/bin/env python3
"""Render sample pages from PDF to PNG images using PyMuPDF Page.get_pixmap().

Default input: data/LAWS-OF-KENYA-BOOKLET.pdf or ROOT PDF
Usage:         python3 renderPageToImage.py [--input PATH] [--pages SPEC] [--output-dir PATH] [--dpi DPI]
"""
import argparse
import sys

import pymupdf
from pdf_utils import ROOT, result_path, run

DEFAULT_PDF = ROOT / "data" / "LAWS-OF-KENYA-BOOKLET.pdf"


def work(doc, *, input_path, output_dir, script_name, shortform, pages, logger):
    # Parse dpi option if provided via additional CLI args
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--dpi", type=int, default=150, help="Image DPI (default: 150)")
    args, _ = parser.parse_known_args()

    dpi = args.dpi
    zoom = dpi / 72.0
    mat = pymupdf.Matrix(zoom, zoom)

    rendered_files = []
    for page_idx in pages:
        page = doc[page_idx]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Save individual page image
        out_img = result_path(output_dir, f"{script_name}_p{page_idx + 1}", shortform, ext="png")
        pix.save(str(out_img))
        rendered_files.append(out_img)
        logger.info("Rendered page %d -> %s (%.1f KB)", page_idx + 1, out_img.name, out_img.stat().st_size / 1024)

    logger.info("Total rendered pages: %d (DPI: %d)", len(rendered_files), dpi)
    return 0


if __name__ == "__main__":
    sys.exit(run(work, input_path=DEFAULT_PDF, output_dir=ROOT / "output", output_ext="png"))
