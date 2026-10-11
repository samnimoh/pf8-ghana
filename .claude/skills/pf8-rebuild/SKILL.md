---
name: pf8-rebuild
description: Rebuild the Pf8 Ghana article, the supplement and all PDFs from source after any edit. Use whenever article.md or the working manuscript changes, so no deliverable is left stale.
---

# Rebuilding the deliverables

Three artefacts must stay in sync. A PDF older than its DOCX has been flagged by review.

```
article/article.md                  --build_article.py-->  article/Pf8_Ghana_article.docx
Pf8_Ghana_manuscript_REVISED.docx   --make_supp3.py----->  article/Additional_file_1.docx
                                    --LibreOffice------->  all three PDFs
```

## 1. Article

Source is `article/article.md`. Tables, figures and the reference list live in the assembler, not in
the markdown; the markdown carries `[[FIG1]]`, `[[TABLE1]]` … placeholders.

```bash
R=/Users/samnimoh/Desktop/chromo            # repo root
mkdir -p /tmp/pf8build/supp && cd /tmp/pf8build/supp
unzip -o -q $R/article/Additional_file_1.docx          # supplies styles, theme, fonts, figure media
cd /tmp/pf8build
ARTICLE_TEMPLATE=/tmp/pf8build/supp \
ARTICLE_MD=$R/article/article.md \
ARTICLE_DOCX=$R/article/Pf8_Ghana_article.docx \
python3 -I $R/tools/build_article.py
```

Markup convention in the markdown: `*italic*`, `**bold**`, and `F~ST~` / `F~ws~` for subscripts.
Never write HTML tags or bare `FST` — the assembler converts the tilde form and nothing else.

## 2. Supplement

Generated from the working manuscript, so **fix the manuscript, then regenerate** — never edit the
supplement directly or the two diverge.

```bash
R=/Users/samnimoh/Desktop/chromo
rm -rf /tmp/pf8supp && mkdir -p /tmp/pf8supp && cd /tmp/pf8supp
unzip -o -q $R/Pf8_Ghana_manuscript_REVISED.docx
python3 -I $R/tools/make_supplement.py
zip -q -r -X $R/article/Additional_file_1.docx '[Content_Types].xml' _rels word docProps
```

It renumbers every caption **by occurrence** (Figure S1–S23, Table S1–S52), binds each
cross-reference to the nearest caption carrying its original label, retitles, and inserts the
preamble. It asserts that the numbering is contiguous and duplicate-free and aborts otherwise.

The source manuscript has six table labels each used twice for different tables; renumbering by
*distinct label* propagates that and is wrong. Renumber by occurrence.

## 3. PDFs — regenerate all three, every time

```bash
/Applications/LibreOffice.app/Contents/MacOS/soffice --headless --convert-to pdf --outdir . \
  Pf8_Ghana_article.docx Additional_file_1.docx Pf8_Ghana_manuscript_REVISED.docx
```

Expected: **18 / 198 / 197** pages.

## 4. Verify before shipping

```bash
# literal markup that should never survive
python3 -I -c "
import re,zipfile,html,sys
for f in sys.argv[1:]:
    x=zipfile.ZipFile(f).read('word/document.xml').decode()
    t=''.join(html.unescape(m.group(1)) for m in re.finditer(r'<w:t[^>]*>(.*?)</w:t>',x,re.S))
    print(f, 'markup:', len(re.findall(r'~[A-Za-z]{1,3}~|</?su[bp]>|\*\*', t)))
" article/*.docx
```

Then sweep the forbidden-claims list in `CLAUDE.md`, confirm the article's supplementary ranges
still read S1–S23 and S1–S52, and check that any `Table S<n>` the article cites exists.

## 5. Commit

```bash
git add -A && git commit -m "<what changed and why>"
```

Never leave a rebuilt deliverable uncommitted — stale and mislabelled files are this project's
most frequent failure.

All three scripts live in **`tools/`** and are tested to run from a clean directory;
`tools/README.md` documents them.
