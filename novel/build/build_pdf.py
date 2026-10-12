#!/usr/bin/env python3
"""
Typeset THE PRICE OF MERCY from novel/chapters/*.md into a 6x9in trade-novel PDF.

Conventions in the markdown:
  # Chapter One: The Net      -> chapter number + title
  *Warsaw — Thursday, 20 May 1943*  -> dateline (first italic line after the heading)
  ***                         -> scene break
  **bold**, *italic*          -> inline emphasis
  everything else             -> body paragraphs

Usage:  python3 novel/build/build_pdf.py [--toc-only] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Flowable)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../novel
REPO = os.path.dirname(ROOT)                                          # repo root
FONT_DIR = os.path.join(ROOT, "assets", "fonts")
CHAPTER_DIR = os.path.join(ROOT, "chapters")
BUILD_DIR = os.path.join(ROOT, "build")

BOOK_TITLE = "The Price of Mercy"
AUTHOR = "Ken Follett"
PLACE_LINE = "Warsaw · 1943"

PAGE_W, PAGE_H = 6 * inch, 9 * inch
MARGIN_X, MARGIN_TOP, MARGIN_BOT = 0.82 * inch, 0.80 * inch, 0.78 * inch
TEXT_W = PAGE_W - 2 * MARGIN_X
TEXT_H = PAGE_H - MARGIN_TOP - MARGIN_BOT

PARTS = [
    ("PART ONE", "The Net", 1, 8),
    ("PART TWO", "The Shortening Rope", 9, 18),
    ("PART THREE", "The Fire", 19, 25),
    ("CODA", "", 26, 26),
]

ROMAN = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
         "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
         "Eighteen", "Nineteen", "Twenty", "Twenty-One", "Twenty-Two", "Twenty-Three",
         "Twenty-Four", "Twenty-Five", "Epilogue"]


# ----------------------------------------------------------------------------- fonts
def register_fonts() -> None:
    files = {
        "Body": "DejaVuSerif.ttf",
        "Body-Italic": "DejaVuSerif-Italic.ttf",
        "Body-Bold": "DejaVuSerif-Bold.ttf",
        "Body-BoldItalic": "DejaVuSerif-BoldItalic.ttf",
        "Display": "DejaVuSerif-Bold.ttf",
    }
    for name, fname in files.items():
        path = os.path.join(FONT_DIR, fname)
        if not os.path.exists(path):
            raise SystemExit(f"missing font: {path}")
        pdfmetrics.registerFont(TTFont(name, path))
    pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold",
                                  italic="Body-Italic", boldItalic="Body-BoldItalic")


# ----------------------------------------------------------------------- text tools
def smart_quotes(text: str) -> str:
    out, open_double, open_single = [], True, True
    for ch in text:
        if ch == '"':
            out.append("\u201c" if open_double else "\u201d")
            open_double = not open_double
        elif ch == "'":
            out.append("\u2019")
        else:
            out.append(ch)
    return "".join(out)


def md_to_markup(text: str) -> str:
    """Markdown -> reportlab mini-HTML, then typographic quotes."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    return smart_quotes(text)


def plain_text(md: str) -> str:
    txt = re.sub(r"^#.*$", "", md, flags=re.M)
    txt = txt.replace("***", " ")
    txt = re.sub(r"\*\*(.+?)\*\*", r"\1", txt)
    txt = re.sub(r"\*(.+?)\*", r"\1", txt)
    return txt


def word_count(md: str) -> int:
    return len(re.findall(r"[^\s]+", plain_text(md)))


# ------------------------------------------------------------------------- structure
@dataclass
class Chapter:
    index: int
    number_line: str          # "Chapter One"
    title: str                # "The Net"
    dateline: str
    paragraphs: List[Tuple[str, str]] = field(default_factory=list)  # (kind, text)

    @property
    def head(self) -> str:
        return f"{self.number_line} · {self.title}" if self.title else self.number_line

    @property
    def running(self) -> str:
        return self.title.upper() if self.title else self.number_line.upper()


def parse_chapter(path: str) -> Chapter:
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()

    number_line, title = ("", "")
    dateline = ""
    paras: List[Tuple[str, str]] = []
    body_started = False

    for block in [b.strip() for b in raw.split("\n\n") if b.strip()]:
        if block.startswith("# "):
            head = block[2:].strip()
            if ":" in head:
                number_line, title = [p.strip() for p in head.split(":", 1)]
            else:
                number_line = head
            continue
        if not body_started and block.startswith("*") and block.endswith("*") and "\n" not in block:
            dateline = block.strip("*").strip()
            body_started = True
            continue
        body_started = True
        if block.strip() == "***":
            paras.append(("break", ""))
            continue
        text = " ".join(line.strip() for line in block.splitlines()).strip()
        paras.append(("para", md_to_markup(text)))

    return Chapter(index=0, number_line=number_line, title=title, dateline=dateline, paragraphs=paras)


