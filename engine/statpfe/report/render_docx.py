"""Rendu Word (.docx) avec python-docx.

Les numéros de tableaux et de figures sont de vrais champs Word (SEQ) et le
sommaire est un champ TOC : Word peut produire la table des illustrations et
mettre à jour la numérotation si l'auteur réorganise le document.
"""

from __future__ import annotations

import io
from pathlib import Path

from docx import Document as new_document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from statpfe.report import theme as themes
from statpfe.report.model import Bullets, Cover, Document, Figure, Heading, PageBreak, Para, Table, Toc

BODY_FONT = "Calibri"
GREY = RGBColor(0x55, 0x55, 0x55)
BLACK = RGBColor(0, 0, 0)


def _field(paragraph, instruction: str, cached: str) -> None:
    """Champ Word complexe (begin / instruction / separate / résultat / end)."""
    def fld(kind: str):
        r = OxmlElement("w:r")
        f = OxmlElement("w:fldChar")
        f.set(qn("w:fldCharType"), kind)
        r.append(f)
        return r

    p = paragraph._p
    p.append(fld("begin"))
    r = OxmlElement("w:r")
    t = OxmlElement("w:instrText")
    t.set(qn("xml:space"), "preserve")
    t.text = f" {instruction} "
    r.append(t)
    p.append(r)
    p.append(fld("separate"))
    paragraph.add_run(cached)
    p.append(fld("end"))


def _shade(cell, color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)


def _repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    tr_pr.append(el)


def _rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color.lstrip("#").upper())


def _setup(doc, title: str, author: str, th: themes.Theme) -> None:
    st = doc.styles["Normal"]
    st.font.name = BODY_FONT
    st.font.size = Pt(11)
    rpr = st.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(attr), BODY_FONT)
    lang = OxmlElement("w:lang")
    lang.set(qn("w:val"), "fr-FR")
    rpr.append(lang)
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.line_spacing = 1.15
    for name, size in (("Heading 1", 16), ("Heading 2", 13), ("Title", 24)):
        h = doc.styles[name]
        h.font.name = BODY_FONT
        h.font.size = Pt(size)
        h.font.color.rgb = _rgb(th.primary) if th.color else BLACK
        h.font.bold = True
    cap = doc.styles["Caption"]
    cap.font.size = Pt(10)
    cap.font.color.rgb = _rgb(th.primary) if th.color else BLACK
    cap.font.bold = True
    cap.font.italic = False
    for s in doc.sections:
        s.top_margin = s.bottom_margin = Cm(2.5)
        s.left_margin = s.right_margin = Cm(2.5)
    props = doc.core_properties
    props.title = title
    props.author = author or "Auteur"
    props.subject = "Rapport statistique préparé avec STATPFE"
    props.comments = "Document de travail à réviser, non validé scientifiquement."
    props.keywords = "STATPFE"
    # Demande à Word de mettre à jour le sommaire et les numéros à l'ouverture.
    settings = doc.settings.element
    upd = OxmlElement("w:updateFields")
    upd.set(qn("w:val"), "true")
    settings.append(upd)


def _footer(doc, text: str) -> None:
    for s in doc.sections:
        p = s.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text + "  Page ")
        r.font.size = Pt(8)
        r.font.color.rgb = GREY
        _field(p, "PAGE", "1")
        for run in p.runs[1:]:
            run.font.size = Pt(8)
            run.font.color.rgb = GREY


def _small(doc, text: str, italic: bool = True):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(9)
    r.italic = italic
    r.font.color.rgb = GREY
    p.paragraph_format.space_after = Pt(2)
    return p


def _caption(doc, kind: str, number: int, caption: str):
    p = doc.add_paragraph(style="Caption")
    p.add_run(f"{kind} ")
    _field(p, f"SEQ {kind} \\* ARABIC", str(number))
    p.add_run(f". {caption}")
    p.paragraph_format.keep_with_next = True
    return p


