# Pf8 Ghana review after the latest revision

Several earlier objections are now resolved. The final scan is available, its q-values reproduce, the previously missing marker and batch scripts can be inspected, and a bibliography has been added. The manuscript still needs major revision because the conclusions and summary tables disagree, part of the reconstruction implementation has an unresolved correctness problem, and the complete generating provenance remains incomplete.

This review concerns the latest [workspace manuscript](/Users/samnimoh/Desktop/chromo/Pf8_Ghana_manuscript_REVISED.docx), SHA256 `fe90d26b0dc6ee4e1391610885c5986ef71d8b1811a3fec630979c3d1a225953`. Its page references come from a fresh render with 193 pages. The document in Downloads is unchanged and is an older version. The earlier audit files have been preserved as a dated baseline.

## What changed and what was verified

Against the earlier hashes, the workspace manuscript and `corrected/CANONICAL_FACTS.txt` changed. The other previously inventoried scripts and numerical output files are unchanged. Twelve files were added under `provenance_final`; a new PDF of the manuscript is also present. The changes therefore principally supply missing evidence and revise the write-up, rather than replace the earlier numerical analysis. [Change inventory](/Users/samnimoh/Desktop/chromo/verification_review/change_inventory.json).

| Earlier finding | Current status | Evidence |
| --- | --- | --- |
| Final 3,916-SNP scan missing locally | Resolved for the saved scan table | All 3,916 rows have unique coordinates and sequential row IDs; 19 outlier flags match the saved threshold |
| Final q-values could not be recomputed | Resolved from saved p-values | Independent Benjamini–Hochberg calculation reproduces every q-value exactly; counts are 8, 10, 13 and 17 at q thresholds 0.01, 0.05, 0.10 and 0.20 |
| Final TreeMix edge output unavailable | Resolved for the supplied output text | Six models and their edge statistics are supplied; the earlier extracted edge statistics agree with the new text |
| Marker and batch source scripts absent | Resolved for source inspection | `step10`, `step11` and `step12` are now present |
| All kelch13 residues described as reference | Corrected in the facts summary and abstract | The summary now acknowledges the previously saved non-reference call; the numerical residue table itself did not change |
| Bibliography absent | Resolved | Section 11 contains 42 entries |
| Formatting tokens in FST and Fws | Improved | The body no longer contains `F~ST~` or `F~ws~`; some asterisks and literal superscript/subscript tags remain |

The [new result checker](/Users/samnimoh/Desktop/chromo/verification_review/check_final_results.py) passed 14 consistency checks. It also records numerical discrepancies and limitations; passing those checks does not validate the complete null model or pipeline. [Results and input identities](/Users/samnimoh/Desktop/chromo/verification_review/final_results_validation.json).

The new scan's locally measured MD5 agrees with the checksum in the supplied notes. That checks the stated checksum, not an independently observed transfer from the server. Likewise, the concatenated TreeMix text now permits local inspection but does not by itself establish the original command or executable revision.

## Findings that need attention

### The revised differentiation conclusion is still incorrect

The abstract conclusion on page 8 now says that the design detects no differentiation at retained common variants. This is an improvement in avoiding a claim of demonstrated random mating, but it replaces that overstatement with another one. Five of the six reported confidence intervals exclude zero. Page 168 explicitly answers that differentiation is distinguishable from zero in five pairs. The abstract and the results therefore contradict each other.

The defensible wording is: “Differentiation is very low; five of six pairwise estimates have reported confidence intervals excluding zero.” Statistical detectability and the size of an effect are separate questions. A small FST does not become an undetectable FST because the effect is small. [Saved estimates](/Users/samnimoh/Desktop/chromo/corrected/final_fst_pairwise.csv).

The consistently low estimates across threshold scenarios remain useful evidence. They establish robustness to those particular changes in the analysis set, not universal panmixia or representativeness of unsampled populations. The unresolved study, year, ecological-zone and regional confounding still constrains causal interpretation.

### The TreeMix correction has not propagated through the manuscript

The revised abstract and main discussion correctly frame the two-edge graph as a descriptive model. The supplied model-selection JSON independently confirms that the stated heuristic chooses m = 2 within the restricted range, but m = 3 across the full sweep. [Model selection](/Users/samnimoh/Desktop/chromo/provenance_final/results/model_selection.json:21).

