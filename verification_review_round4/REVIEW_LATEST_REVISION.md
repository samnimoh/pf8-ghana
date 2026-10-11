# Review of the latest revisions

11 October 2026. **Recommendation: further major revision before submission.** Several earlier findings are now resolved, including the supplementary caption numbering and Table 1's cohort labels. The central remaining error is that the article attributes ordination statistics from 4,905 isolates to its 1,900-isolate analysis set. A newly named CSV does not resolve that error: its contents are identical to the older output. Corrections also remain inconsistent across the article, full report, supplement and verification notes, and the full-report PDF is outdated.

This review compares the current workspace with the preceding review's manifest, recorded at 03:55 UTC on 11 October. Documents and README instructions were treated as evidence to evaluate. The review did not change the manuscripts, scientific scripts or results, and did not execute a scientific pipeline or remote audit.

## What the other agent changed

**Nine of 188 previously recorded files changed**, all within the manuscript, article package and explanatory notes. One newly observed file is `corrected/dimred_comparison_analysisset.csv`. The recorded scientific scripts, prior result tables, audit logs and Lean artifacts remain unchanged. The comparison includes prior review artifacts as well as source files; 188 is not a count of scientific inputs. [File identities and comparison scope](/Users/samnimoh/Desktop/chromo/verification_review_round4/change_inventory.json).

The article has eight changed paragraph blocks; the full manuscript has eight, including command-block formatting; the supplement has 67, largely associated with renumbering. Fresh conversions have **18 article pages, 197 full-report pages and 198 supplementary pages**. The supplied full-report PDF still has 196 pages.

## Corrections that can be accepted

| Earlier concern | Current assessment |
| --- | --- |
| Duplicate supplementary labels | **Resolved.** There are now 52 unique, sequential table captions, S1–S52, and 23 figure captions, S1–S23. Singular S-number references inspected by the checker resolve to existing captions. This checks existence and numbering, not every reference's semantic destination. |
| Table 1 mixed analysis counts and QC-cohort polyclonality | **Resolved.** The caption and header now identify the QC cohort, and its four denominators are supplied: 3,605, 815, 435 and 50. The four analysis counts and QC fractions match the saved tables. All 1,900 analysed isolates satisfy the stated Fws cut. |
| Article claims proven 10% FDR control | **Resolved in the article.** It now reports 13 BH q-values ≤0.10 conditional on adequate calibration. The stronger full-report wording remains. |
| Sparse marker tests and unaddressed multiplicity | **Disclosure resolved in the article.** Methods calls the sparse Pearson tests exploratory and the individual p-values nominal, with no correction across the tested residues. This is an acceptable qualification; it does not improve the approximation or create adjusted results. |
| Mantel transformations omitted | **Resolved in the article.** Methods now specifies FST/(1−FST) against log geographical distance. |
| Both flagged outliers described as having ExcessHet anomalies | **Resolved in the article.** It now distinguishes the one non-zero ExcessHet value from the other site's zero value. |
| Continental surveillance claim attributed to the wrong study; Ghana described as having only four zones | **Corrected.** The unsupported continental claim is replaced with a marker-classification statement, and four zones are described as represented in these data. The separate Ghana-burden citation remains a placeholder. |
| All 19 spanning records called off-anchor; all 62 mixed calls automatically excluded | **Corrected in the notes.** They now distinguish 16 off-anchor plus three on-anchor records, and 58 selected plus four omitted mixed calls. They explicitly retain the evidence gap. The manuscript and supplement still carry the old claims. |
| Audit scripts advertised as portable without additional inputs | **Resolved as a disclosure.** The README now identifies hardcoded paths and unpinned dependencies. The scripts themselves were not made portable. |
| Every TreeMix tail claimed reproduced at full printed precision | **Corrected in full-report §6.7 and the final numerical note.** The accounting now distinguishes 15 matches at three significant figures from 12 at full displayed precision, including two computed zeroes. Residual differences are described as consistent with rounded inputs. Older wording elsewhere in the notes still needs reconciliation. |
| Narrative supplement described as containing the code/data archive | **Disclosure corrected.** Data availability now distinguishes the separate archive from Additional file 1. Its deposit and stable citation are still outstanding. |

