"""Build the submission from REPORT_DRAFT.md and the sprint's Word template.

  python submission/build_report.py          -> submission/report.docx
  python submission/build_report.py --pdf    -> also submission/report.pdf (Word via docx2pdf)

The template supplies the page setup (US Letter, 1-inch margins), the styles and the list numbering; the
styles are restyled to the author's earlier Apart report: Calibri throughout, body 11 pt justified at 1.08
line spacing with 6 pt after, orange (#C55A11) bold headings, centred italic figure captions, tables with
thin black borders and a light-orange header row, round bullets, and a centred page number in the footer.
REPORT_DRAFT.md supplies the content, in the template's section order:
- title, author, affiliation and abstract;
- 1 Introduction, 2 Related Work, 3 Methods, 4 Results;
- 5 Discussion and Limitations, with Limitations and Future Work; 6 Conclusion;
- Code and Data, then References;
- the Appendix (Limitations and Dual-Use / Ethical Considerations), then the LLM Usage Statement.

Markdown is converted to Word: bold, italic and code runs, bullet and numbered lists, real tables, hyperlinks,
and the four figures from data/results/ with numbered captions, each placed where the draft puts it. The Code
and Data section names the commit that holds the code, data, results and this report's source; the build
stops if any of those have uncommitted changes, so the commit it names is the one the report was built from.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "submission" / "template.docx"
DRAFT = ROOT / "REPORT_DRAFT.md"
OUT = ROOT / "submission" / "report.docx"
FIGURES = {1: "fig1_acceptance.png", 2: "fig2_discrimination.png", 3: "fig3_scope_accuracy.png",
           4: "fig4_interpreter.png"}
AUTHOR_NAME = "Arsalan Banekar"
AFFILIATION = ("Independent submission, Apart Research AI x Epistemics Research Sprint "
               "(Track 2: Trust Infrastructure), November 2026")
REPO_URL = "https://github.com/Arsalanbanekar/verification-theatre"
BULLET_NUM_ID, NUMBERED_NUM_ID = 3, 5        # the template's bullet and decimal list definitions
FIG_WIDTH_IN = 5.2
FONT = "Calibri"
BLACK, GREY, ORANGE = RGBColor(0, 0, 0), RGBColor(0x55, 0x55, 0x55), RGBColor(0xC5, 0x5A, 0x11)
HEADER_FILL = "FCE4D6"
LINK_COLOR = "1155CC"
TEMPLATE_HEADINGS = {"1": "1. Introduction", "2": "2. Related Work", "3": "3. Methods", "4": "4. Results",
                     "5": "5. Discussion and Limitations", "6": "6. Conclusion"}
PARA_AFTER, ITEM_AFTER = 6, 2                 # points after a paragraph and between list items
LIMITATIONS_POINTER = ("Appendix A sets out the limitations, chiefly the baseline ceiling, the single unvalidated "
                       "judge, Qwen's parse failures and the lowest reasoning settings.")
CELL_PAD_DXA = 30                             # top and bottom cell padding in the report's tables (1.5 pt)


# ---------------------------------------------------------------- Markdown -> blocks

LIST_ITEM = re.compile(r"( *)(- |\d+\. )(.*)")


def parse(md: str) -> list[dict]:
    """The constructs REPORT_DRAFT.md uses: title, headings, paragraphs, bullet and numbered lists (nested
    by two spaces), pipe tables, figure captions (*Figure N. ...*) and table captions (**Table N.** ...).
    Horizontal rules and the draft's internal status note (a blockquote) are not part of the paper."""
    lines, out, para, i = md.splitlines(), [], [], 0

    def flush():
        if not para:
            return
        text = " ".join(x.strip() for x in para)
        para.clear()
        fig = re.fullmatch(r"\*Figure (\d+)\. (.*)\*", text)
        tab = re.fullmatch(r"\*\*Table (\d+)\.\*\* (.*)", text)
        if fig:
            out.append({"t": "figure", "n": int(fig.group(1)), "text": fig.group(2)})
        elif tab:
            out.append({"t": "tabcap", "n": int(tab.group(1)), "text": tab.group(2)})
        else:
            out.append({"t": "p", "text": text})

    while i < len(lines):
        line, s = lines[i], lines[i].strip()
        if not s or s == "---":
            flush()
            i += 1
        elif s.startswith("# "):
            flush()
            out.append({"t": "title", "text": s[2:].strip()})
            i += 1
        elif re.match(r"#{2,4} ", s):
            flush()
            level = len(s) - len(s.lstrip("#"))
            out.append({"t": "h", "level": level, "text": s[level:].strip()})
            i += 1
        elif s.startswith(">"):
            flush()
            while i < len(lines) and lines[i].strip().startswith(">"):
                i += 1
        elif s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            out.append({"t": "table", "rows": rows})
        elif LIST_ITEM.match(line):
            flush()
            items = []
            while i < len(lines):
                m = LIST_ITEM.match(lines[i])
                if m:
                    items.append({"level": len(m.group(1)) // 2, "num": m.group(2)[0].isdigit(),
                                  "text": m.group(3).strip()})
                elif lines[i].startswith("  ") and lines[i].strip() and items:
                    items[-1]["text"] += " " + lines[i].strip()
                else:
                    break
                i += 1
            out.append({"t": "list", "items": items})
        else:
            para.append(line)
            i += 1
    flush()
    return out


