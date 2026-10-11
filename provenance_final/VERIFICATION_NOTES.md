# Provenance and verification — rounds 3 and 4 (2026-10-10)

Supplies the source and output files the external audit could not find locally, and
records four empirical checks it said could not be run without the input data.

**Scope, stated precisely.** This does not close the reproducibility gap. What it closes
is source inspection and output-level arithmetic. Still not archived locally: the exact
final commands and executable revisions, the raw BayPass POD inputs and core summaries,
the per-isolate reconstructed codon calls, and the preprocessing inputs needed to replay
the pipeline end to end. A reader can now inspect what was run and recompute the saved
tables; they cannot yet regenerate them from raw data.

## Files copied from the server (bacg2:/media/biodataA/pf8/gyadu)

| File | Why it was missing | Verification |
|---|---|---|
| `scripts/step10_resistance_panel.py` | never copied locally | — |
| `scripts/step11_batch_confounding.py` | never copied locally | — |
| `scripts/step12_codon_panel.py` | never copied locally; the codon panel could not be reproduced | — |
| `results/xtx_all_snps.csv` | only the superseded 3,359-row scan existed locally | 3,916 rows; md5 `14ee58aba477e1d229300a6c60aa02f0` matches the server byte for byte |
| `results/treemix_treeout_all.txt` | raw TreeMix output absent | reproduces `RAW_LOG_EXTRACTS.txt` exactly, incl. the `<2.22507e-308` sentinel |
| `results/model_selection.json`, `model_comparison.csv`, `likelihood_by_m.tsv`, `residuals_m2.csv`, `residuals_m3.csv` | absent | — |

## TreeMix: the `-se` doubt is refuted, and every printed p-value is explained

> **Superseded in part — read the “Numerics” section under Round 5 before using this one.**
> This account calls the two zero sentinels an *underflow*; they are not. The true tails are
> representable, and what rounds to zero is `1 - fl(Φ(z))`. This section also treats the
> reproduction as categorical evidence about the generating run: the later section narrows that to
> twelve of fifteen values at full displayed precision, with the rest consistent with rounded
> inputs, and to evidence that jackknife standard errors were computed rather than identification
> of a build, command or lineage.

An earlier version of this file claimed that "five of six reproduce to three significant
figures". That was wrong. The corrected accounting, over all 15 migration edges in m = 0–5:

| | |
|---|---|
| finite printed values | 13 |
| reproduce to 3 significant figures | **10** |
| underflow sentinels (`< 2.22507e-308` = DBL_MIN) | 2 — m=3 edge 2 and **m=4 edge 2** |
| finite but imprecise | 3 — m=1 e1 (0.8%), m=2 e2 (14.2%), m=5 e2 (3.1%) |

All five deviations share one cause: the upper tail is computed as 1 − Φ(z) in double
precision. Near z = 8 the CDF is within about one ulp of 1, so the subtraction destroys
the significand. Evaluating `1 - fl(Φ(8.060))` in float64 returns **3.330669e-16** — the
printed m=2 value to every digit printed — against a true tail of 3.8147e-16. Beyond
z ≈ 9.4 the same subtraction underflows to exactly zero, producing the two sentinels
(m=3 z=10.53, true tail 3.182e-26; m=4 z=9.33, true tail 5.447e-21).

This is stronger evidence than a digit count. Every printed value, sentinels included, is
reproduced by a normal tail computed from the printed mean and SE through that
formulation — in the m=2 case bit for bit — which a run that had not computed jackknife
standard errors could not produce. So `-se` ran, whatever the local script snapshot says.
Nothing reported depends on the anomalies: both sentinels belong to m=3 and m=4, neither
of which is reported.

`model_selection.json` also shows the m = 2 choice is not decided by p-values alone:
the stated variance-explained rule picks **m = 3** over the full 0–5 sweep (0.99966 ≥ 0.998)
and m = 2 only after the range is capped at 2 on identifiability grounds. The two criteria
disagree. The manuscript now says so.

## pfk13 Asn458Asp — consistent with a real variant in the release’s called fields

Codon 458 draws on Pf3D7_13_v3 1,725,626 / 1,725,625 / 1,725,624.

- 1,725,625 — no variant record.
- 1,725,624 — REF A, ALT T, **FILTER_PASS = False**, numalt 1, **zero** non-reference carriers among the 1,900.
- 1,725,626 — REF T, ALT [A, C], FILTER_PASS = True, **numalt 2** (which is why the `numalt == 1`
  ingest mask excluded it from the genome-wide matrix).

Isolate **PF0106-C** is homozygous for ALT 2 (C): `AD = [0, 0, 40]`, `DP = 40`, `GQ = 99`.
Forty of forty reads support the allele. On the minus strand C → G, turning AAT into GAT = Asp.

