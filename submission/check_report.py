"""Check submission/report.pdf: page counts, and every page rendered to PNG for inspection.

  python submission/check_report.py [--png-dir DIR] [--dpi 110]

Prints the total page count, the page on which the References heading starts, and so the number of
pages of main text (title block to the end of the section before References, counting a partly filled
last page). The sprint allows 8. It also lists any character a page's fonts could not render (shown
as U+FFFD or as a missing-glyph box) and any heading that ends a page.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "submission" / "report.pdf"
HEADINGS = ("1. Introduction", "2. Related Work", "3. Methods", "4. Results", "5. Discussion and Limitations",
            "Code and Data", "References", "Appendix A.", "LLM Usage Statement")


def page_of(doc, text: str) -> int | None:
    """1-based page of the first line that starts with text, set in a font larger than body text."""
    for i, page in enumerate(doc, 1):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = line["spans"]
                joined = "".join(s["text"] for s in spans).strip()
                if joined.startswith(text) and max(s["size"] for s in spans) > 12:
                    return i
    return None


def stranded_headings(doc) -> list[str]:
    """Headings whose page ends right after them (the next text is on the following page)."""
    out = []
    for i, page in enumerate(doc, 1):
        lines = [("".join(s["text"] for s in l["spans"]).strip(), max(s["size"] for s in l["spans"]))
                 for b in page.get_text("dict")["blocks"] for l in b.get("lines", []) if l["spans"]]
        lines = [x for x in lines if x[0]]
        if lines and lines[-1][1] > 12.5:
            out.append(f"page {i}: '{lines[-1][0][:60]}'")
    return out


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", type=Path, default=PDF)
    ap.add_argument("--png-dir", type=Path)
    ap.add_argument("--dpi", type=int, default=110)
    a = ap.parse_args(argv)
    doc = pymupdf.open(a.pdf)
    refs = page_of(doc, "References")
    print(f"pages: {doc.page_count}; References starts on page {refs}; main text: {refs} pages "
          f"(title block to the end of Code and Data, the last partly filled)")
    for h in HEADINGS:
        print(f"  {h:32} page {page_of(doc, h)}")
    bad = [(i, ch) for i, page in enumerate(doc, 1) for ch in page.get_text() if ch in "�□"]
    print("unrenderable characters:", bad or "none")
    print("headings ending a page:", stranded_headings(doc) or "none")
    if a.png_dir:
        a.png_dir.mkdir(parents=True, exist_ok=True)
        for i, page in enumerate(doc, 1):
            page.get_pixmap(dpi=a.dpi).save(a.png_dir / f"page-{i:02d}.png")
        print(f"rendered {doc.page_count} pages to {a.png_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
