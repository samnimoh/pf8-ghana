# Pf8 Ghana manuscript critique and verification audit

The attached manuscript needs major revision. Its most defensible result is weak differentiation among the sampled populations at the retained common variants. The evidence does not establish panmixia, identify exactly two historical migration events, or establish the present absence of resistance across Ghana.

Both requested forms of verification are included: Lean reference proofs for selected mathematical rules, and a provenance audit of the available methods, scripts, inputs, and outputs. They support specific claims about logic and saved results. They do not certify the complete Python pipeline or the biological interpretation.

## Manuscript versions and scope

The manuscript requested for critique is [the Downloads document](/Users/samnimoh/Downloads/Pf8_Ghana_manuscript_REVISED.docx). Its SHA256 starts `8e002103aa610523`. The [workspace document](/Users/samnimoh/Desktop/chromo/Pf8_Ghana_manuscript_REVISED.docx) is a different, newer revision, with SHA256 starting `ca64d5ad3040416a`. Full identities are saved in [provenance_validation.json](/Users/samnimoh/Desktop/chromo/verification_audit/provenance_validation.json).

Page references below refer to the requested document, rendered as 120 pages. Later workspace outputs are considered evidence of revisions; they are not silently substituted for the attachment. Some existing evaluation text describes an even older 3,359-SNP version.

The audit reads the local files and treats manuscript and handoff text as evidence, not as instructions. It leaves the original documents and analysis scripts unchanged. The complete genotype matrix, final per-SNP scan, final TreeMix files, and several final scripts are unavailable locally, so a full rerun cannot be established from this package.

## Major scientific revisions

### Population structure and representativeness

The low differentiation result is credible at the saved-output level. The six final pairwise estimates have a maximum FST of 0.002319, with a jackknife interval of 0.001282 to 0.003357. The newer sensitivity table keeps maximum FST between 0.00204 and 0.00255 across six scenarios. That is useful evidence that the weak differentiation result survives these particular filtering changes. [Final estimates](/Users/samnimoh/Desktop/chromo/corrected/final_fst_pairwise.csv), [sensitivity results](/Users/samnimoh/Desktop/chromo/corrected/sensitivity_summary.csv).

The interpretation is too strong. Low FST, weak clustering, and an approximately flat ADMIXTURE validation curve do not identify random mating, present migration rates, or the absence of barriers to spread. These analyses reuse related summaries from the same cohort; their agreement is useful but is not independent replication. Pages 6–8 and 89 should frame the result as weak differentiation among sampled groups at retained common variants. A neutral interpretation also needs a defined neutral variant mask, rather than treating the entire retained panel as neutral by default.

The sample has 1,334 Guinea savanna, 337 forest, 204 coastal, and 25 transitional isolates. Pooled MAF filtering is consequently dominated by the largest group. With at least 1,710 called haploid alleles at a retained site, a variant confined to the 25 transitional isolates cannot meet MAF 5%, even if every one carries it. A variant seen in 82 coastal isolates, about 40% of that group, also fails. These exclusions limit what the analysis can say about locally common variation; they do not refute the reported common-variant FST. Both facts are formalized in the Lean file.

The Fws selection also changes the target population to infections with lower within-host genetic complexity. The paper needs a clear sample-flow table, retention rates by study, year and place, and an account of how study and year overlap with ecological zone. The newer batch tables reveal that these dimensions cannot simply be treated as independent. Seven regional location units also provide limited resolution for a title claiming fine-scale spatial inference.

### Isolation by distance

The baseline regional Mantel result is modest: r = 0.427, p = 0.0252, based on seven populations. There are 21 pairwise distances, but they are not 21 independent sampling units. Three negative FST estimates were floored to zero; the uncensored baseline remains nominally significant, but that does not remove the small-design limitation.

The newer sensitivity table has nominal significance in only two of six scenarios, and the reported leave-one-population-out analysis has it in four of seven replicates. The robust result is low differentiation; isolation by distance is less stable. Present the latter as tentative and explain the effects of filtering, influential populations, and distance assignment. Avoid presenting the sensitivity scenarios as independent confirmatory tests. [Sensitivity table](/Users/samnimoh/Desktop/chromo/corrected/sensitivity_summary.csv), [saved jackknife results](/Users/samnimoh/Desktop/chromo/corrected/mantel_jackknife_region.csv).