The call is real. It is **not** the validated allele: WHO validates **N458Y** (AAT→TAT), a
different substitution at the same base. Codon 458 is therefore 0.9995 reference, not fixed,
and no WHO-screened artemisinin marker is observed.

## New finding: the codon panel bypasses FILTER_PASS, not just numalt

Stage 12 reconstructs codons from every variant record at a panel position, iterating all
ALT alleles without consulting `FILTER_PASS`. Bypassing `numalt == 1` was the deliberate fix;
bypassing `FILTER_PASS` came with it and was never disclosed.

Audit of all 171 panel positions: **29 records fail the release filter**, at 29 distinct
positions. Among the 1,900 isolates, **six** non-reference calls derive from them, at three
positions — all in *pfk13*, all at WHO-validated marker codons:

| position | codon | marker | carriers | effect |
|---|---|---|---|---|
| 1,724,975 | 675 | A675V | 4 | ALT G → codon CCT = **Pro**, non-synonymous but ≠ validated Val; all four heterozygous → codon uncalled |
| 1,725,315 | 561 | R561H | 1 | all ALTs synonymous (CGT → CGG/CGC/CGA = Arg); the one homozygous call correctly counts as Arg561 |
| 1,725,339 | 553 | P553L | 1 | ALTs synonymous (CCG → CCA/CCT = Pro); carrier heterozygous → uncalled |

**No reported panel residue changes, and no screened WHO resistance residue is produced by
any filter-failing record.** Codon reconstruction was verified against the reference FASTA
rather than inferred from marker names.

One caveat travels with this: the four codon-675 carriers have well-supported minor alleles
(22–28% of 173–435 reads at GQ 99), so codon 675's denominator of 1,845 is the panel's lowest
and its exclusions are not random with respect to genotype.

## Reference list

42 entries, each checked against a primary source (publisher deposit, journal JATS, archive
record, or issuing organisation) rather than a citation aggregator. Eight corrected; three
substantive — Otto et al. (2018) ended on the wrong author (Newbold, author 23 of 24, where
APA requires the final author Berriman); Pf7 is published under "MalariaGEN", not the expanded
form used on Pf8; Virtanen et al. (2020) omitted the group author "SciPy 1.0 Contributors".
Two editorial decisions recorded: the scikit-allel Zenodo "pyup.io bot" creator is omitted as
an automated contributor, and Amambua-Ngwa et al. (2019) author 14 follows the published
metadata ("Kolapo, O.") rather than being corrected by inference.


## Round 4 — empirical answers to the source-level concerns

The second review raised two correctness concerns in the supplied scripts and said their
effect "requires the input data". Both were run against the input data.

**step12 reconstruction input domain.** The concern is real as code: a record whose ALT
differs in length from REF is skipped by a `continue` while the isolate stays called, so it
would be reported with the reference-derived residue. Three further limits travel with it —
the spanning-deletion allele `*` has length 1 and therefore *passes* the length test where
REF is a single base, equal-length multi-base records contribute only their first base, and
records are retrieved by anchor position only.

Audited over all 171 panel positions and all 1,900 isolates: of the 125 records sitting
exactly at panel positions, 16 carry a length-changing ALT and 2 have a multi-base REF;
19 records with a multi-base REF span a panel position other than their own anchor — of which
**16 are genuinely anchored outside the panel and three are themselves anchored at panel positions**,
so the “off-anchor” category as originally named over-counted by three. Genotypes were fetched for
all 32 affected records. Three have any homozygous non-reference carrier, and **in every case the carriers
sit on a supported, equal-length allele**:

| record | codon | carriers | on | unsupported alleles |
|---|---|---:|---|---|
| Pf3D7_07_v3:403625 | *pfcrt* 76 | 133 | ALT1 `C` | 55-base insertion: 0 |
| Pf3D7_07_v3:404836 | *pfcrt* 271 | 138 | ALT1 `GAACGTAAGA` | `*` and `C`: 0 each |
| Pf3D7_08_v3:549666 | *pfdhps* 431 | 26 | ALT1 `G` | `*` and 20-base insertion: 0 |

No isolate anywhere in the panel carries a length-changing allele as a homozygous call. Of the 62
mixed calls at these records, **58 fall at records the reconstruction actually selects** (it selects by
panel anchor) and are excluded by its mixed-call rule; the remaining **four fall at genuinely off-anchor
records, which the reconstruction never reads**, so the mixed-call rule is not what excludes them and
the archived aggregate logs do not show what does. That is an evidence gap, not a demonstrated error. Counts
reconcile exactly with the reported table (Lys76Thr 133, Gln271Glu 138, Ile431Val 26;
homozygous-reference 1,741 and 1,735 against reported 1,741 and 1,735). No residue anywhere
in the panel is `X`, which is consistent with no spanning deletion having been substituted —
though it is the panel’s own output checked against itself, not independent confirmation.
Both multi-base REF records differ from the reference at their first base only. None of the
57 codons is record-free. **Real defect; no effect on any published number that this evidence reaches.** The qualification
matters: the per-allele checker archived here covers the two records that carry both supported and
unsupported alleles, while the carrier conclusion spans three, and the four off-anchor mixed calls are
not covered at all. Nothing here shows a published frequency to be wrong; neither does it close the
question for every branch.