def sections(blocks: list[dict]) -> tuple[str, dict[str, list[dict]]]:
    """The title and the draft's level-2 sections, keyed by their leading word or number."""
    title, secs, key = "", {}, None
    for b in blocks:
        if b["t"] == "title":
            title = b["text"]
        elif b["t"] == "h" and b["level"] == 2:
            text = b["text"]                                  # "Abstract", "1".."6", "Appendix A", "References"
            key = text.split(".")[0] if text.startswith("Appendix") else text.split(".")[0].split()[0]
            secs[key] = []
        elif key is not None:
            secs[key].append(b)
    return title, secs


# ---------------------------------------------------------------- styles

def _calibri(rpr) -> None:
    """Calibri in all four script slots of an rPr element, with any theme-font override removed."""
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        fonts.attrib.pop(qn(f"w:{attr}"), None)
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{attr}"), FONT)


def _style(st, size, bold=False, italic=False, color=BLACK, before=None, after=None, align=None, keep=None):
    st.font.name, st.font.size, st.font.bold, st.font.italic = FONT, Pt(size), bold, italic
    st.font.color.rgb = color
    _calibri(st.element.get_or_add_rPr())
    pf = st.paragraph_format
    if before is not None:
        pf.space_before = Pt(before)
    if after is not None:
        pf.space_after = Pt(after)
    if align is not None:
        pf.alignment = align
    if keep is not None:
        pf.keep_with_next = keep


