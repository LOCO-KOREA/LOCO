"""Original annex-one PDF pages with overflow text only when necessary."""
from io import BytesIO
from pathlib import Path
from threading import Lock
from xml.sax.saxutils import escape
import hashlib

from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle

from .form_mapping import map_snapshot

ROOT=Path(__file__).resolve().parent
TEMPLATE=ROOT/'templates/annex1_clean.pdf'
FONT_FILE=ROOT/'assets/LocoPDFKorean-Regular.ttf'
FONT='LocoPDFKorean'
TEMPLATE_VERSION='MOEL_ANNEX1_20180209_PDF_1'
_font_lock=Lock()


def register_font():
    with _font_lock:
        if FONT not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(FONT,str(FONT_FILE)))


def wrap(text,width,size):
    lines=[]
    for paragraph in text.split('\n'):
        line=''
        for char in paragraph:
            if pdfmetrics.stringWidth(line+char,FONT,size)>width:
                lines.append(line);line=''
            line+=char
        lines.append(line)
    return lines


def checked_text(value):
    text=str(value).replace('\r\n','\n').replace('\r','\n').replace('\t','    ')
    glyphs=pdfmetrics.getFont(FONT).face.charToGlyph
    if any((ord(char)<32 and char!='\n') or (char!='\n' and not glyphs.get(ord(char))) for char in text):
        raise ValueError('PDF 글꼴에 없는 문자 또는 지원하지 않는 제어 문자가 있습니다. 원문을 확인해 주세요.')
    return text


