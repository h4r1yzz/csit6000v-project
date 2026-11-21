"""Build the course repository-submission PDF from the current README."""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable, KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'submission' / 'FitPilot-Repository-Submission.pdf'
REPO = 'https://github.com/h4r1yzz/csit6000v-project'
TAG = 'grading-submission-2026-11-21'


def inline(text: str) -> str:
    text = escape(text, quote=False)
    text = re.sub(r'`([^`]+)`', r'<font name="Courier" size="8">\1</font>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^ )]+)\)',
                  r'<link href="\2" color="#1769aa">\1</link>', text)
    return text


def parse_readme(text: str, styles: dict) -> list:
    story: list = []
    paragraph: list[str] = []
    code: list[str] | None = None
    table: list[list[str]] = []

    def flush_paragraph() -> None:
        if paragraph:
            story.append(Paragraph(inline(' '.join(part.strip() for part in paragraph)), styles['BodyText']))
            story.append(Spacer(1, 5))
            paragraph.clear()

    def flush_table() -> None:
        if not table:
            return
        body = [[Paragraph(inline(cell.strip()), styles['TableCell']) for cell in row] for row in table]
        widths = [(7.0 * inch) / len(body[0])] * len(body[0])
        grid = Table(body, colWidths=widths, repeatRows=1, hAlign='LEFT')
        grid.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9eef5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#142238')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), .35, colors.HexColor('#cbd3df')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.extend([grid, Spacer(1, 9)])
        table.clear()

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith('```'):
            flush_paragraph()
            flush_table()
            if code is None:
                code = []
            else:
                story.append(Preformatted('\n'.join(code), styles['SubmissionCode']))
                story.append(Spacer(1, 8))
                code = None
            continue
        if code is not None:
            code.append(line)
            continue
        if line.startswith('|') and line.endswith('|'):
            flush_paragraph()
            cells = [cell.strip() for cell in line.strip('|').split('|')]
            if all(re.fullmatch(r':?-{3,}:?', cell.replace(' ', '')) for cell in cells):
                continue
            table.append(cells)
            continue
        flush_table()
        if not line.strip():
            flush_paragraph()
            continue
        heading = re.match(r'^(#{1,3})\s+(.*)', line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            story.append(Paragraph(inline(heading.group(2)), styles[f'SubmissionHeading{level}']))
            story.append(Spacer(1, 3))
        elif re.match(r'^-\s+', line):
            flush_paragraph()
            story.append(Paragraph(inline(line[2:].strip()), styles['SubmissionBullet'], bulletText='•'))
            story.append(Spacer(1, 2))
        elif re.match(r'^\d+\.\s+', line):
            flush_paragraph()
            match = re.match(r'^(\d+)\.\s+(.*)', line)
            story.append(Paragraph(inline(match.group(2)), styles['SubmissionBullet'], bulletText=f'{match.group(1)}.'))
            story.append(Spacer(1, 2))
        else:
            paragraph.append(line)
    flush_paragraph()
    flush_table()
    return story


def draw_page(canvas, doc):
    canvas.saveState()
    width, _ = letter
    canvas.setStrokeColor(colors.HexColor('#d8dee8'))
    canvas.line(doc.leftMargin, 0.55 * inch, width - doc.rightMargin, 0.55 * inch)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#5a6574'))
    canvas.drawString(doc.leftMargin, 0.36 * inch, 'FitPilot | CSIT6000V repository submission')
    canvas.drawRightString(width - doc.rightMargin, 0.36 * inch, f'{doc.page}')
    canvas.restoreState()


def main() -> None:
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    check_path = ROOT / 'evaluation/results/verification.json'
    verification = json.loads(check_path.read_text()) if check_path.exists() else None
    planning_path = ROOT / 'evaluation/results/planning.json'
    adaptation_path = ROOT / 'evaluation/results/adaptation.json'
    feedback_path = ROOT / 'evaluation/results/feedback.json'
    planning = json.loads(planning_path.read_text()) if planning_path.exists() else None
    adaptation = json.loads(adaptation_path.read_text()) if adaptation_path.exists() else None
    feedback = json.loads(feedback_path.read_text()) if feedback_path.exists() else None
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleCustom', parent=styles['Title'], fontName='Helvetica-Bold',
                              fontSize=22, leading=27, textColor=colors.HexColor('#17243a'), alignment=TA_CENTER,
                              spaceAfter=15))
    styles.add(ParagraphStyle(name='SubtitleCustom', parent=styles['Normal'], fontSize=10, leading=14,
                              alignment=TA_CENTER, textColor=colors.HexColor('#526174'), spaceAfter=18))
    styles.add(ParagraphStyle(name='TableCell', parent=styles['BodyText'], fontSize=7.3, leading=9.3,
                              spaceAfter=0, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='SubmissionCode', fontName='Courier', fontSize=7.2, leading=9,
                              leftIndent=8, rightIndent=8, borderColor=colors.HexColor('#d8dee8'),
                              borderWidth=.4, borderPadding=6, backColor=colors.HexColor('#f5f7fa'),
                              spaceBefore=3, spaceAfter=4))
    styles.add(ParagraphStyle(name='SubmissionBullet', parent=styles['BodyText'], leftIndent=15, firstLineIndent=-10,
                              fontSize=9.2, leading=12, spaceAfter=1))
    for level, size in [(1, 17), (2, 13), (3, 10.5)]:
        styles.add(ParagraphStyle(name=f'SubmissionHeading{level}', parent=styles[f'Heading{level}'],
                                  fontName='Helvetica-Bold', fontSize=size, leading=size + 4,
                                  textColor=colors.HexColor('#17243a'), spaceBefore=9, spaceAfter=5,
                                  keepWithNext=True))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=letter, rightMargin=.68*inch, leftMargin=.68*inch,
                            topMargin=.62*inch, bottomMargin=.75*inch, title='FitPilot Repository Submission',
                            author='CSIT6000V project group')
    story = [Spacer(1, .45*inch), Paragraph('GitHub Repository Submission', styles['TitleCustom']),
             Paragraph('CSIT6000V · FitPilot', styles['SubtitleCustom']),
             Paragraph(f'<b>Repository:</b> <link href="{REPO}" color="#1769aa">{REPO}</link>', styles['BodyText']),
             Paragraph(f'<b>Pinned grading revision:</b> <link href="{REPO}/tree/{TAG}" color="#1769aa">{TAG}</link>', styles['BodyText']),
             Spacer(1, 12), Paragraph('Group contributions', styles['Heading2']),
             Paragraph('The contribution fields are left blank for the group to complete.', styles['BodyText']),
             Spacer(1, 7)]
    for name, student_id in [('Harry Chandra Tsjan', '21340623'),
                             ('Allabonu Sri Harsha Lakshman', '21344461'),
                             ('Nehanth Kasi Geetha', '21386988')]:
        story.append(Paragraph(f'<b>{escape(name)} ({student_id})</b>', styles['BodyText']))
        story.extend([Paragraph('Contribution: __________________________________________________________', styles['BodyText']),
                      Spacer(1, 7)])
    if verification:
        story.extend([Spacer(1, 7), Paragraph('Artifact verification snapshot', styles['Heading2']),
                      Paragraph(f"Recorded {escape(verification.get('timestamp_utc', '')[:10])} on Python {escape(verification.get('python', ''))}; "
                                f"overall status: <b>{'PASS' if verification.get('passed') else 'INCOMPLETE'}</b>.", styles['BodyText'])])
        for row in verification.get('checks', []):
            story.append(Paragraph(f"• {escape(row['name'])}: {'PASS' if row['exit_code'] == 0 else 'FAIL'}", styles['BodyText']))
        story.append(Paragraph('These are local software checks with simulated model responses and synthetic pose tests. They do not establish recommendation quality or real-video pose accuracy.', styles['BodyText']))
    if planning and adaptation and feedback:
        def live_score(suite, mode):
            rows = [row for row in suite['records'] if row['mode'] == mode]
            feasible = [row for row in rows if row['expected'] == 'valid_plan']
            blocked = [row for row in rows if row['expected'] == 'reject']
            return (sum(row['meets_expected_outcome'] for row in feasible), len(feasible),
                    sum(row['meets_expected_outcome'] for row in blocked), len(blocked))

        p = live_score(planning, 'multi_agent')
        a = live_score(adaptation, 'multi_agent')
        good = sum(bool(row['passed']) for row in feedback['cases'])
        story.extend([Spacer(1, 8), Paragraph('Live TACC evaluation snapshot', styles['Heading2']),
                      Paragraph(f"Model: {escape(planning['model'])}. Planning: {p[0]}/{p[1]} feasible drafts passed all checks and {p[2]}/{p[3]} infeasible menus were rejected. Adaptation: {a[0]}/{a[1]} feasible drafts passed and {a[2]}/{a[3]} infeasible menus were rejected. Synthetic-summary exercise feedback: {good}/{len(feedback['cases'])} cases passed.", styles['BodyText']),
                      Paragraph('The scoring uses deterministic app checks and synthetic cases. No real-video pose accuracy was measured.', styles['BodyText'])])
    story.extend([PageBreak(), Paragraph('Repository README', styles['TitleCustom']),
                  Paragraph('Full README.md contents from the repository revision accompanying this PDF.', styles['SubtitleCustom'])])
    story.extend(parse_readme(readme, styles))
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    print(OUT)


if __name__ == '__main__':
    main()
