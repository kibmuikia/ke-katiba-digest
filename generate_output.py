import os
import json
import sqlite3
from build_katiba_digest import parse_constitution

md_file = "/rool-drive/ke-katiba-digest/output-Sun Jul 26 23_55_48 EAT 2026/convertToMarkdown_lok-bk_2026-Jul-26_h23m54s15-606_33261.md"
json_out = "/rool-drive/ke-katiba-digest/constitution_kenya_2010.json"
db_out = "/rool-drive/ke-katiba-digest/constitution_kenya_2010.db"

ast = parse_constitution(md_file)

# Save JSON AST
with open(json_out, 'w', encoding='utf-8') as f:
    json.dump(ast, f, indent=2, ensure_ascii=False)

print(f"JSON AST written to: {json_out} ({os.path.getsize(json_out)} bytes)")

# SQLite Database Populator
if os.path.exists(db_out):
    os.remove(db_out)

conn = sqlite3.connect(db_out)
cur = conn.cursor()

cur.execute("""
CREATE TABLE constitution_nodes (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    node_type TEXT NOT NULL,
    chapter_num INTEGER,
    part_num INTEGER,
    article_num INTEGER,
    clause_num TEXT,
    subclause_id TEXT,
    title TEXT,
    canonical_ref TEXT NOT NULL,
    text_content TEXT NOT NULL,
    depth INTEGER NOT NULL,
    sort_order INTEGER NOT NULL
)
""")

cur.execute("""
CREATE VIRTUAL TABLE constitution_fts USING fts5(
    id UNINDEXED,
    canonical_ref,
    title,
    text_content,
    content='constitution_nodes',
    content_rowid='rowid'
)
""")

sort_order = 0
inserted_ids = set()

def insert_node(node_id, parent_id, node_type, ch_num, pt_num, art_num, cl_num, sub_id, title, can_ref, text, depth):
    global sort_order, inserted_ids
    if node_id in inserted_ids:
        return
    sort_order += 1
    cur.execute("""
        INSERT INTO constitution_nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (node_id, parent_id, node_type, ch_num, pt_num, art_num, cl_num, sub_id, title, can_ref, text, depth, sort_order))
    inserted_ids.add(node_id)

# Insert Preamble
insert_node(
    ast['preamble']['node_id'], None, 'preamble', None, None, None, None, None,
    'Preamble', 'Preamble', ast['preamble']['text'], 0
)

# Traverse AST and populate SQL
for ch in ast['chapters']:
    insert_node(ch['node_id'], None, 'chapter', ch['number'], None, None, None, None, ch['title'], f"Chapter {ch['number']}", ch['title'], 1)
    
    # Chapter Direct Articles
    for art in ch['articles']:
        insert_node(art['node_id'], ch['node_id'], 'article', ch['number'], None, art['number'], None, None, art['title'], art['canonical_ref'], art['raw_text'] or art['title'], 2)
        for cl in art['clauses']:
            insert_node(cl['node_id'], art['node_id'], 'clause', ch['number'], None, art['number'], cl['identifier'], None, art['title'], cl['canonical_ref'], cl['text'], 3)
            for sub in cl['subclauses']:
                insert_node(sub['node_id'], cl['node_id'], 'subclause', ch['number'], None, art['number'], cl['identifier'], sub['identifier'], art['title'], sub['canonical_ref'], sub['text'], 4)

    # Chapter Parts
    for pt in ch['parts']:
        insert_node(pt['node_id'], ch['node_id'], 'part', ch['number'], pt['number'], None, None, None, pt['title'], f"Chapter {ch['number']} Part {pt['number']}", pt['title'], 2)
        for art in pt['articles']:
            insert_node(art['node_id'], pt['node_id'], 'article', ch['number'], pt['number'], art['number'], None, None, art['title'], art['canonical_ref'], art['raw_text'] or art['title'], 3)
            for cl in art['clauses']:
                insert_node(cl['node_id'], art['node_id'], 'clause', ch['number'], pt['number'], art['number'], cl['identifier'], None, art['title'], cl['canonical_ref'], cl['text'], 4)
                for sub in cl['subclauses']:
                    insert_node(sub['node_id'], cl['node_id'], 'subclause', ch['number'], pt['number'], art['number'], cl['identifier'], sub['identifier'], art['title'], sub['canonical_ref'], sub['text'], 5)

# Insert Schedules
for sch in ast['schedules']:
    insert_node(sch['node_id'], None, 'schedule', None, None, None, None, None, sch['title'], f"Schedule {sch['number']}", sch['content_markdown'], 1)

# Populate FTS index
cur.execute("""
INSERT INTO constitution_fts(rowid, id, canonical_ref, title, text_content)
SELECT rowid, id, canonical_ref, title, text_content FROM constitution_nodes
""")

conn.commit()
conn.close()

print(f"SQLite DB generated successfully: {db_out} ({os.path.getsize(db_out)} bytes)")
