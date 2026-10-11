# Corrections and new results

Produced 2026-10-10, after an adversarial multi-agent audit of the original analysis
(see `EVALUATION_REPORT.md`: 110 findings raised, 61 confirmed by three-lens verification).
This document records what was **re-run and verified**, and supersedes the corresponding
parts of `Pf8_Ghana_spatial_genomics_working_manuscript.docx`.

Everything below was checked against primary outputs, and the marker panel was additionally
cross-validated against MalariaGEN's independently published calls.

---

## 1. The headline negative was a filter artefact

The manuscript states, in the abstract and §6.8, that *"no validated antimalarial resistance
locus appears among the outliers"*, and interprets that absence biologically.

**It was not a biological result.** `step03a_fetch_callset_zarr.py` builds the genome-wide
callset under `FILTER_PASS & is_snp & numalt == 1`. In Pf8, almost every canonical resistance
codon is multiallelic or carries a spanning-deletion ALT, so the mask dropped them silently
before any analysis ran.

Verified directly against the Pf8 Zarr:

| Codon | PASS | is_snp | numalt | Kept by the filter? |
|---|---|---|---|---|
| *pfcrt* K76T | yes | **false** | 2 | no |
| *pfcrt* M74I | yes | **false** | 3 | no |
| *pfmdr1* N86Y | yes | **false** | 3 | no |
| *pfdhps* K540E | yes | true | **2** | no |
| *pfdhps* A581G | yes | **false** | 2 | no |

Across the nine panel genes: **13,367 PASS records, of which the filter keeps 3,330 — 10,037
were dropped**, including every canonical codon. Of the 21 canonical codons that are actually
polymorphic in this sample, **only 6 were visible to the original scan**.

---

## 2. New result: resistance marker frequencies by zone

A new script, `scripts/step10_resistance_panel.py`, re-fetches the nine panel genes with no
`numalt` restriction, resolves each annotation to its ALT allele via `ANN_Allele`, applies the
same majority-allele ploidy rule as Step 4a, and reports Wilson confidence intervals.
1,900 isolates; 44 canonical codons genotyped, 21 polymorphic.

| Gene | Variant | In original scan? | Overall | Coastal | Forest | Guinea | Transitional | χ² p |
|---|---|---|---|---|---|---|---|---|
| *pfdhfr* | Ser108Asn | **no** | 0.908 | 0.971 | 0.958 | 0.884 | 1.000 | **6.9e-07** |
| *pfdhfr* | Cys59Arg | yes | 0.886 | 0.946 | 0.928 | 0.864 | 1.000 | **4.6e-05** |
| *pfdhfr* | Asn51Ile | yes | 0.786 | 0.892 | 0.800 | 0.764 | 0.880 | **2.6e-04** |
| *pfmdr1* | Tyr184Phe | **no** | 0.677 | 0.663 | 0.652 | 0.683 | 0.800 | 0.384 |
| *pfaat1* | Ser258Leu | yes | 0.609 | 0.824 | 0.735 | 0.544 | 0.640 | **2.0e-18** |
| *pfmdr2* | Ile492Val | **no** | 0.550 | 0.461 | 0.548 | 0.561 | 0.720 | 0.018 |
| *pfdhps* | Ser436Ala | **no** | 0.540 | 0.468 | 0.490 | 0.559 | 0.800 | **8.9e-04** |
| *pfdhps* | Ala613Ser | **no** | 0.109 | 0.108 | 0.072 | 0.117 | 0.160 | 0.099 |
| *pfap2mu* | Ser160Asn | **no** | 0.097 | 0.078 | 0.071 | 0.107 | 0.080 | 0.171 |
| *pfmdr1* | Asn86Tyr | **no** | 0.088 | 0.035 | 0.081 | 0.097 | 0.120 | 0.029 |
| *pfcrt* | Arg371Ile | **no** | 0.084 | 0.069 | 0.107 | 0.080 | 0.160 | 0.160 |
| *pfcrt* | Met74Ile | **no** | 0.079 | 0.054 | 0.104 | 0.076 | 0.160 | 0.071 |
| *pfcrt* | Asn75Asp | **no** | 0.079 | 0.054 | 0.104 | 0.076 | 0.160 | 0.071 |
| *pfcrt* | Lys76Thr | **no** | 0.079 | 0.054 | 0.107 | 0.075 | 0.160 | 0.049 |
| *pfcrt* | Gln271Glu | **no** | 0.079 | 0.054 | 0.104 | 0.075 | 0.120 | 0.138 |
| *pfcrt* | Ala220Ser | **no** | 0.074 | 0.054 | 0.107 | 0.068 | 0.120 | 0.046 |
| *pfcrt* | Ile356Thr | yes | 0.016 | 0.029 | 0.036 | 0.009 | 0.000 | 0.002 |
| *pfdhps* | Ala581Gly | **no** | 0.014 | 0.034 | 0.027 | 0.007 | 0.040 | **8.3e-04** |
| *pfmdr1* | Asp1246Tyr | yes | 0.011 | 0.020 | 0.006 | 0.011 | 0.040 | 0.260 |
| *pfdhps* | Lys540Glu | **no** | 0.010 | 0.005 | 0.006 | 0.012 | 0.000 | 0.596 |
| *pfcrt* | Asn326Ser | yes | 0.008 | 0.000 | 0.003 | 0.011 | 0.000 | 0.218 |

