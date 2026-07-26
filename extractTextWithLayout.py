#!/usr/bin/env python3
"""Extract text with layout metadata (blocks, lines, spans, bboxes, fonts) to JSON.

Default input: data/LAWS-OF-KENYA-BOOKLET.pdf or ROOT PDF
Usage:         python3 extractTextWithLayout.py [--input PATH] [--pages SPEC] [--output-dir PATH]
"""
import json
import sys

from pdf_utils import ROOT, result_path, run

DEFAULT_PDF = ROOT / "data" / "LAWS-OF-KENYA-BOOKLET.pdf"

def sanitize_for_json(obj):
    """Recursively convert bytes/non-serializable types for json.dumps."""
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]
    return obj

def work(doc, *, input_path, output_dir, script_name, shortform, pages, logger):
    pages_layout = []
    for page_idx in pages:
        page = doc[page_idx]
        # "dict" format returns page dimensions and structured hierarchy:
        # blocks -> lines -> spans -> bbox, text, font, size, flags, color
        layout_dict = page.get_text("dict")
        pages_layout.append(sanitize_for_json({
            "page": page_idx + 1,
            "width": layout_dict.get("width"),
            "height": layout_dict.get("height"),
            "blocks": layout_dict.get("blocks", [])
        }))

    out = result_path(output_dir, script_name, shortform, ext="json")
    out.write_text(json.dumps({"pages": pages_layout}, indent=2, ensure_ascii=False), encoding="utf-8")
    
    logger.info("pages processed: %d", len(pages))
    logger.info("output: %s (%.1f KB)", out, out.stat().st_size / 1024)
    return 0


if __name__ == "__main__":
    sys.exit(run(work, input_path=DEFAULT_PDF, output_dir=ROOT / "output", output_ext="json"))
