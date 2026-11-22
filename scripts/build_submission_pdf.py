"""Render the course artifact report and the complete repository README."""
from __future__ import annotations

import re
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'submission/FitPilot-Repository-Submission.pdf'
REPO = 'https://github.com/h4r1yzz/csit6000v-project'
GRADING_TAG = 'grading-final'
GRADING_URL = f'{REPO}/tree/{GRADING_TAG}'
SOURCE_SHA = 'ca94084617e3458ce639b7074debfe9029af3eb9'
HISTORY = 'https://github.com/NehanthKG/CSIT6000V-fitness-tracker/commit'
ARCHITECTURE_PATH = 'docs/fitpilot-architecture.svg'
MEMBERS = (
    ('Harry Chandra Tsjan', '21340623',
     'Proposed FitPilot and designed its system architecture. Implemented the tool-calling coordinator and built the browser pose estimation module, including bilateral tracking and curl repetition counting.',
     (('Coordinator implementation', f'{REPO}/commit/b7fe39a12170fa0ac6ea4e2e95ae85c239af5a61'),
      ('Bilateral pose tracking', f'{HISTORY}/b3754ded95cd11b90e4872d0a35383a83d25e719'))),
    ('Allabonu Sri Harsha Lakshman', '21344461',
     'Tested FitPilot using 43 backend tests, 17 pose tests, end-to-end API and chat checks, 270 live TACC Qwen trials across shared planning and adaptation cases, and separate feedback checks. Wrote the setup, verification, and reviewer walkthrough documentation.',
     (('Shared test cases and reviewer walkthrough', 'docs/EVALUATION-EXAMPLES.md'),)),
    ('Nehanth Kasi Geetha', '21386988',
     'Built the initial React and FastAPI web app. Developed the planning agent workflow and TACC Qwen integration. Added account login and per-user model request history.',
     (('Initial web app', f'{HISTORY}/cfc5118452e2ef82ba10c1320069aad816bc9d4c'),
      ('TACC integration', f'{HISTORY}/7620f2997721bf9a080f14039777b54894ac3f19'),
      ('Account and request history', f'{REPO}/commit/a1d9f56ba9f7eb30a1eac804f9c330ca362939c4'))),
)

INK = colors.black
LINK_BLUE = colors.HexColor('#17468A')
MARGIN = 48


def style(name, size, leading, *, font='Times-Roman', **kwargs):
    return ParagraphStyle(name, fontName=font, fontSize=size, leading=leading, textColor=INK, **kwargs)


STYLES = {
    'cover_title': style('cover_title', 26, 31, font='Times-Bold', alignment=TA_CENTER, spaceAfter=5),
    'cover_subtitle': style('cover_subtitle', 11.5, 14, alignment=TA_CENTER, spaceAfter=18),
    'title': style('title', 19, 23, font='Times-Bold', keepWithNext=True, spaceAfter=7),
    'section': style('section', 17, 21, font='Times-Bold', keepWithNext=True, spaceBefore=9, spaceAfter=7),
    'heading': style('heading', 13, 16, font='Times-Bold', spaceBefore=11, spaceAfter=4, keepWithNext=True),
    'body': style('body', 11, 14.2, alignment=TA_JUSTIFY, spaceAfter=6),
    'bullet': style('bullet', 11, 14.2, leftIndent=13, bulletIndent=1, spaceAfter=4),
    'cell': style('cell', 10.5, 13),
    'table_head': style('table_head', 10.5, 13, font='Times-Bold'),
}
TOKEN = re.compile(r'\[((?:`[^`]+`|[^\]])+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*')


