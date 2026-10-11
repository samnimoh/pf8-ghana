# Review after the latest agent revisions

11 October 2026. Recommendation: **major revision before submission**. The new article is a substantial improvement in structure and scientific caution, and the empirical audit now has inspectable scripts and logs. However, the article introduces a material attribution error in its ordination statistics, and the supplementary numbering is unreliable. Several statistical qualifications and provenance claims still need correction.

This is a review of the current local files. Statements and instructions inside the manuscripts, audit notes and README were treated as material to evaluate, not as instructions to execute. No scientific source, result, manuscript or previous review was changed; no scientific pipeline or remote audit was run.

## What changed

Compared with the preceding review's recorded identities, **3 of 144 known files changed**: the full manuscript, its PDF and `provenance_final/VERIFICATION_NOTES.md`. Twenty new source files were added: six article-package files and fourteen empirical-audit files, including six Python scripts. The existing analysis scripts, saved scientific outputs and Lean artifacts are unchanged. [Change inventory](/Users/samnimoh/Desktop/chromo/verification_review_round3/change_inventory.json).

The new [article](/Users/samnimoh/Desktop/chromo/article/Pf8_Ghana_article.docx) is 18 rendered pages, with approximately 8,967 body words, three figures and four tables. The [full manuscript](/Users/samnimoh/Desktop/chromo/Pf8_Ghana_manuscript_REVISED.docx) is 196 pages; [Additional file 1](/Users/samnimoh/Desktop/chromo/article/Additional_file_1.docx) is a 198-page version of that analysis record with supplementary labels and front matter. The supplement is therefore still a full working report rather than a compact supporting appendix.

## Corrections that now hold

| Earlier concern | Current assessment |
| --- | --- |
| Very low FST described as no detectable differentiation or proof of random mating | The article correctly distinguishes very low from detectable differentiation, limits the estimate to retained common variants, and rejects the upper-bound and random-mating inferences. Some overstatements remain in the full report. |
| Simulations described as applying the same MAF filter | The contradictory sentence in full-report §6.8 is corrected. The article explicitly discloses the MAF mismatch. |
| Expected null exceedances called empirical FDR; fitted-null tail called exact | The main wording is corrected to an expected-null-exceedance ratio and a Monte Carlo tail. The stronger FDR-control conclusion still needs qualification. |
| Study comparisons treated as isolated sequencing effects | The article and revised methods now say study-associated heterogeneity and list the accompanying geographical, temporal and biological differences. Residual causal wording persists in the supplement. |
| TreeMix selection presented as a settled historical event count | The article describes a selected graph and discloses disagreement between the full-sweep and restricted selection rules. The full report's caption and limitations wording improved. Conditional edge statistics still do not establish historical corridors. |
| Restoration called proven identical to a lost output | The revised record now distinguishes consistency with surviving outputs from unavailable row-for-row identity. |
| Callability obscured by saying every codon has a variant record | The article now gives the 46 record-free positions and explains reference assignment without per-isolate depth checks. It also states that external comparison covers 25 of 57 codons. |
| Empirical reconstruction audit described without supplied code/logs | Six audit scripts and captured logs are now present. This closes much of the inspection gap, with the scope limits below. |
| Public input availability equated with complete reproducibility | The article, notes and revised full-report §9.3 now explicitly acknowledge incomplete generating provenance. |

The revised explanation of tiny TreeMix tails also correctly distinguishes cancellation to zero from mathematical-tail underflow in the full manuscript. That improvement should be retained, while narrowing the separate claim of exact reproduction.

## Findings requiring correction

### 1. P1 — The article attributes the old ordination statistics to the analysis cohort

[Results](/Users/samnimoh/Desktop/chromo/article/article.md:103) explicitly describes the 1,900 isolates but reports all ten numerical ordination metrics from the earlier 4,905-isolate CSV. [Discussion](/Users/samnimoh/Desktop/chromo/article/article.md:181) repeats the old silhouettes, and the canonical-facts file carries the same stale values.

