# Review of the latest Pf8 Ghana revision

The latest revision makes several sound corrections. The abstract now distinguishes small differentiation from undetectable differentiation, the main TreeMix summaries describe a selected graph rather than a historical event count, the concordance claim has the correct scope, and the stale Mantel values have been replaced. The missing-Fws defect can now be shown to have no effect on the available local input tables. The manuscript still needs major revision because methodological contradictions, causal overstatements and incomplete generating provenance remain.

This review concerns the current [workspace manuscript](/Users/samnimoh/Desktop/chromo/Pf8_Ghana_manuscript_REVISED.docx), SHA256 `878d7ec6e1ea7964ac3a6a76647ce7fbbed8cc5b871fe69ad68091b868f73fc4`. Page numbers refer to a fresh render of that file. The supplied PDF has the same 194 pages and identical extracted page text after whitespace normalization. Representative changed pages and tables were visually inspected; this is not a certification of every page's layout.

## What changed since the preceding review

Only the manuscript, its PDF and [verification notes](/Users/samnimoh/Desktop/chromo/provenance_final/VERIFICATION_NOTES.md) changed among the compared files. The supplied scripts, saved numerical outputs, original Lean artifacts and preceding review artifacts are unchanged. The body extraction grew from 90,974 to 91,920 words, including references and appendices. [File comparison](/Users/samnimoh/Desktop/chromo/verification_review_round2/change_inventory.json).

| Previous finding | Current assessment |
| --- | --- |
| Abstract claimed no detectable differentiation | Corrected on page 8: very low but detectable; five of six reported confidence intervals exclude zero |
| Definitive count of exactly two historical migration events | Substantially corrected in the main discussion and summary tables; several definitive statements remain elsewhere |
| Every reconstructed call described as independently compared | Corrected: the abstract restricts comparison to the 25 panel codons with published per-sample genotypes |
| Inconsistent count in the screened-codon negative paragraph | Corrected to all 23 screened codons, with reference-residue and target-marker absence distinguished |
| Incorrect agreement count and extreme-tail explanation | Numerical explanation substantially corrected; see the independent calculation below |
| Stale leave-one-region-out p-values | Corrected; all seven now match the saved CSV |
| Missing Fws included in fraction denominators | Defect remains in source, but is dormant on the complete local input tables |
| Notes said the reproducibility gap was closed | Corrected: the notes explicitly say it remains open |
| Unsupported reconstruction records might affect saved frequencies | Defect is now disclosed; the claimed complete zero-effect audit remains only partly verifiable locally |

The previous 14 saved-result consistency checks retain their scope because their inputs and checker artifacts are unchanged. They were not rerun unnecessarily. Seven additional local QC, batch and Mantel checks passed in this review. These establish arithmetic and input properties, not complete pipeline reproducibility.

## What the new checks establish

The [independent checker](/Users/samnimoh/Desktop/chromo/verification_review_round2/check_batch_and_mantel.py) uses standard-library average ranks, tie-corrected Kruskal statistics and chi-square survival probabilities. It records the runtime, six input hashes and separate numerical tolerances. Tiny p-values are compared with relative tolerance and no absolute tolerance, so a zero value cannot pass against a nonzero extreme tail. [Validation results](/Users/samnimoh/Desktop/chromo/verification_review_round2/batch_mantel_validation.json).

The archived 4,905-row QC table and 1,900-row analysis table contain no missing Fws or call-rate values. Their overlapping measurements agree within CSV serialization roundoff. The local QC input reproduces the saved study-by-zone counts and batch-test statistics, with p-values agreeing to numerical precision. The earlier concern about missing values therefore does not change those local results. This is evidence of a dormant defect for these inputs, not a code repair or independent confirmation of the exact remote final file.

The corrected Mantel paragraph agrees with all seven saved leave-one-region-out p-values: Ashanti 0.0140, Brong Ahafo 0.0398, Central 0.0427, Eastern 0.1355, Greater Accra 0.2324, Upper East 0.2180 and Volta 0.0097. Four are below 0.05 and the same four are below 0.10. [Saved values](/Users/samnimoh/Desktop/chromo/corrected/mantel_jackknife_region.csv).

For TreeMix, stable recomputation from the printed means and standard errors gives agreement to three significant figures for 10 of the 13 finite printed p-values. Rounding the normal CDF before subtracting it from one reproduces all 15 outcomes to three significant figures, including the two zero sentinels. It reproduces the second m = 2 edge's printed value, approximately 3.330669 × 10⁻¹⁶, while the stable tail calculated from the displayed mean and standard error is approximately 3.803964 × 10⁻¹⁶. This supports the revised cancellation explanation. [Numerical calculation](/Users/samnimoh/Desktop/chromo/verification_review_round2/tail_probability_review.json).

