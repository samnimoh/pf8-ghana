# Canonical facts — the ONLY numbers permitted in the article

Every figure below is from a verified output file. Do not compute, round differently, or
infer any other number. If something you need is not here, write `[NUMBER NOT AVAILABLE]`
rather than inventing it.

## Dataset
- Source: MalariaGEN Pf8 (33,325 samples, 12,493,205 variants), accessed via the public Zarr store.
- Ingest mask: `FILTER_PASS & is_snp & numalt == 1`; fields GT, AD, DP, GQ.
- Ghanaian isolates passing Pf8 release QC and assignable to a zone: **4,905**.
- Final analysis set: **1,900 isolates x 3,916 SNPs**, mean variant missingness 2.95%.
- Zones: Guinea savanna **1,334**, deciduous forest **337**, coastal savanna **204**, transitional **25**.
- Sample QC: Fws >= 0.95, call rate >= 0.80, heterozygosity outlier rule, clonal pruning.
  Mixed calls resolved to the majority allele by read depth; one allele per isolate (haploid).
- Variant missingness recomputed AFTER the sample cut (two-pass): provisional pass 1,634,808
  variants; 117 high-missingness samples dropped; 1,807,331 variants at <=10% missingness on the
  1,900 retained; **3,916** at MAF >= 0.05.
- Collection period **2009-2021**.

## Ordination (1,900-isolate analysis set, published Pf8 genotype-distance submatrix)
| method | trustworthiness | distance Spearman | silhouette by zone |
|---|---|---|---|
| original distances | - | 1.000 | -0.0156 |
| UMAP | 0.486 | 0.029 | -0.306 |
| t-SNE | 0.507 | 0.115 | -0.057 |
| PCoA | 0.495 | 0.322 | -0.112 |
All silhouettes negative: zones do not separate. PCoA preserves global distance best.

## Pairwise Hudson FST (ratio of averages, block jackknife)
| pair | FST | 95% CI |
|---|---|---|
| Coastal savanna x Guinea savanna | 0.00232 | 0.00128 - 0.00336 |
| Coastal savanna x Transitional | 0.00158 | 0.00006 - 0.00309 |
| Deciduous forest x Transitional | 0.00158 | 0.00017 - 0.00298 |
| Deciduous forest x Guinea savanna | 0.00134 | 0.00088 - 0.00180 |
| Guinea savanna x Transitional | 0.00047 | -0.00083 - 0.00178 |
| Coastal savanna x Deciduous forest | 0.00045 | 0.00019 - 0.00070 |
- **FIVE of six CIs exclude zero.** Only Guinea savanna x Transitional (n = 25) spans it.
- Differentiation is VERY LOW but statistically detectable. Never say undetectable, absent,
  panmictic, or that low FST bounds true differentiation.

## Threshold sensitivity (six scenarios, one shared genotype load)
| scenario | isolates | SNPs | max FST | Mantel r | Mantel p |
|---|---|---|---|---|---|
| baseline (Fws>=0.95, MAF>=0.05) | 1,900 | 3,916 | 0.00232 | 0.427 | 0.0252 |
| Fws >= 0.90 | 2,196 | 3,629 | 0.00240 | 0.318 | 0.0874 |
| Fws >= 0.80 | 2,746 | 3,496 | 0.00255 | 0.256 | 0.1687 |
| no Fws filter | 4,403 | 3,275 | 0.00254 | 0.245 | 0.1792 |
| MAF >= 0.01 | 1,900 | 10,876 | 0.00204 | 0.432 | 0.0617 |
| MAF >= 0.02 | 1,900 | 6,852 | 0.00217 | 0.434 | 0.0467 |
- Max FST stable at **0.00204-0.00255**; Mantel significant in only **2 of 6**.

## ADMIXTURE (3,385 LD-pruned SNPs, 10-fold CV)
CV error: K=1 **0.84384**, K=2 **0.83925** (minimum), K=3 0.83953, K=4 0.84069, K=5 0.84187,
K=6 0.84284, K=7 0.84389, K=8 0.84488. Total range 0.0056 - a near-flat curve.
K=2 minor component by zone: forest 0.092, coastal 0.085, Guinea 0.053, transitional 0.042;
Kruskal-Wallis H = 105.4, p = 1.05 x 10^-22; eta-squared = **0.019** (1.9% of variance).