**step11 Fws denominators.** Also real as code: §3 compares Fws to the threshold without
dropping NaN, and `NaN < 0.95` is False, so missing values would sit in the denominator as
monoclonal, while §2 drops them first. But the script reads `results/sample_qc_full.csv`,
in which **Fws is missing for 0 of 4,905 rows** (and 0 of 1,900 in the analysis set). Both
conventions give bit-identical results; the recomputation reproduces
`results/batch_within_zone_tests.csv` exactly, and no manuscript number moves. **Real defect,
provably dormant.** It is reachable, though: `step03b_sample_qc.py` merges an external Fws
table with `how='left'`, so a future run with an incomplete table would activate it silently.

**Stale numbers found and corrected.** §3.14's leave-one-region-out paragraph quoted
p-values of 0.0048, 0.0155, 0.0543, 0.0645 and 0.3307, which came from the superseded
3,359-SNP run and match no current file. The live values (md5 `779b9e37…`) are Ashanti
0.014, Brong Ahafo 0.0398, Central 0.0427, Eastern 0.1355, Upper East 0.218, Greater Accra
0.2324, Volta 0.0097 — four below 0.05, the same four below 0.10. The paragraph had been
carrying both the stale and the corrected figures side by side.

## Round 5 — concept-level sweep

The third review named about twelve defective statements. Rather than fix those, the
manuscript was swept **by concept** — nine agents, each hunting one defect idea across all
fifteen sections in every phrasing it could find, followed by an adversarial pass that
rejected proposals failing a verbatim-presence or correctness check.

That found **93** instances, of which 75 survived verification and were applied, plus nine
further edits made directly. The named instances were a minority of every category:

| Concept | Reviewer named | Found | Applied |
|---|---:|---:|---:|
| "empirical FDR" label and "exact permutation" p-value | 2 | 17 | 17 |
| TreeMix edge count / identifiability "resolved" | 3 | 16 | 16 |
| Reproducibility and restoration overstatement | 5 | 18 | 14 |
| "Holding zone constant, only study varies" | 2 | 12 | 12 |
| Literal un-rendered markup | "a small number" | 14 | 11 |
| POD described as MAF-matched | 1 | 3 | 3 |
| Low FST as an upper bound on true differentiation | 1 | 2 | 2 |

**The MAF case is the instructive one.** Section 5.6 said the pseudo-observed set is not
MAF-matched; Section 6.8 said calibration used "the same MAF filter as the observed data";
and an Appendix B note asserted the wording "has been removed from Sections 5.6, 6.8 and
8.1". Two earlier rounds had searched for the string `MAF-matched` and so corrected the
places that used it while leaving the place that did not — and then recorded the job as
done. All three are now corrected, and the Appendix B note records why the variant phrasing
survived.

**Numerics.** The review was right that "underflow" was the wrong word: the true tails
(5.45 × 10⁻²¹ and 3.18 × 10⁻²⁶) are far above the smallest normal double. Working through
the correct mechanism strengthened the result. Immediately below 1 the doubles are spaced
1.1102 × 10⁻¹⁶ apart, so Φ(z) is quantised and the tail recovered by 1 − Φ(z) can only take
those values:

| z | `1 − fl(Φ(z))` | TreeMix printed |
|---:|---|---|
| 7.843 | 2.220446e-15 | 2.22045e-15 |
| 8.060 | 3.330669e-16 | 3.33067e-16 |
| 8.038 | 4.440892e-16 | 4.44089e-16 |
| 9.327 | 0 | `<2.22507e-308` |
| 10.529 | 0 | `<2.22507e-308` |

All fifteen outcomes reproduce to three significant figures under that formulation, and **twelve of
the fifteen — ten finite values and both zeroes — reproduce at their full displayed precision**. The
remaining three are moderate p-values, not the extreme-tail cases: model 2 edge 1, for instance,
recalculates to 0.000747669 against a printed 0.000747653. Those residuals are consistent with the
printed means and standard errors being themselves rounded, so an earlier claim here that all fifteen
reproduce *exactly* was too strong and is withdrawn. Numerical compatibility of this kind is evidence
that jackknife standard errors were computed; it does not identify a particular build, command
invocation or generating lineage.