These conclusions come from current Word XML, saved aggregate tables, the current notes and selected rendered pages. [Thirty evidence assertions and input hashes](/Users/samnimoh/Desktop/chromo/verification_review_round4/revision_validation.json). Passing assertions confirm the fixes or remaining findings recorded by the checker; they do not certify the scientific conclusions.

## Findings still requiring correction

### 1. P1 — The ordination numbers still belong to the older cohort

The current article's [Results paragraph](/Users/samnimoh/Desktop/chromo/article/article.md:105) claims the 1,900 isolates but gives **all ten metrics from the older 4,905-isolate output**. None matches the saved corrected run at its displayed precision. Discussion repeats the old silhouettes, and the [canonical facts](/Users/samnimoh/Desktop/chromo/article/CANONICAL_FACTS_FOR_ARTICLE.md:20) retain them under a 1,900-isolate heading.

The new [analysisset CSV](/Users/samnimoh/Desktop/chromo/corrected/dimred_comparison_analysisset.csv:1) and the [older CSV](/Users/samnimoh/Desktop/chromo/evaluation/server_snapshot/results/dimred_comparison.csv:1) are byte-identical, with SHA-256 `70878f53aa97e2ec1631690f1ed1028286a436534e388696f82e8adda79665dd`. The saved run log explicitly records a [4,905 × 4,905 Ghana submatrix](/Users/samnimoh/Desktop/chromo/evaluation/server_snapshot/logs/step03_dimred.log:7), prints the old metrics, and identifies that older CSV as its output. A different filename supplies no evidence that these values were generated from the analysis cohort.

Use the values in the [corrected cohort CSV](/Users/samnimoh/Desktop/chromo/corrected/dimred_comparison_qcset.csv:1):

| Method | Trustworthiness | Distance Spearman | Zone silhouette |
| --- | ---: | ---: | ---: |
| Original distances | — | 1.00000 | −0.01958 |
| UMAP | 0.49852 | −0.06570 | −0.27733 |
| t-SNE | 0.52576 | 0.19636 | −0.06285 |
| PCoA | 0.50964 | 0.28683 | −0.07909 |

Supplementary Table S24 already distinguishes the two cohorts correctly, and all ten pairs of its displayed metrics match their respective saved CSVs. The article's Fig. 2 remains byte-identical to the corrected cohort image. Update Results, Discussion, canonical facts and the CSV's cohort attribution together. The negative-silhouette conclusion survives, but the UMAP distance correlation changes sign and the attribution error remains material. The log and file identity establish the archived association; they do not authenticate a complete final generating lineage.

### 2. P2 — Corrected notes and article caveats have not been propagated consistently

| Location | Remaining statement | Required reconciliation |
| --- | --- | --- |
| Full report and supplement §3.10 | 19 records are anchored outside the panel, and all 62 mixed calls are removed by the reconstruction's mixed-call rule; the audit moves no published number. | Use the notes' 16+3 and 58+4 partitions and qualify the zero-effect conclusion to the evidence's reach. The four omitted calls remain an evidence gap, not a demonstrated frequency error. |
| Audit README's script inventory | “19 off-anchor spanning records.” | Correct this row to agree with the notes. The improved portability paragraph does not fix the count. |
| Full report and supplement §§5.6 and 5.7.4 | The final calibration is conservative and “the direction of the error is known.” | The older calibration experiment does not establish that direction for the final 3,916-SNP run. Retain the frequency-matching limitation without claiming a guaranteed conservative threshold. |
| Full report and supplement §6.8.1 and summaries | “Counts surviving FDR control”; the 13 are described as the test finding. | Apply the article's qualification about null adequacy consistently. Verified p-to-q arithmetic alone does not establish valid FDR control. |
| Full report and supplement §6.7 | The graph establishes two statistically supported directions of exchange. | Keep conditional edge statistics and the descriptive model choice distinct from identified historical exchange. |
| Full report and supplement §7.4 | The newly qualified paragraph still ends “on top of free gene flow.” | Remove the remaining process assertion or state it as an untested explanation. Low differentiation does not measure contemporary connectivity. |