χ² p tests heterogeneity of allele frequency across the four zones. **Bold** = p < 0.001.
Full output: `results/resistance_panel_frequencies.csv` (4,138 protein-changing alleles) and
`results/resistance_panel_canonical.csv`.

### What this shows

- **Antifolate resistance is near-fixed.** The *pfdhfr* triple mutant (N51I / C59R / S108N) sits
  at 0.79–0.91, and all three are significantly higher in the south than in Guinea savanna.
  *pfdhps* A581G and K540E remain rare, which is the standard West African pattern.
- **Chloroquine resistance has largely reverted.** The full CVIET *pfcrt* haplotype
  (M74I, N75D/E, K76T, A220S, Q271E, R371I) travels together at ~0.074–0.084, consistent with
  post-withdrawal reversion to wild type.
- **No artemisinin resistance.** All 14 validated *pfk13* codons — including C580Y, R561H, R539T,
  I543T and P441L — are at **0.000** in all 1,900 isolates. MalariaGEN's own `kelch13` column
  independently agrees: of 36 isolates with a called status, the commonest change is A578S, which
  is explicitly non-resistance. This is now a genuine tested negative rather than an untested one.
- ***pfaat1* S258L is the standout.** 0.824 coastal → 0.544 Guinea savanna, χ² p = 2 × 10⁻¹⁸.

---

## 3. *pfaat1* S258L — the result the manuscript buried

The manuscript reports this as *"amino acid transporter AAT1 (PF3D7_0629500, two outlier SNPs,
maximum XtX 24.44)"*, an anonymous transporter in a table, while the abstract simultaneously
says no validated resistance locus was found.

Verified from Pf8's own annotation:

- `Pf3D7_06_v3:1215233` = **Ser258Leu**, `missense_variant`, MODERATE impact, XtX 24.44.
  This is the exact variant Amambua-Ngwa et al. (2023, *Nature Microbiology*) edited into
  parasites and showed raises chloroquine resistance — and which the thesis proposal names twice.
- `Pf3D7_06_v3:1214350` = **Ile552Ile**, `synonymous_variant`, LOW impact, 883 bp away.
  So the "two outlier SNPs" are **one signal plus a linked synonymous site**, not two
  independent lines of evidence.
- It is absent from `config.KNOWN_RESISTANCE_LOCI`, which is why it surfaced unflagged.

The cline should be discussed against **amodiaquine**, not chloroquine: Ghana's first-line
artesunate–amodiaquine maintains 4-aminoquinoline pressure, and S258L carries a reported
fitness cost, which is why a cline rather than fixation is the expected post-withdrawal state.

---

## 4. Corrected numbers

| Quantity | Manuscript | Corrected | Why |
|---|---|---|---|
| BayPass XtX threshold | 11.232 | **11.047** | 8-thread BayPass is non-deterministic despite `-seed 42`; two runs gave 15 vs 16 outliers. Now single-threaded and bitwise stable. |
| BayPass outliers | 15 | **17** | same |
| Region Mantel | r = 0.400, p = 0.029 | see Addendum 2 — the values moved with the larger SNP panel | 4 negative *F*<sub>ST</sub> pairs were silently floored to zero at `step06_mantel.py:148`. On the 3,359-SNP matrix the censoring was what carried the result across p < 0.05 (0.051 → 0.030). **On the final 3,916-SNP matrix it no longer is** — see below. |
| Zone Mantel | r = 0.578, p = 0.090 | r = 0.578, **p = 0.084** | permutation test now seeded; previously irreproducible |
| ADMIXTURE zone effect | "no ancestry structure aligned to geography" | **Kruskal–Wallis H = 112.2, p = 3.6 × 10⁻²⁴** | never tested. Zone explains ~2% of minor-component variance — tiny, but real and ordered like *F*<sub>ST</sub>. |
| *F*<sub>ST</sub> CIs spanning zero | "two of six" (abstract) | **three of six** | abstract contradicts §6.4 |

### Isolation by distance: weaker than claimed, but not as weak as the interim figures suggested

Added to `step06_mantel.py`. **These are the final 3,916-SNP values** — the interim ones computed
on 3,359 SNPs were materially worse, and are superseded.

Significant in **4 of 7** region replicates (0 of 4 at zone level):

| Dropped region | r | p |
|---|---|---|
| Brong Ahafo | +0.609 | 0.040 |
| Ashanti | +0.568 | 0.014 |
| Volta | +0.546 | 0.010 |
| Central | +0.396 | 0.043 |
| Eastern | +0.288 | 0.136 |
| Greater Accra | +0.250 | 0.232 |
| **Upper East** | **+0.260** | **0.218** |

Dropping Upper East still removes significance, so the result remains substantially a single
north–south contrast rather than a smooth distance gradient, and should be described that way.
But it is more robust than the 3,359-SNP version implied (which was significant in only 2 of 7).

---

## 5. Validation of the new panel

Cross-checked against `Pf8_drug_resistance_marker_genotypes.tsv`, MalariaGEN's own published
calls for the same 1,900 isolates: **21 of 23 markers agree within 0.03**, most to three decimals.