def load_chapters() -> List[Chapter]:
    if not os.path.isdir(CHAPTER_DIR):
        raise SystemExit("no chapters directory")
    files = sorted(f for f in os.listdir(CHAPTER_DIR) if re.fullmatch(r"ch\d+\.md", f))
    chapters = []
    for f in files:
        ch = parse_chapter(os.path.join(CHAPTER_DIR, f))
        ch.index = int(re.search(r"\d+", f).group())
        chapters.append(ch)
    return chapters


def part_for(index: int) -> Tuple[str, str]:
    for label, name, lo, hi in PARTS:
        if lo <= index <= hi:
            return label, name
    return "", ""


# ----------------------------------------------------------------------------- styles
class Marker(Flowable):
    """Zero-size flowable that records the page on which it is drawn."""

    def __init__(self, key: str, sink: list):
        super().__init__()
        self.key, self.sink = key, sink

    def wrap(self, *args):
        return 0, 0

    def draw(self):
        self.sink.append((self.key, self.canv.getPageNumber()))


def styles() -> dict:
    s = {}
    s["chapter_num"] = ParagraphStyle("chapter_num", fontName="Body", fontSize=10.5, leading=14,
                                      alignment=TA_CENTER, textColor="#1a1a1a", spaceAfter=10)
    s["chapter_title"] = ParagraphStyle("chapter_title", fontName="Body-Italic", fontSize=19,
                                        leading=23, alignment=TA_CENTER, spaceAfter=8)
    s["dateline"] = ParagraphStyle("dateline", fontName="Body", fontSize=9, leading=13,
                                   alignment=TA_CENTER, textColor="#444444", spaceAfter=24)
    s["body"] = ParagraphStyle("body", fontName="Body", fontSize=10.3, leading=15.4,
                               alignment=TA_JUSTIFY, firstLineIndent=15, spaceAfter=0)
    s["body_first"] = ParagraphStyle("body_first", parent=s["body"], firstLineIndent=0)
    s["scene"] = ParagraphStyle("scene", fontName="Body", fontSize=10.5, leading=16,
                                alignment=TA_CENTER, spaceBefore=11, spaceAfter=11)
    s["part_label"] = ParagraphStyle("part_label", fontName="Body", fontSize=11, leading=15,
                                     alignment=TA_CENTER, spaceAfter=16)
    s["part_name"] = ParagraphStyle("part_name", fontName="Body-Italic", fontSize=26, leading=31,
                                    alignment=TA_CENTER)
    s["toc_head"] = ParagraphStyle("toc_head", fontName="Body", fontSize=12, leading=18,
                                   alignment=TA_CENTER, spaceAfter=22)
    s["toc_part"] = ParagraphStyle("toc_part", fontName="Body-Bold", fontSize=9.5, leading=14,
                                   alignment=TA_LEFT, spaceBefore=13, spaceAfter=5, textColor="#333333")
    s["toc_ch"] = ParagraphStyle("toc_ch", fontName="Body", fontSize=9.5, leading=13.6,
                                 alignment=TA_LEFT, leftIndent=14, firstLineIndent=-14)
    s["front_center"] = ParagraphStyle("front_center", fontName="Body", fontSize=10.5, leading=17,
                                       alignment=TA_CENTER)
    s["cover_title"] = ParagraphStyle("cover_title", fontName="Display", fontSize=31, leading=38,
                                      alignment=TA_CENTER)
    s["cover_sub"] = ParagraphStyle("cover_sub", fontName="Body-Italic", fontSize=13, leading=19,
                                    alignment=TA_CENTER)
    s["cover_author"] = ParagraphStyle("cover_author", fontName="Body", fontSize=14.5, leading=20,
                                       alignment=TA_CENTER)
    s["colophon"] = ParagraphStyle("colophon", fontName="Body", fontSize=8.6, leading=13.4,
                                   alignment=TA_JUSTIFY, textColor="#333333")
    return s


def rule(width: float, thickness: float = 0.6, color: str = "#333333") -> Flowable:
    class R(Flowable):
        def __init__(self):
            super().__init__()
            self._avail = width

        def wrap(self, aw, ah):
            self._avail = aw
            return width, thickness + 2

        def draw(self):
            x0 = max(0.0, (self._avail - width) / 2.0)
            self.canv.setStrokeColor(color)
            self.canv.setLineWidth(thickness)
            self.canv.line(x0, 1, x0 + width, 1)

    return R()