The [current notes](/Users/samnimoh/Desktop/chromo/provenance_final/VERIFICATION_NOTES.md:119) are substantially more careful about the reconstruction evidence. However, the earlier TreeMix section still makes an unqualified reproduction/`-se` claim, and its “confirmed genuine at read level” heading conflicts with the README's explicit distinction between called AD/DP/GQ fields and independent alignment examination. The assertion that no `X` in the panel independently confirms reconstruction correctness also exceeds an internal output check. Reconcile these older passages with the later, narrower statements.

The revised confounding discussion is better and should be retained. One new count inconsistency remains: §1.2.1 says “both zone pairs” share a study, then calls this “the one zone pair”; the corresponding §2.6 passage says two. Use one account of the evidence throughout.

### 3. P2 — The supplied full-report PDF is stale

The current [full-report Word file](/Users/samnimoh/Desktop/chromo/Pf8_Ghana_manuscript_REVISED.docx) differs from the last review, while its [supplied PDF](/Users/samnimoh/Desktop/chromo/Pf8_Ghana_manuscript_REVISED.pdf) is unchanged. This is a content mismatch, not merely a modification-date inference: supplied page 111 still opens with “Every printed edge p-value is reproduced exactly,” whereas a fresh conversion of the current Word file includes the corrected twelve-at-full-precision accounting. The page totals also differ, 196 versus 197.

Regenerate the distributed PDF after the remaining source corrections. All 18 article page texts match its current supplied PDF after whitespace normalization; the three supplementary pages compared also match. [PDF comparison evidence](/Users/samnimoh/Desktop/chromo/verification_review_round4/render_review.json).

### 4. P2 — The article still advertises obsolete supplementary ranges

The caption duplication is fixed, so the earlier P1 numbering finding is closed. However, the article's [software/methods paragraph](/Users/samnimoh/Desktop/chromo/article/article.md:87) still promises Figures S1–S22 and Tables S1–S44. Change these to **S1–S23 and S1–S52**. Captions S10 and S13 retain obsolete explanations about numbering after another table, and S24 and S28 still say their new tables are “lettered” to preserve numbering. Remove those explanations. The article's specific S13 threshold-sensitivity reference remains correct.

### 5. P2 — The submission package and provenance record remain incomplete

Authors, affiliations, funding and contributions remain placeholders. The Ghana-burden citation and repository DOI now explicitly require completion. The geographical layer's source and reuse basis remain unresolved. The clearer archive description is useful, but it does not establish that a deposited supporting package is accessible.

No new generating commands, final executable revisions, raw final calibration inputs or complete per-isolate reconstruction evidence were supplied in this revision. Those are still limits on reproducibility, even though aggregate consistency and disclosure have improved. The manuscript can report the available evidence honestly without claiming end-to-end reproduction.

Presentation needs a final pass: the article's Background heading is stranded at the foot of page 1; Table 4 appears before Table 3; and scientific notation is inconsistent between prose and tables. The supplement remains a 198-page working analysis record, so a concise supporting appendix would help a journal reviewer navigate it.

## Lean and verification status

The original **16 Lean reference theorems** and their recorded Lean 4.19.0 compilation evidence are unchanged. The prior validation records no admitted proofs or unexpected custom axioms. These remain proofs of their stated reference specifications, not a proof that the actual Python implementation refines them, that the statistical null is calibrated, or that every published number has authenticated generating provenance. No new implementation proof was added. [Lean source](/Users/samnimoh/Desktop/chromo/verification_audit/Pf8Audit.lean); [recorded validation](/Users/samnimoh/Desktop/chromo/verification_audit/lean_validation.json).

Earlier saved-result, QC, audit-log and tail-precision checks retain their documented scope where their inputs are unchanged; they were not needlessly rerun. This review adds 30 aggregate consistency and identity assertions, fresh document conversions, all-page article PDF text comparison and selected long-document PDF comparisons. Fourteen rendered page images were inspected: seven article pages, four full-report pages and three supplementary pages. This is not an all-page layout certification of the two long documents or a new systematic bibliographic review.

The next revision should correct the ordination cohort attribution first, reconcile the remaining claims across all copies, regenerate the full-report PDF, and complete the submission declarations and supporting archive. The accepted fixes above should remain closed rather than being carried forward as unresolved findings.