def _table(doc, t: Table, th: themes.Theme) -> None:
    if t.number:
        _caption(doc, "Tableau", t.number, t.caption)
    else:
        p = doc.add_paragraph()
        r = p.add_run(t.caption)
        r.bold = True
        p.paragraph_format.keep_with_next = True
    table = doc.add_table(rows=1, cols=len(t.columns))
    table.style = doc.styles["Table Grid"]
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = table.rows[0]
    if not t.key_value:
        _repeat_header(hdr)
    for j, c in enumerate(t.columns):
        cell = hdr.cells[j]
        cell.text = ""
        run = cell.paragraphs[0].add_run(c)
        run.bold = True
        run.font.size = Pt(9.5)
        run.font.color.rgb = _rgb(th.header_text)
        _shade(cell, th.header_fill.lstrip("#").upper())
    for i, row in enumerate(t.rows):
        cells = table.add_row().cells
        if th.color and i % 2 == 1 and not t.key_value:
            for c in cells:
                _shade(c, th.light.lstrip("#").upper())
        for j, v in enumerate(row):
            par = cells[j].paragraphs[0]
            run = par.add_run(v)
            run.font.size = Pt(9.5)
            if t.key_value and j == 0:
                run.bold = True
                if th.color:
                    _shade(cells[j], th.light.lstrip("#").upper())
            if j < len(t.numeric) and t.numeric[j]:
                par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if t.key_value:
        table.rows[0]._tr.getparent().remove(table.rows[0]._tr)
    if len(t.rows) <= 25:
        # Petit tableau : Word le garde sur une seule page (avec sa légende).
        for row in table.rows[:-1]:
            for c in row.cells:
                for par in c.paragraphs:
                    par.paragraph_format.keep_with_next = True
    if t.note:
        _small(doc, f"Note : {t.note}")
    if t.source:
        _small(doc, t.source)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def _runs(par, runs) -> None:
    for r in runs:
        run = par.add_run(r.text)
        run.bold = r.bold
        run.italic = r.italic


def _cover(doc, c: Cover, th: themes.Theme) -> None:
    for _ in range(3):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(c.document.upper())
    r.font.size = Pt(13)
    r.font.color.rgb = GREY
    p = doc.add_paragraph(style="Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title = p.add_run(c.title)
    if th.color:
        title.font.color.rgb = _rgb(th.primary)
    doc.add_paragraph()
    for label, value in c.fields:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        a = p.add_run(f"{label} : ")
        a.font.color.rgb = GREY
        p.add_run(value).bold = True
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(c.date)
    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(c.disclaimer)
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = GREY


def render(document: Document, path: Path, author: str = "") -> None:
    th = themes.get(document.theme)
    doc = new_document()
    _setup(doc, document.title, author, th)
    _footer(doc, document.footer)
    for b in document.blocks:
        if isinstance(b, Cover):
            _cover(doc, b, th)
        elif isinstance(b, PageBreak):
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        elif isinstance(b, Toc):
            doc.add_paragraph("Sommaire", style="Heading 1")
            p = doc.add_paragraph()
            _field(p, 'TOC \\o "1-2" \\h \\z \\u',
                   "Sommaire à mettre à jour : clic droit, puis « Mettre à jour les champs ».")
        elif isinstance(b, Heading):
            doc.add_heading(b.full, level=b.level)
        elif isinstance(b, Para):
            p = doc.add_paragraph()
            if b.style in ("note",):
                for r in b.runs:
                    run = p.add_run(r.text)
                    run.italic = True
                    run.bold = r.bold
                    run.font.size = Pt(9.5)
                    run.font.color.rgb = GREY
            elif b.style == "ai":
                _runs(p, b.runs)
                p.paragraph_format.left_indent = Cm(0.4)
                p.paragraph_format.right_indent = Cm(0.4)
                ppr = p._p.get_or_add_pPr()
                shd = OxmlElement("w:shd")
                shd.set(qn("w:val"), "clear")
                shd.set(qn("w:color"), "auto")
                shd.set(qn("w:fill"), "E8F0FE")
                ppr.append(shd)
            elif b.style == "placeholder":
                for r in b.runs:
                    run = p.add_run(r.text)
                    run.italic = True
                    run.font.highlight_color = WD_COLOR_INDEX.YELLOW
            else:
                _runs(p, b.runs)
        elif isinstance(b, Bullets):
            for item in b.items:
                _runs(doc.add_paragraph(style="List Bullet"), item)
        elif isinstance(b, Table):
            _table(doc, b, th)
        elif isinstance(b, Figure):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_with_next = True
            p.add_run().add_picture(io.BytesIO(b.png), width=Cm(b.width_cm))
            _caption(doc, "Figure", b.number, b.caption).paragraph_format.keep_with_next = False
            _small(doc, f"Description : {b.description}")
            _small(doc, b.source)
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
    doc.save(str(path))


__all__ = ["render"]
