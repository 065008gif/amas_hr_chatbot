"""Render one policy document (content/polNNN_*.yaml) to a PDF with ReportLab.

multiBuild lays the document out repeatedly until the table of contents page numbers are stable.
Anchor flowables record the first and last physical page of every section, clause, table,
annexure and circular into documents/manifest/NNN.json (used to verify traps and ingestion).
"""
import datetime as dt
import json

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, KeepTogether, LongTable, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle, CondPageBreak)
from reportlab.platypus.tableofcontents import TableOfContents

from .common import DOCS, MANIFEST, company, pdf_name, ref_label, registry, to_para_xml

NAVY = colors.HexColor("#1F3864")
HEAD_BG = colors.HexColor("#D9E2F3")
NOTE_BG = colors.HexColor("#F2F2F2")

BODY = ParagraphStyle("body", fontName="Times-Roman", fontSize=10, leading=13.2, alignment=TA_JUSTIFY,
                      spaceAfter=4, bulletFontName="Times-Bold", bulletFontSize=10)
SEC = ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=NAVY,
                     spaceBefore=10, spaceAfter=5, keepWithNext=1)
ANX = ParagraphStyle("anx", parent=SEC, fontSize=12, spaceBefore=4)
CIRC = ParagraphStyle("circ", parent=SEC, fontSize=11, spaceBefore=12)
CAP = ParagraphStyle("cap", fontName="Helvetica-Bold", fontSize=9, leading=11, spaceBefore=4,
                     spaceAfter=3, keepWithNext=1)
CELL = ParagraphStyle("cell", fontName="Times-Roman", fontSize=8.8, leading=10.6)
HCELL = ParagraphStyle("hcell", fontName="Helvetica-Bold", fontSize=8.2, leading=10)
NOTE = ParagraphStyle("note", parent=BODY, fontName="Times-Italic", fontSize=9.2, leading=12,
                      backColor=NOTE_BG, borderPadding=(4, 4, 4, 4), spaceBefore=4, spaceAfter=8)
TOC0 = ParagraphStyle("toc0", fontName="Helvetica-Bold", fontSize=9, leading=11, leftIndent=0)
TOC1 = ParagraphStyle("toc1", fontName="Helvetica", fontSize=8.6, leading=10.5, leftIndent=14)

# indent (points) of clause number and clause text, by clause depth (4.3 -> 2, 4.3.1 -> 3)
INDENT = {2: (0, 30), 3: (30, 64)}


class Anchor(Flowable):
    """Zero-size marker that records the physical page it lands on."""

    def __init__(self, store, key, edge):
        super().__init__()
        self.store, self.key, self.edge = store, key, edge

    def wrap(self, aw, ah):
        return 0, 0

    def draw(self):
        self.store.setdefault(self.key, {})[self.edge] = self.canv.getPageNumber()


def heading(text, style, level, toc_text, key):
    p = Paragraph(text, style)
    p.toc_level, p.toc_text, p.toc_key = level, toc_text, key
    return p


def keep_heading(h, body):
    """Bind a heading to its first real flowable (skipping zero-size anchors) so it is never orphaned."""
    i = 0
    while i < len(body) and isinstance(body[i], Anchor):
        i += 1
    if i < len(body) and not isinstance(body[i], (LongTable, Table)):
        return [KeepTogether([h, *body[:i + 1]]), *body[i + 1:]]
    return [h, *body]


class NexDoc(BaseDocTemplate):
    def __init__(self, filename, doc, **kw):
        super().__init__(filename, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                         topMargin=24 * mm, bottomMargin=22 * mm, title=doc["title"],
                         author="Nexora Technologies Limited (fictional)",
                         subject=f"{doc['number']} version {doc['version']} (fictional, college project)", **kw)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="main")
        self.addPageTemplates([PageTemplate(id="all", frames=[frame])])
        self.anchors, self.toc_log = {}, []

    def beforeDocument(self):
        self.toc_log = []

    def afterFlowable(self, f):
        level = getattr(f, "toc_level", None)
        if level is None:
            return
        self.canv.bookmarkPage(f.toc_key)
        self.canv.addOutlineEntry(f.toc_text, f.toc_key, level=level, closed=level > 0)
        self.notify("TOCEntry", (level, f.toc_text, self.page, f.toc_key))
        self.toc_log.append({"level": level, "text": f.toc_text, "page": self.page})


