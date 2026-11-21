"""Render the complete repository README and a fillable course submission cover."""
from __future__ import annotations

import re
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'submission/FitPilot-Repository-Submission.pdf'
REPO = 'https://github.com/h4r1yzz/csit6000v-project'
REVISION = 'grading-submission-2026-11-21-v3'
REVISION_URL = f'{REPO}/tree/{REVISION}'
MEMBERS = (
    ('Harry Chandra Tsjan', '21340623'),
    ('Allabonu Sri Harsha Lakshman', '21344461'),
    ('Nehanth Kasi Geetha', '21386988'),
)

INK = colors.HexColor('#172B35')
MUTED = colors.HexColor('#485A62')
TEAL = colors.HexColor('#116660')
RULE = colors.HexColor('#CBD9D8')
TINT = colors.HexColor('#F1F6F5')
MARGIN = 48


def style(name, size, leading, *, font='Helvetica', color=INK, **kwargs):
    return ParagraphStyle(name, fontName=font, fontSize=size, leading=leading, textColor=color, **kwargs)


STYLES = {
    'eyebrow': style('eyebrow', 9.5, 14, font='Helvetica-Bold', color=TEAL, spaceAfter=12),
    'cover_title': style('cover_title', 54, 59, font='Times-Bold', spaceAfter=6),
    'cover_subtitle': style('cover_subtitle', 19, 25, color=MUTED, spaceAfter=24),
    'title': style('title', 29, 33, font='Times-Bold', keepWithNext=True, spaceAfter=9),
    'section': style('section', 24, 29, font='Times-Bold', keepWithNext=True, spaceAfter=12),
    'heading': style('heading', 13, 17, font='Helvetica-Bold', spaceBefore=12,
                     spaceAfter=5, keepWithNext=True),
    'body': style('body', 10.5, 14.3, spaceAfter=7),
    'bullet': style('bullet', 10.5, 14.3, leftIndent=13, bulletIndent=1, spaceAfter=4),
    'cell': style('cell', 10, 13.5),
    'table_head': style('table_head', 9.5, 13, font='Helvetica-Bold', color=TEAL),
}
TOKEN = re.compile(r'\[((?:`[^`]+`|[^\]])+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*')


def link(label: str, target: str) -> str:
    if not urlsplit(target).scheme and not target.startswith('#'):
        if target == 'evaluation/results':
            target = f'{REVISION_URL}/{target}'
        else:
            target = f'{REPO}/blob/{REVISION}/{target}'
    return f'<link href="{escape(target, quote=True)}" color="{TEAL.hexval()}"><u>{label}</u></link>'


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
    padding = 8
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
        canvas.setFillColor(TINT)
        canvas.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)
        canvas.setFillColor(INK)
        canvas.setFont(self.font, self.size)
        y = self.height - self.padding - self.size
        for line in self.lines:
            canvas.drawString(self.padding, y, line)
            y -= self.leading


class ContributionField(Flowable):
    spaceAfter = 12

    def __init__(self, name: str, student_id: str):
        super().__init__()
        self.height = 81
        self.name = name
        self.student_id = student_id

    def wrap(self, available_width, available_height):
        self.width = available_width
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        canvas.setFont('Helvetica-Bold', 11)
        canvas.setFillColor(INK)
        canvas.drawString(0, 65, self.name)
        canvas.setFont('Helvetica', 10)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(self.width, 65, self.student_id)
        canvas.acroForm.textfield(
            name=f'contribution_{self.student_id}', tooltip=f'Contribution for {self.name}',
            value='', x=0, y=0, width=self.width, height=55, relative=True,
            borderWidth=0.65, borderColor=RULE, fillColor=colors.white, textColor=INK,
            fontName='Helvetica', fontSize=10.5, fieldFlags='multiline doNotScroll', maxlen=350,
        )


def data_table(rows: list[list[str]]) -> Table:
    num_columns = len(rows[0])
    width = A4[0] - 2 * MARGIN
    proportions = (0.17, 0.39, 0.44) if num_columns == 3 else (0.26, 0.74)
    if len(proportions) != num_columns or any(len(row) != num_columns for row in rows):
        raise ValueError('Unexpected README table shape')
    grid = Table(
        [[Paragraph(inline(cell), STYLES['table_head' if index == 0 else 'cell'])
          for cell in row] for index, row in enumerate(rows)],
        colWidths=[width * fraction for fraction in proportions], repeatRows=1, hAlign='LEFT',
    )
    grid.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TINT),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, RULE),
        ('LINEBELOW', (0, 1), (-1, -1), 0.4, RULE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
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
                if title in ('Detailed Instructions', 'Rerun the live evaluation', 'Results and report references'):
                    flow.append(PageBreak())
                key = {'#': 'title', '##': 'section', '###': 'heading'}[level]
                item = Paragraph(inline(title), STYLES[key])
                if level == '##':
                    item.bookmark = title.lower().replace(' ', '-')
                flow.append(item)
            elif all(row.startswith('| ') and row.endswith(' |') for row in lines):
                rows = [[cell.strip() for cell in row[1:-1].split('|')] for row in lines]
                flow.extend([data_table([rows[0], *rows[2:]]), Spacer(1, 10)])
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
    width, height = A4
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.6)
    canvas.line(MARGIN, 36, width - MARGIN, 36)
    canvas.setFillColor(MUTED)
    canvas.setFont('Helvetica', 8.5)
    canvas.drawString(MARGIN, 22, 'FitPilot  /  CSIT6000V')
    canvas.drawRightString(width - MARGIN, 22, str(doc.page))
    if doc.page > 1:
        canvas.drawString(MARGIN, height - 31, 'REPOSITORY README')
        canvas.line(MARGIN, height - 39, width - MARGIN, height - 39)
    canvas.restoreState()


def main() -> None:
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    if REVISION_URL not in readme:
        raise ValueError('The submission cover and README must reference the same GitHub revision.')
    OUTPUT.parent.mkdir(exist_ok=True)
    doc = Submission(str(OUTPUT), pagesize=A4, title='FitPilot · GitHub repository submission',
                     author='FitPilot project group', leftMargin=MARGIN - 6, rightMargin=MARGIN - 6,
                     topMargin=57, bottomMargin=50)
    cover = [
        Paragraph('CSIT6000V COURSE PROJECT', STYLES['eyebrow']),
        Paragraph('FitPilot', STYLES['cover_title']),
        Paragraph('GitHub repository submission', STYLES['cover_subtitle']),
        Paragraph('GitHub repository', STYLES['heading']),
        Paragraph(link(REPO.removeprefix('https://'), REPO), STYLES['body']),
        Paragraph(f'Pinned revision · {link(REVISION, REVISION_URL)}', STYLES['body']),
        Spacer(1, 12),
        Paragraph('Group contributions', STYLES['heading']),
        Spacer(1, 2),
        *(ContributionField(*member) for member in MEMBERS),
        Spacer(1, 10),
        Paragraph('Repository README', STYLES['heading']),
        Paragraph(link('Getting Started Instructions', '#getting-started-instructions'), STYLES['body']),
        Paragraph(link('Detailed Instructions', '#detailed-instructions'), STYLES['body']),
    ]
    doc.build([*cover, PageBreak(), *render_readme(readme)], onFirstPage=draw_page, onLaterPages=draw_page)
    print(OUTPUT)


if __name__ == '__main__':
    main()
