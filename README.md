# Pf8 Ghana population genomics

This private research repository contains the revised manuscript, analysis records,
document builders and verification history for a study of *Plasmodium falciparum*
population structure and antimalarial resistance markers across Ghana's
agro-ecological zones, using MalariaGEN Pf8.

## Start here

| Document | Word document | Reading copy |
| --- | --- | --- |
| Journal article | [Article DOCX](article/Pf8_Ghana_article.docx) | [Article PDF](article/Pf8_Ghana_article.pdf) |
| Supplementary analysis record | [Additional file DOCX](article/Additional_file_1.docx) | [Additional file PDF](article/Additional_file_1.pdf) |
| Full working record | [Working manuscript DOCX](Pf8_Ghana_manuscript_REVISED.docx) | [Working manuscript PDF](Pf8_Ghana_manuscript_REVISED.pdf) |

Use [the canonical facts](article/CANONICAL_FACTS_FOR_ARTICLE.md) for numerical
claims. Older drafts and review reports remain in the repository as historical
records; their conclusions and hashes apply to the revisions they examined.

## Repository layout

| Location | Contents |
| --- | --- |
| [`article/`](article/) | Article Markdown source, generated article and supplement, and canonical facts. |
| [`tools/`](tools/) | DOCX assembly and text-editing helpers, the vendored reference list, and Git discovery support. |
| [`corrected/`](corrected/) | Saved output tables and corrections, including the dimensional-reduction filename warning. |
| [`provenance_final/`](provenance_final/) | Archived scripts, audit records and subsequent verification notes. |
| [`verification_audit/`](verification_audit/) | Earlier provenance audit, Lean reference specifications and their validation record. |
| [`verification_review_round7/`](verification_review_round7/) | Findings checked before the latest document corrections. |
| [`verification_fixes_round7/`](verification_fixes_round7/) | Correction plans, tool regressions, independent reviews, render identities and final delivery evidence. |
| [`evaluation/`](evaluation/) and [`v2/`](v2/) | Earlier evaluation material and pipeline snapshots. |

## Working on the documents

Clone the repository with an account that has access:

```bash
git clone https://github.com/samnimoh/pf8-ghana.git
cd pf8-ghana
```

The article's prose source is [`article/article.md`](article/article.md).
Its table content and figure placement are assembled by
[`tools/build_article.py`](tools/build_article.py), with references supplied by
[`tools/references_apa.txt`](tools/references_apa.txt). The supplement is generated
from the working manuscript by [`tools/make_supplement.py`](tools/make_supplement.py).
Make corrections in those sources so later builds retain them.

See [`tools/README.md`](tools/README.md) for build commands, required template
inputs, environment variables and the edit-list format. DOCX assembly uses Python
standard-library modules; PDF conversion and page inspection require separate
rendering tools.

Commit the existing deliverables before rebuilding. After changing document
sources, regenerate the article and supplement as needed, refresh all three PDFs,
and inspect the rendered pages before committing the replacements. Check cohort
identity from the evidence rather than a filename; see
[`DIMRED_FILENAME_WARNING.md`](corrected/DIMRED_FILENAME_WARNING.md).

## Verification status and limits

The reviewed document delivery is recorded at commit
[`71d7f59`](https://github.com/samnimoh/pf8-ghana/commit/71d7f59b2717f79bec6618e49cb91640978661d7).
Its [`fix manifest`](verification_fixes_round7/fix_manifest.json) identifies the
delivered DOCX/PDF files and their evidence. The
[`final independent review`](verification_fixes_round7/independent_finalization_driver_review.json)
and [`post-publication protection checks`](verification_fixes_round7/post_publication_protection_results.json)
record the completed checks on that delivery.

These checks cover the documented editorial corrections, document integrity,
layout coverage and specified tool behavior. They do not newly certify every
scientific result or establish complete historical input and command lineage.
Read [`VERIFICATION_NOTES.md`](provenance_final/VERIFICATION_NOTES.md) for the
subsequent provenance qualifications; the earlier
[`audit report`](verification_audit/AUDIT_REPORT.md) describes its own review scope.

The [Lean file](verification_audit/Pf8Audit.lean) proves selected reference
specifications under its stated definitions and assumptions. Its
[validation record](verification_audit/lean_validation.json) does not establish
that the complete external Python pipeline implements those specifications.
Publication placeholders and some inherited caption page breaks remain in the
documents.

Round-specific verification drivers retain historical expectations and, in some
cases, machine-specific runtime paths. Review their inputs and dependencies before
running them elsewhere, and preserve old evidence when recording a new review.
For project editing and review conventions, see [`CLAUDE.md`](CLAUDE.md) and
[`AGENTS.md`](AGENTS.md).