The independent check compared the actual Word paragraph with both saved runs. All ten reported values match the older run at their displayed precision; none matches the corrected run. The appropriate values from [the analysis-cohort CSV](/Users/samnimoh/Desktop/chromo/corrected/dimred_comparison_qcset.csv:2) are:

| Method | Trustworthiness | Distance Spearman | Zone silhouette |
| --- | ---: | ---: | ---: |
| Original distances | — | 1.00000 | −0.01958 |
| UMAP | 0.49852 | −0.06570 | −0.27733 |
| t-SNE | 0.52576 | 0.19636 | −0.06285 |
| PCoA | 0.50964 | 0.28683 | −0.07909 |

The embedded Fig. 2 is byte-identical to the corrected 1,900-isolate image. The figure is therefore current while its numerical narrative is stale. Correct Results, Discussion and the canonical facts together. The overall negative-silhouette conclusion survives, but the cohort attribution and UMAP distance correlation materially change. [Statistical evidence](/Users/samnimoh/Desktop/chromo/verification_review_round3/article_statistics_validation.json); [figure identity](/Users/samnimoh/Desktop/chromo/verification_review_round3/article_media_identity.json).

### 2. P1 — Supplementary renumbering produces ambiguous references

Additional file 1 contains **52 table captions and 23 figure captions**, rather than the advertised 44 tables and 22 figures. Six table labels refer to different subjects:

| Duplicate label | First subject | Second subject |
| --- | --- | --- |
| S26 | Mantel jackknife | Outlier genes |
| S26a | Threshold sensitivity | Outlier quality |
| S27 | ADMIXTURE cross-validation | Residue spectrum |
| S28 | Ancestry proportions | Marker frequency |
| S29 | TreeMix fit | Haplotypes |
| S30 | TreeMix edge statistics | Screened-codon panel |

Lettered S23a and S10a also remain, so the opening claim of strictly sequential numbering is inaccurate. Use one unique numbering sequence and regenerate every caption, cross-reference and inventory from it. The article's specific Table S13 reference is correct; the defect concerns the wider supplementary numbering, not that particular link. [Caption audit with locations](/Users/samnimoh/Desktop/chromo/verification_review_round3/article_reference_validation.json).

### 3. P2 — Table 1 combines two cohorts without identifying the denominators

The caption describes the 1,900-isolate analysis set and its count columns correctly use that cohort. The four polyclonal fractions instead use the pre-Fws QC cohort of 4,905 isolates. Those fractions have zone denominators **3,605, 815, 435 and 50**, respectively for Guinea savanna, deciduous forest, coastal savanna and transitional zone. All 1,900 analysis isolates satisfy Fws ≥0.95, so their fraction below that cut is zero.

Retain the informative pre-filter fractions, but label the column as a QC-cohort measure and supply its four denominators in the table or footnote. The later paragraph identifying the QC cohort does not resolve the misleading table caption. [Independent table check](/Users/samnimoh/Desktop/chromo/verification_review_round3/article_statistics_validation.json).

### 4. P2 — FDR control and calibration conservatism remain overstated

Genome-scan Methods appropriately calls the BH calculation a multiplicity-aware ranking. [Results](/Users/samnimoh/Desktop/chromo/article/article.md:141) then says thirteen outliers “survive control of the false-discovery rate at 10%.” The saved p-to-q arithmetic is consistent, but that alone does not validate the fitted null or establish FDR control when calibration adequacy remains unresolved.

Report **13 SNPs with POD-based BH q-values ≤0.10, conditional on the calibration assumptions**. Apply the qualification to full-report/supplement §6.8.1 and all summaries. In §§5.6 and 5.7.4, distinguish the observed behavior of the older 3,359-SNP calibration experiment from any assertion that the final 3,916-SNP threshold is guaranteed conservative. The raw final POD and core summaries are still unavailable locally, so final calibration adequacy was not independently regenerated.

### 5. P2 — Sparse marker tests and multiplicity need a defensible account

The available script applies four-zone Pearson chi-square tests per residue. Three inspected rare-residue tables each have **three of eight expected cells below five and one below one**. In one table, the expected carrier counts are approximately **2.779, 4.622, 18.255 and 0.344**. These values are calculated directly from the saved margins; they are an assumption concern, not proof that the saved p-value is wrong.