def canvas_maker(doc, info):
    """Canvas that defers drawing header/footer until the total page count is known."""
    left_head = f"Nexora Technologies Limited  |  {doc['title']}"
    right_head = f"{doc['number']}  |  Version {doc['version']}  |  {doc['control']['classification']}"
    foot = "Fictional company - college project. Not real HR policy. Uncontrolled when printed."

    class NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            info["pages"] = total
            for state in self._pages:
                self.__dict__.update(state)
                n = self.getPageNumber()
                if n > 1:
                    w, h = A4
                    self.setFont("Helvetica", 7.5)
                    self.setFillColor(colors.HexColor("#404040"))
                    self.drawString(22 * mm, h - 14 * mm, left_head)
                    self.drawRightString(w - 22 * mm, h - 14 * mm, right_head)
                    self.setStrokeColor(colors.HexColor("#A0A0A0"))
                    self.setLineWidth(0.4)
                    self.line(22 * mm, h - 15.5 * mm, w - 22 * mm, h - 15.5 * mm)
                    self.line(22 * mm, 15 * mm, w - 22 * mm, 15 * mm)
                    self.drawString(22 * mm, 11 * mm, foot)
                    self.setFont("Helvetica-Bold", 8)
                    self.drawRightString(w - 22 * mm, 11 * mm, f"Page {n} of {total}")
                rl_canvas.Canvas.showPage(self)
            rl_canvas.Canvas.save(self)

    return NumberedCanvas


