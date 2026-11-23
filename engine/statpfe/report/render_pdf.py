"""Rendu PDF avec reportlab.

La police DejaVu (fournie avec matplotlib) est incorporée au fichier : les
caractères français, « − », « ≥ », « χ² », « α » s'affichent sur toute machine.
"""

from __future__ import annotations

import io
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, ListFlowable, ListItem, PageBreak as RLPageBreak, PageTemplate,
    Paragraph, Spacer, Table as RLTable, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from statpfe.report import theme as themes
from statpfe.report.model import Bullets, Cover, Document, Figure, Heading, PageBreak, Para, Run, Table, Toc

FONT = "DejaVuSans"
_registered = False
GREY = colors.HexColor("#555555")


def _register_fonts() -> None:
    global _registered
    if _registered:
        return
    import matplotlib

    base = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    variants = {FONT: "DejaVuSans.ttf", f"{FONT}-Bold": "DejaVuSans-Bold.ttf",
                f"{FONT}-Oblique": "DejaVuSans-Oblique.ttf", f"{FONT}-BoldOblique": "DejaVuSans-BoldOblique.ttf"}
    for name, file in variants.items():
        pdfmetrics.registerFont(TTFont(name, str(base / file)))
    pdfmetrics.registerFontFamily(FONT, normal=FONT, bold=f"{FONT}-Bold", italic=f"{FONT}-Oblique",
                                  boldItalic=f"{FONT}-BoldOblique")
    _registered = True


def _styles(th: themes.Theme) -> dict[str, ParagraphStyle]:
    body = ParagraphStyle("body", fontName=FONT, fontSize=10, leading=14, spaceAfter=6)
    accent = colors.HexColor(th.primary) if th.color else colors.black
    return {
        "body": body,
        "note": ParagraphStyle("note", parent=body, fontSize=8.8, leading=12, textColor=GREY, spaceAfter=3),
        "placeholder": ParagraphStyle("placeholder", parent=body, backColor=colors.HexColor("#FFF3B0"),
                                      borderPadding=3, spaceBefore=3, spaceAfter=9),
        "ai": ParagraphStyle("ai", parent=body, backColor=colors.HexColor("#E8F0FE"), borderPadding=4,
                             leftIndent=6, rightIndent=6, spaceBefore=2, spaceAfter=8),
        "lead": body,
        "warning": body,
        "h1": ParagraphStyle("h1", parent=body, fontName=f"{FONT}-Bold", fontSize=15, leading=19, spaceBefore=14,
                             spaceAfter=8, keepWithNext=True, textColor=accent),
        "h2": ParagraphStyle("h2", parent=body, fontName=f"{FONT}-Bold", fontSize=12, leading=16, spaceBefore=10,
                             spaceAfter=6, keepWithNext=True, textColor=accent),
        "caption": ParagraphStyle("caption", parent=body, fontName=f"{FONT}-Bold", fontSize=9.5, leading=12.5,
                                  spaceBefore=4, spaceAfter=4, keepWithNext=True, textColor=accent),
        "cell": ParagraphStyle("cell", parent=body, fontSize=8.6, leading=11, spaceAfter=0),
        "cell_r": ParagraphStyle("cell_r", parent=body, fontSize=8.6, leading=11, spaceAfter=0, alignment=2),
        "cell_h": ParagraphStyle("cell_h", parent=body, fontName=f"{FONT}-Bold", fontSize=8.6, leading=11,
                                 spaceAfter=0, textColor=colors.HexColor(th.header_text)),
        "cover_doc": ParagraphStyle("cover_doc", parent=body, fontSize=12, textColor=GREY, alignment=TA_CENTER,
                                    spaceAfter=18),
        "cover_title": ParagraphStyle("cover_title", parent=body, fontName=f"{FONT}-Bold", fontSize=22, leading=28,
                                      alignment=TA_CENTER, spaceAfter=28, textColor=accent),
        "cover_field": ParagraphStyle("cover_field", parent=body, fontSize=11, leading=16, alignment=TA_CENTER),
        "cover_note": ParagraphStyle("cover_note", parent=body, fontSize=8.8, textColor=GREY, alignment=TA_CENTER),
        "toc1": ParagraphStyle("toc1", parent=body, fontSize=10, leftIndent=0, spaceAfter=2),
        "toc2": ParagraphStyle("toc2", parent=body, fontSize=9.5, leftIndent=14, spaceAfter=1),
    }


def _markup(runs: list[Run]) -> str:
    out = []
    for r in runs:
        t = escape(r.text)
        if r.bold:
            t = f"<b>{t}</b>"
        if r.italic:
            t = f"<i>{t}</i>"
        out.append(t)
    return "".join(out)


