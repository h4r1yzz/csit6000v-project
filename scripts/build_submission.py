"""Build one PDF with the repository link, member contributions and full literal README."""
import argparse
import json
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
import reportlab
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--final', action='store_true', help='Require completed contributions; group must also complete the evaluation checklist.')
    args = parser.parse_args()
    data = json.loads((ROOT/'submission/contributions.json').read_text())
    missing = any(not member['contribution'].strip() for member in data['members'])
    if args.final and missing:
        parser.error('Member contributions are blank. Supply actual contributions before generating a final PDF.')
    output = ROOT/'submission'/('FitPilot-Repository-Submission.pdf' if args.final else 'FitPilot-Repository-Submission-DRAFT.pdf')
    fonts = Path(reportlab.__file__).parent/'fonts'
    pdfmetrics.registerFont(TTFont('Vera', str(fonts/'Vera.ttf')))
    pdfmetrics.registerFont(TTFont('VeraBold', str(fonts/'VeraBd.ttf')))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyV', fontName='Vera', fontSize=10, leading=15, spaceAfter=9))
    styles.add(ParagraphStyle(name='Source', fontName='Vera', fontSize=8, leading=12, splitLongWords=True, spaceAfter=3))
    styles.add(ParagraphStyle(name='TitleV', fontName='VeraBold', fontSize=21, leading=27, spaceAfter=16, textColor=colors.HexColor('#17324d')))
    styles.add(ParagraphStyle(name='HeadingV', fontName='VeraBold', fontSize=13, leading=18, spaceBefore=12, spaceAfter=10))
    story = [Paragraph('FitPilot | Repository submission', styles['TitleV'])]
    if not args.final:
        story += [Paragraph('DRAFT - contributions and research evaluation pending', styles['HeadingV']),
                  Paragraph('This preparation copy is not ready for final submission. See submission/STATUS.txt for the remaining work.', styles['BodyV'])]
    url=data['repository_url']
    story += [Paragraph('1. GitHub repository',styles['HeadingV']),
              Paragraph(f'<link href="{escape(url)}" color="#155ca2">{escape(url)}</link>',styles['BodyV']),
              Paragraph('The group must keep the repository and required evaluation materials accessible to the teaching team throughout grading.', styles['BodyV']),
              Paragraph('2. Group contributions',styles['HeadingV'])]
    for member in data['members']:
        story.append(Paragraph(escape(f"{member['name']} ({member['student_id']})"),styles['HeadingV']))
        story.append(Paragraph(escape(member['contribution'].strip() or 'PENDING - actual contribution to be supplied by the group.'),styles['BodyV']))
    story += [PageBreak(),Paragraph('3. Complete repository README.md', styles['TitleV']),
              Paragraph('The complete Markdown source follows, with line wrapping for the page width. Markdown markers are intentionally preserved.',styles['BodyV'])]
    readme=(ROOT/'README.md').read_text()
    for line in readme.splitlines():
        if not line:
            story.append(Spacer(1,5))
        else:
            # Literal source text, including all Markdown syntax and links.
            story.append(Paragraph(escape(line),styles['Source']))
    def footer(canvas, doc):
        canvas.setFont('Vera',8)
        canvas.setFillColor(colors.HexColor('#586577'))
        canvas.drawString(42,25,'FitPilot | CSIT6000V' + (' | DRAFT' if not args.final else ''))
        canvas.drawRightString(A4[0]-42,25,str(doc.page))
    SimpleDocTemplate(str(output),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=40,bottomMargin=43,
                      title='FitPilot repository submission',author='FitPilot project group').build(story,onFirstPage=footer,onLaterPages=footer)
    reader=PdfReader(output)
    text='\n'.join(re.sub(r'FitPilot \| CSIT6000V(?: \| DRAFT)?\s*\d+\s*', '', p.extract_text()) for p in reader.pages)
    compact=lambda s:re.sub(r'\s+','',s)
    if compact(readme) not in compact(text):
        raise RuntimeError('Full README text did not survive PDF extraction')
    links=[a.get_object().get('/A',{}).get('/URI') for p in reader.pages for a in p.get('/Annots',[])]
    if url not in links:
        raise RuntimeError('Clickable repository link missing')
    print(f'{output}\nPages: {len(reader.pages)}; complete README and clickable repository link verified.')


if __name__=='__main__':
    main()
