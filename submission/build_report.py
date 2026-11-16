"""Build the submission from REPORT_DRAFT.md and the sprint's Word template.

  python submission/build_report.py          -> submission/report.docx
  python submission/build_report.py --pdf    -> also submission/report.pdf (Word via docx2pdf)

The template's page setup, styles and fonts are kept, and its guidance text and info box are removed.
REPORT_DRAFT.md supplies the content, in the template's section order:
- the title block: title, author, abstract;
- 1 Introduction, 2 Related Work, 3 Methods, 4 Results;
- 5 Discussion and Limitations, with Limitations and Future Work; 6 Conclusion;
- Code and Data, then References;
- the Appendix (Limitations and Dual-Use / Ethical Considerations), then the LLM Usage Statement.

Markdown is converted to Word: bold, italic and code runs, bullet and numbered lists on the template's
numbering, real tables, hyperlinks, and the four figures from data/results/ with numbered captions,
each placed where the draft first cites it. The Code and Data section names the commit that holds
the code, data, results and this report's source; the build stops if any of those have uncommitted
changes, so the commit it names is the one the report was built from.
"""
from __future__ import annotations

import argparse
import copy
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
AUTHOR_NAME, AFFILIATION = "Arsalan Banekar", "Independent Researcher, Pune, India"
REPO_URL = "https://github.com/Arsalanbanekar/verification-theatre"
BULLET_NUM_ID, NUMBERED_NUM_ID = 3, 5        # the template's dash-bullet and decimal list definitions
FIG_WIDTH_IN = 5.0
CODE_FONT = "Consolas"
MINUS_FONT = "Cambria"                        # for U+2212 in the abstract box (see fill_title_block)
LINK_COLOR = "1155CC"
TEMPLATE_HEADINGS = {"1": "1. Introduction", "2": "2. Related Work", "3": "3. Methods", "4": "4. Results",
                     "5": "5. Discussion and Limitations", "6": "6. Conclusion"}
PARA_AFTER, ITEM_AFTER = 3, 1                 # points after a paragraph and between list items
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
            text = b["text"]                                  # "Abstract", "1".."5", "Appendix A", "References"
            key = text.split(".")[0] if text.startswith("Appendix") else text.split(".")[0].split()[0]
            secs[key] = []
        elif key is not None:
            secs[key].append(b)
    return title, secs


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
    r = par.add_run(text)
    r.bold, r.italic = bold or None, italic or None
    if code:
        r.font.name = CODE_FONT
        r.font.size = Pt((size or 11) - 1)
    elif size:
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


def add_list(doc, items: list[dict], size=None) -> None:
    for k, it in enumerate(items):
        p = doc.add_paragraph(style="normal")
        add_runs(p, it["text"], size)
        num_pr = p._p.get_or_add_pPr().get_or_add_numPr()
        num_pr.get_or_add_ilvl().val = it["level"]
        num_pr.get_or_add_numId().val = NUMBERED_NUM_ID if it["num"] else BULLET_NUM_ID
        p.paragraph_format.space_after = Pt(PARA_AFTER if k == len(items) - 1 else ITEM_AFTER)


def caption_style(doc):
    if "Caption" not in [s.name for s in doc.styles]:
        st = doc.styles.add_style("Caption", WD_STYLE_TYPE.PARAGRAPH)
        st.base_style = doc.styles["normal"]
        st.font.size = Pt(9.5)
        st.font.color.rgb = RGBColor(0x26, 0x26, 0x26)
        st.paragraph_format.space_after = Pt(6)
    return "Caption"


def caption(doc, text: str, keep_with_next=False):
    p = doc.add_paragraph(style=caption_style(doc))
    add_runs(p, text)
    p.paragraph_format.keep_with_next = keep_with_next
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
        e.set(qn("w:color"), "808080")
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
        cant = OxmlElement("w:cantSplit")
        tr_pr.append(cant)
        for c, text in enumerate(row):
            cell = t.cell(r, c)
            cell.width = Inches(widths[c])
            p = cell.paragraphs[0]
            add_runs(p, text, size, bold=(r == 0))
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.keep_with_next = r < len(rows) - 1   # keep the table on one page
            if c > 0 and r > 0 and re.fullmatch(r"[−+\-]?[\d.]+%?\*?", text):
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            mark, sz = OxmlElement("w:rPr"), OxmlElement("w:sz")      # the paragraph mark in the cell's size,
            sz.set(qn("w:val"), str(int(size * 2)))                   # so the default 11 pt does not set the
            mark.append(sz)                                           # row height
            p._p.get_or_add_pPr().append(mark)


def add_figure(doc, n: int, text: str) -> None:
    p = doc.add_paragraph(style="normal")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(4)
    p.add_run().add_picture(str(ROOT / "data" / "results" / FIGURES[n]), width=Inches(FIG_WIDTH_IN))
    text = re.sub(r";\s*`data/results/[^`]+`", "", text)        # "(95% CIs over claims; `file`)." -> "(… claims)."
    text = re.sub(r"\s*\(`data/results/[^`]+`\)", "", text)      # "marked (`file`)." -> "marked."
    caption(doc, f"**Figure {n}.** {text}")


