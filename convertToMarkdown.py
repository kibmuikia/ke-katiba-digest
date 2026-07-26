#!/usr/bin/env python3
"""Convert PDF content to Markdown optimized for LLM ingestion.

Uses pymupdf4llm or PyMuPDF page.get_text("markdown") to extract structured MD text.

Default input: data/LAWS-OF-KENYA-BOOKLET.pdf or ROOT PDF
Usage:         python3 convertToMarkdown.py [--input PATH] [--pages SPEC] [--output-dir PATH]
"""
import sys

from pdf_utils import ROOT, result_path, run

DEFAULT_PDF = ROOT / "data" / "LAWS-OF-KENYA-BOOKLET.pdf"


def work(doc, *, input_path, output_dir, script_name, shortform, pages, logger):
    md_content = []

    # Attempt pymupdf4llm high-level converter first if available
    use_pymupdf4llm = False
    try:
        import pymupdf4llm
        use_pymupdf4llm = True
    except ImportError:
        logger.info("pymupdf4llm not installed; falling back to native page.get_text('markdown')")

    if use_pymupdf4llm:
        # Convert specified pages with pymupdf4llm
        full_md = pymupdf4llm.to_markdown(str(input_path), pages=pages)
        md_content.append(full_md)
    else:
        for page_idx in pages:
            page = doc[page_idx]
            # Try native markdown mode (available in PyMuPDF 1.23.0+)
            try:
                page_md = page.get_text("markdown")
            except Exception:
                page_md = page.get_text("text")
            
            md_content.append(f"<!-- Page {page_idx + 1} -->\n\n" + page_md)

    out = result_path(output_dir, script_name, shortform, ext="md")
    out.write_text("\n\n".join(md_content), encoding="utf-8")

    logger.info("pages converted: %d", len(pages))
    logger.info("output: %s (%.1f KB)", out, out.stat().st_size / 1024)
    return 0


if __name__ == "__main__":
    sys.exit(run(work, input_path=DEFAULT_PDF, output_ext="md"))