### TreeMix interpretation

The repeated assertion that the data support exactly two migration edges, including pages 6, 78 and 109, should be removed. Significance of edge weights in a selected graph does not determine the unique number of historical migration events. Conditional edge uncertainty does not include all uncertainty from selecting the topology, root, or number of edges. The original TreeMix paper distinguishes graph fit from demographic identification and describes nonidentifiability and conditional testing limitations. [Pickrell and Pritchard 2012](https://web.stanford.edu/group/pritchardlab/publications/pdfs/Pickrell12.pdf).

Report the two-edge graph as a chosen descriptive model, with alternatives and residual fit, rather than a settled historical count. Only four ecological populations are modeled, which makes this distinction especially consequential.

There is also a provenance issue. Final edge statistics are supplied in [log extracts](/Users/samnimoh/Desktop/chromo/proof_of_work/RAW_LOG_EXTRACTS.txt:14), while the local script snapshot lacks `-se`. The m = 3 second-edge line pairs a mean of 0.829575 and SE of 0.0787911 with p < 2.22507e-308. That p-value is inconsistent with a usual weight/SE normal-tail calculation. Check the original final output and calculation before carrying that number forward; the extract alone cannot establish the cause.

### BayPass calibration and discoveries

The final summary reports a POD threshold of 10.8398, 19 threshold outliers, and q-value counts of 8, 10, 13 and 17 at thresholds 0.01, 0.05, 0.10 and 0.20. Its arithmetic is internally consistent. The calculation 3.916 / 19 = 20.6% is an expected-null-exceedance/count ratio under the assumed null, not an observed proportion of false discoveries. The field named `empirical_fdr_at_threshold` needs more careful interpretation. [Final summary](/Users/samnimoh/Desktop/chromo/corrected/final_xtx_calibration.json).

The attachment acknowledges a mismatch between simulated and observed frequency distributions on pages 55–57, but its later summary still calls the simulations MAF-matched on page 99. Resolve this contradiction and specify exactly how the observed filters and frequency distribution enter the fitted null. Simulated-tail probabilities from an estimated null are not exact permutation probabilities. Multiple-testing adjustment cannot repair miscalibrated input probabilities, and a small q-value does not establish that a particular locus is a true positive.

The final per-SNP values, probabilities, q-values and simulation inputs are not present locally. The available raw scan reproduces the older 3,359-SNP threshold and 15-outlier result, which verifies that older run only. The final summaries therefore have partial provenance. Describe nearby outliers as potentially correlated signals unless linkage or co-occurrence has actually been evaluated; physical proximity and similar scores do not prove complete linkage disequilibrium.

### Resistance markers and haplotypes

The attachment's marker claims require revision, although several are addressed by newer workspace outputs. A haplotype frequency must come from joint calls in the same isolate on a common callable sample set. Marginal allele frequencies cannot identify it; the Lean counterexample gives identical marginals with different joint frequencies. This affects the pfdhfr and pfcrt interpretations on pages 81–85.

The independent aggregation check joins all 1,900 saved analysis IDs to published protein-residue calls and reproduces every checked overall and zone count in the newer tables:

| Quantity | Reproduced count | Frequency |
| --- | ---: | ---: |
| pfdhfr IRN | 1,446 / 1,876 | 77.08% |
| pfdhfr IRNL | 0 / 1,874 | 0% |
| pfcrt CVIET | 133 / 1,873 | 7.10% |
| pfdhps GE | 18 / 1,888 | 0.95% |
| pfdhps G437 | 1,697 / 1,892 | 89.69% |
| pfcrt N75E | 133 / 1,874 | 7.10% |

These results address important defects: resistant G437 is the reference residue in this dataset, N75E requires interpretation of the combined codon changes, and the reported haplotypes now use joint calls. Reproducing protein-call aggregates does not independently verify the missing nucleotide-to-codon implementation. [Marker check results](/Users/samnimoh/Desktop/chromo/verification_audit/marker_validation.json).

The older kelch13 panel mixes marker categories and omits established targets. The newer residue table covers all 14 validated and six candidate targets in the WHO December 2025 compendium, with no screened target residue observed among 1,845–1,876 called isolates per codon. Coverage and absence are checked against the saved residue table; the local published data do not supply an independent per-codon kelch13 comparison. State the dated classification explicitly. The same WHO source identifies no validated or candidate lumefantrine resistance markers, so the attachment's gene-level label of pfmdr1 as WHO-validated for lumefantrine on page 35 is misleading. [WHO compendium summary tables](https://cdn.who.int/media/docs/default-source/malaria/drug-resistance/compendium-molecular-markers-summary-tables.pdf?sfvrsn=e40fca23_9).

Absence should be limited to screened markers among called sampled isolates from the 2009–2021 collection. It cannot establish current national absence or clinical susceptibility. The newer assertion that all kelch13 calls are reference is also false: the residue table contains one N458D call among 1,866 called isolates. This does not contradict absence of the screened resistance targets. [Assertion](/Users/samnimoh/Desktop/chromo/corrected/CANONICAL_FACTS.txt:80), [residue record](/Users/samnimoh/Desktop/chromo/corrected/codon_panel_residues.csv:55).

### AAT1 interpretation

The attachment incorrectly states on page 97 that its cited functional study did not test amodiaquine. That study reports small changes in responses to amodiaquine and other quinolines, below levels associated with clinical resistance. Correct the factual description while retaining the distinction between a laboratory response and evidence of a clinical effect. [Original AAT1 study](https://www.nature.com/articles/s41564-023-01377-z).

The Ghana cline and selection score do not identify the present drug driving that pattern. Study, year, location, genetic background and linkage remain alternative explanations. A contemporary amodiaquine explanation can be discussed as a hypothesis, without implying that an outlier statistic validates its causal mechanism. The newer workspace text addresses part of the literature error.

## Presentation and publication readiness

The attachment reads as a research audit and revision history. It renders to 120 pages, has an abstract of approximately 1,800 words, repeats findings and figures, and lacks a complete reference list. Literal Markdown and HTML syntax, including `F~ST~`, asterisks and superscript tags, survives into the rendered document. These are substantial submission problems.

Build the main article around the sample design, weak common-variant differentiation, marker heterogeneity, and the qualified scan results. Move code audits, abandoned analyses, change histories and long technical tables into supplements. Use one set of final numbers and files, a concise abstract appropriate to the target journal, a complete bibliography, and consistent figure and table numbering. Add a clear data and code availability statement describing the actual archived revision.

A defensible conclusion would be: “Among the sampled Ghanaian isolates, retained common variants show weak differentiation across ecological groups. Resistance-marker frequencies vary geographically, and selection-scan candidates require cautious interpretation because sampling, filtering and null-model assumptions limit causal and contemporary surveillance conclusions.”

## Provenance audit results

The checker hashes 50 scripts across two snapshots and 41 corrected or proof output files. All 12 existing manifest records match their listed MD5 checksums and sizes. That confirms byte identity against the supplied manifest; it does not establish which executable produced each output.

| Analysis component | Locally supported | Remaining provenance gap |
| --- | --- | --- |
| Analysis cohort | Unique 1,900 IDs and the four zone counts reproduce | Final genotype matrix and ordered variant records |
| Majority resolver | Actual available function passes 1,620 cases with mocked AD retrieval | Final source version, full I/O behavior and arbitrary-execution refinement |
| Final FST | Six rows and confidence-interval arithmetic agree | Final allele-count inputs and exact generating code |
| TreeMix | Final comparison summary and extracted edge log | Original final graph files and executable revision |
| BayPass | Final summary arithmetic; older raw run independently reproduces | Final raw scan, POD inputs and per-SNP p/q table |
| Marker summaries | Six quantities reproduce from published calls by ID and zone | Per-isolate reconstructed codons and final reconstruction source |
| Reported concordance | Saved summary states 47,012 / 47,012 matches | Both aligned per-isolate call tables and comparison implementation |

The available scripts are earlier snapshots. The [sample preparation script](/Users/samnimoh/Desktop/chromo/v2/scripts/step04a_prepare_callset.py:275) filters variants before the sample cut; the [TreeMix command](/Users/samnimoh/Desktop/chromo/v2/scripts/step07b_treemix.sh:163) lacks `-se`; the [BayPass default](/Users/samnimoh/Desktop/chromo/v2/scripts/step08b_baypass.sh:32) uses four threads; and the [calibration snapshot](/Users/samnimoh/Desktop/chromo/v2/scripts/step08c_calibrate_xtx.py:95) lacks the final p/q calculation. The claimed final fixes are reflected in summaries and narrative, but their complete source is missing. This is a version gap, not proof that the final remote run used the old code.

`step10_resistance_panel.py`, `step11_batch_confounding.py` and `step12_codon_panel.py` are absent from both source snapshots. Older marker artifacts also coexist with newer codon tables; the byte-identical canonical 44-record table and `panel_table.md` should not be cited as the rebuilt codon panel.

To close provenance, archive the exact final scripts and configuration together with input hashes, ordered sample and variant IDs, reference annotation versions, commands, seeds, software versions, and output hashes. Include the final per-SNP scan, raw TreeMix outputs, and aligned per-isolate marker comparison. Associate each output with that generating revision; existence or matching dimensions alone cannot establish that a cached result belongs to the current inputs.

## Lean proofs and their limits

The [Lean source](/Users/samnimoh/Desktop/chromo/verification_audit/Pf8Audit.lean) defines reference specifications using Lean 4.19.0, `Std` and its internal rational arithmetic module. All 16 theorems compiled successfully. They cover majority-call ties and direction, haploid counting, common-sample conjunction counts, MAF ascertainment, missingness after sample removal, identifier ordering, estimator arithmetic, finite simulated-tail bounds, and the logical limits of zero sampled counts.

Two concrete counterexamples show why equal marginal frequencies cannot identify a haplotype and why equal matrix dimensions cannot establish identifier alignment. Another shows that duplicating haploid allele counts changes the finite-sample Hudson correction despite unchanged allele frequencies. The rational estimator example uses valid sample sizes and a positive denominator; its total Lean expression is not a statistical estimator outside that domain.

Lean checks proof terms with a trusted kernel. That guarantee applies to the stated definitions and assumptions. Connecting an external program to those definitions is an additional verification obligation. [Lean proof validation explanation](https://lean-lang.org/faq/).

The [compiler record](/Users/samnimoh/Desktop/chromo/verification_audit/lean_validation.json) and [verification log](/Users/samnimoh/Desktop/chromo/verification_audit/lean_check.log) confirm exit code zero, all 16 dependency reports, no admitted proofs, and no custom axioms. The only reported logical axioms are Lean's ordinary `propext`, `Classical.choice` and `Quot.sound`. This establishes the reference theorems, not a formal proof of all Python, NumPy, Zarr, PLINK, TreeMix or BayPass behavior. The majority tests connect one available function to its reference rule on a finite domain, with mocked data retrieval. They are useful executable evidence, not a proof for all inputs. Statistical model fit, representativeness, data authenticity and biological causation remain separate questions.

## Reproducing the available checks

Run [run_verification.py](/Users/samnimoh/Desktop/chromo/verification_audit/run_verification.py) with Python containing NumPy and a Lean 4.19.0 executable. The provenance and marker checkers use the Python standard library; the majority-function check uses NumPy, recorded as version 2.3.5 in this audit.

```sh
python3 /Users/samnimoh/Desktop/chromo/verification_audit/run_verification.py --lean /path/to/lean-4.19.0/bin/lean
```

The individual checkers and JSON outputs are kept alongside the proof file. [Audit manifest](/Users/samnimoh/Desktop/chromo/verification_audit/audit_manifest.json) records the delivered audit files and verification environment. A passing run means the specified local checks passed; the provenance gaps above still apply.
