import re
from build_katiba_digest import clean_markdown

md_file = "/rool-drive/ke-katiba-digest/output-Sun Jul 26 23_55_48 EAT 2026/convertToMarkdown_lok-bk_2026-Jul-26_h23m54s15-606_33261.md"
cleaned_text = clean_markdown(md_file)

lines = [l.strip() for l in cleaned_text.split('\n') if l.strip()]

# Test regex patterns on cleaned text
chapter_pattern = re.compile(r'^(?:#+|\*\*)*\s*CHAPTER\s+([A-Z]+)\s*[–—\-]\s*(.*?)(?:\*\*)*$', re.IGNORECASE)
part_pattern = re.compile(r'^(?:#+|\*\*)*\s*PART\s+(\d+)\s*[–—\-]?\s*(.*?)(?:\*\*)*$', re.IGNORECASE)
article_pattern = re.compile(r'^(?:#+|\*\*)*\s*(\d+)\.\s+(.*?)(?:\*\*)*$')
clause_pattern = re.compile(r'^\((\d+)\)\s+(.*)')

chapters_found = []
articles_found = []

for idx, line in enumerate(lines):
    ch_m = chapter_pattern.match(line)
    if ch_m:
        chapters_found.append((idx, line, ch_m.group(1), ch_m.group(2)))
    
    art_m = article_pattern.match(line)
    if art_m:
        articles_found.append((idx, art_m.group(1), art_m.group(2)))

print(f"Total lines: {len(lines)}")
print(f"Chapters found: {len(chapters_found)}")
for c in chapters_found[:5]:
    print("  Chapter:", c)

print(f"Articles found: {len(articles_found)}")
for a in articles_found[:10]:
    print("  Article:", a)