def architecture_drawing() -> Drawing:
    diagram = Drawing(A4[0] - 2 * MARGIN, 158)
    diagram.add(Rect(0, 0, diagram.width, diagram.height, fillColor=colors.white, strokeColor=None))

    def box(x, y, width, height, title, lines):
        diagram.add(Rect(x, y, width, height, fillColor=None, strokeColor=INK, strokeWidth=0.6))
        diagram.add(String(x + 10, y + height - 17, title, fontName='Times-Bold',
                           fontSize=11, fillColor=INK))
        for index, line in enumerate(lines):
            diagram.add(String(x + 10, y + height - 33 - 13 * index, line,
                               fontName='Times-Roman', fontSize=10, fillColor=INK))

    def exchange(left, right, y, label):
        diagram.add(Line(left, y, right, y, strokeColor=INK, strokeWidth=0.6))
        diagram.add(Polygon([left, y, left + 4, y + 2.5, left + 4, y - 2.5], fillColor=INK, strokeColor=None))
        diagram.add(Polygon([right, y, right - 4, y + 2.5, right - 4, y - 2.5], fillColor=INK, strokeColor=None))
        diagram.add(String((left + right) / 2, y + 7, label, fontName='Times-Roman',
                           fontSize=8.5, fillColor=INK, textAnchor='middle'))

    box(0, 84, 138, 73, 'Browser', ['React dashboard', 'MediaPipe pose estimation', 'Video stays on device'])
    box(173, 84, 153, 73, 'FastAPI', ['Bounded five-agent workflow', 'Catalog and constraint checks', 'Draft review and approval'])
    box(361, 84, 138, 73, 'TACC Qwen', ['Hosted text model', 'Structured agent responses'])
    box(173, 4, 153, 54, 'PostgreSQL', ['Profiles, approved plans', 'Agent runs and progress'])
    exchange(141, 170, 120, 'API')
    exchange(329, 358, 120, 'Model')
    diagram.add(Line(249.5, 61, 249.5, 81, strokeColor=INK, strokeWidth=0.6))
    diagram.add(Polygon([249.5, 61, 247, 65, 252, 65], fillColor=INK, strokeColor=None))
    diagram.add(Polygon([249.5, 81, 247, 77, 252, 77], fillColor=INK, strokeColor=None))
    return diagram


def link(label: str, target: str) -> str:
    if not urlsplit(target).scheme and not target.startswith('#'):
        if (ROOT / urlsplit(target).path).is_dir():
            target = f'{GRADING_URL}/{target}'
        else:
            target = f'{REPO}/blob/{GRADING_TAG}/{target}'
    return f'<link href="{escape(target, quote=True)}" color="{LINK_BLUE.hexval()}">{label}</link>'


def inline(value: str) -> str:
    parts = []
    end = 0
    for match in TOKEN.finditer(value):
        parts.append(escape(value[end:match.start()]))
        label, target, code, bold = match.groups()
        if label is not None:
            parts.append(link(inline(label), target))
        elif code is not None:
            parts.append(f'<font name="Courier" size="9">{escape(code)}</font>')
        else:
            parts.append(f'<b>{escape(bold)}</b>')
        end = match.end()
    parts.append(escape(value[end:]))
    return ''.join(parts)


class CodeBlock(Flowable):
    font = 'Courier'
    size = 8.0
    leading = 11.5
    padding = 5
    spaceAfter = 7

    def __init__(self, lines: list[str]):
        super().__init__()
        self.lines = lines

    def wrap(self, available_width, available_height):
        self.width = available_width
        self.height = self.leading * len(self.lines) + 2 * self.padding
        if any(stringWidth(line, self.font, self.size) > self.width - 2 * self.padding
               for line in self.lines):
            raise ValueError('A README code line is too wide. Add a shell continuation in README.md.')
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        canvas.setFillColor(INK)
        canvas.setFont(self.font, self.size)
        y = self.height - self.padding - self.size
        for line in self.lines:
            canvas.drawString(self.padding, y, line)
            y -= self.leading


def article_table(rows: list[list[str]], proportions: tuple[float, ...]) -> Table:
    width = A4[0] - 2 * MARGIN
    if any(len(row) != len(proportions) for row in rows):
        raise ValueError('Unexpected table shape')
    grid = Table(
        [[Paragraph(cell, STYLES['table_head' if index == 0 else 'cell'])
          for cell in row] for index, row in enumerate(rows)],
        colWidths=[width * fraction for fraction in proportions], repeatRows=1, hAlign='LEFT',
    )
    grid.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 0.7, INK),
        ('LINEBELOW', (0, 0), (-1, 0), 0.45, INK),
        ('LINEBELOW', (0, -1), (-1, -1), 0.7, INK),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return grid