The two extremely small mathematical tails remain representable. Describe the computational failure as rounding and cancellation to zero, rather than underflow of the true tail. Direct complementary-error-function evaluation avoids subtracting a probability almost equal to one. [Python numerical documentation](https://docs.python.org/3/library/math.html#math.erfc). Numerical compatibility does not identify the actual executable revision or establish the exact generating command; those remain separate provenance questions.

## Remaining findings

### The BayPass MAF contradiction survives the revision

Section 5.6 says the pseudo-observed set is not MAF-matched, and the revised configuration and correction tables acknowledge that fact. Section 6.8 still says the simulations used “the same MAF filter as the observed data” on page 109. This is the same methodological contradiction identified previously. Correct that sentence and check all summaries against one precise account of simulation and filtering.

The final raw POD and core summaries are still absent locally. The saved q-values reproduce from saved p-values, but the final null calibration cannot be independently regenerated. The claim that the final threshold is conservative also extends an experiment on a superseded scan to a final calibration whose raw inputs are unavailable here; keep that scope explicit.

The repeated label “empirical FDR” for 3.916 / 19 remains too strong. This is an expected-null-exceedance/count ratio under the assumed model, not a measured false-discovery fraction. Likewise, the fitted-POD calculation described as an “exact” permutation-style p-value on page 53 should be identified as a Monte Carlo tail probability under the fitted null. Reproducing its adjustment does not establish final null adequacy or unconditional FDR control.

### Low observed FST is not an established upper bound on true differentiation

Page 27 asserts that study effects can only inflate apparent differences, making the observed FST an upper bound on true differentiation. No analysis establishes that one-direction bias guarantee. Study composition, calling differences and missingness can alter the observed contrast in either direction. A small estimate on the retained variants is not a formal upper bound on differentiation in a broader population.

Keep the corrected conclusion: differentiation is very low among the retained common variants and sampled groups, with stable magnitude across the tested threshold scenarios. Remove the unsupported ceiling claim. The manuscript's later discussion of pooled-MAF ascertainment already explains why the result's scope is limited.

The batch results also remain overinterpreted. Pages 26 and 70 say that holding a broad zone constant means only study varies. Collection period, finer location, recruitment and biological variation need not be constant within a zone. The tests demonstrate study-associated heterogeneity; they do not isolate a technical sequencing cause. This concern persists even though the missing-Fws denominator defect is dormant.

### TreeMix caution still needs to reach the caption and limitations register

The main correction is accepted: the m = 2 graph is now described as a selected descriptive model, and page 169 explicitly distinguishes it from the number of historical migration events. However, the Figure 6.7 caption on page 108 says the full-sweep m = 3 choice is “superseded by the edge p-values”; section 7.3 on page 138 says that rerunning with `-se` “settles it”; and Table 9.1 marks the identifiability limitation “Resolved” on page 155 even though its explanatory text says the standard errors do not close it.

Conditional edge tests do not resolve uncertainty about topology, rooting, edge count or historical corridors. Keep the chosen graph and its conditional statistics, explain the restriction used to select it, and label the identifiability limitation as continuing rather than resolved. The numerical tail explanation addresses a computational reporting issue; it does not settle these inferential questions.

### The claimed complete reconstruction audit has not been supplied

The manuscript now discloses the unsupported-input behavior and reports that a record-level audit found no effect on published numbers. That is a useful response to the previous source review. Existing aggregate outputs corroborate 57 codons, 125 reported records, no wholly record-free codon and no emitted `X` residue. They do not independently establish the classifications of all affected carriers or the full zero-effect conclusion.

No affected-record export, checking script or per-isolate reconstructed-call matrix was added. Archive that audit's inputs, code and comparison output before treating the claim as independently verified. Until then, distinguish the reported server audit from what a reader can reproduce locally. There is still no evidence here that the published frequencies are wrong; there is also no complete local proof that every unsupported-input branch was harmless.

Having at least one variant record per codon does not establish callability at every constituent base in every isolate. The convention that an absent variant record implies reference still requires explicit input guarantees. The stronger “confirmed genuine at read level” language likewise exceeds the locally supplied evidence: reported genotype-quality fields provide support, but the underlying record export and an independent read/alignment examination are not archived here.

### The manuscript still overstates generating reproducibility

The new notes correctly list missing final commands, executable revisions, raw calibration inputs, per-isolate reconstruction output and preprocessing inputs. Their opening reproducibility claim is therefore corrected.

Section 9.3 on page 157 still begins “The analysis runs end to end from public data sources.” Public availability of inputs does not establish that the supplied snapshots regenerate the final results. The archived runner's parallel configuration, BayPass thread defaults and TreeMix command differ from the procedure described for the final run. State which source snapshots and outputs are available and which final revisions are still missing.

The repeated “provably faithful” restoration wording also needs narrowing. Matching downstream checksums, thresholds and aggregate counts establishes restoration consistency. It cannot establish equality of every restored row with an original table that is no longer available for comparison.

## Formal verification and publication readiness

All original audit proof artifacts are unchanged. The earlier 16 checked Lean reference proofs retain their original scope; no implementation-refinement proof was added for the reconstruction or batch scripts, and no end-to-end pipeline proof was added. [Lean source](/Users/samnimoh/Desktop/chromo/verification_audit/Pf8Audit.lean).

Formatting has improved materially: most literal asterisks have been removed. A small number of literal superscript/subscript tags remain in the text extraction. The manuscript is still a 194-page working report with approximately 91,920 body words, extensive correction history and implementation narrative. It needs substantial compression and separation of the main article from audit supplements before submission.

The next revision should correct the remaining MAF sentence, remove unsupported causal and upper-bound claims, make TreeMix captions and status labels match the cautious discussion, and archive the empirical reconstruction audit and exact final generating revisions. The additional work has improved the manuscript and has independently resolved the local Fws-impact concern. It has not yet produced a submission-ready paper or complete provenance and formal verification.
