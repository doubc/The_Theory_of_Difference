#!/usr/bin/env python3
"""将优化后的差异论期货市场解读转换为PDF"""

import re
from fpdf import FPDF

INPUT = "/root/.openclaw/workspace/The_Theory_of_Difference/04-社会科学应用/期货市场的差异论解读_V1.0.md"
OUTPUT = "/root/.openclaw/workspace/The_Theory_of_Difference/04-社会科学应用/期货市场的差异论解读_V1.0.pdf"

FONT_REGULAR = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"

class PDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("serif", size=8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, "期货市场的差异论解读", align="C", new_x="LMARGIN", new_y="NEXT")
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("serif", size=8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"— {self.page_no()} —", align="C")

    def chapter_title(self, title):
        self.set_font("serif", style="B", size=16)
        self.set_text_color(0, 0, 0)
        self.ln(8)
        self.multi_cell(0, 10, title.strip("*# "), align="L")
        self.ln(4)

    def section_title(self, title):
        self.set_font("serif", style="B", size=13)
        self.set_text_color(30, 30, 30)
        self.ln(4)
        self.multi_cell(0, 8, title.strip("*# "), align="L")
        self.ln(2)

    def subsection_title(self, title):
        self.set_font("serif", style="B", size=11)
        self.set_text_color(50, 50, 50)
        self.ln(3)
        self.multi_cell(0, 7, title.strip("*# "), align="L")
        self.ln(2)

    def body_text(self, text):
        self.set_font("serif", size=10.5)
        self.set_text_color(0, 0, 0)
        # Clean markdown formatting
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = text.strip()
        if text:
            self.multi_cell(0, 6.5, text, align="J")
            self.ln(2)

    def separator(self):
        self.ln(4)
        y = self.get_y()
        self.line(80, y, 130, y)
        self.ln(6)

    def blockquote(self, text):
        self.set_font("serif", style="B", size=10.5)
        self.set_text_color(40, 40, 40)
        x = self.get_x()
        self.set_x(x + 8)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        self.multi_cell(0 - 8, 6.5, text.strip(), align="L")
        self.set_x(x)
        self.ln(2)


def parse_and_render(pdf, md_text):
    lines = md_text.split('\n')
    i = 0
    in_code_block = False

    while i < len(lines):
        line = lines[i]

        # Skip code blocks
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            i += 1
            continue
        if in_code_block:
            i += 1
            continue

        # Skip empty lines
        if not line.strip():
            i += 1
            continue

        # Separator
        if line.strip() == '---':
            pdf.separator()
            i += 1
            continue

        # Chapter title (# **X**)
        m = re.match(r'^#\s+\*\*(.+?)\*\*\s*$', line)
        if m:
            # Add page break before chapter titles (except first)
            if pdf.page_no() > 1:
                pdf.add_page()
            pdf.chapter_title(m.group(1))
            i += 1
            continue

        # Chapter title without bold (# X)
        m = re.match(r'^#\s+(.+?)\s*$', line)
        if m and not line.startswith('##'):
            if pdf.page_no() > 1:
                pdf.add_page()
            pdf.chapter_title(m.group(1))
            i += 1
            continue

        # Section title (## **X**)
        m = re.match(r'^##\s+\*\*(.+?)\*\*\s*$', line)
        if m:
            pdf.section_title(m.group(1))
            i += 1
            continue

        # Section title without bold
        m = re.match(r'^##\s+(.+?)\s*$', line)
        if m:
            pdf.section_title(m.group(1))
            i += 1
            continue

        # Subsection title (### X)
        m = re.match(r'^###\s+(.+?)\s*$', line)
        if m:
            pdf.subsection_title(m.group(1).strip('*'))
            i += 1
            continue

        # Blockquote
        if line.startswith('>'):
            quote_lines = []
            while i < len(lines) and lines[i].startswith('>'):
                quote_lines.append(lines[i].lstrip('> '))
                i += 1
            pdf.blockquote(' '.join(quote_lines))
            continue

        # Bold definition lines (like ### 定义 X.X)
        m = re.match(r'^###\s+\*\*(.+?)\*\*\s*$', line)
        if m:
            pdf.subsection_title(m.group(1))
            i += 1
            continue

        # Regular text - collect consecutive lines into paragraphs
        para_lines = []
        while i < len(lines) and lines[i].strip() and not lines[i].startswith('#') \
                and not lines[i].startswith('>') and not lines[i].strip() == '---' \
                and not lines[i].strip().startswith('```'):
            para_lines.append(lines[i])
            i += 1
        if para_lines:
            text = ' '.join(para_lines)
            # Handle bold definitions as blockquotes
            if text.startswith('### '):
                pdf.subsection_title(text[4:].strip('*'))
            else:
                pdf.body_text(text)
        continue


def main():
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_font("serif", "", FONT_REGULAR)
    pdf.add_font("serif", "B", FONT_BOLD)

    # Title page
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font("serif", style="B", size=28)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 14, "期货市场的差异论解读", align="C")
    pdf.ln(8)
    pdf.set_font("serif", size=16)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 10, "从现货差异到价格显影", align="C")
    pdf.ln(20)
    pdf.set_font("serif", size=11)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 7, "差异论应用文本 · V1.0", align="C")

    # Read and render
    with open(INPUT, 'r', encoding='utf-8') as f:
        md_text = f.read()

    # Skip the title and ToC (already on cover page)
    # Start from 导论
    start = md_text.find('# **导论')
    if start == -1:
        start = md_text.find('# **第一编')
    if start == -1:
        start = 0

    parse_and_render(pdf, md_text[start:])

    pdf.output(OUTPUT)
    print(f"PDF generated: {OUTPUT}")
    print(f"Pages: {pdf.page_no()}")


if __name__ == '__main__':
    main()
