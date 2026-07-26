#!/usr/bin/env python3
"""Find and extract tabular data from PDF pages into JSON and CSV files.

Default input: data/LAWS-OF-KENYA-BOOKLET.pdf or ROOT PDF
Usage:         python3 extractTables.py [--input PATH] [--pages SPEC] [--output-dir PATH]
"""
import csv
import json
import sys

from pdf_utils import ROOT, result_path, run

DEFAULT_PDF = ROOT / "data" / "LAWS-OF-KENYA-BOOKLET.pdf"


def work(doc, *, input_path, output_dir, script_name, shortform, pages, logger):
    extracted_tables = []
    csv_out_path = result_path(output_dir, script_name, shortform, ext="csv")

    table_count = 0
    all_rows = []

    for page_idx in pages:
        page = doc[page_idx]
        tabs = page.find_tables()
        for idx, tab in enumerate(tabs):
            table_count += 1
            headers = tab.header.names if tab.header else []
            rows = tab.extract()
            
            table_meta = {
                "page": page_idx + 1,
                "table_index": idx + 1,
                "bbox": list(tab.bbox),
                "rowCount": tab.row_count,
                "colCount": tab.col_count,
                "headers": headers,
                "data": rows
            }
            extracted_tables.append(table_meta)

            # Flatten to CSV list
            all_rows.append([f"# Page {page_idx + 1} Table {idx + 1}"])
            all_rows.extend(rows)
            all_rows.append([]) # Blank separator row

    json_out = result_path(output_dir, script_name, shortform, ext="json")
    json_out.write_text(json.dumps({"tables": extracted_tables}, indent=2, ensure_ascii=False), encoding="utf-8")

    if all_rows:
        with open(csv_out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(all_rows)

    logger.info("pages scanned: %d", len(pages))
    logger.info("tables found: %d", table_count)
    logger.info("JSON output: %s (%.1f KB)", json_out, json_out.stat().st_size / 1024)
    if all_rows:
        logger.info("CSV output: %s (%.1f KB)", csv_out_path, csv_out_path.stat().st_size / 1024)
    
    return 0


if __name__ == "__main__":
    sys.exit(run(work, input_path=DEFAULT_PDF, output_dir=ROOT / "output", output_ext="json"))
