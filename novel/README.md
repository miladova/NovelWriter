# The Price of Mercy — manuscript

A historical novel in 25 chapters and an epilogue, written as an exercise in the manner of
Ken Follett. **It is a pastiche: not a work by Ken Follett, and neither authorised nor endorsed
by him, his agents or his publishers.** This note, and the colophon inside the PDF, say so.

## What is in here

| Path | What it is |
|---|---|
| `The_Price_of_Mercy.pdf` | The assembled book — read this. 6×9in trade layout: title page, note on the edition, contents, part pages, chapter openers, running heads. |
| `chapters/ch01.md … ch25.md`, `chapters/epilogue.md` | The source chapters, one Markdown file per unit. |
| `notes/00-story-bible.md` | Private working notes: cast, rules of the book, continuity ledger. Contains plot detail. |
| `notes/01-outline.md` | The 26-unit outline each chapter is written against. |
| `build/build_pdf.py` | Typesetting pipeline (ReportLab). |
| `build/word_counts.md` | Per-chapter word counts, regenerated on every build. |

## Rebuilding the PDF

```bash
pip install --user --break-system-packages reportlab
python3 novel/build/build_pdf.py            # writes novel/The_Price_of_Mercy.pdf
```

The script needs the DejaVuSerif family (regular, bold, italic, bold-italic) in
`novel/assets/fonts/`. Those TTFs are not committed; fetch them with:

```bash
pip download --no-deps matplotlib -d /tmp/mpl
python3 - <<'EOF'
import glob, zipfile, os, shutil
wheel = glob.glob('/tmp/mpl/*.whl')[0]
dest = 'novel/assets/fonts'
os.makedirs(dest, exist_ok=True)
with zipfile.ZipFile(wheel) as z:
    for name in z.namelist():
        if '/fonts/ttf/DejaVuSerif' in name:
            with z.open(name) as src, open(os.path.join(dest, os.path.basename(name)), 'wb') as out:
                shutil.copyfileobj(src, out)
EOF
```

## Status

Work in progress. `build/word_counts.md` gives the current tallies; the contents page of the PDF
lists every unit that is already assembled into the book.