Use suitable exact or resampling inference for sparse tables, or clearly label the existing asymptotic results as exploratory. Define the testing family, address the many residue tests and their dependence, and identify which reported associations remain nominal. Claims resting on unadjusted p-values near 0.02–0.04 particularly need qualification. The official [SciPy documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chi2_contingency.html) describes the expected-frequency limitation and resampling alternatives. [Expected-cell evidence](/Users/samnimoh/Desktop/chromo/verification_review_round3/article_statistics_validation.json). No alternative inferential test was run in this review.

### 6. P2 — The new audit still does not establish its complete zero-effect conclusion

The audit is now inspectable, and its callability aggregates reconcile: 57 codons, 171 positions, 125 positions with records, 46 without, and a 10/26/21 distribution of codons with one/two/three recorded positions. However, two claims in [the verification notes](/Users/samnimoh/Desktop/chromo/provenance_final/VERIFICATION_NOTES.md:120) exceed the archived evidence:

- The log's **19 spanning records** include **three anchored at panel positions**; only **16** are genuinely off-anchor. The category name and notes overcount records anchored outside the panel.
- The **62 mixed calls** are record-level calls: **58** occur at selected anchors and **four** at genuinely off-anchor records. [The reconstruction source](/Users/samnimoh/Desktop/chromo/provenance_final/scripts/step12_codon_panel.py:282) selects records by panel anchor. Its mixed-call rule therefore does not automatically exclude the four omitted off-anchor calls. They may already be excluded for another reason, but the supplied aggregate logs do not show that.

Correct the category count and qualify “zero effect on any published number” until per-isolate downstream evidence covers the omitted records. The archived per-allele checker covers two records, while the notes' carrier conclusion spans three; the carrier-detail log also lacks a corresponding archived generation script. **These are evidence and scope gaps; this review has not demonstrated incorrect published frequencies.** [Static log validation](/Users/samnimoh/Desktop/chromo/verification_review_round3/static_audit_log_validation.json).

The [README](/Users/samnimoh/Desktop/chromo/provenance_final/audit_scripts/README.md:20) says network access is sufficient to rerun the scripts unchanged. Their hardcoded server CSV/FASTA paths and unpinned dependencies contradict that statement. Make the inputs and environment explicit and portable before promising unchanged replay. The notes' older “confirmed genuine at read level” heading should also agree with the new, accurate distinction between release genotype-quality fields and independent alignment examination.

### 7. P2 — Numerical compatibility is overstated as all-digit reproduction

Full-report §6.7 and the [new notes](/Users/samnimoh/Desktop/chromo/provenance_final/VERIFICATION_NOTES.md:197) claim that all fifteen printed edge values reproduce exactly from displayed means and standard errors. Independent CDF-subtraction arithmetic reproduces **all fifteen to three significant figures**, including two zero sentinels, but only **ten of thirteen finite values at their full displayed precision**. With the two zero sentinels, that is twelve of fifteen displayed outcomes.

The three remaining differences are moderate p-values, not the extreme-tail cancellation cases: for example, model 2 edge 1 recalculates to about 0.000747669 rather than the printed 0.000747653. Rounding of the displayed means and SEs may account for these small residuals. Narrow the claim accordingly; do not treat compatibility as proof of a specific build, command invocation or exact generating lineage. The tiny-tail cancellation explanation itself is supported and does not change the qualitative edge results. [Precision check](/Users/samnimoh/Desktop/chromo/verification_review_round3/tail_printed_precision_validation.json).

### 8. P2 — Citation, reporting and residual inferential claims need correction