The two flagged are the same codon, *pfcrt* 75: Pf8's SnpEff annotation labels the ALT Asp while
MalariaGEN calls it Glu, at an identical frequency (0.079 vs 0.070) and within the same CVIET
haplotype. This is a naming discrepancy, not a data disagreement; **MalariaGEN is correct on the
biology** (N75E is the CVIET residue) and should be followed in any write-up.

> A bug this cross-check caught in my own new script: SnpEff emits one annotation per
> (ALT, transcript) pair, so annotation column *a* is **not** ALT allele *a*. The first run
> reported *pfmdr1* N86Y as "Asn86Asp" and Y184F as "Tyr184Ser" — right frequencies, wrong
> names. Fixed by resolving the index through `ANN_Allele`. The table above is post-fix and
> post-validation.

---

## 6. Changes made to the pipeline

| File | Change |
|---|---|
| `scripts/step10_resistance_panel.py` | **new** — multiallelic-aware marker panel with Wilson CIs |
| `scripts/step06_mantel.py` | seeds the permutation test; names the censored pairs; reports r/p censored **and** uncensored; adds leave-one-out jackknife; records all of it in the JSON |
| `scripts/step08b_baypass.sh` | `NTHREADS` default 4 → **1**, with the reason in a comment |
| `scripts/run_all.sh` | parallel mode exports `NTHREADS=1` for BayPass |

Previous 8-thread BayPass outputs archived to `results/baypass_8thread_archive/`.

---

## 7. Still outstanding

Confirmed by the audit, not yet acted on:

1. **Filter order** — variant missingness is measured over 117 isolates that are then dropped.
   Reordering yields ~3,700 SNPs instead of 3,359, at identical thresholds, for free.
2. **TreeMix has no inferential support** — run without `-se`, so no edge standard errors or
   p-values exist. Three of six off-diagonal covariances have |z| < 2.
3. **Study/batch confounding** — a fourth design confounder, unlisted in the manuscript. No
   sequencing study contributes isolates to both Coastal and Guinea savanna, the pair behind
   every headline number.
4. **No FDR accounting** for the XtX outliers; ~3.4 false positives are expected among 17 at a
   0.999 threshold over 3,359 SNPs.
5. **Surveillance claim in §7.4** is contradicted by the project's own literature review.
6. **ghanaAEZ.geojson provenance** is still undocumented — a publication blocker.

### What this means for the thesis

Objective 3 — zone-specific variants relevant to drug response — was reported as a null result.
It is not. The markers are measurable, they are measured here, and two of them show significant
zone structure: the *pfdhfr* triple mutant (higher in the south) and *pfaat1* S258L (a 28-point
coastal-to-northern cline). Meanwhile the *pfk13* negative is now a real tested finding rather
than an artefact. That is a substantially stronger position than the manuscript currently claims.

---

# Addendum: the remaining six fixes

Added 2026-10-10. Items 1–4 below required code changes and a re-run of stages 4–9;
items 5–6 are documentation. All code is on the server in `scripts/`.

## A. Study/batch confounding — a fourth design limit, now quantified

New script `scripts/step11_batch_confounding.py`. Pf8 isolates arrive through named
partner studies, and in Ghana those studies are almost perfectly nested within zones.

**Four of six zone pairs have no sequencing study in common** — including the pair behind
every headline number:

| Zone pair | Studies in common |
|---|---|
| Coastal savanna vs **Guinea savanna** | **0** ← max *F*<sub>ST</sub>, and the polyclonality contrast |
| Coastal savanna vs Transitional | 0 |
| Deciduous forest vs Guinea savanna | 0 |
| Deciduous forest vs Transitional | 0 |
| Coastal savanna vs Deciduous forest | 2 |
| Guinea savanna vs Transitional | 1 |

Each zone is also dominated by one study: Transitional is **100%** one study
(1083-PF-GH-CONWAY, 50/50), Coastal 89%, Guinea savanna 74%, forest 48%.

**Batch effects are demonstrable, not hypothetical.** Holding zone constant, so only batch
varies: within Guinea savanna, call rate differs between its six studies at **p = 2.8 × 10⁻¹⁹⁷**;
within deciduous forest, at p = 7.7 × 10⁻⁸⁸, and the polyclonal fraction ranges 0.430–0.578
between studies (Kruskal p = 0.002).

**Partial mitigation, reported in fairness.** Both zone pairs that *do* share a study reproduce
the overall direction of the polyclonality difference — within 1083-PF-GH-CONWAY, Guinea savanna
is more polyclonal than Transitional (0.532 vs 0.500), matching the overall ordering. So the
gradient is not purely an artefact; it is simply not separable from batch for the pairs that
carry the largest differences.

Outputs: `results/batch_study_by_zone.csv`, `batch_zone_pair_overlap.csv`,
`batch_within_zone_tests.csv`.

## B. Filter order — `step04a_prepare_callset.py`

Variant missingness was measured over 2,017 isolates, 117 of which were then dropped, so every
SNP was charged for isolates that did not survive. Now two-pass: the sample cut is decided on the
same provisional variant set as before (so the same isolates drop), then variant missingness is
recomputed on the isolates that remain. Identical thresholds, identical sample set, more SNPs.
Implemented blockwise so the provisional subset is never materialised.