However, page 88 still says the model choice is settled. Tables on pages 147, 151, 154 and 168 retain definitive wording about exactly two supported edges; the page 168 table says the number is settled. These are presented as current conclusions, not merely quotations of a superseded result. Reconcile every summary with the revised descriptive interpretation. Edge tests conditional on a fitted graph do not prove a unique count of historical migration events. The restricted range is part of the model-selection decision and must remain explicit.

The new output makes the presence of reported standard errors inspectable. My earlier concern was the missing final generating source, rather than proof that the remote run omitted `-se`. The new evidence substantially addresses the output side of that concern; the exact final command is still not archived locally.

### The new explanation of extreme p-values needs numerical precision

The new notes correctly recognize that the m = 3 printed value below 2.22507 × 10⁻³⁰⁸ is not a credible normal-tail calculation from the displayed mean and standard error. Stable recomputation gives approximately 3.182 × 10⁻²⁶. The same problem occurs in the m = 4 second edge, whose stable tail is approximately 5.447 × 10⁻²¹. Both values are representable in double precision. [Supplied output](/Users/samnimoh/Desktop/chromo/provenance_final/results/treemix_treeout_all.txt:13).

The pattern is consistent with cancellation when a very small tail is computed by subtracting a cumulative probability from one. That is an inference from the numerical behavior; the actual TreeMix build source and binary used for this run have not been supplied. Complementary normal probabilities can be evaluated directly rather than through that subtraction. [Primary numerical documentation](https://www.boost.org/doc/libs/latest/libs/math/doc/html/math_toolkit/dist_ref/dists/normal_dist.html).

The notes and page 108 also claim that five of six probabilities reproduce to three significant figures. Only three do under stable recomputation. For the second m = 2 edge, the stable tail is 3.804 × 10⁻¹⁶, compared with the printed 3.33067 × 10⁻¹⁶. This does not change its conditional significance. Correct the numerical agreement claim without presenting it as a change to the overall model choice. [Verification notes](/Users/samnimoh/Desktop/chromo/provenance_final/VERIFICATION_NOTES.md:33).

### BayPass arithmetic is now reproducible but calibration claims remain inconsistent

The new p-value table is a substantial improvement. The BH adjustment matches exactly, the q-value counts reproduce, and both reported AAT1 sites have q = 0.004894951. The p-values also satisfy basic bounds, have the expected monotonic relationship with XtX, and are compatible with the stated simulation-count lattice. These are useful consistency checks.

They do not independently regenerate the p-values or threshold from the final simulated null. The final POD values, raw core summaries and final calibration source are still missing locally. The archived table therefore resolves adjustment and counting, while calibration and model adequacy remain open.

The manuscript also retains a direct contradiction: pages 75, 77 and 88 state that the POD is not MAF-matched; section 6.8 on page 108 describes the same MAF filter as the observations; and the table on page 147 calls the simulations MAF-matched. A new final scan table does not resolve this methodological inconsistency. State the simulation and filtering procedure consistently and archive the inputs needed to reproduce it.

The 20.6% quantity remains an expected-null-exceedance/count ratio under the assumed null. It is not a measured fraction of false discoveries. A q-value below a threshold also cannot establish that a particular discovery is true.

### The newly available reconstruction source has an unresolved correctness problem

Source inspection shows that a called non-reference record with a length-changing allele is skipped while its sample remains eligible for a residue call. The reference-derived state can consequently be reported despite an unsupported allele. Equal-length multi-base records are also handled using only their first character, and retrieval selects records by anchor position rather than the full affected interval. [Reconstruction branch](/Users/samnimoh/Desktop/chromo/provenance_final/scripts/step12_codon_panel.py:375), [record selection](/Users/samnimoh/Desktop/chromo/provenance_final/scripts/step12_codon_panel.py:280).

This establishes a correctness concern in the implementation's claimed input domain. It does not establish that the published frequencies are wrong: the required per-isolate input records are absent locally, so the number of affected reported calls cannot be quantified. Before describing reconstruction as complete, establish its supported variant domain and audit whether unsupported records occur in the actual panel inputs.

The script also treats absence of a variant record as a reference base and, for a wholly record-free codon, labels every isolate as carrying the reference residue. That inference needs an explicit callability assumption. Absence from a variant table is not independently measured per-isolate coverage. Describe that convention and the input guarantees supporting it. [Reference-call assumption](/Users/samnimoh/Desktop/chromo/provenance_final/scripts/step12_codon_panel.py:351).

The source does support several important parts of the intended method: missing or mixed constituent calls exclude a codon; haplotypes use a common complete-case sample set; and published-call comparisons align by sample ID. These resolve uncertainty about whether those operations appear in the supplied code. They still do not independently replay the reconstructed calls or prove that this exact source version generated the saved output.

### The batch script mixes missing-value denominators and overstates causality

The new batch script calculates overall and within-study polyclonal fractions by comparing Fws values with a threshold before excluding missing measurements. For ordinary numeric missing values, that comparison produces false values, so missing observations remain in the denominator. An entirely missing cell can consequently be reported as 0%. Its Kruskal tests and per-study range calculations, by contrast, exclude missing Fws first. The resulting summaries use different denominators. [Fraction calculations](/Users/samnimoh/Desktop/chromo/provenance_final/scripts/step11_batch_confounding.py:143).

The minimum sample-size checks and reported isolate counts also use all isolates rather than the number with an observed value for the outcome being tested. Use consistent observed-value denominators, state missing counts, and distinguish total sample sizes from outcome-specific sample sizes. The actual numerical impact cannot be established without the input table; this is a source-level finding.

The script also describes any within-zone study difference as a batch effect. Holding a broad ecological zone constant does not control collection year, finer geography, recruitment or biological differences among studies. These comparisons establish study-associated heterogeneity. Their direction agreement is a useful descriptive check, but it does not establish a technical cause. [Interpretation](/Users/samnimoh/Desktop/chromo/provenance_final/scripts/step11_batch_confounding.py:103).

### The new read-level claims have only narrative provenance

The revised facts summary correctly retracts the claim that every kelch13 call is reference. Its previously saved non-reference call does not contradict the absence of the screened target markers.

The newly reported supporting call-quality values and the audit of release-filter failures are described in the notes and manuscript, but the underlying per-isolate record export and the checking code are not included. The implementation confirms that it reads `FILTER_PASS` without applying it to panel reconstruction. The omission is now disclosed; the stated numbers of failing records and carriers remain claims that cannot be independently corroborated from the supplied package.

The concordance implementation compares 25 listed markers and saves aggregate counts. It does not export the aligned per-isolate reconstructed calls, and it does not independently validate every reconstructed codon. The 47,012 / 47,012 claim should retain that scope. The manuscript's broader statement that every call was compared is too broad for this implementation. [Comparison scope](/Users/samnimoh/Desktop/chromo/provenance_final/scripts/step12_codon_panel.py:531).

The page 50 kelch13 paragraph also needs a simple editorial correction: all 23 screened codons have no screened target allele in the saved output; 22 are fixed at the reference residue, and the other has a non-target alternative. Its opening “22 of the 23” mixes these two counts, although the abstract gives the intended distinction correctly.

## Publication readiness and formal verification

The bibliography now closes the missing-reference-list finding. Its 42 entries are present, and the literal FST/Fws markup has been improved. This review checked the existence and structure of the bibliography, not all 42 external metadata records claimed in the notes.

The current body contains approximately 90,974 words, including the bibliography and appendices, versus 87,681 in the earlier workspace extraction. The fresh render and the supplied PDF both have 193 pages. The document remains an internal working report with extensive audit history and correction commentary. The main article needs substantial compression, a journal-length abstract, and supplements for the audit record and implementation narrative. Some literal formatting tokens remain visible, including asterisks in the page 50 callout. Representative pages were visually inspected; this was not a layout certification of every page.

The [Lean source](/Users/samnimoh/Desktop/chromo/verification_audit/Pf8Audit.lean), its compiled proof artifact, and all other original audit files are unchanged against the earlier manifest. The earlier 16 checked reference proofs therefore have the same scope. No proof was added that the newly supplied reconstruction or batch implementation refines those specifications. Full formal verification of the pipeline remains incomplete.

The opening claim in the new notes that the local reproducibility gap is closed is too broad. Source inspection and final-table adjustment are substantially improved; the complete final preprocessing and calibration revision, required raw inputs, per-isolate reconstruction exports and exact generating records still need to be archived. [Opening claim](/Users/samnimoh/Desktop/chromo/provenance_final/VERIFICATION_NOTES.md:3).

The most useful next revisions are to reconcile the abstract and all summary tables, resolve the reconstruction input-domain concern against actual records, and complete the generating archive. The strong result remains very low differentiation at retained common variants. The revised material supports a more careful report of that result, but not a submission-ready manuscript or an end-to-end verification claim.