def render(snapshot, images=None, model=None):
    """Return bytes; never open user paths or change the source snapshot."""
    register_font()
    model=map_snapshot(snapshot) if model is None else model
    images=images or {}
    appendix=list(model['appendix'])
    warnings=list(model['warnings'])
    writer=PdfWriter()
    placements=[]

    def page(index,task):
        template=PdfReader(TEMPLATE)
        page_writer=PdfWriter()
        original=page_writer.add_page(template.pages[index])
        if (float(original.mediabox.width),float(original.mediabox.height))!=(595,841):
            raise ValueError('PDF 양식 크기가 올바르지 않습니다.')
        buf=BytesIO();c=canvas.Canvas(buf,pagesize=(595,841),pageCompression=1)

        def put(label,value,box):
            if value is None or value=='':return
            text=checked_text(value)
            x0,top,x1,bottom=box
            plan=None
            for size in (11,10,9,8):
                lines=wrap(text,x1-x0-4,size)
                asc,desc=pdfmetrics.getAscent(FONT,size),pdfmetrics.getDescent(FONT,size)
                block=asc-desc+(len(lines)-1)*size*1.22
                if block<=bottom-top-3:plan=(size,lines,asc,block);break
            if plan is None:
                title=task['name']+' — '+label
                appendix.append({'title':title,'text':text})
                text='별첨 참조'
                size=8;lines=[text];asc=pdfmetrics.getAscent(FONT,size)
                block=asc-pdfmetrics.getDescent(FONT,size)
                plan=(size,lines,asc,block)
            size,lines,asc,block=plan
            c.setFont(FONT,size)
            baseline=top+(bottom-top-block)/2+asc
            for i,line in enumerate(lines):c.drawString(x0+2,841-baseline-i*size*1.22,line)
            placements.append({'task_id':task['task_id'],'source_page':index+1,'label':label,
                               'box':list(box),'shown':text})

        if index==0:
            survey=model['survey']
            put('조사 일시',survey.get('survey_date'),(154,170,282,198))
            put('조사자',survey.get('investigator'),(395,170,530,198))
            put('부서명',survey.get('department'),(154,210,530,238))
            put('작업공정명',survey.get('process'),(154,250,530,278))
            put('작업명',task['name'],(154,290,530,318))
            tops={'equipment':396.10,'workload':447.88,'speed':537.30,'work_pattern':625.76}
            for row in model['situation']:
                mark=row['state']=='NO' or row['key']=='equipment' and row['state']=='YES'
                if mark:
                    x=242.27 if row['state']=='YES' else 148.96;top=tops[row['key']]
                    c.setLineWidth(1.2);c.setLineCap(1)
                    p=c.beginPath();p.moveTo(x+2,841-top-5.4);p.lineTo(x+4.3,841-top-8);p.lineTo(x+9.3,841-top-2);c.drawPath(p)
                if row['key']=='equipment' and row['state']=='YES':put('작업설비 변경 설명',row['note'],(359,393,511,413))
        elif index==1:
            put('작업명',task['name'],(143,109,509,132))
            put('작업내용',task['description'],(92,160.5,509,184.5))
            put('단위작업명',task['name'],(91,472,177,498))
            for label,value,box in [('부담작업 호',task['confirmed_criteria'],(181,472,262,498)),
                    ('작업부하',task['intensity'],(266,472,347,498)),
                    ('작업빈도',task['frequency'],(351,472,432,498)),
                    ('총점수',task['total'],(436,472,518,498))]:put(label,value,box)
        elif index==2:
            put('작업명',task['name'],(145,73,349,93))
            put('근로자명',task['worker_name'],(432,73,536,93))
            put('사진 설명',task['name'],(75,107,296,123))
            put('단위작업명',task['name'],(148,351,363,376))
            put('부담작업 호',task['confirmed_criteria'],(453,352,522,376))
            put('유해요인',task['factor'],(75,398,222,423.7))
            put('발생 원인',task['cause'],(225,398,449,423.7))
            data=images.get(task['task_id'])
            if data:
                with Image.open(BytesIO(data)) as image:
                    image=ImageOps.exif_transpose(image).convert('RGB')
                    width,height=image.size;ratio=min(216/width,173/height)
                    w,h=width*ratio,height*ratio
                    c.drawImage(ImageReader(image),76+(220-w)/2,841-303+(177-h)/2,w,h)
            else:put('대표 사진', '사진 미포함' if not snapshot.get('include_representative') else '대표 사진 없음',(76,204,296,225))
        c.save();original.merge_page(PdfReader(BytesIO(buf.getvalue())).pages[0]);return original

    for task in model['tasks']:
        for index in range(3):writer.add_page(page(index,task))
    writer.add_page(PdfReader(TEMPLATE).pages[3])
    if appendix:
        stream=BytesIO()
        doc=SimpleDocTemplate(stream,pagesize=(595,841),leftMargin=45,rightMargin=45,topMargin=45,bottomMargin=45)
        title_style=ParagraphStyle('title',fontName=FONT,fontSize=13,leading=19,spaceAfter=12,wordWrap='CJK')
        head_style=ParagraphStyle('heading',fontName=FONT,fontSize=10,leading=15,spaceBefore=9,spaceAfter=4,wordWrap='CJK',keepWithNext=True)
        body_style=ParagraphStyle('body',fontName=FONT,fontSize=9,leading=14,wordWrap='CJK',splitLongWords=True)
        story=[Paragraph('긴 작성 내용 별첨',title_style),Paragraph('원본 칸에 담기지 않는 작성 내용의 전체 원문입니다.',body_style),Spacer(1,8)]
        previous_title=None
        for block in appendix:
            if block['title']!=previous_title:
                story.append(Paragraph(escape(checked_text(block['title'])),head_style))
            else:
                story.append(Spacer(1,7))
            story.append(Paragraph(escape(checked_text(block['text'])).replace('\n','<br/>'),body_style))
            previous_title=block['title']
        doc.build(story)
        for item in PdfReader(BytesIO(stream.getvalue())).pages:writer.add_page(item)
    writer.add_metadata({'/Title':'LOCO 유해요인조사표','/Subject':'입력 근거에 기반한 조사 지원 자료'})
    out=BytesIO();writer.write(out)
    return {'data':out.getvalue(),'page_count':len(writer.pages),'warnings':warnings,
            'state':model['state'],'template_version':TEMPLATE_VERSION,'placements':placements,
            'template_sha256':hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()}