## C. TreeMix standard errors — `step07b_treemix.sh`

The sweep ran without `-se`, so every migration line in `.treeout` read `weight NA NA NA` and no
edge could be tested. `SE=1` is now the default, which produces jackknife means, standard errors
and p-values per edge.

## D. False-discovery accounting — `step08c_calibrate_xtx.py`

A 0.999 quantile is not a significance test: 0.1% of neutral SNPs clear it by construction. The
step now reports expected false positives at the threshold, an empirical FDR, per-SNP p-values
against the POD null, Benjamini–Hochberg q-values written into `xtx_all_snps.csv`, and counts at
q ≤ 0.01/0.05/0.10/0.20 — plus how many of the quantile outliers also survive FDR 10%.

## E. The §7.4 surveillance claim — manuscript text

§7.4 concludes that *"sentinel surveillance at a small number of sites is an adequate design for
detecting emergence"*. The analysis does not support this, and **the project's own literature
review argues the opposite mechanism**: selection builds connectivity that neutral demography does
not, so resistance-allele trajectories can be site-specific even under neutral panmixia.

Low genome-wide neutral *F*<sub>ST</sub> licenses a claim about **neutral** structure only.
Marker-frequency representativeness — which is what sentinel surveillance actually measures — is a
separate question, and §2 of this document shows marker frequencies *do* differ by zone
(*pfdhfr* triple mutant p ≤ 2.6 × 10⁻⁴; *pfaat1* S258L p = 2 × 10⁻¹⁸).

Replace with: *"neutral common-variant differentiation between zones is negligible, so a spatially
sparse design is adequate for characterising neutral structure. Marker-frequency
representativeness is a separate question, and the resistance panel in this analysis shows
significant between-zone variation at pfdhfr and pfaat1."* Remove the unqualified version from the
plain-language summary.

## F. `ghanaAEZ.geojson` provenance — resolved as far as it can be

**It is not citable as a published dataset.** Investigated and independently verified.

What the file is: 285,669 bytes, md5 `96b1a7f4da62d6f0153826f41af96152`, written by GDAL/OGR
(legacy `crs` member, clockwise rings, 15-digit coordinates, layer name `ghanaAEZ`). Its only
fields are `id`, `Name`, `AREA`, `PERIMETER` — **no attribution, source, author or date**. `AREA`
and `PERIMETER` as an uppercase pair are the auto-maintained attributes of an ESRI ArcInfo
coverage, so the lineage is coverage → shapefile → GeoJSON. Geometry is a clean topological
partition of Ghana; `AREA` totals 23,871,848 ha against Ghana's official 23,853,300 ha (+0.08%).

Where it came from: ArcGIS Online item `0776dae5c5314102bd03fdaab8df0356`, "Agro Ecological Zones
Ghana". I downloaded it and compared: **byte-for-byte identical**, md5
`96b1a7f4da62d6f0153826f41af96152` on both sides. So the identification is certain, not inferred.
I confirmed via the ArcGIS REST API that `licenseInfo` and `accessInformation` are both **null**,
and the owner is an anonymous personal account — empty display name, no organisation — created
two days before the upload. It is an unattributed re-host, not an origin.

> Do **not** attribute the layer to Wageningen University or to Climate Adaptation Services.
> Those names attach to other items in the same account and to a storymap *theme*, not to this
> file. Naming either as the author would be a fabricated citation.

Why no published scheme matches: Ghana's canonical MoFA/FAO classification is usually given as
five or six zones. This layer keeps the MoFA savanna/transition/coastal names but splits the
forest into "Wet evergreen" and "Moist evergreen" — high-forest *vegetation* types from the
Hall & Swaine lineage — and collapses the semi-deciduous zones into a single "Decidous forest",
a label the FAO/MoA vegetation table does not use. It is a hybrid of two different
classifications, plus a water body that is not a zone at all. Ruled out by direct checking: HDX,
data.gov.gh, GADM, Harvard Dataverse, Zenodo, figshare, FAO GAEZ, FAO Africover and ICPAC.

**Recommended handling.** Do not cite it as a dataset. Instead: (i) cite what was actually
accessed, flagged as an unattributed re-host, with the checksum for identity; (ii) cite the
*classification* separately — MoFA/FAO for the savanna zones, Hall & Swaine/FAO for the evergreen
split — noting the scheme is a hybrid; (iii) state the provenance gap as a limitation; (iv) ask
whoever supplied the original Colab notebook, whose `!wget` cells are the most likely surviving
record of a fetch URL; (v) email **cersgis@ug.edu.gh** (Centre for Remote Sensing and GIS,
University of Ghana) — the ArcInfo-coverage fingerprint points to a pre-2005 national coverage,
and CERSGIS is the most likely custodian. That is the one unexhausted lead.

Suggested interim wording, citing the data as accessed rather than as authoritative:

> *Agro ecological zones Ghana* [Data set]. (2025). ArcGIS Online.
> https://www.arcgis.com/home/item.html?id=0776dae5c5314102bd03fdaab8df0356