**Callability, quantified.** The earlier statement that no codon is record-free was true but
misleading. Of the 171 panel positions, **46 carry no variant record**, so the reference base
is read there for every isolate regardless of coverage; per codon, 21 have a record at all
three positions, 26 at two and 10 at only one. No per-isolate depth field is consulted
anywhere in the reconstruction. Source: `audit_scripts/check_coverage.py`.

**Audit evidence archived.** The scripts and captured output behind the read-level and
input-domain checks are now under `audit_scripts/` and `audit_logs/`, with a README stating
what they do and do not establish. They run against the public Pf8 store, so they can be
re-executed; they are not an independent examination of read alignments, and they do not
establish that the archived outputs were produced by the archived scripts.

# Round 6 document and helper corrections

The current working record and article now describe very low, detectable differentiation at
retained common variants and its stability across the tested filters. The interpretation was
propagated through abstracts, answers, tables and correction narratives; it does not estimate
the mating system, contemporary exchange or the adequacy of a sparse sampling design.
TreeMix summary answers now carry the same fixed-graph qualification as the methods. Earlier
panmixia interpretations remain only as explicitly withdrawn history or excluded inferences.
Scientific numbers, analysis scripts, output tables and figure bytes were preserved.

The unsupported Table 6.8 pointer in the canonical-panel cascade paragraph was removed rather
than assigned a speculative replacement. The two unfinished caption sentences were removed.
Current Git tracking is distinguished from the still-unestablished exact generating state of
historical runs. The supplement was regenerated from the working record and the article from
its Markdown source; neither derivative was patched independently.

The editor now counts exact and spacing-variant matches together, validates occurrence indices,
and prevents quotes from crossing paragraph, cell or displayed-control boundaries. The article
builder validates retained package dependencies before replacement and rejects paths that
overlap or alias its disposable work directory. Primary regression suites passed 49 editor
checks and 38 builder checks; independent follow-up suites passed 14 and 30 respectively.
These checks concern document helpers, not statistical calibration or full OOXML-schema/image
validation. The existing Lean reference proofs were unchanged; no implementation-refinement
proof or complete historical input/command lineage was added.

Rendered-page review also found headings alone at page ends. Pagination flags were added to the
three used heading styles in the working record and to article-builder headings, and article
table headers repeat across page breaks. These formatting changes preserve all paragraph text.

Edit plans, independent reviews, source identities and build evidence are archived in
`verification_fixes_round6/`. PDF synchronization and visual review are recorded there after
the final rebuild. The six findings are assessed individually in its correction record; this
entry does not certify every claim in the full analysis or fill publication placeholders.

# Round 7 confirmed corrections and propagation

The surveillance correction in Table F.2 now matches the narrower common-variant conclusion
in the body. Table 8.1 states that differentiation is very low but detectable, and Section
10.1 explicitly marks the historical near-panmixia label as withdrawn. These are wording and
correction-record changes, not new estimates of a mating system or sampling adequacy.

The fixed-codon contradiction was corrected in Table 10.2 and, after page review located
equivalent wording, in Table 5.2 and Section 5.7.3. Section 6.9.8 already excepted codon 458
and now states the count explicitly as twenty-two fixed codons. The codon-458 exception,
existing rounded frequencies, callability qualifications and sampling dates are preserved.
There are seven local paragraph substitutions in the working record; the supplement is
regenerated from that record. All digit-containing numeric tokens and figure bytes are retained.

The article's first citations and physical tables now follow the order 1, 2, 3, 4. Table 2
identifies its count columns as the first and second zones in each pair. Both generated
documents derive their searchable metadata titles from their visible titles.

The article assembler now creates a unique, exclusive sibling archive and writes and validates
through its original descriptor. A pre-existing legacy temporary path is not opened or removed.
Failure checks cover unrelated symlinks, archive/validation/fsync/replacement failures and
detected temporary-path substitution. An independent follow-up also resolved inconsistent
matching of URI-encoded core-properties declarations. Nine review utilities resolve Git from
an explicit PF8_GIT override or PATH instead of a particular machine's cache path; isolated
imports are anchored to each script's location. Historical review assertions remain snapshots
of their original revisions rather than assertions about every later working tree.

Initial and follow-up edit plans, scratch regressions, independent reviews, exact source hashes,
rendered-page reviews and PDF publication evidence are preserved in verification_fixes_round7.
The initial document review is retained as a bounded intermediate record; the final follow-up
review supersedes it for delivery. Scientific calculations, archived data/results, canonical
facts and Lean reference proofs are unchanged. These corrections do not supply historical
generating commands or a Python-to-Lean implementation-refinement proof, and they do not fill
the article's author, funding, contribution or repository placeholders.
