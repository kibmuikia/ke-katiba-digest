import os
import re
import json
import sqlite3

WORD_TO_NUM = {
    'ONE': 1, 'TWO': 2, 'THREE': 3, 'FOUR': 4, 'FIVE': 5,
    'SIX': 6, 'SEVEN': 7, 'EIGHT': 8, 'NINE': 9, 'TEN': 10,
    'ELEVEN': 11, 'TWELVE': 12, 'THIRTEEN': 13, 'FOURTEEN': 14,
    'FIFTEEN': 15, 'SIXTEEN': 16, 'SEVENTEEN': 17, 'EIGHTEEN': 18
}

def clean_text(raw_text):
    # Locate actual body (after Table of Contents)
    body_marker = re.search(r'We,\s+the\s+people\s+of\s+Kenya', raw_text)
    if body_marker:
        # Step back to include PREAMBLE line
        preamble_line = raw_text.rfind('PREAMBLE', 0, body_marker.start())
        if preamble_line != -1:
            body_text = raw_text[preamble_line:]
        else:
            body_text = raw_text[body_marker.start():]
    else:
        body_text = raw_text

    # Strip page headers/footers
    cleaned = re.sub(
        r'(\d+\s*\n+\s*Constitution of Kenya 2010|Constitution of Kenya 2010\s*\n+\s*\d+|\b\d+\s+Constitution of Kenya 2010)',
        '',
        body_text
    )
    cleaned = re.sub(r'Revised and published by the National Council for Law Reporting.*?\n\n', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'Printed by Katiba Institute', '', cleaned)
    cleaned = re.sub(r'www\.kenyalaw\.org', '', cleaned)
    return cleaned

