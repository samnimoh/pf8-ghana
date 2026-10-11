# Build and editing tools

Everything needed to regenerate the deliverables. See the `/pf8-rebuild` skill for the workflow.

| Script | Does |
|---|---|
| `build_article.py` | `article/article.md` → `article/Pf8_Ghana_article.docx`. Holds the four tables, the three figure placements and the reference list; the markdown carries only `[[FIG1]]`/`[[TABLE1]]` placeholders. Converts `*italic*`, `**bold**` and `F~ST~` subscripts. |
| `make_supplement.py` | Run from inside an unzipped copy of `Pf8_Ghana_manuscript_REVISED.docx`. Renumbers every caption **by occurrence** to Figure S1–S23 / Table S1–S52, binds each cross-reference to the nearest caption carrying its original label, retitles and inserts the preamble. Asserts contiguous, duplicate-free numbering and aborts otherwise. |
| `apply_edits.py` | Applies a JSON list of edits to `word/document.xml`, resolving quotes that span runs. Each edit needs only `{quote, repl}`; `concept`, `sev` and `occurrence` are optional. A quote must be **unique** unless the edit gives `"occurrence": <1-based int>` — a non-unique quote is reported as ambiguous and nothing is written. It **refuses to write at all** if any edit is unlocated or ambiguous (override with `ALLOW_PARTIAL=1`). Edits that collide on the same run are deferred, not dropped: re-run with `LEFTOVER=` until the leftover list is empty. |

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

## Safety properties, and the tests that hold them

These were added after a review demonstrated each failure on synthetic input:

- **`build_article.py` never destroys its destination.** It builds to `<target>.tmp-build`, fsyncs,
  runs `testzip()`, then `os.replace()`s atomically. An injected mid-archive `IOError` leaves the
  existing deliverable byte-identical and removes the temp file.
- **`build_article.py` is self-contained.** The APA reference list is vendored at
  `tools/references_apa.txt` (override with `ARTICLE_REFS`), and every input is existence-checked
  with a named error before any work starts. It previously pointed at a session scratch directory
  and could not run anywhere else.
- **`apply_edits.py` never writes a partial result.** A list containing one good and one unmatched
  edit exits non-zero and leaves the document byte-identical.
- **`apply_edits.py` never silently half-edits a repeated passage.** A quote matching twice is
  refused, with the match count, until an `occurrence` is named.