with a Methods sentence stating that the layer's original provenance and licence could not be
established, that it is verified by md5 `96b1a7f4da62d6f0153826f41af96152`, and that zone names
are reproduced verbatim — including the "Decidous forest" misspelling — because the spatial join
keys on them.

**A bonus finding.** The layer records Sudan savanna as **293,062 ha, just 1.2% of Ghana's land
area** — a sliver in the far northeast. The manuscript treats its absence from the sample as a
gap in the ecological gradient; the better explanation is that it is a very small zone that
Pf8's admin-level-1 sampling frame was never likely to capture.

**Robustness check worth doing (not yet done).** Because isolates join on admin-1 centroids, the
join could be repeated against an authoritative six-zone Ghana layer. If zone assignments are
stable, the provenance gap becomes a sensitivity result instead of a threat.

---

# Addendum 2: results after the corrected re-run

Stages 4–9 were re-run on 2026-10-10 with all fixes in place. **These supersede every
corresponding number above and in the manuscript.**

## G. A seventh defect, found by the re-run itself

Worth recording because it is the most dangerous kind. The `"skip if output exists"` guards in
`step05b`, `step07b` and `step08b` do not check whether the *input* changed. When the SNP set went
from 3,359 to 3,916, every stage regenerated its inputs — and then ADMIXTURE and TreeMix saw their
old output files, skipped the work entirely, and reported **"stage finished"**.

The evidence was in the timestamps: `ghana_pruned.bim` rebuilt at 01:27, `ghana_pruned.2.Q` still
dated 03:57 the previous day. Only stage 8 caught it, because `step08c` asserts that its position
table and the BayPass output have matching row counts — it failed loudly with the right diagnosis.
ADMIXTURE and TreeMix have no such assertion and failed silently.

All three guards now require the output to be **newer than its input**. Had the timestamps not
been checked, the previous day's ADMIXTURE and TreeMix results would have been reported as though
they came from the new matrix.

## H. Final corrected numbers

| Quantity | Manuscript | **Corrected** |
|---|---|---|
| SNPs in the analysis matrix | 3,359 | **3,916** (+16.6%, same 1,900 isolates) |
| Max pairwise *F*<sub>ST</sub> | 0.0024 | **0.0023** (Coastal–Guinea, SE 0.0005) |
| ADMIXTURE CV minimum | K = 2 (0.83736) | K = 2 (**0.83925**) vs K = 1 (0.84199) |
| XtX threshold | 11.232 | **10.840** |
| XtX outliers | 15 | **19** above threshold; **13** also pass FDR 10% |
| Expected false positives | not reported | **3.9 — empirical FDR 20.6%** |
| Outlier genes | 11 | **13** |
| TreeMix selection | m = 3 (full), m = 2 (identifiable) | **m = 2**, now with edge p-values |

### TreeMix finally has inferential support

With `-se`, the migration edges have jackknife standard errors and p-values for the first time:

| m | Edge weights | p-values |
|---|---|---|
| 1 | 0.313 (SE 0.040) | **2.2 × 10⁻¹⁵** |
| 2 | 0.152 (SE 0.048); 0.805 (SE 0.100) | **7.5 × 10⁻⁴**; **3.3 × 10⁻¹⁶** |
| 3 | adds 0.065 (SE 0.147) | **0.328 — not significant** |

**The data support exactly two migration edges.** The third is indistinguishable from zero. This
independently confirms the identifiability argument (four populations support ~2 edges) from the
statistics rather than from theory, and resolves the model-choice question the manuscript left
open: report m = 2.

### The outlier list is stronger and better qualified

13 genes, led by PTP7, **AAT1**, FIKK4.2, ACS8 and NT2. Both *pfaat1* SNPs now carry
**q = 0.0049**, so S258L survives FDR correction comfortably — it is not one of the ~4 expected
false positives. Newly appearing: REX2 (ring-exported protein 2) and two further exported
proteins, which strengthens the exported/host-interaction pattern noted in §6.8.

Of the 19 SNPs above the quantile threshold, **6 do not pass FDR 10%**. Report the 13 as the
finding and the 19 as a ranking.

### What did not change

The conclusions. *F*<sub>ST</sub> stayed ≈0.002, ADMIXTURE still shows a near-flat CV curve with a
negligible K = 2 improvement, and near-panmixia still holds. A 17% larger SNP panel and a correct
FDR did not move the headline — which is the most reassuring outcome available, and worth stating
in the manuscript explicitly as a robustness result.

### Correction to an earlier statement in this document

The Mantel figures quoted in §4 above (r = 0.381, p = 0.051 uncensored) came from the interim
3,359-SNP matrix. On the final 3,916-SNP matrix they move, and the conclusion changes:

| | 3,359 SNPs (interim) | **3,916 SNPs (final)** |
|---|---|---|
| negative *F*<sub>ST</sub> pairs floored | 4 | **3** |
| censored | r = 0.4000, p = 0.0298 | **r = 0.4269, p = 0.0252** |
| uncensored | r = 0.3807, **p = 0.0509** | **r = 0.4138, p = 0.0413** |
| significant leave-one-out replicates | 2 of 7 | **4 of 7** |

**The censoring no longer determines significance.** On the final matrix both the censored and
uncensored tests clear p < 0.05, so the undisclosed flooring is now a transparency problem rather
than a result-determining one. Both versions should still be reported, and the disclosure is
still required — but the IBD finding itself is better supported than the interim numbers implied.