The [Background](/Users/samnimoh/Desktop/chromo/article/article.md:25) attributes five-gene continental surveillance and frequency trends to Amambua-Ngwa et al. 2023, but the listed [Nature paper](https://www.nature.com/articles/s41564-023-01377-z) is the Gambian longitudinal AAT1/chloroquine study. Cite the appropriate surveillance evidence or narrow the statement to what that paper supports. The two WHO 2025 bibliography entries concern marker classification and methods; they do not support the opening Ghana burden and programme claims. Supply relevant epidemiological/programme sources and distinguish same-author/year entries unambiguously.

Describe four **sampled** zones rather than implying these exhaust Ghana's zones; the [FAO classification](https://www.fao.org/4/a0013e/a0013e05.htm) and the supplement itself include additional zones. The stated Pf8 release totals do match the [official data guide](https://malariagen.github.io/parasite-data/pf8/Data_access.html).

Two additional reporting fixes are needed. Article Mantel Methods should specify **FST/(1−FST) against log geographic distance**, as implemented in the available script. Genome-scan Results says both flagged chromosome-11 sites carry ExcessHet anomalies, but the [saved audit](/Users/samnimoh/Desktop/chromo/corrected/outlier_quality_check.csv:6) has ExcessHet=0 at one of them; both have low InbreedingCoeff, while elevated ExcessHet occurs at only the other site.

The full report/supplement still says “two directions of exchange are statistically supported” (§6.7), describes an “unobstructed demographic route” (§7.4), and infers “not purely a batch artefact” from direction agreement (§§2.6/4.3/6.2). Replace those with descriptive, conditional statements. Low FST and conditional graph tests do not identify connectivity or remove the study/geography/year confounding.

### 9. P2 — The submission package is incomplete

[Data availability](/Users/samnimoh/Desktop/chromo/article/article.md:237) says scripts and derived outputs accompany the article as Additional file 1. The supplementary Word file contains narrative and an inventory, with no embedded code/data bundle. Explicitly attach or deposit the supporting archive and identify it with stable access information; distinguish that archive from the narrative supplement.

The article has no author byline or affiliations. Funding and author-contribution placeholders remain; the supplement also retains author/affiliation placeholders. The geographical layer's original attribution/licence remains unresolved and is honestly disclosed, but the Figure 1 source and reuse basis still need a documented account.

Minor presentation work remains: Table 4 is displayed before Table 3; Table 2's heading is split across pages 7–8; Table 3 leaves its last row on page 11; the Background heading is stranded at the end of page 1. Several scientific-notation expressions render as literal `x 10^-n` text. Define table dashes as omitted values if that is their meaning, and trim references not cited in the article. These are visible in the fresh render, rather than inferred solely from extracted text.

## Provenance and Lean status

| Layer | Current status |
| --- | --- |
| Saved-result arithmetic | Earlier 14 checks and the subsequent seven QC/batch/Mantel checks retain their scope because their sources, inputs and artifacts are unchanged. They were not rerun unnecessarily. |
| New article consistency | Nine assertions passed, establishing stale metrics, mixed denominators and sparse expected cells; passing means the findings were confirmed, not that the article was certified. |
| New audit-log consistency | Fifteen checks passed for internal arithmetic and category partitioning. Six audit scripts parse as valid Python. No remote script was executed or log-generation lineage authenticated. |
| New precision claim | All fifteen outcomes match at three significant figures under CDF subtraction; full printed precision is not established for all fifteen. |
| Generating provenance | Improved disclosure and new inspection evidence, but final command/revision identities, raw calibration inputs, preprocessing inputs and per-isolate reconstruction evidence remain incomplete. |
| Lean formal verification | The original sixteen checked reference proofs are unchanged. No proof connecting the actual Python implementation to those specifications, and no end-to-end pipeline correctness proof, was added. [Original Lean source](/Users/samnimoh/Desktop/chromo/verification_audit/Pf8Audit.lean). |

The fresh DOCX conversions produced 18, 196 and 198 pages. All eighteen article page texts and nine selected pages in each long document match their supplied PDFs after whitespace normalization. Every article page image and representative long-document images were inspected. This is not a certification of all 394 long-document pages, nor a systematic review of every bibliographic claim. [Render record](/Users/samnimoh/Desktop/chromo/verification_review_round3/render_review.json).

The next revision should first repair the cohort attribution and supplementary labels, then reconcile statistical qualifications and audit scope, and finally complete the author/declaration/source package. The stronger cautious explanations should be retained. The current work is better documented and easier to inspect, but it is neither submission-ready nor fully reproduced or formally verified as an implemented pipeline.