# --------------------------------------------------------------------------- template
class NovelDoc(BaseDocTemplate):
    def __init__(self, filename: str, chapter_titles: dict, **kw):
        super().__init__(filename, pagesize=(PAGE_W, PAGE_H), title=BOOK_TITLE,
                         author=AUTHOR, subject="A novel of Warsaw, 1943–1945",
                         creator="NovelWriter manuscript build", **kw)
        self.chapter_titles = chapter_titles      # page -> running head
        self.suppress_head = set()                # pages with no running head
        self.suppress_folio = set()               # pages with no folio

    def _decorate(self, canv, doc):
        page = canv.getPageNumber()
        canv.saveState()
        if page not in self.suppress_head:
            canv.setFont("Body", 7.6)
            canv.setFillColor("#555555")
            y = PAGE_H - 0.46 * inch
            head = self.chapter_titles.get(page, BOOK_TITLE.upper())
            if page % 2 == 0:      # verso
                canv.drawCentredString(PAGE_W / 2, y, BOOK_TITLE.upper())
            else:                  # recto
                canv.drawCentredString(PAGE_W / 2, y, head)
        if page not in self.suppress_folio:
            canv.setFont("Body", 8.6)
            canv.setFillColor("#333333")
            canv.drawCentredString(PAGE_W / 2, 0.47 * inch, str(page))
        canv.restoreState()

    def build_story(self, story):
        frame = Frame(MARGIN_X, MARGIN_BOT, TEXT_W, TEXT_H, id="main",
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        blank = Frame(0, 0, PAGE_W, PAGE_H, id="blank", leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate(id="plain", frames=[blank]),                       # cover / part pages
            PageTemplate(id="normal", frames=[frame], onPage=self._decorate),
        ])
        return self.build(story)


# ------------------------------------------------------------------------- frontmatter
def cover(st) -> list:
    return [
        Spacer(1, 1.55 * inch),
        Paragraph("THE PRICE<br/>OF MERCY", st["cover_title"]),
        Spacer(1, 0.22 * inch),
        rule(1.5 * inch),
        Spacer(1, 0.22 * inch),
        Paragraph("A Novel", st["cover_sub"]),
        Spacer(1, 2.35 * inch),
        Paragraph(AUTHOR, st["cover_author"]),
        Spacer(1, 0.10 * inch),
        Paragraph(PLACE_LINE, st["cover_sub"]),
    ]


def colophon(st) -> list:
    return [
        Spacer(1, 2.4 * inch),
        Paragraph(
            "<b>A note on this edition.</b> This manuscript was produced as a private reading "
            "edition, typeset from the working chapter files of the project <i>NovelWriter</i>. "
            "It is a pastiche written in the manner of Ken Follett; it is not a work by him, "
            "and it is neither authorised nor endorsed by him, his agents or his publishers.",
            st["colophon"]),
        Spacer(1, 12),
        Paragraph(
            "The book is a work of fiction. Some historical figures, offices, places and events of "
            "occupied Warsaw appear in the background in their historical roles; every principal "
            "character, and every action and conversation attributed to them, is invented. Where "
            "the historical record is uncertain the novel follows the record as far as it is known "
            "and invents only where fiction must.",
            st["colophon"]),
    ]


def contents(st, chapters: List[Chapter], pages: Optional[dict]) -> list:
    out = [Spacer(1, 0.55 * inch), Paragraph("CONTENTS", st["toc_head"])]
    current_part = None
    for ch in chapters:
        label, name = part_for(ch.index)
        if label and (label, name) != current_part:
            current_part = (label, name)
            head = f"{label} · {name.upper()}" if name else label
            out.append(Paragraph(head, st["toc_part"]))
        pg = "" if pages is None else str(pages.get(f"ch{ch.index}", ""))
        dots = " " + ("." * max(2, 62 - len(ch.head) - len(pg))) + " " if pg else ""
        title = f"{ch.head}{dots}"
        out.append(Paragraph(f"{title}&nbsp;&nbsp;{pg}" if pg else title, st["toc_ch"]))
    return out


def part_page(st, label: str, name: str) -> list:
    story = [Spacer(1, 3.1 * inch)]
    if name:
        story.append(Paragraph(f"{label}&nbsp;&nbsp;·&nbsp;&nbsp;{name.upper()}", st["part_label"]))
        story.append(SPACER_RULE := rule(1.1 * inch))
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph(name, st["part_name"]))
    else:
        story.append(Paragraph(label, st["part_label"]))
        story.append(rule(1.1 * inch))
    return story