class _Doc(BaseDocTemplate):
    def __init__(self, target, footer: str, **kw):
        super().__init__(target, pagesize=A4, leftMargin=2.3 * cm, rightMargin=2.3 * cm, topMargin=2.2 * cm,
                         bottomMargin=2.2 * cm, **kw)
        self.footer = footer
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="main")
        self.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=self._decorate)])

    def _decorate(self, canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(GREY)
        canvas.drawString(self.leftMargin, 1.2 * cm, self.footer)
        canvas.drawRightString(A4[0] - self.rightMargin, 1.2 * cm, f"{doc.page}")
        canvas.restoreState()

    def afterFlowable(self, flowable) -> None:
        level = getattr(flowable, "_toc_level", None)
        if level is not None:
            key = f"h{id(flowable)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(), key, level=level - 1, closed=level > 1)
            self.notify("TOCEntry", (level - 1, flowable.getPlainText(), self.page, key))


def _col_widths(t: Table, total: float) -> list[float]:
    lengths = []
    for j in range(len(t.columns)):
        texts = [t.columns[j]] + [r[j] for r in t.rows if j < len(r)]
        longest = max((len(w) for x in texts for w in x.split()), default=4)
        avg = sum(len(x) for x in texts) / max(1, len(texts))
        lengths.append(max(longest, min(avg, 60), 4))
    s = sum(lengths)
    return [total * x / s for x in lengths]


def render(document: Document, path: Path, author: str = "") -> None:
    _register_fonts()
    th = themes.get(document.theme)
    st = _styles(th)
    buf = io.BytesIO()
    doc = _Doc(buf, document.footer, title=document.title, author=author or "Auteur",
               subject="Rapport statistique préparé avec STATPFE", creator="STATPFE",
               keywords="STATPFE ; document de travail à réviser")
    story = []
    for b in document.blocks:
        if isinstance(b, Cover):
            story += [Spacer(1, 4 * cm), Paragraph(escape(b.document.upper()), st["cover_doc"]),
                      Paragraph(escape(b.title), st["cover_title"])]
            story += [Paragraph(f"<font color='#555555'>{escape(k)} :</font> <b>{escape(v)}</b>", st["cover_field"])
                      for k, v in b.fields]
            story += [Spacer(1, 0.8 * cm), Paragraph(escape(b.date), st["cover_field"]), Spacer(1, 5 * cm),
                      Paragraph(f"<i>{escape(b.disclaimer)}</i>", st["cover_note"])]
        elif isinstance(b, PageBreak):
            story.append(RLPageBreak())
        elif isinstance(b, Toc):
            toc = TableOfContents()
            toc.levelStyles = [st["toc1"], st["toc2"]]
            story += [Paragraph("Sommaire", st["h1"]), toc]
        elif isinstance(b, Heading):
            p = Paragraph(escape(b.full), st["h1" if b.level == 1 else "h2"])
            p._toc_level = b.level
            story.append(p)
        elif isinstance(b, Para):
            story.append(Paragraph(_markup(b.runs), st.get(b.style, st["body"])))
        elif isinstance(b, Bullets):
            story.append(ListFlowable([ListItem(Paragraph(_markup(i), st["body"]), leftIndent=14) for i in b.items],
                                      bulletType="bullet", start="•", leftIndent=14, bulletFontName=FONT))
        elif isinstance(b, Table):
            head = Paragraph(escape(b.label), st["caption"])
            data = [] if b.key_value else [[Paragraph(escape(c), st["cell_h"]) for c in b.columns]]
            for row in b.rows:
                data.append([Paragraph(("<b>%s</b>" if b.key_value and j == 0 else "%s") % escape(v),
                                       st["cell_r" if j < len(b.numeric) and b.numeric[j] else "cell"])
                             for j, v in enumerate(row)])
            widths = [doc.width * 0.32, doc.width * 0.68] if b.key_value else _col_widths(b, doc.width)
            tbl = RLTable(data, colWidths=widths, repeatRows=0 if b.key_value else 1, hAlign="CENTER")
            style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#888888")),
                     ("VALIGN", (0, 0), (-1, -1), "TOP"),
                     ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
            if not b.key_value:
                style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(th.header_fill)))
                if th.color:
                    style.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(th.light)]))
            elif th.color:
                style.append(("BACKGROUND", (0, 0), (0, -1), colors.HexColor(th.light)))
            if th.color:
                style[0] = ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B7C3CF"))
            tbl.setStyle(TableStyle(style))
            after = []
            if b.note:
                after.append(Paragraph(f"<i>Note : {escape(b.note)}</i>", st["note"]))
            if b.source:
                after.append(Paragraph(f"<i>{escape(b.source)}</i>", st["note"]))
            if len(b.rows) <= 25:
                story.append(KeepTogether([head, tbl] + after))
            else:
                story += [head, tbl] + after
            story.append(Spacer(1, 8))
        elif isinstance(b, Figure):
            img = Image(io.BytesIO(b.png))
            ratio = img.imageHeight / img.imageWidth
            img.drawWidth = min(b.width_cm * cm, doc.width)
            img.drawHeight = img.drawWidth * ratio
            story.append(KeepTogether([img, Paragraph(escape(b.label), st["caption"]),
                                       Paragraph(f"<i>Description : {escape(b.description)}</i>", st["note"]),
                                       Paragraph(f"<i>{escape(b.source)}</i>", st["note"])]))
            story.append(Spacer(1, 8))
    doc.multiBuild(story)
    path.write_bytes(buf.getvalue())


__all__ = ["render"]
