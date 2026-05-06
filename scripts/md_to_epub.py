#!/usr/bin/env python3
"""将差异论期货市场解读转换为EPUB"""

import re
import os
import zipfile
import html
from datetime import datetime

INPUT = "/root/.openclaw/workspace/The_Theory_of_Difference/04-社会科学应用/期货市场的差异论解读_V1.0.md"
OUTPUT = "/root/.openclaw/workspace/The_Theory_of_Difference/04-社会科学应用/期货市场的差异论解读_V1.0.epub"

def md_to_html(md_text):
    """Convert markdown to simple HTML, splitting into chapters"""
    lines = md_text.split('\n')
    chapters = []
    current_title = "前言"
    current_html = []
    in_code = False

    for line in lines:
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            current_html.append(f'<pre>{html.escape(line)}</pre>')
            continue
        if not line.strip():
            continue
        if line.strip() == '---':
            current_html.append('<hr/>')
            continue

        # Chapter title
        m = re.match(r'^#\s+\*\*(.+?)\*\*\s*$', line)
        if not m:
            m = re.match(r'^#\s+(.+?)\s*$', line)
        if m and not line.startswith('##'):
            if current_html:
                chapters.append((current_title, '\n'.join(current_html)))
            current_title = m.group(1).strip('*# ')
            current_html = []
            continue

        # Section title
        m = re.match(r'^##\s+\*\*(.+?)\*\*\s*$', line)
        if not m:
            m = re.match(r'^##\s+(.+?)\s*$', line)
        if m:
            current_html.append(f'<h2>{html.escape(m.group(1).strip("*# "))}</h2>')
            continue

        # Subsection
        m = re.match(r'^###\s+(.+?)\s*$', line)
        if m:
            current_html.append(f'<h3>{html.escape(m.group(1).strip("*# "))}</h3>')
            continue

        # Blockquote
        if line.startswith('>'):
            text = line.lstrip('> ').strip()
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            current_html.append(f'<blockquote><p>{text}</p></blockquote>')
            continue

        # Regular paragraph
        text = line.strip()
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        if text:
            current_html.append(f'<p>{text}</p>')

    if current_html:
        chapters.append((current_title, '\n'.join(current_html)))

    return chapters


def create_epub(chapters, output_path):
    """Create EPUB file"""
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

    # Build content.opf
    manifest_items = []
    spine_items = []
    toc_items = []

    for i, (title, _) in enumerate(chapters):
        filename = f'chapter_{i:03d}.xhtml'
        manifest_items.append(f'<item id="ch{i}" href="{filename}" media-type="application/xhtml+xml"/>')
        spine_items.append(f'<itemref idref="ch{i}"/>')
        toc_items.append((title, filename))

    # Also add CSS
    manifest_items.append('<item id="style" href="style.css" media-type="text/css"/>')

    content_opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="BookId">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>期货市场的差异论解读</dc:title>
    <dc:creator>差异论研究组</dc:creator>
    <dc:language>zh-CN</dc:language>
    <dc:identifier id="BookId">urn:uuid:futures-diff-theory-v1.0</dc:identifier>
    <dc:date>{now}</dc:date>
    <dc:description>从现货差异到价格显影——差异论对期货市场的系统解读</dc:description>
  </metadata>
  <manifest>
    {''.join(manifest_items)}
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  </manifest>
  <spine>
    {''.join(spine_items)}
  </spine>
</package>'''

    # Build nav.xhtml
    nav_list = []
    for title, filename in toc_items:
        nav_list.append(f'<li><a href="{filename}">{html.escape(title)}</a></li>')

    nav_xhtml = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>目录</title></head>
<body>
<nav epub:type="toc" id="toc">
<h1>目录</h1>
<ol>
{''.join(nav_list)}
</ol>
</nav>
</body>
</html>'''

    # CSS
    css = '''
body { font-family: "Noto Serif CJK SC", "Source Han Serif SC", "SimSun", serif; line-height: 1.8; margin: 1em; color: #1a1a1a; }
h1 { font-size: 1.6em; margin: 1.5em 0 0.8em; border-bottom: 2px solid #333; padding-bottom: 0.3em; }
h2 { font-size: 1.3em; margin: 1.2em 0 0.6em; color: #222; }
h3 { font-size: 1.1em; margin: 1em 0 0.5em; color: #333; }
p { text-indent: 2em; margin: 0.4em 0; text-align: justify; }
blockquote { margin: 1em 1.5em; padding: 0.5em 1em; border-left: 3px solid #666; background: #f9f9f9; font-style: italic; }
blockquote p { text-indent: 0; }
hr { margin: 1.5em 0; border: none; border-top: 1px solid #ccc; }
pre { background: #f4f4f4; padding: 0.8em; font-size: 0.9em; overflow-x: auto; }
strong { font-weight: bold; }
'''

    # Build chapter XHTML files
    chapter_files = []
    for i, (title, content) in enumerate(chapters):
        xhtml = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{html.escape(title)}</title><link rel="stylesheet" href="style.css"/></head>
<body>
<h1>{html.escape(title)}</h1>
{content}
</body>
</html>'''
        chapter_files.append((f'chapter_{i:03d}.xhtml', xhtml))

    # Write EPUB
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # mimetype must be first and uncompressed
        zf.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        zf.writestr('META-INF/container.xml', '''<?xml version="1.0" encoding="utf-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>''')
        zf.writestr('OEBPS/content.opf', content_opf)
        zf.writestr('OEBPS/nav.xhtml', nav_xhtml)
        zf.writestr('OEBPS/style.css', css)
        for filename, content in chapter_files:
            zf.writestr(f'OEBPS/{filename}', content)

    print(f"EPUB generated: {output_path}")
    print(f"Chapters: {len(chapters)}")


def main():
    with open(INPUT, 'r', encoding='utf-8') as f:
        md_text = f.read()

    # Start from 导论
    start = md_text.find('# **导论')
    if start == -1:
        start = md_text.find('# **第一编')
    if start == -1:
        start = 0

    chapters = md_to_html(md_text[start:])
    create_epub(chapters, OUTPUT)


if __name__ == '__main__':
    main()