def parse_constitution(md_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    cleaned_text = clean_text(raw_text)
    
    # Split body between Main Articles and Schedules
    sched_split = re.search(r'\nSCHEDULES\n', cleaned_text)
    if sched_split:
        main_body = cleaned_text[:sched_split.start()]
        schedules_body = cleaned_text[sched_split.start():]
    else:
        main_body = cleaned_text
        schedules_body = ""

    lines = [l.strip() for l in main_body.split('\n') if l.strip()]

    ast = {
        "metadata": {
            "title": "The Constitution of Kenya, 2010",
            "country": "Kenya",
            "year": 2010,
            "source": "National Council for Law Reporting (Kenya Law) / Katiba Institute",
            "parsed_at": "2026-07-27"
        },
        "preamble": {
            "node_id": "coK2010:preamble",
            "text": "",
            "paragraphs": []
        },
        "chapters": [],
        "schedules": []
    }

    current_chapter = None
    current_part = None
    current_article = None
    current_clause = None
    current_subclause = None

    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        if line == 'PREAMBLE':
            i += 1
            while i < n and not lines[i].startswith('CHAPTER'):
                if lines[i] and not lines[i].startswith('Constitution of Kenya'):
                    ast['preamble']['paragraphs'].append(lines[i].replace('**', ''))
                i += 1
            ast['preamble']['text'] = "\n\n".join(ast['preamble']['paragraphs'])
            continue

        if line.startswith('CHAPTER'):
            parts = line.split()
            ch_word = parts[1] if len(parts) > 1 else 'ONE'
            ch_num = WORD_TO_NUM.get(ch_word, 1)

            title_lines = []
            i += 1
            while i < n and (lines[i].startswith('**') or lines[i].isupper()) and not re.match(r'^\d+\.', lines[i]) and not lines[i].startswith('PART'):
                title_lines.append(lines[i].replace('**', '').strip())
                i += 1
            ch_title = " ".join(title_lines) if title_lines else f"Chapter {ch_num}"

            current_chapter = {
                "node_id": f"coK2010:ch{ch_num}",
                "number": ch_num,
                "title": ch_title,
                "parts": [],
                "articles": []
            }
            ast['chapters'].append(current_chapter)
            current_part = None
            current_article = None
            continue

        if line.startswith('PART'):
            part_m = re.match(r'^PART\s+(\d+)\s*[–—\-]?\s*(.*)', line)
            if part_m:
                part_num = int(part_m.group(1))
                part_title = part_m.group(2).strip()
                if not part_title and i + 1 < n and lines[i+1].startswith('**'):
                    i += 1
                    part_title = lines[i].replace('**', '').strip()

                current_part = {
                    "node_id": f"{current_chapter['node_id']}:pt{part_num}",
                    "number": part_num,
                    "title": part_title,
                    "articles": []
                }
                current_chapter['parts'].append(current_part)
            i += 1
            continue

        art_m = re.match(r'^(\d+)\s*\.\s*(.*)', line)
        if art_m:
            art_num = int(art_m.group(1))
            art_title = art_m.group(2).replace('**', '').strip()

            current_article = {
                "node_id": f"coK2010:art{art_num}",
                "number": art_num,
                "title": art_title,
                "canonical_ref": f"Article {art_num}",
                "clauses": [],
                "raw_text": ""
            }

            if current_part:
                current_part['articles'].append(current_article)
            elif current_chapter:
                current_chapter['articles'].append(current_article)

            current_clause = None
            current_subclause = None
            i += 1
            continue

        cl_m = re.match(r'^\((\d+)\)\s+(.*)', line)
        if cl_m and current_article:
            cl_id = cl_m.group(1)
            cl_text = cl_m.group(2)

            # Safeguard against duplicate clause ID within same article
            existing_ids = [c['identifier'] for c in current_article['clauses']]
            if cl_id in existing_ids:
                cl_id_unique = f"{cl_id}_{len(existing_ids)+1}"
            else:
                cl_id_unique = cl_id

            current_clause = {
                "node_id": f"{current_article['node_id']}:cl{cl_id_unique}",
                "identifier": cl_id,
                "canonical_ref": f"{current_article['canonical_ref']}({cl_id})",
                "text": cl_text,
                "subclauses": []
            }
            current_article['clauses'].append(current_clause)
            current_subclause = None
            i += 1
            continue

        sub_m = re.match(r'^\(([a-z0-9]+)\)\s+(.*)', line)
        if sub_m and current_clause:
            sub_id = sub_m.group(1)
            sub_text = sub_m.group(2)

            existing_sub_ids = [s['node_id'] for s in current_clause['subclauses']]
            target_sub_id = f"{current_clause['node_id']}:sub{sub_id}"
            if target_sub_id in existing_sub_ids:
                target_sub_id = f"{target_sub_id}_{len(existing_sub_ids)+1}"

            current_subclause = {
                "node_id": target_sub_id,
                "identifier": sub_id,
                "canonical_ref": f"{current_clause['canonical_ref']}({sub_id})",
                "text": sub_text,
                "items": []
            }
            current_clause['subclauses'].append(current_subclause)
            i += 1
            continue

        if current_subclause:
            current_subclause['text'] += " " + line
        elif current_clause:
            current_clause['text'] += " " + line
        elif current_article:
            if not current_article['clauses']:
                current_article['raw_text'] += (" " if current_article['raw_text'] else "") + line

        i += 1

    # Parse Schedules body
    if schedules_body:
        sched_lines = [l.strip() for l in schedules_body.split('\n') if l.strip()]
        cur_sched = None
        for sl in sched_lines:
            if 'FIRST SCHEDULE' in sl:
                cur_sched = {"node_id": "coK2010:sch1", "number": 1, "title": "COUNTIES", "content_markdown": ""}
                ast['schedules'].append(cur_sched)
            elif 'SECOND SCHEDULE' in sl:
                cur_sched = {"node_id": "coK2010:sch2", "number": 2, "title": "NATIONAL SYMBOLS", "content_markdown": ""}
                ast['schedules'].append(cur_sched)
            elif 'THIRD SCHEDULE' in sl:
                cur_sched = {"node_id": "coK2010:sch3", "number": 3, "title": "NATIONAL OATHS AND AFFIRMATIONS", "content_markdown": ""}
                ast['schedules'].append(cur_sched)
            elif 'FOURTH SCHEDULE' in sl:
                cur_sched = {"node_id": "coK2010:sch4", "number": 4, "title": "DISTRIBUTION OF FUNCTIONS BETWEEN THE NATIONAL GOVERNMENT AND THE COUNTY GOVERNMENTS", "content_markdown": ""}
                ast['schedules'].append(cur_sched)
            elif 'FIFTH SCHEDULE' in sl:
                cur_sched = {"node_id": "coK2010:sch5", "number": 5, "title": "LEGISLATION TO BE ENACTED BY PARLIAMENT", "content_markdown": ""}
                ast['schedules'].append(cur_sched)
            elif 'SIXTH SCHEDULE' in sl:
                cur_sched = {"node_id": "coK2010:sch6", "number": 6, "title": "TRANSITIONAL AND CONSEQUENTIAL PROVISIONS", "content_markdown": ""}
                ast['schedules'].append(cur_sched)
            elif cur_sched:
                cur_sched['content_markdown'] += sl + "\n"

    return ast

print("Cleaned build_katiba_digest parser updated.")