## Isolation by distance
- Region level (7 populations, 21 pairs, 9,999 permutations, one-sided, seed 42):
  r = **0.4269**, p = **0.0252**. Three of 21 pairs had negative FST floored to zero;
  uncensored r = 0.4138, p = 0.0413.
- Zone level (4 populations, 6 pairs): r = 0.4709, p = **0.1218** (no flooring).
- Leave-one-region-out (file md5 779b9e379b6640afbbeb39409206ed69): significant in **4 of 7** -
  Volta 0.0097, Ashanti 0.014, Brong Ahafo 0.0398, Central 0.0427; not significant dropping
  Eastern 0.1355, Upper East 0.218, Greater Accra 0.2324.
- **VERDICT: isolation by distance is NOT ROBUST and is not reported as a supported result.**

## TreeMix (4 populations, jackknife SEs via -se)
Variance explained m=0..5: 0.8970, 0.9405, **0.9969**, 0.99966, 0.99958, 0.99959.
At m=2 the edges are 0.152 (SE 0.048, p = 7.5 x 10^-4) and 0.805 (SE 0.100, p = 3.3 x 10^-16);
the third edge added at m=3 is 0.065 (SE 0.147, p = 0.33), indistinguishable from zero.
- m = 2 is a **SELECTED DESCRIPTIVE MODEL**, never a count of historical migration events.
- The two selection criteria DISAGREE: the 0.998 variance rule picks m = 3 over the full
  0-5 sweep; m = 2 follows only after capping the range at 2 on identifiability grounds.
- Four populations cannot identify more than about two edges; this limitation is CONTINUING.

## BayPass XtX scan
Threshold **10.840** (0.999 quantile of 100,000 pseudo-observed SNPs). **19 outliers** (0.49%).
Expected false positives under the assumed null 3.916; the ratio 3.916/19 = 20.6% is an
**expected-null-exceedance ratio**, NOT a measured false-discovery rate - never call it
"empirical FDR". Benjamini-Hochberg q-value counts: 8 at q<=0.01, 10 at q<=0.05,
**13 at q<=0.10**, 17 at q<=0.20.
The pseudo-observed set is **NOT MAF-matched** (pi.maf truncates the simulated ancestral
frequency; it does not apply the observed MAF filter).
Top outlier genes by max XtX: PTP7 (PF3D7_0301700) 26.44; AAT1 (PF3D7_0629500) 24.20;
FIKK4.2 (PF3D7_0424700) 22.02; ACS8 (PF3D7_0215300) 22.00; NT2 (PF3D7_0824400) 20.46;
PIESP2 (PF3D7_0501200) 18.50; SNRPF (PF3D7_1126900) 13.98.
Two adjacent chromosome-11 SNPs (Pf3D7_11_v3:1,054,078 and 1,054,447, 369 bp apart) are flagged
lower confidence. BOTH have low InbreedingCoeff (0.1468 and 0.1931; 8th and 13th percentiles).
ONLY 1,054,078 has elevated ExcessHet (69.588, the only non-zero value among all 3,916 SNPs);
ExcessHet is 0.0 at 1,054,447. Do not write that both carry both anomalies.

## Resistance markers (codon reconstruction from CDS + 3D7 reference; 57 codons, 9 genes)
Overall frequencies (denominator = isolates called at that codon):
- *pfdhfr*: N51I 0.786 (n=1,891, p=2.43x10^-4); C59R 0.886 (n=1,888, p=4.80x10^-5);
  S108N 0.908 (n=1,889, p=9.40x10^-7); I164L **0.000** (fixed at reference Ile).
- *pfdhfr* IRN triple haplotype on complete cases: **0.771** (n=1,876; CI 0.751-0.789).
  By zone: coastal 0.867 (n=203), transitional 0.880 (n=25), forest 0.788 (n=330),
  Guinea savanna 0.750 (n=1,318). Quadruple IRNL **0 of 1,874**.
- *pfdhps*: **G437 = 0.897** (n=1,892, p=1.17x10^-6) - the resistance residue IS the 3D7
  reference residue, which is why annotation-string matching missed it entirely.
  By zone: forest 0.964, coastal 0.941, Guinea 0.875, transitional 0.800.
  S436A 0.541; K540E 0.0095; A581G 0.0138; A613S 0.108; I431V 0.0137.
  A437G+K540E double (GE) 0.0095.