This is itself an instance of the lesson running through this whole exercise: numbers quoted from
a superseded run are wrong even when the pipeline is right. Every figure in Addendum 2 and in this
correction was read from the final run's own logs, which are reproduced verbatim in
`proof_of_work/RAW_LOG_EXTRACTS.txt`.

---

# Addendum 3: response to the external critique (2026-10-10)

All five points of an external critique were upheld. Four of them identified defects in the
analysis code, not merely in the prose. A new script, `scripts/step12_codon_panel.py`, replaces
the marker panel entirely; every figure below comes from it.

## The root cause: identifying markers by annotation string

`step10` found markers by matching SnpEff's `ANN_HGVS_p` protein-change strings against a
hand-written list. That has two failure modes, and both occurred.

**(i) A resistance allele that IS the reference residue can never appear as an ALT change.**
The official Pf8 methodology states this outright, and we verified the sentence in the source
document: *"3D7 sequence translates as a G at 437, this is thought to be the mutant allele, i.e.
3D7 does not have the wild type allele."* So at *pfdhps* 437 the only annotation is `Gly437Ala` —
the revertant. Searching for "Ala437Gly" matched nothing, and **A437G was absent from the panel
entirely at a true frequency of 0.897**.

**(ii) A residue reachable only by two changes in one codon is never annotated.** *pfcrt* codon 75
carries two variants, 403621 (A>G, annotated `Asn75Asp`) and 403623 (T>A, annotated `Asn75Lys`).
Asn→Glu requires both. Neither annotation names N75E, which is the residue the CVIET haplotype
actually carries. This, not a "naming discrepancy", is the whole explanation of the MalariaGEN
disagreement reported in the previous version.

**The fix** reconstructs the codon: each requested codon is mapped to its three genomic positions
through the CDS, every variant record at those positions is collected regardless of `numalt` or
`is_snp`, each isolate's alleles are applied to the reference codon, and the result is translated.
The output is the **full residue spectrum including the reference residue**, so a resistance allele
cannot hide in the reference and a two-SNP residue cannot be missed. 57 codons across 9 genes;
mixed calls make a codon uncalled rather than being assigned a residue.

## 1. The *pfk13* panel, rebuilt from the WHO compendium

The previous panel used a list written from memory. It contained 13 distinct protein changes
(a duplicated M476I record inflated the apparent count to 14), included **P441L and C469F, which
are candidate not validated**, and omitted **P574L, G533S and R622I**. R622I was requested but
never retrieved, so it became a silent non-result.

The panel now covers **all 14 WHO-validated** artemisinin markers (F446I, N458Y, C469Y, M476I,
Y493H, G533S, R539T, I543T, P553L, R561H, P574L, C580Y, R622I, A675V) and **all 6 candidates**
(E252Q, P441L, C469F, N537I, G538V, V568G), classified per WHO v1.0 (December 2025).

**Result: every one of the 23 *pfk13* codons is fixed at the reference residue** in all 1,900
isolates (codon 458 at 0.999). The negative is now a tested result across the complete validated
set, not an artefact of an incomplete list.

> Two caveats the critique rightly demanded. The denominator is **per codon, 1,845–1,876 isolates
> called** out of 1,900, not "all 1,900 at every codon". And the sampling period is **2009–2021**,
> so this is a historical statement, not a current one.

## 2. *pfdhps* A437G recovered — and it changes the antifolate picture

| Zone | G437 frequency | 95% CI |
|---|---|---|
| Deciduous forest | 0.964 | 0.939–0.980 |
| Coastal savanna | 0.941 | 0.900–0.966 |
| Guinea savanna | 0.875 | 0.856–0.892 |
| Transitional zone | 0.800 | 0.609–0.911 |
| **Overall** | **0.897** | n = 1,892 |

χ² p = 1.2 × 10⁻⁶. This locus was **wholly absent** from the previous version.

## 3. Haplotypes reconstructed within isolates — the triple mutant is lower than implied

The previous version reported the *pfdhfr* "triple mutant" as the range of its three marginal
frequencies, 0.786–0.908. That is not a haplotype frequency. Counted on isolates called at all
three codons:

| Haplotype | Complete cases | Frequency | 95% CI |
|---|---|---|---|
| *pfdhfr* **IRN** (N51I+C59R+S108N) | 1,876 | **0.771** | 0.751–0.789 |
| *pfdhfr* IRNL (adds I164L) | 1,874 | **0.000** | 0.000–0.002 |
| *pfcrt* **CVIET** (72–76) | 1,873 | **0.071** | 0.060–0.084 |
| *pfdhps* GE (A437G+K540E) | 1,888 | **0.010** | 0.006–0.015 |

As the critique predicted, the true triple-mutant frequency (0.771) is **below the minimum
component frequency** on the same complete-case set (51I = 0.788). It is also not a near-fixed
single haplotype: NRN sits at 0.116 and the fully wild-type NCS at 0.091.

CVIET is genuinely a unit — the only two *pfcrt* 72–76 haplotypes observed are CVMNK (0.929) and
CVIET (0.071), with nothing intermediate — but that is now demonstrated rather than inferred from
six similar marginals.