class Builder:
    def __init__(self, doc):
        self.doc, self.here, self.reg = doc, doc["doc_id"], registry()
        self.anchors = {}
        self.width = A4[0] - 44 * mm
        self._k = 0

    def x(self, s):
        return to_para_xml(str(s), self.here, self.reg)

    def key(self):
        self._k += 1
        return f"h{self._k}"

    def anchored(self, key, flowables):
        return [Anchor(self.anchors, key, "start"), *flowables, Anchor(self.anchors, key, "end")]

    # ---------- front matter ----------
    def cover(self):
        d, c = self.doc, company()["company"]
        t = ParagraphStyle
        out = [Spacer(1, 30 * mm),
               Paragraph("NEXORA TECHNOLOGIES LIMITED", t("c1", fontName="Helvetica-Bold", fontSize=20,
                                                          leading=24, alignment=TA_CENTER, textColor=NAVY)),
               Paragraph("(a fictional company created for a college project)",
                         t("c2", fontName="Helvetica-Oblique", fontSize=9, alignment=TA_CENTER, leading=12)),
               Spacer(1, 28 * mm),
               Paragraph(self.x(d["title"]).upper(), t("c3", fontName="Helvetica-Bold", fontSize=22, leading=27,
                                                        alignment=TA_CENTER)),
               Spacer(1, 4 * mm),
               Paragraph(f"Document No. {d['number']}", t("c4", fontName="Helvetica", fontSize=12,
                                                         alignment=TA_CENTER, leading=15)),
               Spacer(1, 20 * mm)]
        rows = [["Version", d["version"]], ["Effective Date", d["effective_date"]],
                ["Classification", d["control"]["classification"]], ["Policy Owner", d["control"]["owner"]]]
        out.append(self.simple_table(rows, [0.35, 0.65], header=False, center=True, width=0.6))
        out += [Spacer(1, 22 * mm),
                Paragraph(self.x(c["fictional_notice"]), t("c5", parent=NOTE, alignment=TA_CENTER)),
                Spacer(1, 6 * mm),
                Paragraph(f"Uncontrolled when printed. The current version is published on the {c['portal']}.",
                          t("c6", fontName="Helvetica", fontSize=8.5, alignment=TA_CENTER, leading=11)),
                PageBreak()]
        return out

    def control_page(self):
        d, ctl = self.doc, self.doc["control"]
        rows = [["Document Title", d["title"]], ["Document Number", d["number"]], ["Version", d["version"]],
                ["Effective Date", d["effective_date"]], ["Supersedes", ctl.get("supersedes", "None")],
                ["Policy Owner", ctl["owner"]], ["Approved By", ctl["approver"]],
                ["Date of Approval", ctl.get("approval_date", "")],
                ["Classification", ctl["classification"]], ["Review Cycle", ctl.get("review_cycle", "Annual")],
                ["Applicable To", ctl.get("applicable_to", "")]]
        out = [Paragraph("DOCUMENT CONTROL", SEC), self.simple_table(rows, [0.3, 0.7], header=False),
               Spacer(1, 6 * mm), Paragraph("VERSION HISTORY", SEC),
               self.simple_table([["Version", "Date", "Description of Change", "Prepared / Approved By"]]
                                 + [list(map(str, r)) for r in d["history"]], [0.11, 0.16, 0.48, 0.25])]
        if ctl.get("distribution"):
            out += [Spacer(1, 6 * mm), Paragraph("DISTRIBUTION AND ACCESS", SEC),
                    Paragraph(self.x(ctl["distribution"]), BODY)]
        out.append(PageBreak())
        return out

    def toc_page(self):
        toc = TableOfContents(dotsMinLevel=0, tableStyle=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        toc.levelStyles = [TOC0, TOC1]
        return [Paragraph("CONTENTS", SEC), toc, PageBreak()]

    # ---------- body ----------
    def simple_table(self, rows, widths, header=True, center=False, width=1.0, form=False):
        cells = []
        for i, r in enumerate(rows):
            style = HCELL if (header and i == 0) else CELL
            cells.append([Paragraph(self.x(v), HCELL if (not header and j == 0) else style)
                          for j, v in enumerate(r)])
        tw = self.width * width
        tbl = LongTable(cells, colWidths=[tw * w / sum(widths) for w in widths], repeatRows=1 if header else 0,
                        hAlign="CENTER" if center else "LEFT")
        cmds = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#808080")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 10 if form else 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
        if header:
            cmds.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_BG))
        else:
            cmds.append(("BACKGROUND", (0, 0), (0, -1), NOTE_BG))
        tbl.setStyle(TableStyle(cmds))
        return tbl

    def table(self, t, indent=0):
        header = t.get("header")
        rows = ([header] if header else []) + [list(map(str, r)) for r in t["rows"]]
        ncol = len(t["rows"][0])
        widths = t.get("widths") or [max(6, min(40, sum(len(str(r[j])) for r in rows) / len(rows)))
                                     for j in range(ncol)]
        long_table = len(rows) > 12
        # a short table stays with its caption; a long one may start on the current page and split
        out = [CondPageBreak(45 * mm)] if long_table else []
        cap = f"{t['id']}: {t['title']}" if t.get("id") else t.get("title")
        if cap:
            out.append(Paragraph(self.x(cap), ParagraphStyle("capi", parent=CAP, leftIndent=indent,
                                                             keepWithNext=0 if long_table else 1)))
        tbl = self.simple_table(rows, widths, header=bool(header), form=t.get("form", False),
                                width=(self.width - indent) / self.width)
        out.append(tbl)
        if t.get("note"):
            out.append(Paragraph(self.x(t["note"]), ParagraphStyle("tn", parent=NOTE, leftIndent=indent,
                                                                   backColor=None, spaceBefore=2)))
        else:
            out.append(Spacer(1, 4))
        return self.anchored(t["id"], out) if t.get("id") else out

    def items(self, items, indent, roman=False):
        out = []
        labels = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"]
        for i, it in enumerate(items):
            lab = f"({labels[i]})" if roman else f"({chr(97 + i)})"
            st = ParagraphStyle("it", parent=BODY, leftIndent=indent + 20, bulletIndent=indent, spaceAfter=2,
                                bulletFontName="Times-Roman")
            out.append(Paragraph(self.x(it), st, bulletText=lab))
        if out:
            out.append(Spacer(1, 2))
        return out

    def clause(self, b):
        num = str(b["clause"])
        depth = num.count(".") + 1
        bi, ti = INDENT.get(depth, INDENT[3])
        st = ParagraphStyle(f"cl{depth}", parent=BODY, leftIndent=ti, bulletIndent=bi)
        parts = []
        if b.get("term"):
            parts.append(f'<b>"{self.x(b["term"])}"</b>')
        if b.get("title"):
            t = self.x(b["title"])
            parts.append(f"<b>{t if t[-1] in '.?:' else t + '.'}</b>")
        if b.get("text"):
            parts.append(self.x(b["text"]))
        out = [Paragraph(" ".join(parts), st, bulletText=num)]
        out += self.items(b.get("items") or [], ti, roman=depth >= 3)
        out += self.blocks(b.get("body") or [], ti)
        return self.anchored(num, out)

    def blocks(self, blocks, indent=0):
        out = []
        for b in blocks:
            if "clause" in b:
                out += self.clause(b)
            elif "table" in b:
                out += self.table(b["table"], indent)
            elif "para" in b:
                out.append(Paragraph(self.x(b["para"]), ParagraphStyle("p", parent=BODY, leftIndent=indent)))
            elif "note" in b:
                out.append(Paragraph(self.x(b["note"]), ParagraphStyle("n", parent=NOTE, leftIndent=indent + 4)))
            elif "items" in b:
                out += self.items(b["items"], indent)
        return out

    def sections(self):
        out = []
        for s in self.doc["sections"]:
            if s.get("new_page"):
                out.append(PageBreak())
            h = heading(f"{s['num']}. {self.x(s['title']).upper()}", SEC, 0, f"{s['num']}. {s['title']}", self.key())
            out += self.anchored(f"Section {s['num']}", keep_heading(h, self.blocks(s.get("body", []))))
        return out

    def annexures(self):
        out = []
        for i, a in enumerate(self.doc.get("annexures", [])):
            out.append(PageBreak() if (i == 0 or a.get("new_page")) else CondPageBreak(70 * mm))
            h = heading(f"ANNEXURE {a['id']}: {self.x(a['title']).upper()}", ANX, 0,
                        f"Annexure {a['id']}: {a['title']}", self.key())
            out += self.anchored(f"Annexure {a['id']}", keep_heading(h, self.blocks(a.get("body", []))))
        return out

    def circulars(self):
        circs = self.doc.get("circulars", [])
        if not circs:
            return []
        out = [PageBreak(), heading("AMENDMENT CIRCULARS", ANX, 0, "Amendment Circulars", self.key())]
        if self.doc.get("circulars_intro"):
            out.append(Paragraph(self.x(self.doc["circulars_intro"]), BODY))
        for c in circs:
            h = heading(f"CIRCULAR NO. {c['number']}", CIRC, 1, f"Circular {c['number']}: {c['subject']}", self.key())
            amends = ", ".join(self.x(f"{{ref:{a}}}") if "#" in a else ref_label(a) for a in c["amends"])
            rows = [["Circular No.", c["number"]], ["Date of Issue", c["date"]],
                    ["Effective From", c["effective_from"]], ["Subject", c["subject"]],
                    ["Amends", amends], ["Issued By", c["issued_by"]]]
            meta = self.simple_table(rows, [0.25, 0.75], header=False)
            body = []
            if c.get("intro"):
                body.append(Paragraph(self.x(c["intro"]), BODY))
            body += self.blocks(c.get("body", []))
            out += self.anchored(c["number"], [h, meta, Spacer(1, 5), *body])
        return out

    def story(self):
        return (self.cover() + self.control_page() + self.toc_page() + self.sections()
                + self.annexures() + self.circulars())


def build(doc):
    DOCS.mkdir(exist_ok=True)
    MANIFEST.mkdir(exist_ok=True)
    out_pdf = DOCS / pdf_name(doc["doc_id"])
    b = Builder(doc)
    info = {}
    pdf = NexDoc(str(out_pdf), doc)
    pdf.multiBuild(b.story(), canvasmaker=canvas_maker(doc, info), maxPasses=10)
    manifest = {"doc_id": doc["doc_id"], "title": doc["title"], "number": doc["number"],
                "version": doc["version"], "effective_date": doc["effective_date"], "pdf": out_pdf.name,
                "pages": info["pages"], "built": dt.datetime.now().isoformat(timespec="seconds"),
                "toc": pdf.toc_log, "anchors": b.anchors}
    (MANIFEST / f"{doc['doc_id']}.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return out_pdf, manifest