- *pfcrt*: K76T 0.071 (n=1,874); CVIET core haplotype **0.071** (n=1,873), only CVMNK (0.929)
  and CVIET occur. By zone: forest 0.104, transitional 0.125, Guinea 0.064, coastal 0.054.
  N75E requires two base changes in one codon, so no single-variant annotation names it.
- *pfmdr1*: N86Y 0.088 (n=1,887, p=0.029); Y184F 0.677 (n=1,858); D1246Y 0.011.
- *pfmdr2*: I492V 0.549 (n=1,885).
- *pfaat1*: **S258L 0.609 overall** (n=1,896, p=1.89x10^-18), running **0.824 in coastal
  savanna to 0.544 in Guinea savanna** - the steepest geographic cline in the panel.
  F313S absent; codon 313 fixed at reference Phe in all 1,900.
- *pfk13*: 23 codons screened, covering all 14 WHO-validated and all 6 candidate variants
  (which occupy 19 distinct codons) plus 4 potential-tier codons. **Twenty-two are fixed at
  the reference residue; codon 458 is at 0.9995** - one isolate of 1,866 carries Asn458Asp,
  which is NOT the validated allele at that codon (WHO validates N458**Y**).
  **No WHO-screened artemisinin resistance allele was observed.** Denominators 1,845-1,876 per codon.
- Concordance with MalariaGEN's published per-sample genotypes: **47,012 of 47,012 calls agree**,
  across the **25 of the 57 panel codons** for which MalariaGEN publishes a per-sample genotype.
  The other 32, every *pfk13* codon among them, have no external per-sample check.
- Marker tiers follow WHO's compendium of molecular markers v1.0 (December 2025), which
  classifies VARIANTS not genes, and contains no validated or candidate lumefantrine marker.

## Within-host complexity (Fws, 4,905-isolate QC set)
Polyclonal fraction (Fws < 0.95): coastal savanna 0.4437, deciduous forest 0.5387,
Guinea savanna 0.5972, transitional zone 0.5000. Not monotone with latitude.

## Confounding and ascertainment - MUST appear in the article
- Zone is very nearly a relabelling of administrative region, sequencing study and collection
  period. Three of four zones are dominated by a single study; Guinea savanna / Upper East
  supplies **1,334 of 1,900 (70.2%)** of the analysis set.
- Holding zone constant does NOT isolate a technical cause: study varies together with
  collection year, finer geography, recruitment and host biology. These tests demonstrate
  study-ASSOCIATED heterogeneity, not a demonstrated sequencing artefact.
- Pooled MAF ascertainment floor: with <=10% variant missingness a retained site has at least
  **1,710 called haploid alleles**, so a variant private to the 25 transitional isolates cannot
  exceed **25/1,710 = 1.46%**, and a variant at 40% frequency in coastal savanna reaches only
  **82/1,710 = 4.80%**. Both fall below the 5% cut. The panel is therefore variants common
  enough to clear a threshold dominated by one zone.
- No neutral mask was defined; "neutral" means "genome-wide at the retained common variants",
  not "at sites shown to be free of selection".
- Callability: of the 171 panel positions, **46 carry no variant record**, so the reference base
  is read there for every isolate regardless of coverage. Per codon, 21 have a record at all
  three positions, 26 at two, 10 at only one. No per-isolate depth field is consulted.
- Fws >= 0.95 selects infections of low within-host complexity, changing the target population.
- Seven administrative regions are the finest spatial unit available; the transitional zone
  contributes 25 isolates.

## Software
Pf8 Zarr via zarr/scikit-allel; PLINK 1.9/2.0; ADMIXTURE 1.3; TreeMix (with -se); BayPass 2.4;
bedtools; PlasmoDB-71 annotation; NumPy/SciPy/pandas/scikit-learn/matplotlib.

## Forbidden claims
Never write: panmixia or random mating; undetectable/absent differentiation; "exactly two
migration edges" or a settled edge count; "empirical FDR"; MAF-matched simulations; isolation
by distance as supported; "all 23 pfk13 codons fixed"; low FST as an upper bound on true
differentiation; that holding zone constant isolates a batch effect; that the analysis is
end-to-end reproducible from the archived snapshots.
