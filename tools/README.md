# Build and editing tools

Everything needed to regenerate the deliverables. See the `/pf8-rebuild` skill for the workflow.

| Script | Does |
|---|---|
| `build_article.py` | `article/article.md` → `article/Pf8_Ghana_article.docx`. Holds the four tables, the three figure placements and the reference list; the markdown carries only `[[FIG1]]`/`[[TABLE1]]` placeholders. Converts `*italic*`, `**bold**` and `F~ST~` subscripts. |
| `make_supplement.py` | Run from inside an unzipped copy of `Pf8_Ghana_manuscript_REVISED.docx`. Renumbers every caption **by occurrence** to Figure S1–S23 / Table S1–S52, binds each cross-reference to the nearest caption carrying its original label, retitles and inserts the preamble. Asserts contiguous, duplicate-free numbering and aborts otherwise. |
| `apply_edits.py` | Applies a JSON list of `{quote, repl}` edits to `word/document.xml`, resolving quotes that span runs. Reports anything it cannot locate and never writes a partial result. Iterate it until the leftover list is empty. |

## Usage

```bash
# article  (ARTICLE_TEMPLATE = an unzipped .docx supplying styles/theme/fonts/figure media)
mkdir -p /tmp/pf8build/supp && cd /tmp/pf8build/supp && unzip -o -q $R/article/Additional_file_1.docx
cd /tmp/pf8build
ARTICLE_TEMPLATE=/tmp/pf8build/supp ARTICLE_MD=$R/article/article.md \
ARTICLE_DOCX=$R/article/Pf8_Ghana_article.docx python3 -I $R/tools/build_article.py

# supplement
mkdir -p /tmp/supp && cd /tmp/supp && unzip -q <repo>/Pf8_Ghana_manuscript_REVISED.docx
python3 -I <repo>/tools/make_supplement.py
zip -q -r -X <repo>/article/Additional_file_1.docx '[Content_Types].xml' _rels word docProps
```

`build_article.py` takes its OOXML skeleton from `$ARTICLE_TEMPLATE` (default: a directory named
`supp` beside the working directory). Both scripts are tested to run from a clean directory.

## Two invariants these encode

- **Renumber by caption occurrence, not by distinct label.** The source manuscript uses six table
  labels twice for different tables; renumbering by label silently propagates the ambiguity.
- **Assert occurrence counts on every substitution and write only at the end**, so an aborted run
  leaves the document untouched.