# ---------------------------------------------------------------- the document

def emit(doc, blocks: list[dict], tables: dict[int, list[float]]) -> None:
    """Draft blocks in order. A table caption goes above its table; Table 2's notes (a list after a
    'Notes to Table 2:' line) are set below it as one caption-style paragraph."""
    pending_caption, i = None, 0
    while i < len(blocks):
        b = blocks[i]
        if b["t"] == "h":
            heading(doc, b["text"], min(b["level"], 4))
        elif b["t"] == "p" and b["text"].startswith("Notes to Table") and i + 1 < len(blocks) \
                and blocks[i + 1]["t"] == "list":
            notes = " ".join(it["text"] for it in blocks[i + 1]["items"])
            caption(doc, f"*Notes.* {notes}")
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
                caption(doc, f"**Table {n}.** {pending_caption['text']}", keep_with_next=True)
                pending_caption = None
            add_table(doc, b["rows"], tables.get(n, [6.5 / len(b["rows"][0])] * len(b["rows"][0])))
            gap = doc.add_paragraph(style="normal").paragraph_format     # a 6-point gap below the table
            gap.line_spacing, gap.space_after = Pt(6), Pt(0)
        elif b["t"] == "figure":
            add_figure(doc, b["n"], b["text"])
        i += 1


def fill_title_block(doc, title: str, abstract: str) -> None:
    """The template's first table: the title in its first cell; in its second, the author block (a grid of
    six 'Author name / Affiliation' cells, then 'With Apart Research'), 'Abstract', and a box holding the
    abstract guidance. The grid becomes the one author, in the grid's own formatting; the abstract
    replaces the guidance in the box, in the box's font, not italic."""
    block = doc.tables[0]
    tcell, acell = block.cell(0, 0), block.cell(1, 0)
    title_p = next(p for p in tcell.paragraphs if p.style.name == "Title")
    runs = title_p.runs
    runs[0].text = title
    for r in runs[1:]:
        r.text = ""

    author_cell = acell.tables[0].cell(0, 0)
    grid = author_cell.tables[0]
    author_p = copy.deepcopy(grid.cell(0, 0).paragraphs[0]._p)
    texts = list(author_p.iter(qn("w:t")))
    assert [t.text for t in texts[:2]] == ["Author name 1", "Affiliation"], [t.text for t in texts]
    texts[0].text, texts[1].text = AUTHOR_NAME, AFFILIATION
    grid._tbl.addprevious(author_p)
    grid._tbl.getparent().remove(grid._tbl)

    box_p = acell.tables[1].cell(0, 0).paragraphs[0]
    font = next((r.font.name for r in box_p.runs if r.font.name), None)
    for r in list(box_p.runs):
        r._r.getparent().remove(r._r)
    add_runs(box_p, abstract)
    for r in box_p.runs:
        r.font.name, r.italic = font, None
    for r in list(box_p.runs):                  # the box font's minus is nearly em-dash wide (0.94 em), so
        if "−" not in r.text:                   # minus signs are set in a serif with a plus-width minus
            continue
        pieces = [x for x in re.split("(−)", r.text) if x]
        for piece in pieces:
            el = copy.deepcopy(r._r)
            r._r.addprevious(el)
            new = type(r)(el, box_p)
            new.text = piece
            if piece == "−":
                new.font.name = MINUS_FONT
        r._r.getparent().remove(r._r)


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
    body_el = doc.element.body
    title_block = doc.tables[0]._tbl
    started = False
    for child in list(body_el.iterchildren()):   # keep the leading spacer and the title block; drop the rest,
        if child is title_block:                 # the info box and all guidance text included
            started = True
            continue
        if child.tag == qn("w:sectPr") or not started:
            continue
        body_el.remove(child)
    abstract = " ".join(b["text"] for b in secs["Abstract"] if b["t"] == "p")
    fill_title_block(doc, title, abstract)

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
    ])

    heading(doc, "References", 2)
    for b in secs["References"]:
        for it in (b["items"] if b["t"] == "list" else []):
            p = doc.add_paragraph(style="normal")
            add_runs(p, it["text"], size=10)
            pf = p.paragraph_format
            pf.left_indent, pf.first_line_indent, pf.space_after = Inches(0.3), Inches(-0.3), Pt(4)

    appendix = secs["Appendix A"]
    heading(doc, "Appendix A. Limitations and Dual-Use / Ethical Considerations", 2)
    ai = next(k for k, b in enumerate(appendix) if b["t"] == "p" and b["text"].startswith("**AI assistance.**"))
    emit(doc, appendix[:ai] + appendix[ai + 1:], widths)
    if "Appendix B" in secs:
        heading(doc, "Appendix B. Supplementary methods and results", 2)
        emit(doc, secs["Appendix B"], widths)

    heading(doc, "LLM Usage Statement", 2)
    body(doc, appendix[ai]["text"].replace("**AI assistance.** ", "", 1))

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