def apply_styles(doc) -> None:
    defaults = doc.styles.element.find(qn("w:docDefaults")).find(qn("w:rPrDefault")).find(qn("w:rPr"))
    _calibri(defaults)
    normal = doc.styles["normal"]
    _style(normal, 11, after=PARA_AFTER, before=0, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    normal.paragraph_format.line_spacing = 1.08
    _style(doc.styles["Heading 2"], 14, bold=True, color=ORANGE, before=18, after=6,
           align=WD_ALIGN_PARAGRAPH.LEFT, keep=True)
    _style(doc.styles["Heading 3"], 12, bold=True, color=ORANGE, before=10, after=4,
           align=WD_ALIGN_PARAGRAPH.LEFT, keep=True)
    if "Caption" not in [s.name for s in doc.styles]:
        cap = doc.styles.add_style("Caption", WD_STYLE_TYPE.PARAGRAPH)
        cap.base_style = normal
    _style(doc.styles["Caption"], 10, italic=True, before=2, after=10, align=WD_ALIGN_PARAGRAPH.CENTER)
    for st in doc.styles:                                  # every other style that names a font: Calibri
        rpr = st.element.find(qn("w:rPr"))
        if rpr is not None and rpr.find(qn("w:rFonts")) is not None:
            _calibri(rpr)
    numbering = doc.part.numbering_part.element             # round bullets; list labels in Calibri
    for an in numbering.findall(qn("w:abstractNum")):
        for lvl in an.findall(qn("w:lvl")):
            if lvl.find(qn("w:numFmt")).get(qn("w:val")) == "bullet":
                lvl.find(qn("w:lvlText")).set(qn("w:val"), "•")
            rpr = lvl.find(qn("w:rPr"))
            if rpr is not None:
                _calibri(rpr)


def page_number_footer(doc) -> None:
    footer = doc.sections[0].footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        r = p.add_run()
        r.font.name, r.font.size = FONT, Pt(11)
        if kind:
            fld = OxmlElement("w:fldChar")
            fld.set(qn("w:fldCharType"), kind)
            r._r.append(fld)
        else:
            instr = OxmlElement("w:instrText")
            instr.set(qn("xml:space"), "preserve")
            instr.text = text
            r._r.append(instr)


# ---------------------------------------------------------------- Word helpers

INLINE = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`|(?<![\w*\\])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])|\\\*")
URL = re.compile(r"https?://[^\s)]+[^\s).,;]")


def add_hyperlink(par, url: str, text: str, size: float | None = None) -> None:
    r_id = par.part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                              is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run, rpr = OxmlElement("w:r"), OxmlElement("w:rPr")
    color, underline = OxmlElement("w:color"), OxmlElement("w:u")
    color.set(qn("w:val"), LINK_COLOR)
    underline.set(qn("w:val"), "single")
    rpr.extend([color, underline])
    if size:
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), str(int(size * 2)))
        rpr.append(sz)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    run.extend([rpr, t])
    link.append(run)
    par._p.append(link)


def _run(par, text, bold=False, italic=False, code=False, size=None):
    if not text:
        return
    if not code and URL.search(text):                              # URLs become live links
        pos = 0
        for m in URL.finditer(text):
            _run(par, text[pos:m.start()], bold, italic, False, size)
            add_hyperlink(par, m.group(0), m.group(0), size)
            pos = m.end()
        _run(par, text[pos:], bold, italic, False, size)
        return
    r = par.add_run(text)                                          # code spans are set in Calibri like the rest
    r.bold, r.italic = bold or None, italic or None
    if size:
        r.font.size = Pt(size)


def add_runs(par, text: str, size=None, bold=False, italic=False) -> None:
    """Markdown inline markup -> runs: **bold**, *italic*, `code`, \\* for a literal asterisk."""
    pos = 0
    for m in INLINE.finditer(text):
        _run(par, text[pos:m.start()], bold, italic, False, size)
        if m.group(1) is not None:
            add_runs(par, m.group(1), size, True, italic)
        elif m.group(2) is not None:
            _run(par, m.group(2), bold, italic, True, size)
        elif m.group(3) is not None:
            add_runs(par, m.group(3), size, bold, True)
        else:
            _run(par, "*", bold, italic, False, size)
        pos = m.end()
    _run(par, text[pos:], bold, italic, False, size)


def body(doc, text: str, size=None, space_after=PARA_AFTER, align=None):
    p = doc.add_paragraph(style="normal")
    add_runs(p, text, size)
    p.paragraph_format.space_after = Pt(space_after)
    if align is not None:
        p.alignment = align
    return p


def heading(doc, text: str, level: int):
    return doc.add_paragraph(text, style=f"Heading {level}")


def add_list(doc, items: list[dict], size=None, align=None) -> None:
    for k, it in enumerate(items):
        p = doc.add_paragraph(style="normal")
        add_runs(p, it["text"], size)
        if align is not None:
            p.alignment = align
        num_pr = p._p.get_or_add_pPr().get_or_add_numPr()
        num_pr.get_or_add_ilvl().val = it["level"]
        num_pr.get_or_add_numId().val = NUMBERED_NUM_ID if it["num"] else BULLET_NUM_ID
        p.paragraph_format.space_after = Pt(PARA_AFTER if k == len(items) - 1 else ITEM_AFTER)


def caption(doc, text: str, keep_with_next=False):
    p = doc.add_paragraph(style="Caption")
    add_runs(p, text)
    p.paragraph_format.keep_with_next = keep_with_next
    return p


def table_caption(doc, n: int, text: str):
    """'Table N.' in bold, then the caption in italic, both 10 pt, above the table."""
    p = doc.add_paragraph(style="normal")
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _run(p, f"Table {n}.", bold=True, size=10)
    add_runs(p, " " + text, size=10, italic=True)
    pf = p.paragraph_format
    pf.keep_with_next, pf.space_before, pf.space_after = True, Pt(4), Pt(3)
    return p


def _tbl_pr(table, el) -> None:
    """Add a table property in schema order, before tblLook."""
    tbl_pr = table._tbl.tblPr
    look = tbl_pr.find(qn("w:tblLook"))
    if look is not None:
        look.addprevious(el)
    else:
        tbl_pr.append(el)


def _borders(table, size=4):
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), str(size))
        e.set(qn("w:color"), "000000")
        borders.append(e)
    _tbl_pr(table, borders)


def _cell_padding(table, top_bottom=CELL_PAD_DXA, sides=100):
    """This table's cell padding; the template's table style pads every side by 100 dxa (5 pt)."""
    mar = OxmlElement("w:tblCellMar")
    for edge, w in (("top", top_bottom), ("left", sides), ("bottom", top_bottom), ("right", sides)):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:w"), str(w))
        e.set(qn("w:type"), "dxa")
        mar.append(e)
    _tbl_pr(table, mar)


def add_table(doc, rows: list[list[str]], widths: list[float], size=9.5) -> None:
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    _borders(t)
    _cell_padding(t)
    for r, row in enumerate(rows):
        tr_pr = t.rows[r]._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
        for c, text in enumerate(row):
            cell = t.cell(r, c)
            cell.width = Inches(widths[c])
            if r == 0:                                             # header row: light-orange fill
                shd = OxmlElement("w:shd")
                shd.set(qn("w:val"), "clear")
                shd.set(qn("w:color"), "auto")
                shd.set(qn("w:fill"), HEADER_FILL)
                cell._tc.get_or_add_tcPr().append(shd)
            p = cell.paragraphs[0]
            add_runs(p, text, size, bold=(r == 0))
            pf = p.paragraph_format
            pf.space_after, pf.space_before, pf.line_spacing = Pt(1), Pt(0), 1.0
            pf.keep_with_next = r < len(rows) - 1                 # keep the table on one page
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            mark, sz = OxmlElement("w:rPr"), OxmlElement("w:sz")   # the paragraph mark in the cell's size,
            sz.set(qn("w:val"), str(int(size * 2)))                # so the default 11 pt does not set the
            mark.append(sz)                                        # row height
            p._p.get_or_add_pPr().append(mark)


def add_figure(doc, n: int, text: str) -> None:
    p = doc.add_paragraph(style="normal")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(0)
    p.add_run().add_picture(str(ROOT / "data" / "results" / FIGURES[n]), width=Inches(FIG_WIDTH_IN))
    text = re.sub(r";\s*`data/results/[^`]+`", "", text)        # "(95% CIs over claims; `file`)." -> "(… claims)."
    text = re.sub(r"\s*\(`data/results/[^`]+`\)", "", text)      # "marked (`file`)." -> "marked."
    caption(doc, f"Figure {n}. {text}")


# ---------------------------------------------------------------- the document

def emit(doc, blocks: list[dict], tables: dict[int, list[float]]) -> None:
    """Draft blocks in order. A table caption goes above its table; a table's notes (a list after a
    'Notes to Table N:' line) are set below it as one small paragraph."""
    pending_caption, i = None, 0
    while i < len(blocks):
        b = blocks[i]
        if b["t"] == "h":
            heading(doc, b["text"], min(b["level"], 4))
        elif b["t"] == "p" and b["text"].startswith("Notes to Table") and i + 1 < len(blocks) \
                and blocks[i + 1]["t"] == "list":
            notes = " ".join(it["text"] for it in blocks[i + 1]["items"])
            body(doc, f"*Notes.* {notes}", size=9.5, space_after=10)
            i += 1
        elif b["t"] == "p":
            body(doc, b["text"])
        elif b["t"] == "list":
            add_list(doc, b["items"])
        elif b["t"] == "tabcap":
            pending_caption = b
        elif b["t"] == "table":
            n = pending_caption["n"] if pending_caption else 0
            if pending_caption:
                table_caption(doc, n, pending_caption["text"])
                pending_caption = None
            add_table(doc, b["rows"], tables.get(n, [6.5 / len(b["rows"][0])] * len(b["rows"][0])))
            gap = doc.add_paragraph(style="normal").paragraph_format     # a 6-point gap below the table
            gap.line_spacing, gap.space_after = Pt(6), Pt(0)
        elif b["t"] == "figure":
            add_figure(doc, b["n"], b["text"])
        i += 1


def title_block(doc, title: str, abstract: str) -> None:
    """Title, author, affiliation, the Abstract heading and the abstract, as in the author's earlier report."""
    def line(text, size, bold=False, color=BLACK, after=0, align=WD_ALIGN_PARAGRAPH.CENTER):
        p = doc.add_paragraph(style="normal")
        p.alignment = align
        r = p.add_run(text)
        r.font.size, r.bold, r.font.color.rgb = Pt(size), bold or None, color
        p.paragraph_format.space_after = Pt(after)
        return p

    line(title, 17, bold=True, after=10).paragraph_format.line_spacing = 1.0
    line(AUTHOR_NAME, 11, bold=True)
    line(AFFILIATION, 10, color=GREY, after=16)
    line("Abstract", 12, bold=True, color=ORANGE, after=3, align=WD_ALIGN_PARAGRAPH.LEFT) \
        .paragraph_format.keep_with_next = True
    body(doc, abstract)


def git_commit(paths=("REPORT_DRAFT.md", "src", "data", "corpus", "models.yaml", "PREREGISTRATION.md")) -> str:
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no", "--", *paths], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit("Commit these first, so the Code and Data line names the commit the report was built "
                         f"from:\n{dirty}")
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def build(out: Path = OUT, commit: str | None = None) -> Path:
    commit = commit or git_commit()
    title, secs = sections(parse(DRAFT.read_text(encoding="utf-8")))
    doc = Document(str(TEMPLATE))
    apply_styles(doc)
    body_el = doc.element.body
    for child in list(body_el.iterchildren()):     # the template's own content goes: title block, info box, guidance
        if child.tag != qn("w:sectPr"):
            body_el.remove(child)
    page_number_footer(doc)
    abstract = " ".join(b["text"] for b in secs["Abstract"] if b["t"] == "p")
    title_block(doc, title, abstract)

    widths = {1: [0.45, 3.0, 3.0], 2: [1.6, 0.85, 0.65, 0.65, 0.65, 1.05, 1.05]}
    for key in ("1", "2", "3", "4"):
        heading(doc, TEMPLATE_HEADINGS[key], 2)
        emit(doc, secs[key], widths)

    heading(doc, TEMPLATE_HEADINGS["5"], 2)
    disc = secs["5"]
    fw = next(k for k, b in enumerate(disc) if b["t"] == "p" and b["text"].startswith("**Future work.**"))
    emit(doc, disc[:fw], widths)
    heading(doc, "Limitations", 3)
    body(doc, LIMITATIONS_POINTER)
    heading(doc, "Future Work", 3)
    body(doc, disc[fw]["text"].replace("**Future work.** ", "", 1))
    emit(doc, disc[fw + 1:], widths)

    heading(doc, TEMPLATE_HEADINGS["6"], 2)
    emit(doc, secs["6"], widths)

    heading(doc, "Code and Data", 2)
    add_list(doc, [
        {"level": 0, "num": False, "text": f"**Code repository**: {REPO_URL}, commit `{commit[:12]}`. It holds the "
                                           "code, the corpus, the pre-registration, the deviations log and this "
                                           "report's source."},
        {"level": 0, "num": False, "text": "**Data**: every model response (`data/raw/`), every judge call and score "
                                           "(`data/graded/`) and every analysis output (`data/results/`), in the "
                                           "same repository."},
    ], align=WD_ALIGN_PARAGRAPH.LEFT)                 # a long URL would stretch a justified line

    heading(doc, "References", 2)
    for b in secs["References"]:
        for it in (b["items"] if b["t"] == "list" else []):
            p = doc.add_paragraph(style="normal")
            add_runs(p, it["text"], size=10)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pf = p.paragraph_format
            pf.left_indent, pf.first_line_indent, pf.space_after = Inches(0.3), Inches(-0.3), Pt(4)

    appendix = secs["Appendix A"]
    heading(doc, "Appendix A. Limitations and Dual-Use / Ethical Considerations", 2)
    ai = next(k for k, b in enumerate(appendix) if b["t"] == "p" and b["text"].startswith("**AI assistance.**"))
    emit(doc, appendix[:ai] + appendix[ai + 1:], widths)

    heading(doc, "LLM Usage Statement", 2)
    body(doc, appendix[ai]["text"].replace("**AI assistance.** ", "", 1))

    for rpr in doc.element.body.iter(qn("w:rPr")):    # Calibri everywhere, whatever a run or mark names
        if rpr.find(qn("w:rFonts")) is not None:
            _calibri(rpr)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    return out


def to_pdf(docx: Path) -> Path:
    pdf = docx.with_suffix(".pdf")
    try:
        from docx2pdf import convert
        convert(str(docx), str(pdf))
    except Exception as e:                                          # fall back to LibreOffice, if installed
        print(f"docx2pdf failed ({e!r}); trying LibreOffice")
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(docx.parent), str(docx)],
                       check=True)
    return pdf


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", action="store_true", help="also convert to PDF with Word")
    a = ap.parse_args(argv)
    out = build()
    print(f"wrote {out}")
    if a.pdf:
        print(f"wrote {to_pdf(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