# ------------------------------------------------------------------------------- build
def compute_decor(markers: list, chapters: List[Chapter]) -> dict:
    """From pass-1 page markers, work out running heads and what to suppress."""
    ordered = sorted(markers.items() if isinstance(markers, dict) else markers,
                     key=lambda kv: (kv[1], kv[0]))
    heads, suppress_head, suppress_folio = {}, set(), set()
    by_index = {ch.index: ch for ch in chapters}
    for i, (key, page) in enumerate(ordered):
        nxt = ordered[i + 1][1] if i + 1 < len(ordered) else 10 ** 6
        if key == "toc":
            for p in range(page, nxt):
                suppress_head.add(p)
                suppress_folio.add(p)
            continue
        if key.startswith("part"):
            suppress_head.add(page)
            suppress_folio.add(page)
            continue
        m = re.fullmatch(r"ch(\d+)", key)
        if m:
            ch = by_index.get(int(m.group(1)))
            head = (ch.running if ch else BOOK_TITLE.upper())
            for p in range(page, nxt):
                heads[p] = head
            suppress_head.add(page)          # no head on a chapter opener
    return {"heads": heads, "suppress_head": suppress_head, "suppress_folio": suppress_folio}


def build_pdf(out_path: str, chapters: List[Chapter], st: dict, toc_pages: Optional[dict],
              decor: Optional[dict] = None) -> dict:
    story = []
    markers: list = []

    # front matter
    story += cover(st)
    story.append(NextPageTemplate("plain"))
    story.append(PageBreak())
    story += colophon(st)
    story.append(PageBreak())
    story.append(NextPageTemplate("normal"))
    story.append(Marker("toc", markers))
    story += contents(st, chapters, toc_pages)
    story.append(PageBreak())

    chapter_titles: dict = {}
    pending_suppress: List[int] = []

    current_part = None
    for ch in chapters:
        label, name = part_for(ch.index)
        if label and (label, name) != current_part:
            current_part = (label, name)
            story.append(NextPageTemplate("plain"))
            story.append(Marker(f"part{len(markers)}{label}", markers))
            story += part_page(st, label, name)
            story.append(NextPageTemplate("normal"))
            story.append(PageBreak())

        story.append(Marker(f"ch{ch.index}", markers))
        chapter_titles  # filled after first pass
        story.append(Spacer(1, 0.30 * inch))
        num_line = "&nbsp;&nbsp;".join(ch.number_line.upper())
        story.append(Paragraph(num_line, st["chapter_num"]))
        if ch.title:
            story.append(Paragraph(ch.title, st["chapter_title"]))
        story.append(rule(1.15 * inch))
        story.append(Spacer(1, 0.16 * inch))
        if ch.dateline:
            story.append(Paragraph(f"<i>{ch.dateline}</i>", st["dateline"]))
        first = True
        for kind, text in ch.paragraphs:
            if kind == "break":
                story.append(Paragraph("·&nbsp;&nbsp;·&nbsp;&nbsp;·", st["scene"]))
                first = True
                continue
            story.append(Paragraph(text, st["body_first"] if first else st["body"]))
            first = False
        story.append(PageBreak())

    doc = NovelDoc(out_path, chapter_titles)
    if decor:
        doc.chapter_titles = decor["heads"]
        doc.suppress_head = decor["suppress_head"]
        doc.suppress_folio = decor["suppress_folio"]
    doc.build_story(story)
    return dict(markers)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "The_Price_of_Mercy.pdf"))
    args = ap.parse_args()

    register_fonts()
    st = styles()
    chapters = load_chapters()
    if not chapters:
        raise SystemExit("no chapter files found")

    # pass 1: page numbers for the contents, plus everything needed to decorate
    tmp = args.out + ".pass1"
    markers = build_pdf(tmp, chapters, st, None)
    decor = compute_decor(markers, chapters)
    # pass 2: real contents with page numbers and running heads
    markers = build_pdf(args.out, chapters, st, markers, decor)
    pages = markers
    if os.path.exists(tmp):
        os.remove(tmp)

    counts = []
    total = 0
    for ch in chapters:
        path = os.path.join(CHAPTER_DIR, f"ch{ch.index:02d}.md")
        with open(path, encoding="utf-8") as fh:
            wc = word_count(fh.read())
        total += wc
        counts.append((ch.index, ch.head, wc))
        print(f"  ch{ch.index:02d}  {ch.head:<34} {wc:>6,} words   p.{pages.get(f'ch{ch.index}','?')}")
    print(f"  {'TOTAL':<40} {total:>6,} words")
    print(f"  PDF: {args.out}")

    os.makedirs(BUILD_DIR, exist_ok=True)
    with open(os.path.join(BUILD_DIR, "word_counts.json"), "w", encoding="utf-8") as fh:
        json.dump({"chapters": [{"chapter": i, "title": t, "words": w} for i, t, w in counts],
                   "total": total}, fh, indent=2, ensure_ascii=False)
    with open(os.path.join(BUILD_DIR, "word_counts.md"), "w", encoding="utf-8") as fh:
        fh.write("| # | Chapter | Words |\n|---|---------|-------|\n")
        for i, t, w in counts:
            fh.write(f"| {i} | {t} | {w:,} |\n")
        fh.write(f"| | **Total** | **{total:,}** |\n")


if __name__ == "__main__":
    main()