def render_readme(markdown: str) -> list:
    """Render the headings, paragraphs, lists, fences and tables used in README.md."""
    blocks = re.split(r'^```[^\n]*\n(.*?)^```\s*$', markdown, flags=re.MULTILINE | re.DOTALL)
    flow = []
    for index, block in enumerate(blocks):
        if index % 2:
            flow.append(CodeBlock(block.splitlines()))
            continue
        for group in re.split(r'\n\s*\n', block.strip()):
            if not group:
                continue
            lines = group.splitlines()
            line = lines[0]
            heading = re.fullmatch(r'(#{1,3}) (.+)', line)
            if heading:
                level, title = heading.groups()
                if len(lines) != 1:
                    raise ValueError(f'Add a blank line after heading: {title}')
                if title in ('Getting Started Instructions', 'Test cases and scoring',
                             'Sample workflows and chat history', 'Recorded evaluation results'):
                    flow.append(PageBreak())
                key = {'#': 'title', '##': 'section', '###': 'heading'}[level]
                item = Paragraph(inline(title), STYLES[key])
                if level == '##':
                    item.bookmark = title.lower().replace(' ', '-')
                flow.append(item)
            elif len(lines) == 1 and re.fullmatch(r'!\[[^\]]+\]\(' + re.escape(ARCHITECTURE_PATH) + r'\)', line):
                flow.extend([architecture_drawing(), Spacer(1, 6)])
            elif all(row.startswith('| ') and row.endswith(' |') for row in lines):
                rows = [[cell.strip() for cell in row[1:-1].split('|')] for row in lines]
                proportions = (0.17, 0.39, 0.44) if len(rows[0]) == 3 else (0.26, 0.74)
                cells = [[inline(cell) for cell in row] for row in [rows[0], *rows[2:]]]
                flow.extend([article_table(cells, proportions), Spacer(1, 8)])
            elif all(row.startswith('- ') for row in lines):
                flow.extend(Paragraph(inline(row[2:]), STYLES['bullet'], bulletText='•') for row in lines)
            else:
                flow.append(Paragraph(inline(' '.join(lines)), STYLES['body']))
    return flow


class Submission(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        bookmark = getattr(flowable, 'bookmark', None)
        if bookmark:
            self.canv.bookmarkPage(bookmark)
            self.canv.addOutlineEntry(flowable.getPlainText(), bookmark, level=0)


def draw_page(canvas, doc):
    width, _ = A4
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.setFont('Times-Roman', 10)
    canvas.drawCentredString(width / 2, 27, str(doc.page))
    canvas.restoreState()


def main() -> None:
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    if GRADING_URL not in readme:
        raise ValueError('The README must link to the grading repository.')
    renderSVG.drawToFile(architecture_drawing(), str(ROOT / ARCHITECTURE_PATH))
    OUTPUT.parent.mkdir(exist_ok=True)
    doc = Submission(str(OUTPUT), pagesize=A4, title='FitPilot · GitHub repository submission',
                     author='FitPilot project group', leftMargin=MARGIN - 6, rightMargin=MARGIN - 6,
                     topMargin=48, bottomMargin=43)
    cover = [
        Paragraph('FitPilot', STYLES['cover_title']),
        Paragraph('Course Project Artifacts Submission · CSIT6000V', STYLES['cover_subtitle']),
        Paragraph('1. GitHub repository', STYLES['section']),
        Paragraph(link(f'Grading repository · {GRADING_TAG}', GRADING_URL), STYLES['body']),
        Paragraph(f'Evaluated source commit · {link(SOURCE_SHA, f"{REPO}/tree/{SOURCE_SHA}")}', STYLES['body']),
        Paragraph('2. Group contributions', STYLES['section']),
    ]
    members = [['Member', 'Student ID', 'Contribution and related work']]
    for name, student_id, contribution, work in MEMBERS:
        links = ' · '.join(link(label, url) for label, url in work)
        members.append([escape(name), student_id, f'{escape(contribution)}<br/>{links}'])
    cover.extend([
        article_table(members, (0.225, 0.15, 0.625)),
        Spacer(1, 9),
        Paragraph('3. Repository README', STYLES['section']),
    ])
    doc.build([*cover, *render_readme(readme)], onFirstPage=draw_page, onLaterPages=draw_page)
    print(OUTPUT)


if __name__ == '__main__':
    main()