## 4. Per-sample concordance replaces marginal agreement

The previous version cited agreement of marginal frequencies as validation. Call-by-call against
MalariaGEN's published genotypes, on isolates where both pipelines called:

**47,012 of 47,012 calls agree — 100.0000% across 25 markers**, including all nine *pfcrt* codons.
Codon 75 now agrees exactly, because reconstruction yields Glu where string-matching yielded Asp.

> The *kelch13* corroboration must be stated more weakly than before. Pf8 assigns a status over
> the whole 349–726 domain and classifies any missing call as undetermined ("Any missing call in
> amino acids 349-726 → Missing → Undetermined"), so only 36 isolates have a complete status.
> That is weak corroboration for per-codon calls on ~1,860 isolates, and the two should not be
> presented as equivalent evidence.

## 5. The AAT1 interpretation was wrong, and the error was mine

The previous version stated that the functional experiment did not test amodiaquine, and framed
the Ghanaian cline as maintained by amodiaquine pressure. Verified against the source:

- **Amodiaquine was tested.** Methods: *"Parasite IC50 values for CQ, amodiaquine, lumefantrine,
  mefloquine and quinine were measured…"*
- **The shifts were sub-threshold.** *"these IC50 value shifts were well below the threshold
  associated with clinical resistance"* (amodiaquine threshold 60 nM).
- **The authors reject the other-quinoline hypothesis.** *"The alternative hypothesis — that high
  frequencies of F313S mutations are driven by widespread use of other quinoline partner drugs in
  SEA — is not supported."* They conclude CQ was *"the primary selective force"*.
- **The effect is modest and background-dependent**: S258L raised CQ IC50 **1.5-fold**, in a single
  chloroquine-resistant Southeast Asian line (NHP4026), with epistasis between S258L and F313S and
  an explicit *pfcrt*-background caveat.
- The longitudinal 0%→97% rise is **Gambian**, 1984–2014. The paper says nothing about Ghana.

So S258L should be described as a variant with a demonstrated but modest, epistasis- and
background-dependent effect that *potentiates* chloroquine resistance — not as "the functionally
validated chloroquine-resistance variant". Amodiaquine may be presented only as an **untested
possible** contemporary driver, alongside historical persistence and the documented fitness cost.

## 6. Gene-level WHO labels removed

The WHO compendium classifies **variants, not genes**, and it contains **no validated or candidate
lumefantrine marker** — verbatim: *"The review did not identify any validated or candidate
molecular markers associated with lumefantrine resistance."* The label "*pfmdr1*, WHO-validated,
lumefantrine" is therefore a category error twice over.

Also: ***pfaat1*, *pfap2mu* and *pfmdr2* appear nowhere in the WHO compendium at any tier.** They
remain in the panel because they are scientifically interesting, but must not be described as
WHO-classified markers. *pfcoronin* is in the compendium, at the **potential** tier only.

## Outputs

`results/codon_panel_residues.csv` (57 codons, full residue spectrum by zone with Wilson CIs),
`codon_panel_haplotypes.csv`, `codon_panel_concordance.csv`, `logs/step12_codon_panel.log`.

## What this says about the process, again

This is the fourth consecutive round in which a correction contained its own defect. The pattern
is consistent: each layer was checked for internal consistency against our own outputs, and what
escaped was external correctness — whether the marker list matched an authoritative source,
whether the annotation direction matched the reference genome, whether a co-occurrence claim had
co-occurrence data behind it. The verification architecture was built to catch stale numbers, and
it did. It was not built to ask *"is this the right list?"*

---

# Addendum 4: the four outstanding robustness checks (2026-10-10)

All four were run. One of them **overturns a conclusion**.

## A. The isolation-by-distance result is not robust

`scripts/step13_sensitivity.py` loads the 2.19 M x 4,682 genotype matrix once and rebuilds the
analysis matrix under six threshold scenarios, recomputing pairwise *F*<sub>ST</sub> and the
region-level Mantel test for each. Both thresholds that drive the dataset were varied: the
*F*<sub>ws</sub> monoclonality cut (which discards 57% of isolates, unevenly by zone) and the MAF
floor (which discards 99.8% of sites).

| Scenario | Isolates | SNPs | max *F*<sub>ST</sub> | Mantel p | Significant? |
|---|---|---|---|---|---|
| **baseline** (*F*<sub>ws</sub> ≥ 0.95, MAF ≥ 0.05) | 1,900 | 3,916 | 0.00232 | **0.0252** | yes |
| *F*<sub>ws</sub> ≥ 0.90 | 2,196 | 3,629 | 0.00240 | 0.0874 | **no** |
| *F*<sub>ws</sub> ≥ 0.80 | 2,746 | 3,496 | 0.00255 | 0.1687 | **no** |
| no *F*<sub>ws</sub> filter | 4,403 | 3,275 | 0.00254 | 0.1792 | **no** |
| MAF ≥ 0.01 | 1,900 | 10,876 | 0.00204 | 0.0617 | **no** |
| MAF ≥ 0.02 | 1,900 | 6,852 | 0.00217 | 0.0467 | yes (marginal) |

**The Mantel result is significant in 2 of 6 scenarios.** It holds at the published thresholds and
at MAF ≥ 0.02, and fails at every relaxation of the *F*<sub>ws</sub> cut and at MAF ≥ 0.01. Taken
with the leave-one-region-out jackknife, which already showed significance in only 4 of 7
replicates and collapse when Upper East is dropped, **the isolation-by-distance finding should be
reported as not robust**, not as a supported result.

This is the manuscript's only positive spatial finding, and it does not survive the two checks the
audit said were most needed.

### What *is* robust

Near-panmixia. Maximum pairwise *F*<sub>ST</sub> ranges only **0.00204 to 0.00255** across all six
scenarios — a total spread of 0.0005 — against a range of sample sizes from 1,900 to 4,403
isolates and SNP counts from 3,275 to 10,876. The headline conclusion is insensitive to both
thresholds, which is the strongest evidence for it in the whole analysis.

Two secondary observations worth recording. Relaxing *F*<sub>ws</sub> slightly **raises**
*F*<sub>ST</sub> (0.00232 → 0.00255), so polyclonal isolates were not masking differentiation.
And tripling the SNP count via MAF ≥ 0.01 **lowers** it (0.00204), as expected if rarer variants
are less differentiated between zones.

## B. The outlier set is not an artefact

MQ, VQSLOD, FS, SOR, QD, ReadPosRankSum and `culprit` were pulled from the Pf8 Zarr for all 19
outliers and compared against the other 3,897 scanned SNPs. Per-SNP table in
`results/outlier_quality_check.csv`.

Every significant difference runs **in the outliers' favour**: higher VQSLOD (p = 0.008), QD
(p = 0.016) and QUAL (p = 0.007). No outlier has MQ < 50, strand bias, or read-position bias; all
19 are RegionType Core. The `culprit` field reads "MQRankSum" for all 19, but also for 99.6% of
the rest of the panel, so it carries no information here.

**The exported-protein concern is not supported.** The eight SNPs in PTP7, PIESP2, GEXP22, REX2,
PF3D7_0831400 and PF3D7_0221200 are the cleanest subset in the panel: FS = 0.00 for all eight,
MQ median 60.00, VQSLOD significantly higher than the rest. These families are repetitive, but
these particular sites are in uniquely mappable sequence.

**Two SNPs should be downgraded, for a different reason.** `Pf3D7_11_v3:1054078` (*SNRPF*) and
`Pf3D7_11_v3:1054447` (intergenic) are 369 bp apart and are the two lowest-InbreedingCoeff sites
in the panel; 1054078 carries **ExcessHet = 69.59, the only nonzero value among all 3,916 SNPs**
and roughly 400x the genome-wide maximum. In a near-haploid organism that points to collapsed
paralogy or copy-number variation, not to mismapping — MQ and FS are both clean. This matters
because 1054447 is the **fifth-ranked outlier in the scan**. Report both as lower confidence. The
mechanism is unverified; a read-level check (per-sample depth ratio against the genome median)
would settle it.

## C. Stage 3 re-run on the analysis set

The ordinations previously described the 4,905 pre-QC isolates while every other result described
1,900. `step03_umap.py` now takes `--samples` and `--suffix`, and re-slices the distance submatrix
rather than reusing the cached full-set one. Outputs carry a `_qcset` suffix so the published
figures are untouched.

| Metric | 4,905 pre-QC (published) | 1,900 analysis set |
|---|---|---|
| Silhouette by zone, raw distances | −0.016 | **−0.020** |
| UMAP trustworthiness | 0.486 | 0.499 |
| t-SNE trustworthiness | 0.507 | 0.526 |
| PCoA trustworthiness | 0.495 | 0.510 |
| PCoA distance correlation | 0.322 | 0.287 |

Removing the polyclonal and clonally redundant isolates does **not** sharpen the structure: the
silhouette becomes slightly more negative. The conclusion is unchanged, and the figures can now be
reported on the same sample set as the rest of the analysis.

## D. GeoJSON provenance — not closable here

This needs an email to **cersgis@ug.edu.gh**. The ArcInfo-coverage fingerprint dates the original
to a pre-2005 workflow and CERSGIS (University of Ghana) is the most likely custodian. The interim
citation and the md5 are in Addendum 2 §F.

## Two incidents during these runs

**A results file was destroyed and restored.** `results/baypass/xtx_all_snps.csv` was found at
**0 bytes**, truncated at 08:29:53 — hours after the 01:42 run that produced it, so almost
certainly a shell redirect where a read was intended during a verification pass. It was the only
zero-byte file under `results/` or `interim/`. It was regenerated from the intact BayPass outputs,
and the regeneration is provably faithful: `outlier_snps.bed`, `xtx_calibration.json` and
`xtx_threshold.txt` are byte-identical by md5 before and after, and the restored file has the same
3,916 rows and 19 outliers.

**A log lied about where it wrote.** The `--suffix` patch to `step03_umap.py` suffixed the file
writes but not the `print` statements, so the run reported writing to the published
`dimred_comparison.csv` when it had correctly written `dimred_comparison_qcset.csv`. The data were
never at risk — verified by checking the published file's mtime and contents — but a log that
misreports its own output path is exactly the sort of thing that causes a later misattribution.
Fixed.
