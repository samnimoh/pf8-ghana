# Evaluation of the Pf8 Ghana spatial population-genomics analysis

Adversarial multi-agent audit, 2026-10-09. Eight independent reviewers across separate dimensions,
then three adversarial verifiers per finding (each prompted to **refute**, defaulting to refuted when
it could not substantiate the claim). A finding is CONFIRMED only when at least 2 of 3 verifiers
actively failed to refute it after checking the code, data or outputs themselves.

| | |
|---|---|
| Reviewers | 8 dimensions |
| Findings raised | 110 |
| Verification agents | 309 completed (30 lost to a rate limit — reproducibility dimension) |
| **Confirmed** | **61** |
| Disputed (1 of 3) | 19 |
| Refuted | 21 |
| Agent tokens | 28.0 M |

Confirmed by severity: **14 high**, 31 medium, 16 low.

> **Caveat.** The 30 lost verifications were all in the reproducibility dimension; those findings are
> listed separately as unverified. The server went off-LAN before they could be re-run.

---

## Confirmed — high severity

These change a number, a conclusion, or the credibility of the work.

### 1. '100,000 MAF-matched POD SNPs' is factually false - simulate.baypass clamps pi, it does not MAF-filter

`correctness` · Code: the prior agent’s own fixes · survived **3/3** · scripts/step08b_baypass.sh, R heredoc comment 'The observed SNPs were filtered at MAF >= 5% (config.MIN_MAF); the POD must be filtered the same way'; manuscript sections 5.6 and 6.

**What is wrong.** The prior agent set pi.maf=0.05 believing it imposes the observed MAF >= 0.05
filter on the POD ('the POD must be filtered the same way or rare simulated SNPs drag the threshold
around'). In baypass_utils.R, pi.maf only TRUNCATES the simulated ancestral frequency pi to [0.05,
0.95] (Pi[Pi<pi.maf]=pi.maf; Pi[Pi>1-pi.maf]=1-pi.maf), after which binomial sampling freely
produces observed MAF well below 0.05. The POD is therefore not MAF-matched, and 0.05 is also
simulate.baypass's own default, so the 'fix' only restored a default.

**Evidence.** baypass_utils.R, simulate.baypass:
'if(sum(beta.pi==1)==2){Pi=runif(nsnp,pi.maf,1-pi.maf)}else{Pi=rbeta(nsnp,beta.pi[1],beta.pi[2]);
Pi[Pi<pi.maf]=pi.maf ; Pi[Pi>1-pi.maf]=1-pi.maf}'. Here beta.pi = (a=2.4935, b=0.9355) from
ghana_core_summary_beta_params.out, so the else branch runs (clamping, no filtering). Measured on
G.pod vs interim/ghana_baypass.geno: observed global MAF min 0.0500, median 0.1358, fraction <0.05 =
0.0000; POD MAF min 0.0000, median 0.2119, fraction <0.05 = 0.0940. So 9,400 POD SNPs are rarer than
any observed SNP, and the POD bulk is shifted to HIGHER MAF than the data.

**Why it matters.** Moves the threshold 11.232 -> 10.52 and the outlier count 15 -> 18 if actually
enforced. More importantly it removes a false methodological claim that appears three times in the
manuscript and once in the configuration table.

**Fix.** Either drop the 'MAF-matched' wording and say pi.maf truncates the simulated ancestral
frequency, or actually enforce it: after simulate.baypass, drop G.pod rows whose global MAF <
config.MIN_MAF (and ideally resample to the observed MAF spectrum), then recompute the quantile.
Both the filtered and unfiltered thresholds should be reported.

### 2. TreeMix run without -se: no migration-edge SEs or p-values exist; m=1 is already saturated

`statistics` · Statistical validity · survived **3/3** · /media/biodataA/pf8/gyadu/scripts/step07b_treemix.sh:163; manuscript §6.7, Table 6.6, Table 7.1 (TreeMix row), §10.1 item 4

**What is wrong.** The manuscript's TreeMix conclusion ("a strictly bifurcating tree does not
describe these populations", graded "Supported" in §10.1 and given its own row in Table 7.1) rests
on no statistical test whatsoever. TreeMix was invoked without `-se` and without `-bootstrap`, so
migration-edge standard errors and p-values were never computed, and no topology support values
exist. Separately, the fit target is 6 numbers: with 4 populations there are 6 off-diagonal
covariance entries, a rooted 4-taxon tree already consumes ~5 free drift parameters, so m=1 is at
saturation and the 0.876 -> 0.935 increase is what adding one parameter to a 6-point fit does by
construction. Worse, TreeMix's own `.covse` output shows 3 of the 6 off-diagonal covariances are not
distinguishable from zero (|z| = 0.97 Coastal-Transitional, 1.40 Guinea-Transitional, 1.83 Forest-
Transitional), so there is no information to select among models.

**Evidence.** `/media/biodataA/pf8/gyadu/scripts/step07b_treemix.sh:163`: `treemix -i "$INPUT" -root
"$ROOT" -m "$m" -k "$BLOCK" -seed "$SEED" -o "treemix_m${m}"` — no `-se`, no `-bootstrap`. Every
migration line in `results/treemix/treemix_m*.treeout.gz` reads weight then three NAs, e.g. m=1:
`0.29952 NA NA NA Guinea_savanna:8.21206e-05 Decidous_forest:0.000194528` (TreeMix's columns are
weight, jackknife mean, jackknife SE, p-value). `results/treemix/bootstrap` does not exist. `grep -i
'se|jack' logs/treemix_m1.log` returns only `SEED: 42`. Dividing `treemix_m1.cov.gz` by
`treemix_m1.covse.gz`: Coastal-Forest 5.985e-5/2.127e-5=2.81; Coastal-Guinea
-1.631e-4/3.405e-5=-4.79; Coastal-Transitional -5.443e-5/5.631e-5=-0.97; Forest-Guinea
-5.904e-5/2.050e-5=-2.88; Forest-Transitional -8.823e-5/4.810e-5=-1.83; Guinea-Transitional
6.694e-5/4.788e-5=1.40.

**Why it matters.** One of the five "independent analyses" in the convergent-evidence table (Table
7.1) and one of the four items in §10.1 "What has been established" carries zero inferential
support. Variance explained is reported to four decimal places (0.8760, 0.9346, 0.9633, 0.9976) over
6 numbers, half of which are statistically indistinguishable from zero.

**Fix.** Re-run the sweep with `-se` (and `-bootstrap` for topology support) and report each edge's
weight +/- SE and p-value in Table 6.6; it costs minutes. If the edges are not significant, delete
the TreeMix row from Table 7.1 and §10.1 item 4 and replace it with an explicit statement that a
4-population covariance matrix has 6 independent entries, 3 of which have |z| < 2, and therefore
admits no model comparison.

### 3. Region-level IBD signal collapses when Upper East is dropped (r 0.400 -> 0.136, p=0.33)

`statistics` · Statistical validity · survived **3/3** · manuscript §6.5 (lines 1012-1016), Table 7.1 Mantel row, §10.2 item 2, abstract; /media/biodataA/pf8/gyadu/scripts/step06_mantel.py (region branch)

**What is wrong.** A leave-one-region-out jackknife shows the Mantel result is not a distance
gradient but a single north-south contrast. Dropping Upper East — the only region north of the
forest belt, and 6 of the 21 pairs — takes r from 0.400 to 0.136 and p from 0.029 to 0.33. Dropping
Greater Accra takes r to 0.223, p=0.26. Five of the seven jackknife replicates leave p > 0.05. The
manuscript notes qualitatively that "the fitted relationship is driven substantially by the Upper
East comparisons at the right-hand side of the plot" (§6.5 caveat), but never quantifies it, and
§10.2 nonetheless grades "Isolation by distance is detectable at administrative-region level ...
Moderately supported" and Table 7.1 reads "A weak but real distance effect". Compounding this, 9 of
the 21 region pairs have |F_ST| < 0.0008 — roughly one standard error at the small-region sample
sizes — and no standard errors are reported for the region-level F_ST matrix at all, unlike the
zone-level matrix in Table 6.4.

**Evidence.** Leave-one-region-out Pearson Mantel, 9,999 permutations each: drop Ashanti r=+0.561
p=0.016; drop Brong Ahafo r=+0.566 p=0.054; drop Central r=+0.362 p=0.065; drop Eastern r=+0.312
p=0.119; drop Greater Accra r=+0.223 p=0.264; drop Upper East r=+0.136 p=0.331; drop Volta r=+0.519
p=0.005. Region n: Upper East 1334, Greater Accra 204, Ashanti 157, Central 125, Eastern 34, Brong
Ahafo 25, Volta 21. Upper East is 410-578 km from every southern region; all southern pairs are
87-282 km apart. Of 21 region pairs, 9 have |F_ST| < 0.0008 and only 6 exceed 0.0016.

**Why it matters.** "Isolation by distance" implies a continuous distance-decay relationship. What
the data show is that one far-northern population differs from six southern ones; that is equally
consistent with a single discontinuity, with the collection-year difference, or with Upper East's
distinct study provenance. The claim should be restated, not deleted.

**Fix.** Add the leave-one-out jackknife table to §6.5 and restate the conclusion as "a single
north-south contrast that a distance metric detects; the relationship is not identifiable within the
southern regions alone". Also report block-jackknife SEs for the region-level F_ST matrix, as is
already done at zone level.

### 4. Section 4.2.3 attributes the GQ-mask effect to the call-rate decision; 1,566 and 1,862 are mutually impossible

`honesty` · Numerical audit · survived **3/3** · Manuscript Section 4.2.3 ("Effect"); /media/biodataA/pf8/gyadu/logs/run_stages_4to7.log:8,65,94

**What is wrong.** Section 4.2.3 says of the call-rate MAD rule: "Retaining these isolates raised
the QC-passing count from 1,566 to 2,017 and the final analysis set from 1,862 to 1,900." Both
halves are wrong. (a) The 1,862 figure comes from logs/run_stages_4to7.log, and that run already
used 2,017 QC-passing samples — i.e. the MAD rule was already disabled. The only difference between
that run and the reported one is the genotype mask (GQ<20 on, 21.35% masked, 2,143 SNPs vs DP-only,
13.52% masked, 3,359 SNPs). So 1,862 → 1,900 is the GQ-mask effect, already claimed separately in
Section 4.2.5 — it is double-counted here and misattributed. (b) The final analysis set is a subset
of the QC-passing set (Table 4.1 filter 13 runs 2,017 → 1,900), so a QC-passing count of 1,566
cannot produce a final set of 1,862. The two numbers cannot both describe the same configuration.

**Evidence.** logs/run_stages_4to7.log line 8: "Using QC-passing samples from
ghana_samples_qc_pass.csv (2,017 samples)"; line 64: "GQ < 20: 4,706,404,099 calls"; line 65:
"Called genotypes: 12,540,727,880 -> 9,863,685,827 (21.35% masked)"; line 88: "dropping 155 high-
missingness samples"; line 94: "Final matrix: 2,143 SNPs x 1,862 samples". Neither 1,566 nor 449
appears anywhere in logs/, scripts/ or results/ (grepped).

**Why it matters.** The stated benefit of the single most-criticised session decision (Section 4.2.3
even carries its own "Honesty note") is not the benefit of that decision. Either the call-rate rule
changed far less than claimed, or the GQ change is being credited twice. A reviewer who pulls the
log will read this as the analysis overstating the payoff of a post-hoc threshold choice.

**Fix.** Re-run step03b with --call-rate-mad enabled under the current DP-only mask to get the true
MAD-on QC-pass and final-set counts, then restate Section 4.2.3's Effect paragraph against those.
Delete the 1,862 → 1,900 comparison from 4.2.3 (it belongs in 4.2.5) or re-derive it holding the
mask fixed.

### 5. pfk13, pfmdr1 and pfcoronin contain ZERO scanned SNPs; their "absence" is read as biology

`honesty` · Manuscript honesty and overclaiming · survived **3/3** · Pf8_Ghana_Spatial... manuscript §6.8 ("What XtX does and does not detect") and Abstract, "Principal findings"; results/baypass/xtx_all_snps.csv

**What is wrong.** Section 6.8 and the abstract state that "No validated antimalarial resistance
locus appears among the outliers" and then offer two explanations for that absence — uniform
nationwide selection, or low scan power — concluding "These data cannot distinguish the two" and
that the absence of pfcrt and pfk13 "is, if anything, weakly consistent with their being under
uniform selection." In fact three of the eight panel loci contain no SNP at all in the 3,359-site
matrix, so they were never tested. A third explanation exists, is the correct one for those three
loci, is trivially checkable, and is never stated. The manuscript assigns positive evidential weight
("weakly consistent with uniform selection") to pfk13, a gene with zero data points.

**Evidence.** Counted SNPs per gene body from results/baypass/xtx_all_snps.csv against PlasmoDB-71
gene spans (script /tmp/evalwork/panel.py on gyadu): pfk13 0 SNPs, pfmdr1 0, pfcoronin 0; pfcrt 2
(max XtX 4.32), pfdhfr 2 (9.16), pfdhps 2 (3.11), pfmdr2 2 (6.55), pfap2mu 1 (3.03). Mean SNP
spacing in the matrix is ~6.9 kb against gene spans of 2.2-7.1 kb. Manuscript line 1154 ([Observed]
tag) and abstract line 139.

**Why it matters.** Changes a conclusion and an abstract sentence. The resistance-locus null result
is not a biological finding at all for 3 of 8 loci and rests on 1-2 sites for the other 5. Any
reader or examiner who checks this will conclude the interpretation was written without looking at
the input.

**Fix.** Add a short table to §6.8: for each of the eight panel loci, the number of scanned SNPs in
the gene body (and ±5 kb) and the maximum XtX. Replace the uniform-selection speculation with the
factual statement that pfk13, pfmdr1 and pfcoronin carry no MAF>=5% site in the matrix and were not
tested, and that the remaining five are tested by 1-2 sites each. Remove or heavily qualify "No
validated antimalarial resistance locus appears among the outliers" in the abstract.

### 6. The top AAT1 outlier IS pfaat1 S258L — the thesis's own named marker — and the manuscript never says so

`honesty` · Manuscript honesty and overclaiming · survived **3/3** · manuscript §6.8 (Table 6.7 and the AAT1 interpretation), Abstract; verified against https://pf8-release.cog.sanger.ac.uk/zarr variants/ANN_* ; /Users/samnimoh/Downloads/genomic ana

**What is wrong.** The manuscript's strongest result is reported generically as "amino acid
transporter AAT1 (PF3D7_0629500, two outlier SNPs, maximum XtX 24.44)." The 24.44 SNP is Ser258Leu —
the exact pfaat1 variant the thesis proposal names twice (Gambia 0%->97% 1984-2014; Kumasi 2023 at
64.7%) and includes in its candidate panel. Simultaneously the abstract asserts "No validated
antimalarial resistance locus appears among the outliers." The scan independently recovered the
project's own pre-specified candidate marker and the manuscript reports it as an anonymous
transporter next to a resistance-null headline. This is a severe underclaim fused to a misleading
claim.

**Evidence.** Pf8 Zarr variants/ANN_HGVS_p at Pf3D7_06_v3:1,215,233 = 'Ser258Leu' (ANN_HGVS_c
773C>T, MODERATE, missense_variant), XtX 24.436; global Pf8 AF 0.626. The second AAT1 outlier at
1,214,350 is 'Ile552Ile' — synonymous_variant, LOW impact — XtX 16.05. Thesis proposal lines 64, 76,
96, 126, 138 ("Pfaat1 S258L ... sat at 64.7% in the same Kumasi sample"; "Adding pfcoronin, pfaat1
and the background loci"). config.py KNOWN_RESISTANCE_LOCI omits PF3D7_0629500.

**Why it matters.** Changes the headline of the outlier section from "candidate list, no resistance
locus" to "independent recovery of the thesis's pre-specified pfaat1 S258L marker." Also corrects
the corroboration claim: the "two outlier SNPs" are 883 bp apart and the second is synonymous, so it
is one LD-linked signal, not two.

**Fix.** Name the variant (pfaat1 S258L, 773C>T) in Table 6.7 and the text; state that it is a
thesis-panel candidate omitted from config.KNOWN_RESISTANCE_LOCI, which is why it surfaced as an
unflagged outlier; state that the second AAT1 SNP is synonymous and 883 bp away and therefore not
independent support. Pull ANN_Annotation / ANN_HGVS_p for all 15 outliers from the Zarr already in
use (one query) and report consequence class per outlier.

### 7. Four negative pairwise FST values are silently censored to zero in the Mantel test that carries the IBD claim

`reproducibility` · Manuscript honesty and overclaiming · survived **3/3** · scripts/step06_mantel.py:148; manuscript §3.9 (Mantel methods), §6.5 and Figure 6.4 caption

**What is wrong.** step06_mantel.py line 148 contains `lin_fst[lin_fst < 0] = 0.0   # DistanceMatrix
rejects negatives`. Four of the 21 region pairs have negative Hudson FST and are floored to zero
before the Mantel test. This transformation is nowhere disclosed: the word "negative" appears in the
manuscript only for the PCoA eigenvalues (§6.3, where negatives are handled transparently). §6.5
instead describes the affected points as pairs that "sit at or very near zero differentiation",
presenting censored values as observations. The censoring is also not neutral: it raises the
reported r from 0.3807 to 0.4000.

**Evidence.** /media/biodataA/pf8/gyadu/scripts/step06_mantel.py:148. Recomputed region FST:
Ashanti-Volta -0.001039, Eastern-Volta -0.000405, Brong Ahafo-Volta -0.000346, Greater Accra-Volta
-0.000248 (all four involve Volta, n = 21 — the smallest region). Pearson r uncensored 0.3807,
censored 0.4000 (/tmp/evalwork/mant2.py). Manuscript §6.5 caveat: "five pairs in Figure 6.4 sit at
or very near zero differentiation."

**Why it matters.** An undisclosed data transformation on the response variable of the paper's only
positive result, in a manuscript whose whole premise is per-claim traceability. It also means the
four plotted points nearest the origin are not data.

**Fix.** State the censoring in §3.9 and the Figure 6.4 caption, report how many pairs were affected
and which, report the Mantel r both ways, and note that all four negatives come from the n=21
region. Better: use a Mantel implementation that accepts negative values, or exclude Volta and Brong
Ahafo from the region-level test and report that version.

### 8. The surveillance-design conclusion is contradicted by the project's own literature review

`honesty` · Manuscript honesty and overclaiming · survived **3/3** · manuscript §7.4 "Practical significance", §1.1 framing, Reviewer-notes A ("Explain it simply")

**What is wrong.** §7.4 concludes "sentinel surveillance at a small number of sites is an adequate
design for detecting emergence — the samples do not need to be spatially comprehensive to be
representative", and the plain-language summary repeats it with no caveat at all. The project's own
literature review argues the opposite mechanism explicitly: selection builds connectivity that
neutral demography does not, resistance-allele trajectories differ by site under near-panmixia,
pfcrt wild-type re-expansion "is not expected to run at one rate everywhere", and pfaat1 S258L
"seems to underlie regional differences in resistance dynamics". Low genome-wide neutral FST
therefore does not license a claim about the spatial representativeness of marker frequencies —
which is what sentinel surveillance measures. §7.4's own "Caveat on that inference" addresses a
different objection (gene flow vs recent common ancestry) and the plain-language section drops even
that.

**Evidence.** Proposal line 49 ("Gene flow, then, is not uniform along the genome. Selection can
ferry a haplotype across a continent while the neutral background stays regionally structured"),
line 70 ("Isolation by environment acting through drug selection predicts differentiation
concentrated at resistance loci ... faint or absent at neutral markers"), line 76, line 109
("Selection builds connectivity that neutral demography does not"), line 138 ("Whether any of these
is zone-structured is unknown, because each has been measured at a single site"). Manuscript §7.4
and Reviewer-notes section A.

**Why it matters.** This is the manuscript's only policy claim and the one most likely to be quoted.
As written it is not supported by the analysis and is refuted by the project's own reading of the
literature. It also undercuts the thesis's own rationale for building a marker panel across the
gradient.

**Fix.** Restrict the claim to what was measured: "neutral common-variant differentiation between
zones is negligible, so a spatially sparse design is adequate for characterising neutral structure."
State that marker-frequency representativeness is a separate question these data do not address,
cite the lit review's evidence that resistance-marker trajectories are site-specific, and remove the
unqualified version from the plain-language summary.

### 9. Zone is confounded with sequencing study, and no study contains both a Guinea savanna and a Coastal savanna isolate

`honesty` · Filtering and QC decisions · survived **3/3** · manuscript 4.2.1 ([Hypothesized] paragraph on differential regional loss), 4.3 Selection bias summary, and the Limitations section; data in /media/biodataA/pf8/gyadu/results/sample

**What is wrong.** The documented hard limits cover zone-region collinearity, admin-level-1
geolocation and year confounding, but not study/batch confounding. Zone is very nearly a relabelling
of sequencing study, and for the pair that produces every headline number (Coastal savanna vs Guinea
savanna, max F_ST 0.0024; polyclonal fraction 0.444 vs 0.597) there is zero within-study
replication: not one of the 11 studies contributes isolates to both zones. Combined with the
previous finding (studies differ 10-fold in low-GQ call rate) and with the differential sample-
missingness drop (below), batch effects are demonstrable in the genotype data and are inseparable
from zone for exactly that comparison.

**Evidence.** Study x zone crosstab from results/sample_qc_full.csv (n=4,905): Coastal savanna is
supplied only by 1241-PF-GH-ANINAGYEI (387) and 1183-PF-GH-AWANDARE-SM (48); Guinea savanna only by
1017 (384), 1083 (47), 1094 (241), 1151 (79), 1168 (2,678), 1294 (176); Transitional zone only by
1083-PF-GH-CONWAY (50/50). The only zone-spanning studies are 1083 (Guinea+Transitional), 1183 and
1241 (Coastal+Forest). One study, 1168-PF-GH-AMENGA-ETEGO-SM, is 2,678 of 3,605 Guinea isolates
(74%); 1241 is 387 of 435 Coastal isolates (89%). Mean Fws by study spans 0.779 (1294) to 0.883
(1096), overlapping the 0.823-0.891 between-zone range. Within Deciduous forest, the four
contributing studies differ significantly in Fws (Kruskal p=0.0019; polyclonal fraction 0.430 to
0.578), so study-level heterogeneity in the quantity driving the largest filter is real, not
hypothetical.

**Why it matters.** Adds a fourth, previously unlisted confound to the design-limit set, and it is
the one that bites hardest: the Coastal-Guinea contrast cannot be separated from a study/batch
contrast by any reanalysis of these data. The 'polyclonality gradient' the handoff calls the
clearest ecological signal, and the max pairwise F_ST, are both between-study comparisons.
Credibility cost is high because the manuscript is otherwise candid about collinearity and a
reviewer will find this in one crosstab.

**Fix.** Add study/batch confounding to the hard-limits list alongside zone-region collinearity,
with the crosstab as a supplementary table. State that the Coastal-Guinea contrast has no within-
study replicate. Note the two partial mitigations that do exist: studies 1183 and 1241 both span
Coastal and Forest and both show Forest more polyclonal than Coastal (0.488 vs 0.438; 0.534 vs
0.444), which is within-study support for that one leg of the gradient. Report the within-zone-
between-study Kruskal tests so readers can see where batch heterogeneity is and is not significant
(Coastal p=0.378, Guinea p=0.103, Forest p=0.0019).

### 10. Filter order costs ~10% of the final SNP panel for free: variant missingness is measured over 117 isolates that are then discarded

`improvement` · Filtering and QC decisions · survived **3/3** · /media/biodataA/pf8/gyadu/scripts/step04a_prepare_callset.py, the "Missingness and MAF" block: var_missing computed from gt.n_samples (2,017) and keep_var applied before smp_missin

**What is wrong.** Stage 4a measures per-variant missingness against all 2,017 QC-passing isolates,
applies the <=0.10 bar, and only then drops 117 isolates for excess sample missingness. Those 117
have a median QC-panel call rate of 0.882 and so inflate every SNP's measured missingness. Measuring
variant missingness after the sample drop (PLINK's conventional --mind-before---geno order) retains
materially more SNPs at the identical threshold.

**Evidence.** Measured directly on a 50,000-SNP panel under the as-run DP>=5 mask
(/tmp/gq_check.py). With the 2,017-isolate denominator, 37,076 panel SNPs (74.2%) pass missingness
<=0.10 - this reproduces the pipeline's genome-wide 1,634,808/2,190,026 = 74.65%, confirming the
panel is calibrated. With the 1,900-isolate denominator, 41,137 (82.3%) pass: +4,061 SNPs, +10.95%.
Projecting at the pipeline's observed MAF pass rate (3,359/1,634,808 = 0.20547%): 2,190,026 x 0.823
= 1,802,391 entering the MAF step, giving ~3,703 final SNPs vs 3,359, i.e. +344 SNPs (+10.3%). Under
DP+GQ>=20 the gain is larger: 50.8% -> 61.4%, +21.0%. The 117 dropped isolates' call rates
(0.803-0.989, median 0.882) overlap the retained range (min 0.896), confirming they are a tail of
the same distribution rather than a distinct bad-data population.

**Why it matters.** Changes a headline number: the final matrix becomes ~3,703 SNPs rather than
3,359, recovering ~23% of the gap between the reported panel and the manuscript's own stated
unmasked ceiling of ~4,832. More power for the BayPass scan, which 4.2.6 itself flags as the
analysis most limited by SNP density. Costs nothing: no threshold changes, same filters, one
reordering. It also means the manuscript's claim that the order is "deliberate" is only half right -
masking before missingness is correct, but measuring variant missingness before the sample drop is
not.

**Fix.** In step04a_prepare_callset.py, move the sample-missingness block (smp_missing / keep_smp)
ahead of the variant-missingness block, or iterate once: compute variant missingness on 2,017, drop
samples, then recompute variant missingness on the survivors before applying the <=0.10 bar and the
MAF bar. Either way the MAF step must run last, on the recomputed panel. Report the new SNP count
and re-run stages 4b-9; the manuscript's Table 4.1 cascade rows 12-14 change.

### 11. BayPass with -nthreads > 1 is not reproducible; reported XtX values and outlier count are one random draw

`reproducibility` · Reproducibility and engineering · survived **3/3** · scripts/step08b_baypass.sh:32 and scripts/run_all.sh:109

**What is wrong.** step08b_baypass.sh passes -seed 42 but the committed run used -nthreads 8
(run_all.sh --parallel exports NTHREADS=8). Two runs of the committed interim/ghana_baypass.geno at
-nthreads 8 -seed 42 differ by up to 1.12 in M_XtX and give 15 vs 16 SNPs above the reported
threshold 11.2325. At -nthreads 1 two runs are bitwise identical and give 17 outliers. The headline
threshold 11.232, the 15 outliers, the top XtX values 26.48 (PTP7) and 24.44 (AAT1) and the 11-gene
list are all one unreproducible draw. Manuscript line 1285, 'Random seeds are fixed ... BayPass
-seed 42', is false in effect.

**Evidence.** Two runs, same input and seed, -nthreads 8: max|dM_XtX| = 1.1179, outliers 15 vs 16.
Two runs at -nthreads 1: max|dM_XtX| = 0.0000, outliers 17 vs 17. 8-thread rerun vs committed
results/baypass/ghana_core_summary_pi_xtx.out: max|dM_XtX| = 1.1559. Committed top-5 XtX [20.08,
21.52, 21.97, 24.44, 26.48] vs 8-thread rerun [19.37, 20.94, 21.42, 23.50, 25.59].
logs/stage8.log:25 'Populations: 4  SNPs: 3359  threads: 8'. Timing: 25.9 s at 1 thread vs 20.9 s at
8.

**Why it matters.** Changes reported numbers: the XtX threshold, the outlier count (15 vs 16 vs 17)
and potentially which genes appear in Table 6.7. A reviewer who re-runs gets different values.

**Fix.** Set NTHREADS=1 for BayPass in run_all.sh and as the step08b default (costs 5 s), re-run the
core model and the POD single-threaded, regenerate the threshold, outlier BED and Table 6.7.

### 12. The top AAT1 outlier is S258L, the published functional CQ-resistance variant, and it forms a year-controlled latitudinal cline

`biology` · Biological interpretation · survived **3/3** · manuscript Section 6.8 [Interpreted] paragraph and Section 10 summary row; data /Users/samnimoh/Desktop/chromo/pf8_proof/outliers_annotated.txt line 6-7; full annotated table writt

**What is wrong.** Pf8's own SnpEff annotation shows the stronger of the two AAT1 outliers is
Ser258Leu — the exact variant Amambua-Ngwa et al. 2023 edited into parasites and showed raises
chloroquine resistance, and which rose 0% to 97% in The Gambia 1984-2014. Its frequency falls
monotonically from the coast to the far north, the gradient survives restriction to a single
collection year, and there is no temporal trend within Guinea savanna. The manuscript reports only
"two outlier SNPs here with a maximum XtX of 24.44" and never names the amino-acid change, never
gives the frequencies, and classifies the whole outlier set as "provisional". This is the thesis's
objective-3 result and it is currently buried.

**Evidence.** ANN_HGVS_p at Pf3D7_06_v3:1215233 = Ser258Leu, missense_variant, XtX=24.44, MQ=60.00,
VQSLOD=12.09, RegionType=Core (second AAT1 outlier 1214350 = Ile552Ile synonymous, XtX=16.05). Zone
ALT frequencies from interim/allele_counts_by_zone.npz: Coastal 0.823 (n=203), Decidous forest 0.733
(n=330), Transitional 0.640 (n=25), Guinea 0.544 (n=1332); chi2 = 84.3, p = 3e-18. Restricted to
2018 only (from interim/ghana_core_snps.npz + analysis_samples.csv): Coastal 0.812 (n=176), Forest
0.775 (n=40), Guinea 0.507 (n=556), chi2 = 57.5, p < 1e-12. Within Guinea savanna, Spearman(Year,
ALT) = -0.074. By region sorted on latitude: Central 0.814, Greater Accra 0.823, Eastern 0.706,
Ashanti 0.682, Volta 0.714, Brong Ahafo 0.640, Upper East 0.544. Consistent across partner studies
(southern studies 0.68-0.95, Upper East studies 0.51-0.65).

**Why it matters.** Upgrades the headline from "near-panmixia, candidate list requiring independent
support" to a named, functionally validated 4-aminoquinoline-resistance allele with a 30-percentage-
point north-south cline in a country whose first-line ACT (artesunate-amodiaquine) maintains
4-aminoquinoline pressure. It is the one result in the document that is both a positive finding and
a published-mechanism finding.

**Fix.** State the amino-acid change explicitly in Table 6.7 and in the abstract. Add zone and
region frequency tables with Wilson CIs, the 2018-only stratified comparison, and the within-Guinea-
savanna year series as the temporal control. Discuss in terms of amodiaquine (AS-AQ) rather than
chloroquine per se, and note the S258L fitness cost reported by Amambua-Ngwa et al. 2023 as the
reason a cline rather than fixation is expected post-CQ-withdrawal.

### 13. ADMIXTURE K=2 minor component differs by zone at p=3.6e-24; manuscript asserts the opposite

`statistics` · Statistical validity · survived **2/3** · manuscript §6.6 (line 1055 of extracted text), Table 7.1 ADMIXTURE row, §10.1 item 3; results/admixture/Q_K2.csv

**What is wrong.** §6.6 states "The minority component is present at similar low frequency
everywhere", Table 7.1 reads "No ancestry structure aligned to geography", and §10.1 grades this
"Well supported as a negative result". The manuscript's own Q matrix contradicts all three: the
minor component differs between zones with Kruskal-Wallis H=112.2, p=3.6e-24 (ANOVA F=13.1,
p=1.9e-8). Medians are Coastal 0.0612, Deciduous forest 0.0582, Guinea savanna 0.0442, Transitional
0.0417 — a ~40 per cent relative difference, ordered south-high to north-low, i.e. the same ordering
as the pairwise F_ST ranking. It is not a QC or temporal artefact: adjusting for call rate, Fws and
year leaves a zone partial F-test of 12.06, p=8.0e-8, and within collection year 2018 alone Coastal
(n=177) vs Guinea (n=556) gives Mann-Whitney p=1.9e-9. The magnitude is genuinely tiny (zone R^2 =
0.020), which is the manuscript's substantive point and remains true — but "no structure corresponds
to geography" is false as a statistical statement and was never tested.

**Evidence.** results/admixture/Q_K2.csv joined to results/admixture/ghana_pruned.fam. Group summary
(count, mean, median): Coastal_savanna 204, 0.0880, 0.0612; Decidous_forest 337, 0.0945, 0.0582;
Guinea_savanna 1334, 0.0548, 0.0442; Transitional_zone 25, 0.0419, 0.0417. Pairwise Mann-Whitney:
Coastal vs Guinea p=2.98e-16, Forest vs Guinea p=4.59e-15, Coastal vs Transitional p=4.9e-4, Forest
vs Transitional p=3.7e-3. OLS `minor ~ C(zone) + call_rate + Fws + Year`: Guinea coefficient -0.0315
(t=-3.44, p=0.001); partial F-test for zone F=12.06, p=8.03e-8; R^2 0.0219 with zone vs 0.0032
without. Year-2018-only subset: Coastal mean 0.0891 vs Guinea 0.0591, Mann-Whitney p=1.85e-9.

**Why it matters.** A declared negative result is actually a significant positive one, and in the
authors' favour: it is a third independent line of evidence for the same weak north-south cline that
F_ST and the Mantel show, it survives temporal control (which the Mantel analysis never attempts),
and unlike the Mantel it is not driven by a single population. The manuscript currently discards its
strongest and most robust piece of structure evidence.

**Fix.** Replace the negative claim with the tested one: "zone explains 2.0 per cent of variance in
minor-component ancestry (Kruskal-Wallis p=3.6e-24); mean minor ancestry is 0.055 in Guinea savanna
and 0.088-0.095 in the coastal/forest zones, an ordering concordant with the F_ST ranking and robust
to call rate, Fws and collection year (zone partial F=12.1, p=8e-8; within 2018 alone p=1.9e-9)".
Keep the near-flat CV curve as the argument that the effect is negligible in magnitude, which it is.

### 14. Canonical resistance markers were excluded at ingest by the biallelic filter, not by XtX

`biology` · Biological interpretation · survived **2/3** · /media/biodataA/pf8/gyadu/scripts/step03a_fetch_callset_zarr.py:334-336; manuscript Section 6.8 ("What XtX does and does not detect") and Section 8.2 item 5

**What is wrong.** The manuscript attributes the absence of pfcrt/pfmdr1/pfdhfr/pfdhps/pfk13 from
the outlier list to XtX being blind to spatially uniform selection, and proposes new direct
genotyping as the remedy. The real cause is upstream: step03a's `FILTER_PASS & is_snp & (numalt ==
1)` mask silently discards every canonical marker, because in Pf8 these codons are multiallelic
and/or carry a spanning-deletion ALT. They were never in the 2,190,026-site callset, so they could
not have appeared among the outliers whatever selection regime applies. This misdiagnoses the
negative result and misdirects the proposed fix.

**Evidence.** Fetched variants/AC, AN, ALT, numalt, is_snp, FILTER_PASS, RegionType, ANN_HGVS_p
directly from https://pf8-release.cog.sanger.ac.uk/zarr. pfcrt K76T, Pf3D7_07_v3:403625 —
FILTER_PASS=True, RegionType=Core, AC=29972 / AN=58452 (global ALT freq 0.513), numalt=2,
is_snp=False (second ALT is a 54-bp insertion). pfcrt M74I 403620 AC=28718 numalt=3 is_snp=False;
pfcrt N75D 403621 AC=28948 numalt=2. pfmdr1 N86Y, Pf3D7_05_v3:958145 — PASS, Core, AC=5512,
numalt=3, is_snp=False. pfdhps K540E, Pf3D7_08_v3:549993 — PASS, Core, is_snp=True, AC=17913,
numalt=2. pfdhps A581G 550117 PASS AC=11517 numalt=2 is_snp=False. pfdhps A613S 550212 PASS AC=2489
numalt=3. Whole-gene tally of PASS biallelic SNPs / those with global MAF>=5%: pfmdr1 503/0,
pfcoronin 230/0, pfk13 335/1 (only K189T), pfcrt 359/3 (N75K, N326S, I356T), pfdhfr 209/2 (N51I,
C59R). Explicit string search returned "NOT a PASS biallelic SNP in Pf8" for Lys76Thr, Asn86Tyr,
Tyr184Phe, Ser108Asn, Ile164Leu, Cys580Tyr, Cys469Tyr. Filter source:
/media/biodataA/pf8/gyadu/scripts/step03a_fetch_callset_zarr.py:334-336 and
logs/run_from4_parallel.log:33-35.

**Why it matters.** Rewrites the central negative conclusion of the thesis's objective 3. "No
validated resistance locus is differentiated between zones" becomes "the validated loci were never
tested". It also changes the remedy from "needs new code / direct genotyping" (Section 8.2 item 5,
listed as expensive) to a one-line filter change on ~20 positions.

**Fix.** For the panel positions, decompose multiallelic records instead of requiring numalt==1
(bcftools norm -m-any equivalent, or index the specific ALT allele in the Zarr AD/GT arrays), or
simply use MalariaGEN's released Pf8 per-sample drug-resistance marker table, which already reports
K76T, N86Y, Y184F, S108N, I164L, A437G, K540E, A581G and k13 status. Then recompute zone-wise
frequencies with CIs. Correct the Section 6.8 explanation.


## Confirmed — medium severity

### 1. "No validated resistance locus among the outliers" is vacuous for 3 of 8 loci — they contain zero tested SNPs

`honesty` · Code: never-reviewed scripts · survived **3/3** · /media/biodataA/pf8/gyadu/scripts/step09_annotate.py:176-192; manuscript Abstract (Principal findings) and §6.8 [Observed]

**What is wrong.** step09_annotate.py decides which configured resistance loci were "not in the
outlier set" by pure set difference against the annotated outlier genes (`missed = [... for k,v in
C.KNOWN_RESISTANCE_LOCI.items() if k not in set(per_gene['gene_id'])]`, lines 189-191). It never
checks whether a locus contained any SNP in the 3,359-SNP panel at all. In fact pfmdr1
(PF3D7_0523000), pfk13 (PF3D7_1343700) and pfcoronin (PF3D7_1251200) contain ZERO panel SNPs, so
they could not have been flagged under any circumstance. The remaining five contain 1-2 SNPs each —
9 SNPs in total across all eight genes — with a maximum XtX of 9.16 (pfdhfr) against a threshold of
11.232. The manuscript reports this as a tested negative in the Abstract ("No validated antimalarial
resistance locus appears among the outliers") and in §6.8 ("None of the eight validated antimalarial
resistance loci in the configured panel — pfcrt, pfmdr1, pfdhfr, pfdhps, pfk13, pfmdr2, pfcoronin,
pfap2mu — appears among the outliers"). For three of the eight, that statement describes the absence
of data, not the absence of signal.

**Evidence.** Intersected the 8 IDs in config.KNOWN_RESISTANCE_LOCI with PlasmoDB-71 gene intervals
and the panel positions in interim/allele_counts_by_zone.npz, joined to
results/baypass/xtx_all_snps.csv. All 8 IDs resolve in the GFF. Result: pfcrt 2 SNPs (max XtX 4.32);
pfmdr1 0; pfdhfr 2 (9.16); pfdhps 2 (3.11); pfk13 0; pfmdr2 2 (6.55); pfcoronin 0; pfap2mu 1 (3.03).
Total 9 of 3,359 SNPs. Threshold = 11.232 (results/baypass/xtx_calibration.json). step09_annotate.py
lines 176-192 contain no coverage check.

**Why it matters.** Turns a stated empirical negative into an untested one for 3 of 8 loci, and
shows the other 5 were tested at 1-2 sites each. The §6.8 hedge ("equally consistent with the scan
lacking power at 3,359 SNPs") understates this: it is not low power, it is zero coverage for three
loci. A thesis examiner asking "how many SNPs did you actually test in pfk13?" gets the answer
"none".

**Fix.** In step09_annotate.py, before the KNOWN_RESISTANCE_LOCI report, intersect the full scanned
position table (interim/baypass_snp_positions.csv) with each locus's GFF interval and print `locus,
n_snps_tested, max_xtx`. Print "UNTESTED (0 SNPs in panel)" rather than "not in the outlier set"
when the count is zero. Replace the Abstract and §6.8 sentences with the per-locus table; state that
pfmdr1, pfk13 and pfcoronin carry no panel SNP and so were not tested.

### 2. Abstract says "two of six" FST confidence intervals span zero; the correct number is three

`numbers` · Code: never-reviewed scripts · survived **3/3** · /Users/samnimoh/Desktop/chromo/Pf8_Ghana_spatial_genomics_working_manuscript.docx, Abstract, Principal findings

**What is wrong.** The Abstract states "two of six pairs have confidence intervals spanning zero".
results/fst_pairwise.csv has three rows with a negative ci95_low: Coastal savanna-Transitional zone
(-0.000360), Decidous forest-Transitional zone (-0.000423), Guinea savanna-Transitional zone
(-0.001112). The manuscript contradicts its own Abstract in four other places: Table 6.4 caption
("The three pairs involving the transitional zone (n = 25) have confidence intervals spanning
zero"), §9 ("All three FST comparisons involving it have confidence intervals spanning zero"), the
objection/response table ("Yes for three of six pairs"), and the Reviewer Notes ("Three FST
confidence intervals spanning zero").

**Evidence.** results/fst_pairwise.csv ci95_low column: -0.000360, -0.000423, -0.001112 are
negative; the other three (0.001404, 0.000854, 0.000204) are positive. I independently recomputed
all six Hudson FST values from interim/ghana_core_snps.npz and interim/analysis_samples.csv and
reproduced the pipeline's point estimates to 5 decimal places (e.g. Coastal-Guinea 0.00238 vs
0.002381), confirming the CSV is correct and the Abstract is wrong. Manuscript paragraph 139 vs
paragraphs 1007, 1259, 1302, 1669.

**Why it matters.** A wrong number in the Abstract, understating the uncertainty, and internally
inconsistent with four later statements. The Abstract is the part of the document most likely to be
read in isolation; an inconsistency here costs credibility disproportionately.

**Fix.** Change "two of six pairs" to "three of six pairs — all three involving the transitional
zone (n = 25)" in the Abstract.

### 3. No false-discovery accounting for the 15 XtX outliers; expected false positives under the stated null is 3.36

`statistics` · Code: never-reviewed scripts · survived **3/3** · /media/biodataA/pf8/gyadu/scripts/step08c_calibrate_xtx.py:77-114; manuscript §6.8 [Observed] and Table 6.7

**What is wrong.** step08c_calibrate_xtx.py sets the threshold at the 0.999 quantile of the
100,000-SNP POD distribution and then reports the outlier count and fraction only (`n_outliers`,
`outlier_fraction` in xtx_calibration.json). By construction, 0.1% of 3,359 neutral SNPs — 3.36 SNPs
— are expected to exceed that threshold. Fifteen were observed, so the expected false-discovery
proportion among the 15 is 3.36/15 = 22%. Neither the script nor §6.8 states this. The manuscript's
§6.8 reports "Fifteen SNPs (0.45 per cent) exceed it" and then interprets individual genes down to
max XtX 11.90 (ACS8) and 12.04 (PF3D7_0831400) as if each were a finding.

**Evidence.** results/baypass/xtx_calibration.json: {"threshold": 11.232456940590037, "method": "POD
quantile 0.999", "n_snps": 3359, "n_outliers": 15}. config.py:170 XTX_POD_QUANTILE = 0.999. 0.001 x
3359 = 3.359. The joint excess IS highly significant (Poisson(3.359), P(X>=15) = 2.6e-6, computed
with scipy), but ~3-4 individual entries in the 11-gene table are expected to be noise.
step08c_calibrate_xtx.py lines 77-83 and 107-114 compute no expected count and no per-SNP q-value.

**Why it matters.** Changes how the 11-gene table must be read. The set as a whole is a real excess;
roughly three of its members are not. Without this, every gene in Table 6.7 reads as an equally
supported hit, and the two lowest (ACS8, PF3D7_0831400 at XtX 11.90 and 12.04) are the least
defensible.

**Fix.** In step08c, add `expected_false_positives = (1 - quantile) * n_snps` and a per-SNP
empirical q-value (fraction of POD XtX >= observed XtX, times n_snps, divided by rank) to
xtx_calibration.json and xtx_all_snps.csv. In §6.8 add one sentence: "Under the calibrated null, 3.4
of 3,359 SNPs are expected above this threshold; 15 were observed (Poisson p = 2.6e-6 for the set),
implying roughly a 22 per cent false-discovery proportion among the individual hits."

### 4. step09 does not URL-decode GFF attributes, so %2C leaks into the published results file

`improvement` · Code: never-reviewed scripts · survived **3/3** · /media/biodataA/pf8/gyadu/scripts/step09_annotate.py:68-72 and 118-121

**What is wrong.** step09_annotate.py's parse_attrs stores the raw GFF attribute values without
percent-decoding. VEuPathDB GFF encodes commas as %2C, so results/outlier_genes.csv — which is cited
in the manuscript as the source of Table 6.7 and has been copied to the proof directory — contains
strings like "serine/threonine protein kinase%2C FIKK family", "RING zinc finger protein%2C
putative", "small nuclear ribonucleoprotein F%2C putative" and "Plasmodium exported protein%2C
unknown function". Separately, `--flank` defaults to 0, so a hit 59 bp past a gene boundary
(Pf3D7_11_v3:1,054,447, immediately downstream of SNRPF PF3D7_1126900 which ends at 1,054,388) is
classified as intergenic with no indication of how near it was.

**Evidence.** results/outlier_genes.csv rows 4, 6, 8, 9, 10 contain literal '%2C'. Also present in
/Users/samnimoh/Desktop/chromo/pf8_proof/outlier_genes.csv. step09_annotate.py:39 (ATTR_RE) and
68-72 (parse_attrs) — no urllib.parse.unquote. step09_annotate.py:61-62, 118-121 (flank default 0).
outliers_annotated.txt has 13 rows and omits 1,054,447, confirming the 59 bp near-miss.

**Why it matters.** Cosmetic in the manuscript (the author cleaned the strings by hand for Table 6.7
— '%2C' appears nowhere in the .docx), but the published results artefact that Table 6.7 cites does
not match the table, which a reader checking the supplementary file will notice. The flank point
means "two of the 15 outlier SNPs fall outside annotated protein-coding genes" is literally true but
hides that one of the two is 59 bp from a gene end.

**Fix.** Wrap parse_attrs values in `urllib.parse.unquote(...)` and re-run step09. Add a nearest-
gene distance column (bedtools closest -d) so near-misses are reported as distances rather than
silently dropped, and note in Table 6.7's caption that one of the two intergenic outliers is 59 bp
downstream of SNRPF.

### 5. Manuscript's stated reason for the 8.375 -> 11.232 threshold move is wrong; it is POD-size Monte Carlo noise

`honesty` · Code: the prior agent’s own fixes · survived **3/3** · manuscript section 5.6, paragraphs beginning 'Corrections.' and '[Interpreted] The direction is as expected'; and section 6.8 '[Observed]'

**What is wrong.** Section 5.6 attributes the threshold shift to MAF matching ('an unfiltered
simulation contains rare sites whose XtX is low, which depresses the upper quantile and admits too
many outliers') and then rules the 25 intermediate SNPs to have 'failed calibration, not [to be]
marginal'. Both claims are unsupported. MAF matching on its own moves the threshold in the OPPOSITE
direction, and the whole observed shift is inside the sampling noise of a 0.999 quantile estimated
from only 1,000 values.

**Evidence.** Measured on the server. (a) 200 random 1,000-SNP subsamples of the CURRENT pi.maf=0.05
POD give q0.999 in [8.988, 13.248] (median 10.59) and observed-outlier counts from 7 to 41 - both
old reported values (8.375 and 40 outliers) fall inside that range with no MAF difference at all.
(b) Restricting the current 100k POD to global MAF >= 0.05 (n=90,604) lowers the threshold to
10.5315 and raises outliers to 18; a properly MAF-matched resample gives 10.5221 and 18. (c)
corr(POD MAF, POD XtX) = -0.029, so the asserted mechanism (rare sites have low XtX) is essentially
absent.

**Why it matters.** Changes the defence of the headline outlier count. The correction is still an
improvement (a 1,000-SNP 0.999 quantile is indefensible), but the manuscript's causal story and its
verdict on the 25 dropped SNPs are both wrong. A reviewer who repeats this check will find the
reasoning does not hold.

**Fix.** Replace the '[Interpreted]' paragraph with the measured decomposition: POD size accounts
for the move (1,000-SNP q0.999 has a 95% range of roughly 9.0-13.2), MAF matching contributes about
-0.7 in the other direction. Drop the claim that the 25 intermediate SNPs 'failed calibration' and
report instead that the 1,000-SNP threshold was unstable. State the threshold with a bootstrap
interval.

### 6. Ploidy fix changes FST point estimates 1.6x-31x, contradicting the manuscript's 'not much'

`honesty` · Code: the prior agent’s own fixes · survived **3/3** · manuscript section 5.4 ('Why this is a defect, not a convention') and section 5.3 ploidy paragraph; scripts/callset_io.py:332 isolate_allele_counts

**What is wrong.** The manuscript (section 5.4 and section 5 defect table) says doubling sample
sizes via diploid coding makes FST, TreeMix SEs and XtX 'anticonservative - narrower intervals, more
apparently significant edges, more apparent outliers - without changing the point estimates much'.
For Hudson's FST this is wrong in kind: the sample-size correction enters the numerator
subtractively (-p(1-p)/(n-1) per population), so doubling n inflates the point estimate, and with
these data it inflates it enormously.

**Evidence.** Recomputed on the server from interim/ghana_core_snps.npz with allel.hudson_fst,
haploid (callset_io.isolate_allele_counts) vs diploid (GenotypeArray.count_alleles), ratio-of-
averages: Coastal-Decidous 0.000467 vs 0.002483 (5.3x); Coastal-Guinea 0.002381 vs 0.003827 (1.6x);
Coastal-Transitional 0.001245 vs 0.012726 (10.2x); Decidous-Guinea 0.001346 vs 0.002304 (1.7x);
Decidous-Transitional 0.001219 vs 0.012190 (10.0x); Guinea-Transitional 0.000346 vs 0.010817
(31.3x).

**Why it matters.** The correction is genuinely load-bearing and the prior agent undersold it.
Without the fix the reported maximum pairwise FST would have been 0.0127 (Coastal-Transitional), 5x
the reported 0.0024, and the small-n Transitional comparisons would have looked like the most
differentiated pairs rather than the least. A reader assessing how much to trust 'near-panmictic'
needs to know the headline number is 5-31x sensitive to this one coding choice.

**Fix.** Replace 'without changing the point estimates much' with the measured ratios above, and
state explicitly that the Hudson correction is subtractive so the bias is upward and largest where n
is smallest (Transitional n=25). This strengthens rather than weakens the paper.

### 7. step06_mantel sets no random seed, so both reported p-values are irreproducible Monte Carlo estimates of enumerable exact tests

`reproducibility` · Code: the prior agent’s own fixes · survived **3/3** · /media/biodataA/pf8/gyadu/scripts/step06_mantel.py (no seed; mantel(..., permutations=999) call ~line 165); results/mantel_result_zone.json, results/mantel_result_region.json

**What is wrong.** config.py defines set_seeds() but only step03_umap.py calls it; step06_mantel.py
contains no seed call and no numpy seeding, yet it is the step that produces the only p < 0.05
result in the paper. With 4 and 7 populations the permutation distributions have 24 and 5,040
members and are fully enumerable, so a Monte Carlo approximation is both unnecessary and
unreproducible. The handoff's claim 'Seeds fixed at 42 throughout (config, ADMIXTURE -s, TreeMix
-seed, BayPass -seed)' omits this step.

**Evidence.** grep for seed/random in scripts/step06_mantel.py returns nothing; grep -l set_seeds
over scripts/*.py returns only config.py and step03_umap.py. Re-running the zone test as written
reproduced r=0.5776 but p=0.081 against the stored results/mantel_result_zone.json p=0.09. Exact
enumeration: zone p = 2/24 = 0.0833 (reported 0.090); region p = 141/5040 = 0.02798 (reported
0.029). Twenty 999-permutation repeats of the region test gave p from 0.021 to 0.039, none above
0.05.

**Why it matters.** Conclusions are unaffected - I independently confirmed the exact region p is
0.028, so the one significant result holds. But both published p-values are off in the third decimal
and cannot be reproduced bit-for-bit, and the handoff overstates seed coverage. A thesis examiner
re-running the script will get different numbers.

**Fix.** Call C.set_seeds() at the top of main() in step06_mantel.py, and when n! <= 100,000 compute
the exact one-sided p by enumerating itertools.permutations instead of sampling - about 10 lines,
and it replaces 0.090/0.029 with 0.0833/0.0280 exactly.

### 8. Region-level Mantel p=0.029 depends on an undisclosed truncation of 4 negative F_ST values to zero

`honesty` · Statistical validity · survived **3/3** · /media/biodataA/pf8/gyadu/scripts/step06_mantel.py (lin_fst clip); manuscript §3.9 (line 483), §6.5 caveat paragraph, abstract

**What is wrong.** step06_mantel.py silently clips negative linearised F_ST to zero to satisfy a
scikit-bio input constraint, not for any statistical reason. Four of the 21 region pairs have
negative Hudson F_ST. With the clip (as run) r=0.400, p=0.029. Without it, r=0.381, p=0.049. On
ranks (Spearman-Mantel, which the script supports via `--method spearman` but never ran) r=0.324,
p=0.097. So the headline p-value crosses 0.05 only because of a software-driven data transformation.
The manuscript describes the affected pairs as "five pairs in Figure 6.4 sit at or very near zero
differentiation" (§6.5) — which conceals that four of them are negative and were censored at zero
before the test. No clipping is mentioned anywhere in §3.9, §6.5 or the appendices.

**Evidence.** `/media/biodataA/pf8/gyadu/scripts/step06_mantel.py`: `lin_fst[lin_fst < 0] = 0.0   #
DistanceMatrix rejects negatives`. Recomputed region matrix: 4 of 21 off-diagonal Hudson F_ST are
negative — Ashanti-Volta -0.00104, Brong Ahafo-Volta -0.00035, Eastern-Volta -0.00040, Greater
Accra-Volta -0.00025. Pearson Mantel, 99,999 permutations, one-sided: clipped r=0.4000 p=0.0286
(reproduces the reported 0.400/0.029); unclipped r=0.3807 p=0.0489; raw unclipped F_ST (no
linearisation) r=0.3804 p=0.0489; rank-based Mantel r=0.3244 p=0.0973.

**Why it matters.** The abstract, §6.5, Table 7.1 and §10.2 all carry "r = 0.400, p = 0.029" as the
evidence for isolation by distance. The honest range is p = 0.029 to 0.097 depending on two
undeclared choices (clip and correlation metric), straddling 0.05.

**Fix.** Disclose the clipping in §3.9 and report all three: clipped-Pearson 0.029, unclipped-
Pearson 0.049, rank-Mantel 0.097. Prefer the rank-based Mantel as primary, since the genetic-
distance matrix contains negative values and a long-distance outlier structure that Pearson is
sensitive to. Downgrade the claim accordingly.

### 9. Per-SNP FDR is computable from the POD and never reported; 5 of 11 outlier genes fail FDR 10%

`statistics` · Statistical validity · survived **3/3** · manuscript §6.8 (line 1090), Table 6.7, §7.2 (line 1185); results/baypass/xtx_all_snps.csv

**What is wrong.** The BayPass threshold is the 0.999 quantile of 100,000 POD SNPs, so the expected
number of null SNPs above it is 3,359 x 0.001 = 3.4 out of the 15 called — an FDR of about 22 per
cent. §7.2 says only "No multiple-testing correction beyond the calibrated threshold has been
applied", which is honest but leaves the reader unable to tell which hits are real. Converting each
observed XtX to an empirical p against the POD and applying Benjamini-Hochberg gives q < 0.05 for
only 9 of the 15 SNPs; the lowest 6 (XtX 11.69-12.31) have q = 0.137-0.161. At FDR 10% the gene list
drops from 11 genes to 6: PTP7 (q=0.007), AAT1 (0.007), NT2 (0.007), FIKK4.2 (0.007), PIESP2
(0.011), SNRPF (0.045). The five that fall out are GEXP22 (q=0.137), PF3D7_0215100 RING zinc finger
(0.137), PF3D7_0824200 (0.137), PF3D7_0831400 exported protein (0.137/0.161) and ACS8 (0.144).

**Evidence.** results/baypass/ghana_core_summary_pi_xtx.out (3,359 SNPs) and
ghana_pod_summary_pi_xtx.out (100,000 POD SNPs); threshold 11.2325 from
results/baypass/xtx_calibration.json. BH q-values of the 15 outliers in XtX order: 0.0067 (x5),
0.0112, 0.0192, 0.0294, 0.0448, 0.1369 (x4), 0.1440, 0.1612. Counts: q<0.05 -> 9 SNPs; q<0.10 -> 9;
q<0.20 -> 15. Positions mapped to results/outlier_genes.csv via Pf3D7_09:1402365=GEXP22,
Pf3D7_02:623146=PF3D7_0215100, Pf3D7_08:1056829=PF3D7_0824200,
Pf3D7_08:1344521/1344546=PF3D7_0831400, Pf3D7_02:630420=ACS8.

**Why it matters.** §6.8's second interpretive point — that "several of the remaining genes ...
PTP7, PIESP2, FIKK4.2 and two exported proteins ... belong to the exported and host-interaction
compartment" — loses both of its exported proteins (GEXP22 and PF3D7_0831400, both q~0.14). PTP7,
PIESP2 and FIKK4.2 survive, so the observation is weakened rather than destroyed. The headline AAT1
result (q=0.007 and 0.019 for its two SNPs) is unaffected.

**Fix.** Add a q-value column to Table 6.7, state "expected false positives 3.4 of 15, FDR ~22 per
cent" in §6.8, and split the table into a q<0.05 tier and a marginal tier. Rewrite the exported-
protein sentence to name only the hits that survive FDR 10%.

### 10. "Observed and simulated XtX distributions overlap well" is false (KS D=0.155, p=3e-68) and it is the only stated model-adequacy check

`correctness` · Statistical validity · survived **3/3** · manuscript §8.1 robustness table (line 1633 of extracted text), §6.8; results/baypass/ghana_{core,pod}_summary_pi_xtx.out

**What is wrong.** §8.1 names the overlap of the observed and POD XtX distributions as the
assumption test for the BayPass demographic model: "Poor overlap between the observed and simulated
XtX distributions would indicate the demographic model is inadequate. Here they overlap well." They
do not. A two-sample KS test gives D=0.155, p=3.2e-68; restricted to the non-outlier body (XtX < 8)
it is D=0.158, p=2.0e-70, so the mismatch is in the bulk of the distribution, not in the selected
tail. The POD is stochastically larger through the body (POD median 3.690 vs observed 3.428; 63 per
cent of POD SNPs lie above the observed median) and far shorter in the extreme tail (POD maximum
19.77 and 0.999-quantile 11.23, against observed 0.999-quantile 21.0 and maximum 26.5). The stated
check therefore fails, and the manuscript reports it as passing.

**Evidence.** Quantile comparison (observed | POD): 0.25 3.086|3.219; 0.50 3.428|3.690; 0.75
3.922|4.428; 0.90 4.665|5.399; 0.95 5.244|6.146; 0.99 8.902|8.096; 0.999 21.006|11.232; max
26.477|19.766. Means 3.707|3.990, variances 1.711|1.278. ks_2samp(all) D=0.1545 p=3.24e-68;
ks_2samp(obs<8 vs POD<8) D=0.1580 p=1.98e-70; Mann-Whitney p=5e-85. Fraction of POD above the
observed median = 0.631.

**Why it matters.** The manuscript's only quantitative defence of the BayPass null is contradicted
by the data. The threshold is a quantile of a distribution with a materially different shape from
the one being tested, which undermines the stated rationale for preferring a POD threshold over an
empirical one. The shorter POD tail is also what makes the scan look conservative; that comparison
is not interpretable while the bodies disagree.

**Fix.** Replace the "they overlap well" sentence with the KS statistic and the quantile table, and
state what the mismatch does and does not license. Diagnose the cause (see the MAF-matching finding)
before claiming the threshold is calibrated.

### 11. The POD is not MAF-matched, contrary to §6.8 and §8.1; proper matching gives threshold 10.59 and 18 outliers

`correctness` · Statistical validity · survived **3/3** · manuscript §6.8 (line 1090), §5.6 (line 811), §8.1 (line 1629); /media/biodataA/pf8/gyadu/scripts/step08b_baypass.sh (PI_MAF and the embedded Rscript)

**What is wrong.** §6.8 says the POD was simulated "with the same MAF filter as the observed data"
and §8.1 calls it "100,000 MAF-matched POD SNPs". `pi.maf = 0.05` in simulate.baypass truncates the
simulated *expected* allele frequency pi, not the realised sample frequency, so no such matching
happened: 9,396 of the 100,000 POD SNPs (9.4 per cent) have realised MAF below 0.05, against 0 of
3,359 observed SNPs. The spectra differ throughout, not just at the boundary — POD median MAF 0.212
versus observed 0.136. Importance-resampling the POD to the observed MAF histogram moves the 0.999
quantile from 11.232 to 10.59 +/- 0.21 and the outlier count from 15 to a mean of 18.1 (range
15-19). This is the same bias the author claims to have fixed as defect 6 in Table 5.2; it is only
partly fixed.

**Evidence.** interim/ghana_baypass.geno realised MAF: min 0.0500, 1st pct 0.0507, median 0.1358, 0
SNPs below 0.05. results/baypass/G.pod realised MAF: min 0.0000, 1st pct 0.0211, median 0.2119,
9,396/100,000 below 0.05. Thresholds: all POD 11.232 -> 15 outliers; POD restricted to realised
MAF>=0.05 (90,604 SNPs) 10.532 -> 18 outliers; POD resampled to the observed MAF histogram (200
replicates, n=50,000) 10.585 +/- 0.205, 95% range [10.20, 10.95] -> 18.1 outliers. MAF differences
also explain the body mismatch in the previous finding, since XtX dispersion depends on allele
frequency.

**Why it matters.** Changes a reported number (threshold 11.23 -> ~10.6, outliers 15 -> 18) and
falsifies a methods claim made twice. The direction is anti-conservative, so the reported 15 is the
conservative count and no substantive conclusion flips — but the methods text as written cannot be
reproduced.

**Fix.** Either resample/reweight the POD to the observed MAF histogram and re-derive the threshold,
or correct the methods text to say that pi.maf truncates the expected rather than the realised
frequency and report the sensitivity (11.23/15 vs 10.59/18).

### 12. Abstract says 2 of 6 F_ST CIs span zero; the true number is 3

`numbers` · Numerical audit · survived **3/3** · Manuscript Abstract (Principal findings); results/fst_pairwise.csv

**What is wrong.** The Abstract states "two of six pairs have confidence intervals spanning zero."
Three of six do. results/fst_pairwise.csv gives negative ci95_low for all three transitional-zone
pairs: Coastal–Transitional (-0.000360), Deciduous–Transitional (-0.000423), Guinea–Transitional
(-0.001112). Table 6.4's caption and Section 6.4 both correctly say three ("The three pairs
involving the transitional zone (n = 25) have confidence intervals spanning zero"), so the Abstract
contradicts the body and the source file. I independently recomputed every CI as point ± 1.96×SE and
all six match the file to 5 decimal places, so the file is right and the Abstract is wrong.

**Evidence.** results/fst_pairwise.csv rows 3,4,6: ci95_low = -0.000359996399622059,
-0.0004225297236615793, -0.0011119002463185828. Recomputation: 0.0012447-1.96*0.0008187 = -0.00036;
0.0012192-1.96*0.0008376 = -0.00042; 0.00034608-1.96*0.00074387 = -0.00111. Manuscript Abstract,
para "Principal findings".

**Why it matters.** Understates by one third how many zone comparisons are statistically
indistinguishable from zero, in the one paragraph most readers will read. It is also the kind of
slip a reviewer will find in ten seconds and will use to discount the rest of the numbers.

**Fix.** Change "two of six pairs" to "three of six pairs" in the Abstract.

### 13. Table 4.1's 13.52% genotype-mask rate is over 6,653 isolates, not the 2,017 analysed

`numbers` · Numerical audit · survived **3/3** · Manuscript Table 4.1 row 10; scripts/step04a_prepare_callset.py:207-249

**What is wrong.** Table 4.1 row 10 reports the depth mask as 12,540,727,880 calls → 10,845,661,093
(13.52% masked), presented as a step in the cascade that yields the final matrix. Those counts are
over all 6,653 fetched isolates, because step04a applies the mask before sample alignment: masking
is printed at lines 207-230 and columns are reordered to the 2,017-sample metadata only at line
234/249. The adjacent rows 11-13 (mixed calls, variant missingness, sample missingness) are all on
the 2,017-sample scope. So one row of the cascade silently uses a denominator 3.3x larger than its
neighbours, and the headline 13.52% does not describe the data that entered any analysis.

**Evidence.** scripts/step04a_prepare_callset.py:207 `C.banner("Genotype-level masking")`, :230
`print(f"  Called genotypes: {before:,} -> {after:,} ...")`, :234 `C.banner("Sample alignment")`,
:249 "Genotype columns reordered to match the metadata: 2017 samples", :252 comment "After
alignment, so read depths are fetched only for the samples kept." logs/run_from4_parallel.log: "In-
memory genotype array: (2190026, 6653, 2)" then "Called genotypes: 12,540,727,880 -> 10,845,661,093
(13.52% masked)". 2,190,026 x 6,653 = 14,570,342,978 possible calls, consistent with 6,653 isolates.

**Why it matters.** Changes the meaning of a number in the cascade table and makes rows 10 and 11
non-comparable. The QC-passing isolates have systematically higher call rates (median 0.9962) than
the 4,636 discarded ones, so the true mask rate on the analysed 2,017 isolates is lower than 13.52%
and the table overstates how much data the depth floor cost the analysis.

**Fix.** Add a scope column or footnote to Table 4.1 stating that row 10 is over all 6,653 fetched
isolates while rows 11-14 are over the 2,017 QC-passing set, or have step04a print the mask rate
again after alignment and report that figure.

### 14. The isolation-by-distance result is one region's leverage: r falls 0.400 -> 0.136 when Upper East is dropped

`statistics` · Manuscript honesty and overclaiming · survived **3/3** · manuscript Abstract, §6.5, Table 7.1 row 5, §10.1 bullet 2, Table 10.1 row 2

**What is wrong.** The abstract states "Isolation by distance is supported at region level (Mantel r
= 0.400, p = 0.029)", Table 7.1 reads it as "A weak but real distance effect", and §10.1 rates it
"Moderately supported". §6.5 concedes qualitatively that the fit is "driven substantially by the
Upper East comparisons", but never quantifies it. Removing the 6 Upper East pairs from the 21 leaves
r = 0.136. Within the remaining 15 pairs there is essentially no distance relationship. A single-
population leverage point in a 7-point design is not an isolation-by-distance gradient, and Upper
East is also the region with the distinct sampling years, the distinct polyclonality and 70% of the
isolates — i.e. the result is confounded in exactly the way the manuscript says its other results
are.

**Evidence.** Recomputed region-level Hudson FST from interim/ghana_core_snps.npz with one allele
per isolate (reproduces results/fst_pairwise.csv exactly: Greater Accra-Upper East 0.002381 =
Coastal-Guinea 0.002381). Pearson r on log(km) vs FST/(1-FST), 21 pairs: 0.4000 as run; 0.1358 with
the 6 Upper East pairs removed (15 pairs). Script /tmp/evalwork/mant2.py on gyadu. Note also Brong
Ahafo-Upper East at 352 km has FST 0.000346, lower than Ashanti-Central at 140 km (0.001785), so the
relationship is not monotone even within the long-distance pairs.

**Why it matters.** Downgrades the only positive population-structure result in the paper from "weak
but real" to "not separable from an Upper-East-is-different effect". It also removes the basis for
the convergent-evidence framing in Table 7.1.

**Fix.** Report the leave-one-region-out Mantel r values in §6.5 (or at minimum the Upper-East-
excluded value) and soften the claim to "consistent with isolation by distance but not separable
from a single-region effect". Reviewer-note H already says "either strengthen it or soften the
claim" — this is the number that forces the choice.

### 15. Abstract says "two of six pairs" have CIs spanning zero; the correct number is three

`numbers` · Manuscript honesty and overclaiming · survived **3/3** · manuscript Abstract, "Principal findings" (line 139); results/fst_pairwise.csv

**What is wrong.** The abstract states "two of six pairs have confidence intervals spanning zero."
Table 6.4, its caption, §6.4 and Table 10.1 all correctly say three. The abstract is the one place a
reader checks, and the error runs in the direction that makes the results look firmer than they are.

**Evidence.** results/fst_pairwise.csv ci95_low: Coastal-Transitional -0.000360, Decidous forest-
Transitional -0.000423, Guinea-Transitional -0.001112 — three negative lower bounds. Manuscript line
139 (abstract) vs line 1302 (Table 10.1: "Yes for three of six pairs") and Table 6.4 caption ("The
three pairs involving the transitional zone ... have confidence intervals spanning zero"). The prior
agent's own HANDOFF_evaluation.md also says "3 of 6 pairs".

**Why it matters.** A factual self-contradiction in the abstract that understates uncertainty. Cheap
to fix, expensive if a reviewer finds it, because it undermines the manuscript's central claim to
arithmetic traceability.

**Fix.** Change "two of six" to "three of six" in the abstract, and add the analysed transitional-
zone n (25, not the 50 the abstract quotes from the pre-QC join).

### 16. "Five independent lines of evidence" — four read the same matrix and the fifth points the other way

`honesty` · Manuscript honesty and overclaiming · survived **3/3** · manuscript §7.1 Table 7.1 and surrounding text, §10.1 bullet 1, Reviewer-notes closing assessment

**What is wrong.** §7.1 ("Five independent lines of evidence converge on the same conclusion"),
§10.1 ("Five independent analyses agree. This is a well-supported result") and the closing
assessment ("well supported by five independent lines of evidence") all rest on an independence
claim that is false. FST, ADMIXTURE (on 2,923 LD-pruned sites of the same 3,359) and TreeMix are all
computed from the same per-zone allele counts; TreeMix's covariance matrix and pairwise FST are
near-deterministic functions of each other at this scale. Only the ordinations use a different input
(the Pf8 distance matrix) — and on a different, pre-QC sample. Separately, the Mantel row is listed
as a convergent line although its reading ("A weak but real distance effect") is evidence of
structure, i.e. the opposite direction from panmixia.

**Evidence.** manuscript Table 7.1 rows; Table 4.1 filter 15 (LD pruning applied to the same 3,359
SNPs for ADMIXTURE only); Appendix C: interim/allele_counts_by_zone.npz "feeds stages 7 and 8"; §6.3
opening (ordinations on the 4,905 pre-QC set). Lines 1159, 1291, 1786.

**Why it matters.** Inflates the evidential weight of the headline negative result by a factor that
a population geneticist will spot immediately. Replacing "five independent lines" with an accurate
description costs nothing and removes the single easiest attack on the paper.

**Fix.** Rewrite as "four summaries of one genotype matrix, plus three ordinations of the published
Pf8 distance matrix on the pre-QC sample" and state explicitly that the agreement is largely
arithmetic rather than independent corroboration. Move the Mantel row out of the convergence table
into a separate line, since it argues for weak structure.

### 17. "The one variable that orders cleanly along the north-south gradient" does not, on the manuscript's own numbers

`correctness` · Manuscript honesty and overclaiming · survived **3/3** · manuscript §6.2 [Interpreted], §7.3 "Polyclonality as the clearest ecological signal", §10.1 bullet 6

**What is wrong.** §7.3 states that polyclonality "orders cleanly along the north-south gradient
(0.597 in Guinea savanna to 0.444 in coastal savanna)" and §6.2 reads the ordering as "consistent
with a north-south transmission-intensity gradient". Ghana's zones run north to south as Guinea
savanna, transitional, deciduous forest, coastal savanna (Brong Ahafo lies north of Ashanti). The
reported fractions in that geographic order are 0.597, 0.500, 0.539, 0.444 — not monotone. The
transitional zone, which is north of the deciduous forest, has the lower polyclonality. The quoted
range is formed by citing only the two endpoints and skipping the two that break the trend. The
transitional value is also 25/50, which carries no information.

**Evidence.** manuscript §6.2 [Observed] ("Guinea savanna 0.597 (2,153 of 3,605), deciduous forest
0.539 (439 of 815), transitional zone 0.500 (25 of 50), coastal savanna 0.444 (193 of 435)") and
§7.3 line 1188. Zone ordering from the proposal abstract: "Sudan savanna, Guinea savanna,
transitional zone, moist semi-deciduous forest, and coastal savanna".

**Why it matters.** The claim held up as the clearest ecological signal in the paper is stated more
strongly than the four numbers support, and it is the finding most likely to be developed into a
results section (reviewer-note F item 7). Getting the ordering wrong there would propagate.

**Fix.** State all four fractions in geographic order, note that the transitional zone breaks the
monotone trend and that its 25/50 is uninformative, and test the trend formally with and without the
transitional zone (and with year as a covariate, since coastal is 2018-heavy and national
transmission declined over 2009-2021).

### 18. TreeMix: the saturation argument that voids m=3 applies equally at m=1, which is then used as evidence

`statistics` · Manuscript honesty and overclaiming · survived **3/3** · manuscript §6.7, Table 7.1 row 4, §10.1 bullet 4

**What is wrong.** §6.7 correctly argues that with four populations "three edges on four tips is
close to saturation — the model can reproduce almost any covariance structure at that point". It
then declares "The improvement from m = 0 to m = 1 (0.876 to 0.935) is the one substantive result",
and Table 7.1 and §10.1 carry that improvement as one of the convergent lines ("Supported"). The
same parameter count voids it. The fitted quantity is the 6 off-diagonal between-population
covariances (the manuscript's own definition, matching get_f). An unrooted 4-taxon tree has 5
branch-length parameters, so m=0 already has 1 residual degree of freedom; m=1 adds a weight plus
extra branch lengths, leaving zero or negative. A variance-explained increase from 5 to 7 parameters
fitted to 6 numbers is not evidence of gene flow.

**Evidence.** results/treemix/model_comparison.csv (m=0 0.8760, m=1 0.9346, m=2 0.9633, m=3 0.99762,
m=4 0.99762, m=5 0.99761); results/treemix/model_selection.json "variance_explained_definition":
"over off-diagonal (between-population) covariances"; manuscript §6.7 [Interpreted], Table 7.1 row
4, §10.1 bullet 4.

**Why it matters.** Removes one of the five claimed convergent lines of evidence and one of §10.1's
"established" findings. Also closes the inconsistency where the manuscript applies a degrees-of-
freedom argument against m=3 but not against m=1.

**Fix.** State the parameter count explicitly (6 off-diagonal targets, 5 parameters at m=0) and say
that no m is informative with 4 populations, rather than singling out m=1 as substantive. Reviewer-
note C item 4 already asks which m to report; the answer the data support is none — report the
covariance matrix and stop.

### 19. Outliers are physically clustered, so "15 SNPs in 11 genes" overstates the number of independent signals

`statistics` · Manuscript honesty and overclaiming · survived **3/3** · manuscript §6.8, Table 6.7 and caption, Abstract; results/baypass/outlier_snps.bed

**What is wrong.** §6.8 and the abstract report "15 outlier SNPs ... intersecting 11 genes" as if 15
tests had independently exceeded the threshold, and the gene-level enrichment reading ("several of
the remaining genes ... belong to the exported and host-interaction compartment") treats them as
independent hits. Five of the 15 fall into clustered pairs well within P. falciparum LD range. No LD
pruning was applied to the scan (Table 4.1 filter 15 applies it to ADMIXTURE only), and clustering
is nowhere mentioned.

**Evidence.** results/baypass/outlier_snps.bed: Pf3D7_08_v3 1,344,521 and 1,344,546 (25 bp apart,
same gene PF3D7_0831400); Pf3D7_11_v3 1,054,078 and 1,054,447 (369 bp, SNRPF and its 3' flank);
Pf3D7_06_v3 1,214,350 and 1,215,233 (883 bp, both AAT1); Pf3D7_02_v3 623,146 and 630,420 (7.3 kb,
PF3D7_0215100 and PF3D7_0215300); Pf3D7_08_v3 1,056,829 and 1,064,970 (8.1 kb, PF3D7_0824200 and
PF3D7_0824400). Mean genome-wide SNP spacing in the matrix is ~6.9 kb, so several of these pairs are
adjacent scanned sites.

**Why it matters.** The effective number of independent outlier signals is roughly 9-10, not 15, and
two of the 11 "genes" (PF3D7_0215100/0215300 and PF3D7_0824200/0824400) are 7-8 kb neighbours that
may share one signal. This changes the counts quoted in the abstract and weakens the exported-
protein enrichment impression. It also removes the "two outlier SNPs" corroboration for AAT1.

**Fix.** Report outliers as clusters, not SNPs: list each cluster with its span, peak XtX and
overlapping genes, and state the number of independent clusters alongside the SNP count. This also
makes the proposed functional-enrichment permutation test (reviewer-note F item 8) valid, which it
is not on 15 linked SNPs.

### 20. [Observed] tag misapplied to a projection and to a claim no log records

`honesty` · Manuscript honesty and overclaiming · survived **3/3** · manuscript §4.2.6 [Observed], §3.5 [Observed] and "Consequence for the core-genome filter"

**What is wrong.** The evidence key defines [Observed] as "Printed directly by a pipeline script and
preserved in a log or results file." Two load-bearing claims carry that tag without meeting it. (a)
§4.2.6: "[Observed] The diagnostic panel establishes that this is a property of the organism and the
population, not of the pipeline: ... only about 4,832 SNPs genome-wide reach MAF >= 5 per cent ...
The ceiling is therefore roughly 5,500 SNPs" — this is a genome-wide extrapolation from a SNP panel,
hedged with "about" and "roughly", plus an interpretive causal attribution; it is [Calculated] plus
[Interpreted] at best. (b) §3.5: "[Observed] ... Every one of them carries RegionType = 'Core',
confirmed by a direct tabulation" — RegionType is not among VARIANT_FIELDS, is not in the local
store, and no log or results file records the tabulation. I independently verified this claim and it
is TRUE, so the defect is traceability, not accuracy.

**Evidence.** (a) manuscript §4.2.6 [Observed] paragraph; the 5,500 ceiling is also carried into
§7.3 and Table 9.1 row 4 without the projection caveat. (b) scripts/step03a_fetch_callset_zarr.py:13
(docstring assertion only) and :67 VARIANT_FIELDS = [CHROM, POS, REF, ALT, numalt, is_snp,
FILTER_PASS]; interim/pf8_ghana.zarr/*/variants/ contains no RegionType; no hit for "RegionType" in
logs/. Independent check against https://pf8-release.cog.sanger.ac.uk/zarr: 2,190,026 PASS biallelic
SNPs, RegionType Counter({'Core': 2190026}); genome-wide RegionType Counter({'Core': 10678058,
'SubtelomericHypervariable': 1069628, 'SubtelomericRepeat': 477093, 'InternalHypervariable': 235993,
'Centromere': 18731, 'Apicoplast': 11122, 'Mitochondrion': 2580}).

**Why it matters.** The evidence-tag system is the manuscript's main credibility device. Two
[Observed] tags on claims that are an extrapolation and an unrecorded assertion respectively devalue
every other tag. The core-genome claim is also the one that justifies dispensing with
pf_core_regions.bed, so a reader is entitled to see the tabulation.

**Fix.** Retag §4.2.6 as [Calculated] with the panel size and extrapolation method stated, and keep
the causal attribution as a separate [Interpreted] sentence. For §3.5, add a tiny script that prints
the RegionType x FILTER_PASS cross-tabulation to a log (it runs in minutes against the public store;
note that Pf8's FILTER vocabulary includes SubtelomericHypervariable, SubtelomericRepeat,
InternalHypervariable and Centromere, so PASS implies Core by construction — worth saying, since it
makes the claim structural rather than empirical).

### 21. The most consequential methods justification contains a garbled sentence and overstates its own evidence

`correctness` · Manuscript honesty and overclaiming · survived **3/3** · manuscript §4.2.5 "Genotype quality mask (filter 10)"

**What is wrong.** §4.2.5 is the justification for disabling the GQ filter, the decision that raised
the SNP count by 57% and therefore affects every downstream number. Its key evidence sentence is
left in a self-correcting, mid-sentence state: "Applying the GQ rule halved the number of common
SNPs surviving the missingness bar (from 51.0 per cent of panel SNPs under DP-only masking to... in
fact missingness <= 10 per cent fell from 74.3 per cent of SNPs under DP-only to 51.0 per cent under
DP+GQ)". "Halved" is also wrong on both available figures: 74.3% -> 51.0% is a 31% relative
reduction, and 3,359 -> 2,143 SNPs is a 36% reduction. The paired frequency comparison (0.282 ->
0.294) is additionally between two different SNP sets rather than the same sites, so it does not
test what it is offered to test.

**Evidence.** manuscript line 741 (§4.2.5, "Evidence gathered before deciding"), quoted verbatim.
SNP counts from §4.2.5 itself (2,143 under DP+GQ, 3,359 under DP-only).

**Why it matters.** This paragraph is the single place a reviewer will look hardest (the
manuscript's own reviewer-note C puts it first). A visible unedited fragment and a wrong relative-
change word there do more damage than the underlying decision, which is defensible.

**Fix.** Rewrite the sentence with one consistent pair of numbers; replace "halved" with the actual
relative reduction; and state that the allele-frequency comparison is across different SNP sets, so
the concordance check reviewer-note C asks for is still outstanding.

### 22. Mantel p-values are unseeded: reported p = 0.090 and p = 0.029 are not reproducible

`reproducibility` · Reproducibility and engineering · survived **3/3** · scripts/step06_mantel.py:162-172

**What is wrong.** step06_mantel.py never calls C.set_seeds() and passes no seed to
skbio.stats.distance.mantel, which draws its 999 permutations from numpy's unseeded global RNG.
Twelve repeats of the committed zone-level test gave p from 0.069 to 0.090, and the manuscript's
reported 0.090 is the maximum of those draws. The region-level p = 0.029 carries the same Monte-
Carlo noise (SE about 0.005 at 999 permutations) and is the only significant result in the abstract.

**Evidence.** grep of step06_mantel.py finds no 'set_seeds' and no seed argument to mantel();
C.set_seeds() is called in step03_umap.py:225 but nowhere in step06. Twelve unseeded repeats on
results/fst_matrix.npy and results/geographic_distance_km_zone.csv: r = 0.5776 fixed, p = [0.079,
0.088, 0.082, 0.086, 0.090, 0.074, 0.082, 0.084, 0.069, 0.088, 0.074, 0.077].

**Why it matters.** Two reported p-values change on every run, including the one that supports the
isolation-by-distance conclusion in the abstract.

**Fix.** Add C.set_seeds() at the top of main() and raise --permutations to 99999 (7 populations,
cost in milliseconds). Re-run both levels and update the JSON files, figures and abstract.

### 23. Appendix B attributes three ADMIXTURE parameters to config.py that config.py does not control

`honesty` · Reproducibility and engineering · survived **3/3** · manuscript Appendix B Table B.1; scripts/step05b_admixture.sh:24-35

**What is wrong.** Table B.1 lists K_MIN/K_MAX = 2,8; ADMIXTURE_CV_FOLDS = 10; LD_PRUNE_ARGS =
50,10,0.2 under 'Set in: config.py'. step05b_admixture.sh never reads config.py; it hardcodes
K_MIN=${K_MIN:-2}, K_MAX=${K_MAX:-8}, CV_FOLDS=${CV_FOLDS:-10}, PRUNE_WIN/STEP/R2 = 50/10/0.2. A
grep across every script finds zero references to config.ADMIXTURE_CV_FOLDS and
config.LD_PRUNE_ARGS; config.MANTEL_JSON and config.BAYPASS_THREADS are likewise referenced nowhere.
By contrast step07b_treemix.sh really does shell out to read config.TREEMIX_*, so the practice is
inconsistent rather than uniformly absent.

**Evidence.** grep -l for C./config. forms of ADMIXTURE_CV_FOLDS, LD_PRUNE_ARGS, MANTEL_JSON and
BAYPASS_THREADS across scripts/*.py returns nothing. step05b_admixture.sh:24-35.
step07b_treemix.sh:59-66 runs python -c 'import config as C; print(C.TREEMIX_MAX_M,
C.TREEMIX_BLOCK_SIZE, C.TREEMIX_ROOT)'. config.BAYPASS_THREADS = 4 while the run used 8. config.py's
docstring promises 'exactly one place to change a path'.

**Why it matters.** A successor who edits config.py to change LD pruning or CV folds re-runs and
gets identical output with no warning. The manuscript's configuration table is wrong for 3 of its 20
rows.

**Fix.** Either make step05b read config.py the way step07b does, or correct the 'Set in' column to
step05b_admixture.sh and delete the four dead constants from config.py.

### 24. "No panel locus among the outliers" hides measured XtX at five panel genes and an outlier 912 bp from pfap2mu

`honesty` · Biological interpretation · survived **3/3** · manuscript Section 6.8, [Observed] and [Interpreted] paragraphs

**What is wrong.** Section 6.8 says "None of the eight validated antimalarial resistance loci in the
configured panel ... appears among the outliers" and concludes "These data cannot distinguish the
two" (uniform selection vs lack of power). Both statements understate what is in hand. Five of the
eight panel genes have SNPs inside the 3,359-SNP scan with measured, non-significant XtX — that is a
quantified negative, not an absence. And one of the two intergenic outliers sits 912 bp upstream of
pfap2mu (PF3D7_1218300), i.e. in its putative promoter, with a zone difference that survives year
control.

**Evidence.** XtX at panel positions (results/baypass/xtx_all_snps.csv joined to Pf8 ANN): pfcrt
N75K Pf3D7_07_v3:403623 XtX 4.32; pfcrt intron 405528 XtX 2.89; pfdhfr N51I 748239 XtX 7.89; pfdhfr
C59R 748262 XtX 9.16; pfdhps 548505 XtX 2.84 and 550871 XtX 3.11; pfmdr2 F423Y 1956408 XtX 4.87 and
S208N 1957053 XtX 6.55; pfap2mu E163E 718443 XtX 3.03. Threshold 11.23. Intergenic outlier
Pf3D7_12_v3:715788, XtX 14.76 (8th highest of 3,359), nearest genes PF3D7_1218200 end at 715718 (70
bp) and PF3D7_1218300 AP2-MU start at 716700 (912 bp); zone ALT freq Coastal 0.307, Forest 0.183,
Transitional 0.240, Guinea 0.111; restricted to 2018 Coastal 0.318 (n=173) vs Guinea 0.078 (n=549),
chi2 = 64.2, p < 1e-14.

**Why it matters.** Changes an uninformative null into a reportable result and removes a statement a
thesis examiner can falsify from the author's own result files. The pfap2mu-adjacent outlier is
directly on the thesis's marker panel and is currently invisible in the manuscript.

**Fix.** Replace the "no panel locus appears" sentence with a table of every panel SNP that entered
the scan, its XtX and its zone frequencies, and state explicitly which panel loci could not be
tested (see finding 1). Add the nearest-gene distance for both intergenic outliers and flag the
pfap2mu proximity.

### 25. Table 6.7's per-gene max XtX understates SNRPF; two of the fifteen outliers' XtX values appear nowhere

`correctness` · Biological interpretation · survived **3/3** · manuscript Table 6.7 and its caption ("two of the 15 outlier SNPs fall outside annotated protein-coding genes")

**What is wrong.** The results table reports max XtX per intersecting gene, so the 5th and 8th
strongest outliers in the whole scan are absent from the manuscript entirely. The chr11 outlier is
59 bp past SNRPF's annotated 3' end, which means SNRPF's reported max XtX of 14.01 omits an adjacent
XtX of 20.08 that is almost certainly the same signal. A reader cannot reconstruct the outlier set
from the document.

**Evidence.** results/baypass/xtx_all_snps.csv, is_outlier rows ranked by XtX: 26.48, 24.44, 21.97,
21.52, 20.08, 18.02, 16.05, 14.76, 14.01, 12.31, 12.18, 12.07, 12.04, 11.90, 11.69. The manuscript's
Table 6.7 lists 26.48, 24.44, 21.97, 21.52, 18.02, 14.01, 12.31, 12.18, 12.07, 12.04, 11.90 — 20.08
and 14.76 appear nowhere in the document. Pf3D7_11_v3:1054447 (XtX 20.08) vs PF3D7_1126900 SNRPF
1052969-1054388 = 59 bp downstream; the in-gene SNRPF outlier is 1054078 (Gly29Arg, XtX 14.01).
Pf3D7_12_v3:715788 (XtX 14.76) is 70 bp from PF3D7_1218200 and 912 bp from pfap2mu.

**Why it matters.** No conclusion changes, but the table's ordering by max XtX is misleading for
SNRPF and the two highest-ranked unreported outliers include the pfap2mu-adjacent site (finding 3).
Reproducibility and completeness.

**Fix.** Make the primary table one row per outlier SNP: chromosome, position, XtX, SnpEff
consequence and amino-acid change, nearest gene and distance. Keep the gene-level table as a
summary. Use a window (e.g. gene +/- 1 kb) for the intersection rather than exact gene bounds.

### 26. The polyclonality gradient is confounded with partner study and site, not with depth or year as hypothesised

`biology` · Biological interpretation · survived **3/3** · manuscript Section 6.2 [Interpreted], Section 4.2.2, Section 9 Table 9.1; results/sample_qc_full.csv

**What is wrong.** Section 6.2 reads the Fws ordering (Guinea 0.597 to Coastal 0.444) as "arguably
the clearest ecological signal in the entire analysis", and Section 9 lists year as the confound.
The actual confound is partner study and sampling site: Coastal savanna is 100% one study, one
region and one sample type, and Guinea savanna never appears in that study, so the headline Coastal-
vs-Guinea contrast is entirely between-study. Within that one study, the neighbouring Central region
is as polyclonal as Guinea savanna. The depth and year hypotheses, by contrast, do not hold — which
is a defensible thing to report.

**Evidence.** results/sample_qc_full.csv (n=4,905). Coastal savanna: 435/435 from study 1241-PF-GH-
ANINAGYEI, 435/435 Greater Accra, 435/435 sWGA. Study 1241 contains no Guinea savanna samples.
Within study 1241, polyclonal fraction by region: Central 0.585, Greater Accra 0.444, Eastern 0.392
— a within-study spread (0.392-0.585) wider than the whole claimed zone gradient (0.444-0.597), and
Central matches Guinea savanna's 0.597. Transitional zone is the only all-gDNA zone (50/50 gDNA)
while the other three are predominantly sWGA, and gDNA vs sWGA mean Fws differ (0.814 vs 0.837).
Checks that come out clean: Spearman(Fws, % callable) = 0.027 (p=0.061) overall and 0.018 (p=0.21)
after within-study centring; Spearman(Fws, Year) = 0.050; across the 11 studies, study-mean Fws vs
study-median % callable Spearman = -0.28 (p=0.40); and the gradient survives restriction to sWGA
only (Coastal 0.444, Forest 0.554, Guinea 0.598).

**Why it matters.** Does not reverse the result — the direction matches Ghana's EIR literature
(Kassena-Nankana annual EIR ~228-630, Navrongo 157-1,132, versus coastal savanna villages ~60-96 and
urban Accra 6.6-19.2) — but it changes how strongly it can be claimed, and it names the right caveat
in place of the wrong one. If this is to be developed as a result in its own right (Section 8.2 item
7), the study confound must be stated.

**Fix.** State that Coastal savanna is a single partner study / single region / single sample type
and that the Coastal-Guinea Fws contrast is therefore between-study. Report the within-study-1241
regional breakdown as the internal control, report the sWGA-only stratum as the sample-type control,
and cite the Ghana EIR literature for the expected direction rather than asserting the gradient.
Exclude or separately flag Transitional (all gDNA, median year 2012).

### 27. "Eight validated antimalarial resistance loci" is wrong, and the panel omits the thesis's own pfaat1

`correctness` · Manuscript honesty and overclaiming · survived **2/3** · manuscript §3.9 "Annotation (Stage 9)", §6.8 [Observed] (line 1154), Abstract; scripts/config.py:173

**What is wrong.** §3.9 and §6.8 describe the cross-reference panel as "eight validated antimalarial
resistance loci" including pfcoronin and pfap2mu. The project's own literature review states that
pfcoronin is "not a WHO-validated marker at present", and pfap2mu and pfmdr2 are likewise candidate
rather than validated markers. More consequentially, the panel in config.py omits PF3D7_0629500
(pfaat1), which the proposal names as a panel member — which is precisely why the manuscript's top
hit appears as an unflagged outlier rather than as a hit on a pre-specified candidate.

**Evidence.** scripts/config.py:173-182 KNOWN_RESISTANCE_LOCI (eight IDs, no PF3D7_0629500).
Proposal line 96: "Pfcoronin has been linked to artemether-lumefantrine failure ... Neither is a
WHO-validated marker at present"; line 144: "Adding pfcoronin, pfaat1 and the background loci
flagged by Tandoh and colleagues". Manuscript lines 486 and 1154.

**Why it matters.** Makes the resistance-null claim sound stronger than its definition supports, and
hides that the scan's top candidate was a pre-specified thesis marker. Also means the panel cross-
reference did not test the markers the thesis actually cares about (pfaat1 S258L, pfcoronin P76S).

**Fix.** Call it "a panel of validated and candidate resistance loci", list which are WHO-validated
and which are candidates, add PF3D7_0629500 (pfaat1) and the other proposal-panel loci to
config.KNOWN_RESISTANCE_LOCI, and re-run stage 9's cross-reference (seconds).

### 28. gdv1 — the standout FST outlier of the most directly relevant prior study — has zero scanned SNPs and is never mentioned

`improvement` · Manuscript honesty and overclaiming · survived **2/3** · manuscript §6.8, §7.1 (West African comparison), §8.2 (checks not performed)

**What is wrong.** The project's literature review calls Mobegi et al. (2014) "the more directly
relevant work" and reports that its most striking result was "exceptional differentiation at a
handful of loci, above all a 15 kb region spanning gdv1", attributed to the difference in vector
abundance and seasonality between the two settings. The Ghana data show exactly that kind of
transmission contrast (polyclonality 0.597 vs 0.444). A directed look-up of gdv1's XtX would have
been a hypothesis test rather than a fishing expedition. It was never done, and gdv1 has no SNP in
the 3,359-site matrix, so it could not have been tested — a fact that belongs in the power
discussion.

**Evidence.** Proposal line 58. PlasmoDB-71: PF3D7_0935400 (GDV1) spans
Pf3D7_09_v3:1,377,653-1,381,134. Query of results/baypass/xtx_all_snps.csv over that span returns 0
rows (/tmp/evalwork/panel.py). Manuscript §6.8 and §7.1 do not mention gdv1.

**Why it matters.** Converts a fishing-expedition outlier list into a design with at least one a
priori target, and adds a concrete, citable instance to the power argument: the scan cannot test the
one locus the most relevant prior study nominated.

**Fix.** Add a pre-specified target list to §6.8 (gdv1 plus the proposal's resistance panel) with
the scanned-SNP count and maximum XtX for each, stating explicitly which were untestable. This is
the same table that fixes the pfk13/pfmdr1/pfcoronin finding.

### 29. Seven clonal groups span more than one ecological zone; they are discarded as redundancy and never reported

`improvement` · Filtering and QC decisions · survived **2/3** · /media/biodataA/pf8/gyadu/scripts/step03b_sample_qc.py, clonal_groups() and the representative-selection block; manuscript 4.2.4

**What is wrong.** Clonal pruning removes 77 isolates from 68 near-identical groups. Seven of those
groups contain isolates from more than one ecological zone. Near-identical parasite genomes
recovered in different zones are the most direct evidence available in this dataset for recent
parasite movement between zones - which is the paper's central claim - and the pipeline throws them
away as redundancy without counting or reporting them.

**Evidence.** Computed from /media/biodataA/pf8/gyadu/results/sample_qc_full.csv: 145 isolates in 68
multi-member clonal groups at the chosen threshold of 0.00005; grouping by clonal_group and counting
distinct zone values gives 7 groups with zone nunique > 1. Context: median pairwise genotype
distance among Ghanaian isolates is 0.00112, so these pairs are ~22x closer than typical, and the
largest group contains 3 isolates (no single-linkage chaining). Two incidental checks that came out
clean and should not be treated as findings: the clonal-representative rule (sorted by call_rate
then Fws) causes only 1 isolate to be lost to a filter interaction where the chosen representative
fails Fws while a dropped member passes, and only 1 of the 68 groups ends with zero surviving
isolate.

**Why it matters.** A positive result left on the floor. Pairwise F_ST of 0.0024, a Mantel r that is
marginal at zone level, and an ADMIXTURE CV that barely prefers K=2 over K=1 are all weak, indirect
evidence for gene flow. Seven cross-zone identical-by-descent groups are direct evidence,
independent of allele-frequency estimation, and they cost nothing to report because the grouping is
already computed and written to disk.

**Fix.** Add a short results paragraph and a supplementary table listing the 7 cross-zone clonal
groups with their zone pairs, collection years and studies, computed from the existing clonal_group
/ zone columns of sample_qc_full.csv. Check the year and study fields for each: a cross-zone group
within one study and year could be a sample-handling or barcode artefact rather than migration, and
that distinction should be stated. Keep the pruning for the main analyses - the point is to report
the groups, not retain them.

### 30. The documented reproduce command cannot regenerate the reported XtX threshold, independent of RNG

`reproducibility` · Reproducibility and engineering · survived **2/3** · scripts/step08b_baypass.sh:72-77 and logs/stage8_pod_rerun.log:1

**What is wrong.** Appendix E says 'bash run_all.sh --from 4 --parallel' reproduces the analysis,
but it cannot regenerate 11.232. The POD that fixes the threshold was a manual re-run at 12 threads,
whereas run_all.sh --parallel exports NTHREADS=8. step08b_baypass.sh guards the core model with an
existence check on ghana_core_summary_pi_xtx.out, so that manual re-run silently reused the 8-thread
core output while simulating a 12-thread POD against it. The committed script plus the documented
command therefore mix two configurations that were never run together.

**Evidence.** logs/stage8.log:25 'threads: 8'; logs/stage8_pod_rerun.log:1 'Populations: 4  SNPs:
3359  threads: 12'. step08b_baypass.sh:72-77 'if [ -f "ghana_core_summary_pi_xtx.out" ]; then echo "
core model output already present - skipping"'. run_all.sh:109 'export NTHREADS="${NTHREADS:-8}"'.
File mtimes: ghana_core_* 03:56:27, G.pod 04:00:48, ghana_pod_* 04:05:21, xtx_threshold.txt
04:05:22.

**Why it matters.** The single calibration constant that turns the scan into a result list came from
a configuration no documented command reproduces.

**Fix.** Re-run stage 8 end to end from the committed script at one fixed thread count, with the
core-model skip guard removed or keyed to an input hash, and record the actual invocation in the
methods.

### 31. The exported-protein enrichment the manuscript lists as untested is strongly positive

`improvement` · Biological interpretation · survived **2/3** · manuscript Section 6.8 [Interpreted]; Section 8.2 item 8; Section 10 "testable now, not yet tested"

**What is wrong.** Section 6.8 asserts that "several of the remaining genes ... belong to the
exported and host-interaction compartment" and Section 8.2 item 8 lists the matched permutation test
as not performed. The claim is accurate and the test is positive with a large effect, computable in
seconds from files already on the server. Leaving it as an unquantified impression is a needless
weakness.

**Evidence.** Classified the 1,561 genes carrying at least one of the 3,359 scan SNPs by PlasmoDB-71
description/Name matching exported|erythrocyte membrane|surface protein|FIKK|PHIST|Maurer|EMP1
trafficking|rifin|stevor. Exported outlier genes: PF3D7_0301700 PTP7, PF3D7_0424700 FIKK4.2,
PF3D7_0501200 PIESP2, PF3D7_0831400 (exported, unknown function), PF3D7_0935500 GEXP22 = 5 of 11.
Background exported fraction among scanned genes 0.0589. Fisher exact OR = 14.0, p = 2.22e-4. SNP-
level, which conditions on SNP density: 6 of 13 in-gene outlier SNPs exported vs 0.076 of the 2,880
non-outlier in-gene SNPs, OR = 10.4, p = 2.23e-4.

**Why it matters.** Converts a qualitative aside into a quantified enrichment result and closes one
of the manuscript's own listed gaps. Also strengthens the immune-selection interpretation, which is
currently asserted without support.

**Fix.** Report the Fisher test (both gene-level and SNP-level). The SNP-level version already
controls for SNP density, so the length/density-matched permutation described in Section 8.2 is
optional; if run, match on CDS length and SNP count per gene.


## Confirmed — low severity

### 1. Figure 6.5 (ADMIXTURE CV) plots K=2-8 only; K=1 is missing and the caption describes a figure that does not exist

`reproducibility` · Code: never-reviewed scripts · survived **3/3** · /media/biodataA/pf8/gyadu/scripts/config.py:157 and /media/biodataA/pf8/gyadu/figures/admixture_cv.png; manuscript Figure 6.5 caption

**What is wrong.** config.py sets `K_MIN, K_MAX = 2, 8`, so step05c_plot_admixture.py plotted only
K=2-8. figures/admixture_cv.png was written at 04:04 on Oct 9; results/admixture/ghana_pruned.1.Q
was written at 04:08, i.e. the K=1 run finished after the figure was made and step05c was never re-
run. results/admixture/cv_errors.csv has no K=1 row. The rendered figure (verified by opening
/Users/samnimoh/Desktop/chromo/pf8_proof/admixture_cv.png) shows a monotonically rising curve from
K=2 with an auto-scaled y-axis spanning 0.8373-0.8432, titled "ADMIXTURE CV error (minimum at K =
2)" — it looks like a decisive optimum. The caption, however, reads "The curve is nearly flat and
the total range across K = 1-8 is 0.0058". The figure cannot show a K=1-8 range because it does not
contain K=1, and with its own axis limits it does not look flat.

**Evidence.** scripts/config.py:157 `K_MIN, K_MAX = 2, 8`. results/admixture/cv_errors.csv contains
K=2..8 only. `ls -la results/admixture/` timestamps: cv_errors.csv 04:04, ghana_pruned.1.Q 04:08,
figures/admixture_cv.png 04:04. Rendered PNG inspected: x-axis ticks 2,3,4,5,6,7,8; no K=1 point;
y-range 0.8373-0.8432. Manuscript Figure 6.5 caption claims the K=1-8 range of 0.0058.

**Why it matters.** The single most informative point — K=1 = 0.84199, the no-structure reference
the whole "near-panmictic" conclusion rests on — is absent from the figure that is supposed to
demonstrate it, and the figure's visual message (steep, decisive K=2) is the opposite of the text's
(flat, K=2 barely beats K=1). Adding K=1 places a point at y=0.84199, between K=6 and K=7, making
the non-monotonicity and the flatness immediately visible.

**Fix.** Re-run `python step05c_plot_admixture.py --k-min 1` (logs/admixture_K1.out already exists,
so read_cv will pick it up), regenerate figures/admixture_cv.png and
results/admixture/cv_errors.csv, and re-copy to pf8_proof/. Optionally set the y-axis lower bound to
0 or annotate the axis range so the flatness is not hidden by autoscaling.

### 2. Zone-level Mantel p reported as a Monte Carlo estimate when the exact value is enumerable

`reproducibility` · Statistical validity · survived **3/3** · manuscript §6.5 (lines 1012, 1014), abstract; /media/biodataA/pf8/gyadu/scripts/step06_mantel.py (`permutations` default 999)

**What is wrong.** With 4 populations all 4! = 24 permutations can be enumerated exhaustively, so
the exact one-sided p is available and there is no reason to approximate it with 999 random draws.
The exact value is 2/24 = 0.0833 (the observed arrangement ranks 2nd of 24; the 24 permutation r
values are all distinct, so there are no ties to adjudicate), against the reported 0.090. The
manuscript's accompanying statement that "the finest attainable p-value is 0.042 and significance
requires essentially the single best permutation" is a correct bound but is paired with a Monte
Carlo p, which is internally inconsistent — the right statement is that the exact p is 2/24 and that
no zone-level test could ever reach 0.05 unless the observed arrangement were the single best of 24.

**Evidence.** results/mantel_result_zone.json: p_value 0.09, permutations 999, mantel_r 0.5776.
Exhaustive enumeration over all 24 permutations of the 4x4 zone matrices (F_ST matrix from
results/fst_matrix.csv, geographic distances from the sample-weighted zone centroids): observed r =
0.5776, number of permutations with r >= observed = 2, exact p = 0.0833; the 24 r values are [-0.637
... 0.500, 0.509, 0.578, 0.602], all distinct.

**Why it matters.** A reported p-value is 8 per cent off its exact value for no reason, in a passage
that is specifically about permutation resolution. No conclusion changes (both are above 0.05).

**Fix.** At k <= 8 enumerate exhaustively and report the exact p (2/24 = 0.083). One branch in
step06_mantel.py.

### 3. Abstract says "two of six pairs" have CIs spanning zero; it is three

`numbers` · Statistical validity · survived **3/3** · manuscript abstract, "Principal findings" paragraph (line 139 of extracted text)

**What is wrong.** The abstract states "two of six pairs have confidence intervals spanning zero".
Three do. Table 6.4's caption, §9.1 and §10.2 all correctly say three, so the abstract is the only
place that is wrong — and it errs in the direction of overstating how much of the F_ST evidence is
statistically resolved.

**Evidence.** results/fst_pairwise.csv has negative ci95_low for all three transitional-zone pairs:
Coastal-Transitional -0.000360, Forest-Transitional -0.000423, Guinea-Transitional -0.001112.
Manuscript line 139 (abstract) says "two of six pairs"; line 1007 (Table 6.4 caption) says "The
three pairs involving the transitional zone (n = 25) have confidence intervals spanning zero"; line
1302 says "Yes for three of six pairs"; line 1669 says "Three FST confidence intervals spanning
zero".

**Why it matters.** A reader who reads only the abstract — which is most readers, and the thesis
examiner's first pass — gets the wrong count, biased toward the result looking better resolved than
it is.

**Fix.** Change "two of six" to "three of six" in the abstract.

### 4. The RegionType = "Core" tabulation that voids the subtelomeric warning is nowhere recorded

`reproducibility` · Numerical audit · survived **3/3** · Manuscript Section 3.5 ("Consequence for the core-genome filter"); interim/pf8_ghana.zarr/*/variants/; scripts/step03a_fetch_callset_zarr.py:13

**What is wrong.** Section 3.5 states, under the [Observed] label: "Every one of them carries
RegionType = 'Core', confirmed by a direct tabulation." There is no such tabulation. The local Zarr
store does not retain RegionType (its variants group holds only ALT, CHROM, FILTER_PASS, is_snp,
numalt, POS, REF); no log in logs/ contains the string "RegionType"; the only occurrences in the
whole project are a prose docstring line in scripts/step03a_fetch_callset_zarr.py:13 and unexercised
code in the unused step04a_prepare_callset_malariagen.py. The manuscript's own evidence key defines
[Observed] as "printed directly by a pipeline script and preserved in a log or results file", which
this is not.

**Evidence.** `ls interim/pf8_ghana.zarr/Pf3D7_01_v3/variants/` → ALT CHROM FILTER_PASS is_snp
numalt POS REF. `grep -rni regiontype logs/` → no matches. scripts/step03a_fetch_callset_zarr.py:13:
"Every PASS site in Pf8 has RegionType \"Core\", so the PASS filter already does the job the
optional core-region BED does". logs/run_from4_parallel.log still prints the pipeline's warning: "No
core-region BED found in data/ — subtelomeric var/rifin regions are NOT excluded. Genotyping there
is unreliable and will dominate Step 8's outlier list."

**Why it matters.** This single unrecorded claim is the sole basis for declaring the pipeline's own
subtelomeric-contamination warning "a false alarm in this dataset", which in turn underwrites the
whole outlier list. It matters concretely: the top outlier is PTP7 (PF3D7_0301700, an
EMP1-trafficking exported protein) at Pf3D7_03_v3:96,476, ~96 kb from a chromosome end, and the
second-tier hits include PIESP2 at Pf3D7_05_v3:65,071 plus two unnamed exported proteins — exactly
the compartment the warning names. Section 6.8 then reads that exported-protein composition as a
possible immune-selection signal.

**Fix.** Tabulate variant_RegionType over the PASS-biallelic site set from the public Pf8 Zarr (one
1-D array fetch, no genotypes) and write the counts to a log, or re-label the claim [Interpreted]
and reinstate the subtelomeric caveat on the outlier list in Sections 6.8 and 7.2.

### 5. A large block of [Observed]-labelled numbers has no log, script or results-file source

`reproducibility` · Numerical audit · survived **3/3** · Manuscript Sections 4.2.2, 4.2.3, 4.2.5, 4.2.6, 5.6, 8.1; Tables 4.2 and 4.3

**What is wrong.** Many quantitative claims carrying the [Observed] label (defined in the manuscript
as "printed directly by a pipeline script and preserved in a log or results file") exist nowhere in
logs/, scripts/ or results/. Specifically: the GQ diagnostic panel (12.6% of hom-ref and 12.4% of
hom-alt calls below GQ 20; median depths 46 and 40; 3.0% and 0.7% at DP>=10; missingness<=10%
falling from 74.3% to 51.0% of panel SNPs; mean alt-allele frequency 0.282 vs 0.294), the MAF
ceilings ("about 4,832 SNPs" and "about 5,529"), all of Table 4.2 (2,117 / 3,416 / 1,843 / 1,878 and
the per-zone splits), the Fws sensitivity projections (2,341 and 2,924 isolates), the call-rate
figures (1,566 / 449 flagged-but-otherwise-passing / their median call rate 0.956), and the POD MAF
comparison ("17.0 per cent of simulated sites ... against 0.5 per cent of observed"). By contrast I
reproduced Table 4.3 exactly, all 35 cells, from interim/ghana_dist_submatrix.npy, so the gap is
specific to these diagnostics rather than general.

**Evidence.** Grepped each value across logs/, scripts/ and results/: 4832, 5529, 2341, 2924, 2117,
3416, 1566, 449, 0.956, 74.3, 51.0 return only incidental substring hits inside .Q/.P matrices and
embedding CSVs, never a printed diagnostic. scripts/ contains no sensitivity or panel script
(step00–step09 and config/callset_io only). Manuscript Table 4.3's caption itself admits "the
corresponding script is not part of the pipeline". My independent recomputation of the Fws
projections from results/sample_qc_full.csv gives 2,343 and 2,926 against the stated 2,341 and
2,924.

**Why it matters.** These numbers are the entire justification for the two most consequential
session decisions (disabling the GQ filter, which raised the SNP count 2,143 → 3,359, and disabling
the call-rate MAD rule). They cannot be audited or reproduced, and Section 9.3's reproducibility
claim does not mention the gap. The 2-isolate offsets in the Fws projections suggest they were
computed by a method that is not recoverable.

**Fix.** Commit the diagnostic scripts to scripts/ and their output to logs/ (they are cheap to re-
run), or downgrade these claims from [Observed] to [Calculated] with the procedure stated, and add
the gap to Section 9.3's list of what is not reproducible.

### 6. Appendix D reference counts are wrong three ways: 26 claimed, 30 listed, subtotals sum to 27

`numbers` · Numerical audit · survived **3/3** · Manuscript Appendix D; Section 11.1-11.5

**What is wrong.** Appendix D opens "All 26 references were checked against publisher-deposited
metadata. Of these, 25 were fully verified via the Crossref REST API." Section 11 actually lists 30
references (11.1: 2; 11.2: 8; 11.3: 7; 11.4: 6; 11.5: 7). The appendix's own subtotals then give
"Fully verified (24 entries)", "Verified without a DOI (2 entries)" and "Partially verified (1
entry)", which sum to 27 — contradicting both its own header count of 26 and its own "25 were fully
verified" sentence, and leaving 3 of the 30 listed references unaccounted for under any verification
category.

**Evidence.** Programmatic count of author-year entries in the Section 11 block of the extracted
manuscript: 30 (29 matched by a capitalised-surname pattern plus "van der Maaten, L., & Hinton, G.
(2008)"). Appendix D text: "All 26 references" / "25 were fully verified" / "Fully verified (24
entries)" + "(2 entries)" + "(1 entry)".

**Why it matters.** Appendix D exists solely to establish that the bibliography was independently
verified. Three mutually inconsistent counts in its first five lines, none of which equals the
number of references actually present, destroys the assurance it is meant to provide — and leaves
open whether the three unaccounted references were ever checked.

**Fix.** Recount: state 30 references, assign each to exactly one of the three verification
categories, and make the subtotals sum to 30.

### 7. Section 10.1 says the outlier list is "headed by AAT1"; Table 6.7 is headed by PTP7

`honesty` · Numerical audit · survived **3/3** · Manuscript Section 10.1 bullet 5 (and Table 10.1 row 5); results/outlier_genes.csv

**What is wrong.** Section 10.1 bullet 5 reads "Fifteen SNPs in 11 genes exceed a calibrated
differentiation threshold, headed by AAT1 (PF3D7_0629500)". AAT1 does not head the list.
results/outlier_genes.csv, which Table 6.7 reproduces faithfully and in the correct order, puts PTP7
(PF3D7_0301700) first at max XtX 26.48; AAT1 is second at 24.44. Table 6.7's own ordering is "by
maximum XtX", so "headed by" is false on the manuscript's own stated ranking. Section 6.8 is careful
here — it calls AAT1 "the one entry with a direct and recent literature connection" and "the
strongest candidate", which is a defensible interpretive claim — but 10.1 converts that into a rank
claim that the data contradict.

**Evidence.** results/outlier_genes.csv line 2: PF3D7_0301700,PTP7,EMP1 trafficking protein
PTP7,1,26.47654196; line 3: PF3D7_0629500,AAT1,amino acid transporter AAT1,2,24.43605575.
results/baypass/xtx_all_snps.csv top two outliers: Pf3D7_03_v3:96476 xtx=26.4765 (PTP7),
Pf3D7_06_v3:1215233 xtx=24.4361 (AAT1).

**Why it matters.** In the conclusions section, the gene with a publishable chloroquine-resistance
story is presented as the top-ranked hit when it is second. That is the specific direction of error
a reviewer treats as motivated, and it is avoidable because Section 6.8 already states the honest
version.

**Fix.** Change "headed by AAT1" to "headed by PTP7 (max XtX 26.48), with AAT1 (PF3D7_0629500,
24.44) second and the only entry carrying a direct resistance-literature connection", matching
Section 6.8's wording.

### 8. The core-genome claim is true but the evidence cited for it was never produced in this pipeline

`honesty` · Biological interpretation · survived **3/3** · manuscript Section 3.5 [Observed]/[Interpreted] and Section 2.1; scripts/step03a_fetch_callset_zarr.py:67

**What is wrong.** Section 3.5 states "Every one of them carries RegionType = 'Core', confirmed by a
direct tabulation" and Section 2.1 lists the retrieved store as holding "per-site annotations
including FILTER_PASS and RegionType". RegionType was never retrieved: step03a's VARIANT_FIELDS
omits it, the local store has no such array, and no log records the tabulation. The claim itself is
true (I verified it independently against the release) and the underlying logic is sound — but it is
definitional, not empirical, and stating it as an observation with a tabulation that does not exist
is the kind of thing a reviewer who checks will find.

**Evidence.** scripts/step03a_fetch_callset_zarr.py:67 VARIANT_FIELDS = ["CHROM", "POS", "REF",
"ALT", "numalt", "is_snp", "FILTER_PASS"]. Walking interim/pf8_ghana.zarr: per-contig variants
arrays are ALT, CHROM, FILTER_PASS, POS, REF, is_snp, numalt only — no RegionType. `grep -rn
RegionType scripts/ logs/` returns only a docstring assertion at step03a:13 and the unused
alternative script step04a_prepare_callset_malariagen.py. logs/run_from4_parallel.log:33-38 shows
the applied filter was FILTER=PASS plus SNP plus biallelic, and the pipeline's own "No core-region
BED found ... var/rifin regions are NOT excluded" warning fired. Independent verification against
the release: all-site RegionType counts Core 10,678,058 / SubtelomericHypervariable 1,069,628 /
SubtelomericRepeat 477,093 / InternalHypervariable 235,993 / Centromere 18,731 / Apicoplast 11,122 /
Mitochondrion 2,580; among the 2,190,026 PASS biallelic SNPs, Core 2,190,026 and nothing else.

**Why it matters.** Does not change any number, but it is a verifiable overstatement in the one
place the manuscript overrides an explicit pipeline warning. If challenged and not defensible from
the record it costs more credibility than the point is worth.

**Fix.** Replace the appeal to a tabulation with the structural argument, which is stronger and
checkable from the release metadata: Pf8's FILTER vocabulary itself contains the region categories
(FILTER_SubtelomericHypervariable, FILTER_SubtelomericRepeat, FILTER_InternalHypervariable,
FILTER_Centromere, FILTER_Apicoplast, FILTER_Mitochondrion), so a non-Core site cannot be PASS by
construction. Then either add RegionType to VARIANT_FIELDS and print the tabulation, or cite the
release documentation. Also correct Section 2.1's field list.

### 9. rifin and stevor SNPs are present in the analysis set, so their absence from the outlier list is a result, not a tautology

`correctness` · Biological interpretation · survived **3/3** · manuscript Section 6.8 [Observed] and Section 3.5 "Consequence for the core-genome filter"

**What is wrong.** Section 6.8 says "no outlier falls in a recognised antigenic-variation or
invasion gene family" and Section 3.5 implies the PASS filter excludes var/rifin/stevor entirely.
The second part is not exact: four of the 3,359 analysis SNPs lie in rifin or stevor genes, all
RegionType Core. That makes the absence of antigenic-family genes from the outlier list a genuine
(if weakly powered) finding rather than a filtering artefact — which is the more useful claim.
Separately, the top outlier is non-coding, which the gene-centric table obscures.

**Evidence.** Scan SNPs mapped to PlasmoDB-71 genes: PF3D7_0114700 (RIF) Pf3D7_01_v3:563710 missense
XtX 3.49 and 564033 stop_gained XtX 4.36; PF3D7_0401600 (RIF) Pf3D7_04_v3:93405 missense XtX 3.81;
PF3D7_0402600 (stevor) Pf3D7_04_v3:159572 missense XtX 2.99. No var (PfEMP1) SNPs in the set.
Consequence breakdown of the 15 outliers from Pf8 SnpEff: 9 missense, 1 synonymous, 2 3'UTR, 1
5'UTR, 2 intergenic. The top outlier PTP7 Pf3D7_03_v3:96476 (XtX 26.48) is a 3_prime_UTR_variant,
not a coding change.

**Why it matters.** Lets the manuscript make a stronger claim (antigenic-family genes were tested
and are not differentiated) instead of an incorrect one (they were filtered out). The consequence
breakdown matters because Table 6.7 reads as a list of coding hits.

**Fix.** Note that four rifin/stevor SNPs survive into the scan and are not outliers. Add the SnpEff
consequence column to the outlier table and say explicitly that the top-ranked outlier is a 3'UTR
variant and that 5 of 15 outliers are non-coding.

### 10. The 15 outliers are not independent; AAT1's "two outlier SNPs" are in strong LD (r2 = 0.60)

`statistics` · Code: never-reviewed scripts · survived **2/3** · /media/biodataA/pf8/gyadu/scripts/step09_annotate.py:165-168; manuscript §6.8 [Interpreted], first observation

**What is wrong.** Neither step08a_baypass_input.py, step08c_calibrate_xtx.py nor step09_annotate.py
applies LD pruning or clumping, and step09 counts `n_outlier_snps=("xtx","size")` per gene as if the
SNPs were independent observations. Five of the 15 outliers are members of close same-chromosome
pairs with substantial LD. In particular the two AAT1 SNPs (Pf3D7_06_v3:1,214,350 and 1,215,233, 883
bp apart) have r2 = 0.602, and the manuscript uses the pair as corroboration: "it carries two
outlier SNPs here with a maximum XtX of 24.44. That makes it the strongest candidate in the set".
The two PF3D7_0831400 SNPs are 25 bp apart (r2 = 0.398) and the two chromosome-11 SNPs 369 bp apart
(r2 = 0.454).

**Evidence.** Computed r2 from interim/ghana_core_snps.npz (haploid allele matrix gt[:,:,0],
pairwise-complete) for all same-chromosome outlier pairs within 200 kb: 02:623146-630420 r2=0.262
(n=1777); 06:1214350-1215233 r2=0.602 (n=1803); 08:1056829-1064970 r2=0.101 (n=1785);
08:1344521-1344546 r2=0.398 (n=1803); 11:1054078-1054447 r2=0.454 (n=1866). step08a lines 67-96 and
step09 lines 165-168 contain no LD handling.

**Why it matters.** "15 outlier SNPs in 11 genes" overstates independence: the effective number of
independent signals is about 11, not 15. More specifically, the sentence that elevates AAT1 to "the
strongest candidate in the set" rests on a SNP count of two that is really closer to one independent
observation — AAT1 is not the top hit by XtX (PTP7 is, at 26.48).

**Fix.** Report pairwise r2 among outliers in step09's output and add an LD-clumped count (e.g.
collapse outliers within 10 kb and r2 > 0.3 into one signal). In §6.8, replace "it carries two
outlier SNPs here" with "it carries two outlier SNPs 883 bp apart (r2 = 0.60), i.e. one LD-clumped
signal" and rank AAT1 by its XtX (24.44, second behind PTP7) rather than by SNP count.

### 11. step07c docstring misdescribes its own selection rule, and the rule degenerates to argmax

`correctness` · Code: the prior agent’s own fixes · survived **2/3** · /media/biodataA/pf8/gyadu/scripts/step07c_plot_treemix.py (module docstring, lines ~14-20; pick_m, ~line 115)

**What is wrong.** The new module docstring states 'The rule in each range: the smallest m whose
variance explained reaches 0.998; failing that, the maximum-likelihood m.' The implemented fallback
in pick_m() is different - 'smallest m within VE_PLATEAU (0.001) of the best variance explained in
the range'. Worse, that fallback silently reduces to 'the largest m in the range' whenever variance
explained is still rising, which is the same class of failure the prior agent fixed in the original
(gains.fillna(1).idxmax() always returning m=0), just at the other extreme.

**Evidence.** scripts/step07c_plot_treemix.py module docstring vs pick_m() docstring/body (the
'else' branch uses best - VE_PLATEAU, never log_likelihood). results/treemix/variance_explained.csv:
m=0 0.87597, m=1 0.93456, m=2 0.96334, m=3 0.99762, m=4 0.99762, m=5 0.99761. In the identifiable
range 0..2 no two values are within 0.001, so the rule returned m=2 purely as the argmax, and
model_selection.json records basis='no m reached 0.998; smallest m within 0.001 of the best variance
explained in 0..2 (0.9633)'. VE_THRESHOLD was never reached by any m (max 0.99762 < 0.998), so the
documented primary rule never fired at all.

**Why it matters.** The manuscript's 'TreeMix fit improves monotonically to a plateau at three
migration edges' is defensible for the full range (0.99762 / 0.99762 / 0.99761 is a genuine
plateau), but the m=2 pick reported for the identifiable range carries no plateau or adequacy
evidence - 0.963 after a 0.028 jump from m=1 is not a plateau. Anyone reading the docstring will
also believe a likelihood criterion was used.

**Fix.** Correct the module docstring to match pick_m. Have pick_m return a flag when the chosen m
equals the range maximum and no plateau was detected (i.e. the rule hit the boundary), and surface
that in model_selection.json and on the figure. Also soften the 'Pickrell & Pritchard (2012)'
attribution for 0.998 - that paper reports f as a goodness-of-fit summary, not a model-selection
cut-off, and with 4 populations f is computed from only 6 off-diagonal values.

### 12. Temporal F_ST is estimable within a zone and accounts for the entire transitional-zone signal

`statistics` · Statistical validity · survived **2/3** · manuscript §7.2 "Spatial effects cannot be separated from temporal ones", §9.1, Table 6.4 (three transitional pairs)

**What is wrong.** §7.2 says "Spatial effects cannot be separated from temporal ones" and leaves it
there, but the temporal rate is directly estimable from within-zone year contrasts and was never
computed. Within Guinea savanna alone, 2017 (n=243) versus 2018 (n=556) gives Hudson F_ST = +0.00017
+/- 0.00008 (z=2.2) — a detectable one-year signal in a single zone. The transitional zone and
coastal savanna differ by 6 median years; linear accumulation at that rate predicts ~0.0010,
essentially the whole of the observed Coastal-Transitional F_ST of 0.00124 and of the Forest-
Transitional 0.00122. Conversely, coastal (median 2018) and Guinea (2017) are 1 median year apart,
so the headline 0.00238 is largely spatial. At region level the confound is in fact separable and
was not tried: |median-year difference| is nearly orthogonal to log distance (r = -0.053), the
partial Mantel controlling for it gives r = 0.445, p = 0.016, and a year-difference-only Mantel
gives r = 0.341, p = 0.072.

**Evidence.** Within Guinea savanna, Hudson F_ST 2017 vs 2018 = +0.00017, block-jackknife SE
0.00008, z=+2.22 (interim/ghana_core_snps.npz, blen=167). Region median years: Brong Ahafo 2012,
Ashanti 2015, Volta 2016, Upper East 2017, Greater Accra 2018, Central 2020, Eastern 2020. Zone
median years per the manuscript: Transitional 2012, Coastal 2018. Partial Mantel on the 21 region
pairs: r(F_ST/(1-F_ST), log distance | |dYear|) = 0.4451, permutation p = 0.0163 (9,999
permutations); r(F_ST, |dYear|) = 0.3409, p = 0.0721; r(log distance, |dYear|) = -0.0525.

**Why it matters.** Supplies a quantified, unacknowledged consequence of the known year/zone
confound: the three transitional-zone F_ST values are of the same magnitude as the differentiation
their 6-year offset alone predicts, so they are plausibly temporal rather than spatial. It also
strengthens the headline pair (1 median year apart) and shows that at region level the confound is
separable and the distance signal survives it (r=0.445, p=0.016) — a result the manuscript should be
claiming.

**Fix.** Add a within-zone temporal F_ST table (Guinea savanna by year, the only zone with the depth
for it) to §6.4, add the partial Mantel to §6.5, and qualify the transitional-zone rows of Table 6.4
accordingly rather than leaving §7.2's blanket "cannot be separated".

### 13. No isolate is "assigned entirely (1.000)" at K = 2; the maximum is ADMIXTURE's 0.99999 bound

`numbers` · Numerical audit · survived **2/3** · Manuscript Section 6.6 [Observed] paragraph; results/admixture/Q_K2.csv

**What is wrong.** Section 6.6 states "At least one isolate is assigned entirely (1.000) to a single
component." No isolate reaches 1.000. In results/admixture/Q_K2.csv the extreme values are exactly
0.99999 and 0.00001 — ADMIXTURE's internal clamp — and 100 of the 1,900 isolates sit at that bound.
The claim is a rounding artefact of a software boundary presented as a property of the data, and "at
least one" understates the count by two orders of magnitude.

**Evidence.** results/admixture/Q_K2.csv: max(comp1) = 0.99999, min(comp1) = 1e-05; count of
isolates with comp1 >= 0.99999 or comp2 >= 0.99999 = 100.

**Why it matters.** Small, but it is the one sentence in Section 6.6 that gestures at any
individual-level structure, and it is an artefact. If it is kept it invites a reviewer to ask what
those 100 isolates are (plausibly residual clonal or low-coverage isolates) — a question worth
answering rather than one worth raising by accident.

**Fix.** Replace with "100 of 1,900 isolates sit at ADMIXTURE's parameter bound of 0.99999 for one
component", and say whether those isolates are concentrated in any zone or year.

### 14. §3.7 cross-references the GQ/DP revision to the wrong section

`reproducibility` · Manuscript honesty and overclaiming · survived **2/3** · manuscript §3.7 "Thresholds"

**What is wrong.** §3.7 states "the depth and quality settings were revised during this session and
that revision is documented in Section 5.5." Section 5.5 is "TreeMix jackknife block size". The
genotype-mask revision is documented in §4.2.5. In a manuscript whose stated purpose is that "a
reader can tell, without re-running anything, which statements rest on recorded output", a broken
pointer to the single most consequential methodological decision is a traceability defect rather
than a typo.

**Evidence.** manuscript line 476 (§3.7 "Thresholds") vs §4.2.5 "Genotype quality mask (filter 10)"
and §5.5 "TreeMix jackknife block size".

**Why it matters.** Minor on its own, but it sends a reader following the paper's most important
decision to the wrong place. Worth a sweep of all internal cross-references before circulation.

**Fix.** Change to Section 4.2.5 and verify every other internal section reference (the document has
roughly 40 of them and no automated cross-reference fields).

### 15. ADMIXTURE K=1 is not produced by the pipeline, and step05c silently consumes the manual leftover

`reproducibility` · Reproducibility and engineering · survived **2/3** · scripts/step05b_admixture.sh:24-25 and scripts/step05c_plot_admixture.py:41,116

**What is wrong.** The sweep runs K=2..8 (K_MIN and K_MAX are hardcoded in the shell script). K=1,
the manuscript's no-structure reference, exists only from a manual run at 04:08:35. Consequences:
Figure 6.5 (figures/admixture_cv.png, written 04:04:55, before K=1 existed) plots K=2..8 only while
its caption and Table 6.5 are labelled 'K = 1-8', which I confirmed by inspecting the image; step05c
builds its barplot panels from glob('ghana_pruned.*.Q'), so re-running it today picks up the
leftover ghana_pruned.1.Q and yields an 8-panel figure where the manuscript's has 7; and step05b's
summary line greps logs/admixture_K*.out, which now also matches admixture_K1.out, so a re-run
rewrites cv_errors.txt with different content without computing anything.

**Evidence.** results/admixture/cv_errors.txt and cv_errors.csv contain only K=2..8 (0.83736 to
0.84316). ghana_pruned.1.Q mtime 04:08:35 vs ghana_pruned.2.P 03:57:14; figures/admixture_cv.png
04:04:55; figures/admixture_barplots.png 04:06:38. Visual inspection: CV plot x-axis runs 2 to 8;
barplot has exactly 7 panels, K=2 to K=8.

**Why it matters.** A figure caption and a table claim a range the figure does not show, and the
figure cannot be regenerated as published by any documented command.

**Fix.** Set K_MIN=1 in step05b_admixture.sh so the sweep owns the reference point, delete the hand-
made leftovers, re-run step05b and step05c, and have step05c read its K range from cv_errors rather
than globbing the directory.

### 16. The fws_sites column in the published QC table is a boolean flag, not a site count, and reads as n=1

`reproducibility` · Biological interpretation · survived **2/3** · /media/biodataA/pf8/gyadu/scripts/step03b_sample_qc.py:177; /media/biodataA/pf8/gyadu/results/sample_qc_full.csv

**What is wrong.** results/sample_qc_full.csv ships a column named fws_sites whose value is 1 for
every one of the 4,905 isolates, because the code writes a boolean indicator rather than the number
of contributing sites. Anyone auditing the supplementary table will read it as "Fws estimated from a
single site" and discount the entire Fws filter, which carries the largest exclusion in the pipeline
(57%).

**Evidence.** scripts/step03b_sample_qc.py:177 — `stats["fws_sites"] = (sum_hs > 0).astype(int)`. In
results/sample_qc_full.csv, fws_sites has min=max=1 and sd=0 across all 4,905 rows; Spearman(Fws,
fws_sites) is undefined (constant input).

**Why it matters.** No number changes. But it is a self-inflicted credibility hazard in the one
table that documents the filter responsible for the largest sample loss, and it also means the
actual per-isolate site count behind each Fws value is not recorded anywhere.

**Fix.** Change to `(ok.sum(axis=0))` accumulated across chunks so the column records the real
number of qualifying sites per isolate, or rename it fws_estimable and add a separate fws_n_sites.
Re-export sample_qc_full.csv and report the median site count in Section 3.6.


---

## Disputed — survived only 1 of 3 verifiers

Treat as leads, not findings.

- **The unperformed mapping-quality check on the 15 outliers resolves in the analysis's favour and should be reported** (Biological interpretation, claimed medium) — The handoff and Reviewer Notes flag that several outliers are in repetitive exported-protein
families and that no mapping-quality check was done, leaving the objection open. The check is cheap
and comes out clean: the outliers have better-than-background alignment and variant-quality metrics,
and all 15 are core-genome sites. Reporting this removes the single easiest reviewer attack on the
outlier
- **The abstract and both conclusion sections omit that 70% of the analysed isolates come from one region** (Manuscript honesty and overclaiming, claimed medium) — Table 9.1 row 7 states plainly that "The 'national' picture is substantially a Upper East picture"
(70% of the final set). The abstract gives pre-QC zone counts ("Guinea savanna (n = 3,605)") and
never the analysed per-zone n, never the regional imbalance, and then concludes "The Ghanaian
parasite population behaves as a largely panmictic unit". §10.1, §10.2 and the plain-language
summary likewise
- **Mobegi 2014 is cited for a finding that inverts what it reported, and as a within-country benchmark when it is between-country** (Manuscript honesty and overclaiming, claimed medium) — §7.1 states the result is consistent "with the observation that differentiation within West African
countries is weak relative to the differentiation between endemicity strata that Mobegi et al.
(2014) reported between The Gambia and Guinea." Per the project's own reading of that paper, Mobegi
found shared balancing selection across the two endemicity strata, population-specific directional
select
- **The 117 sample-missingness drops are non-random by study, not by zone - answering the zone question but exposing a batch one** (Filtering and QC decisions, claimed low) — The 117 isolates dropped by the stage-4a sample-missingness bound (<= 0.20) are not significantly
non-random across ecological zones, so that particular worry is unfounded. They are strongly non-
random across sequencing studies, which is a third independent demonstration of the batch structure
that is absent from the documented limits.
- **environment.yml does not describe the environment that ran, and there is no lockfile** (Reproducibility and engineering, claimed high) — environment.yml declares name: pf8ghana, python=3.11 and 'mamba env create'. The environment that
ran is /home/gyadu/.conda/envs/spatial on Python 3.10.22, built with micromamba, as the manuscript's
own Appendix A states. bedtools is listed in the yml but is not installed in the env: Stage 9's gene
intersection used /usr/bin/bedtools v2.30.0, a system binary outside the captured environment, and
b
- **BayPass POD fails the canonical Omega-recovery check, which was never run** (Code: the prior agent’s own fixes, claimed critical) — The entire XtX threshold (11.232) rests on a pseudo-observed dataset that does not reproduce the
covariance matrix it was simulated from. The BayPass manual's POD validity check (agreement between
the core Omega and the Omega re-estimated from G.pod, via fmd.dist) was never performed by the prior
agent's POD fix. When run, it fails badly. The manuscript substitutes a different, weaker check
(bulk 
- **g[:, :, 0] silently discards half-called genotypes; latent, not triggered here** (Code: the prior agent’s own fixes, claimed low) — _count_mixed() classifies a call as mixed only when both copies are >= 0, so a half-call such as
(-1, 0) or (0, -1) is not flagged. isolate_allele_counts then takes g[:, :, 0]: a (-1, 0) call is
dropped as missing even though an allele was called, and a (0, -1) call is counted as a confident
call. The docstring's assurance that 'the first copy is the isolate's allele' holds only for fully
called o
- **TreeMix m>=2 optima are degenerate; the abstract presents m=3 as a fit plateau** (Statistical validity, claimed medium) — The m=3 fit that the abstract calls a plateau ("TreeMix fit improves monotonically to a plateau at
three migration edges") is a non-identified optimum, and the diagnostics that say so are in the
output files but nowhere in the manuscript. At m=3 the migration weights are 0.0131, 0.9158 and
0.0694 — a weight of 0.92 means the target population's ancestry is essentially entirely from the
source — an
- **§5.5's stated rationale for the TreeMix block-size change was never realised** (Statistical validity, claimed low) — §5.5 justifies changing the TreeMix jackknife block size from 500 to 50 SNPs on the grounds that 6-7
blocks is "far too few for stable standard errors, which in turn makes the migration-edge tests
unreliable". No migration-edge test was ever produced, because `-se` was not passed. `-k` does
legitimately affect the covariance standard errors (`.covse`) that enter TreeMix's likelihood, so
the change
- **F_ST jackknife uses ~20 blocks (167 SNPs), never stated, and contradicts Section 5.5's own standard** (Numerical audit, claimed high) — Section 3.8 says only "Blocks are 2,000 SNPs by default, reduced automatically to at most one
twentieth of the available SNPs." The actual block length in force is blen = min(2000, max(10,
3359//20)) = 167 SNPs, giving ~20 jackknife blocks. The manuscript never states 167 or 20. This is
directly inconsistent with Section 5.5, which rejects the supplied TreeMix setting precisely because
"With 3,359
- **The "residual heterozygous call rate ... 0.0000" is printed before mixed-call resolution, not after** (Numerical audit, claimed medium) — Section 5.3 states: "The residual heterozygous call rate printed by Step 4a is 0.0000 to four
decimal places, consistent with the Fws filter having already removed most mixed infections." That
printout is not residual. step04a prints the heterozygous call rate at line 256 and calls
resolve_mixed_calls at line 263 — i.e. the 0.0000 is the rate before any resolution, which is why
the very next log l
- **Validation window totals round to 472 million while Section 8.1 says ~471 million** (Numerical audit, claimed low) — Section 3.5 reports "zero differing values across 158 million, 139 million and 175 million compared
values", which sums to 472 million; Table 8.1 reports "approximately 471 million compared values".
The 471 figure is the correct one (471,231,990). The discrepancy comes from rounding the middle
window's 138,515,460 up to "139 million". The underlying validation itself is sound: all three
windows ma
- **The headline FST confidence intervals rest on ~20 jackknife blocks, a count the manuscript never states** (Manuscript honesty and overclaiming, claimed medium) — §5.5 argues that 6-7 TreeMix jackknife blocks are "far too few for stable standard errors, which in
turn makes the migration-edge tests unreliable" and fixes it to ~67 blocks, stating the number. §3.8
describes the FST jackknife only as "Blocks are 2,000 SNPs by default, reduced automatically to at
most one twentieth of the available SNPs" and never states the resulting count. The auto-rule yields
- **Table 5.2's "Verification" column conflates "it ran", "it is documented" and "I tested it myself" with "it is correct"** (Manuscript honesty and overclaiming, claimed medium) — The manuscript discloses the review's non-exhaustiveness well (§5.7 closing, reviewer-notes E,
question G10) but never discloses the actual conflict: the same author found the defects, wrote the
fixes, chose the verification, and reported the verdict. Table 5.2 is presented as evidence of
rigour, yet several of its "Verification" entries establish nothing about correctness. "Stage 7 ran
to complet
- **The panel cross-reference uses gene bodies only; an outlier sits 912 bp from pfap2mu** (Manuscript honesty and overclaiming, claimed medium) — The resistance-panel cross-reference intersects outlier positions with protein-coding gene features
only, with no flanking window. One of the 15 outliers (XtX 14.76, 6th highest) lies 912 bp upstream
of pfap2mu (PF3D7_1218300), a panel locus — close enough to be in near-complete LD with it in P.
falciparum. The manuscript nevertheless reports it only as one of "two of the 15 outlier SNPs [that]
fa
- **The reviewer-notes objections all attack the data; none attacks the conclusions drawn from it** (Manuscript honesty and overclaiming, claimed medium) — Reviewer-notes D lists eight objections, and they are genuine, severe and well-evidenced — but every
one of them is an objection to the design or the inputs (zone=region, year confound, SNP count, Fws
exclusion, n=25, possible artefacts, GQ removal, zone-layer provenance). Not one objects to an
inference. The objections that would actually damage the paper are absent: that the five lines of
eviden
- **Table 4.2's blank ">= 0.90" call-rate row is answerable in one line from a file the pipeline already wrote** (Filtering and QC decisions, claimed medium) — Section 4.2.3 contains an explicit honesty note that the call-rate MAD rule was disabled after
seeing its effect on sample counts, and that "a reviewer is entitled to ask whether the alternative
was examined with equal care. Table 4.2 records the alternatives that were quantified before the
choice was made." Table 4.2 then leaves the entire ">= 0.90" row blank. The isolate-count half of
that row i
- **The Pf8 manifest's own "% callable" metric was never used, and the in-house call rate is on a different scale from it** (Filtering and QC decisions, claimed medium) — The Pf8 sample manifest carries "% callable", MalariaGEN's own genome-wide call-rate metric, and it
is loaded into sample_qc_full.csv but never used - not as the filter input and not as a cross-check.
The in-house call rate computed from a 50,000-SNP PASS-biallelic panel sits ~13 percentage points
higher, so the config floor of 0.80 is a default threshold applied to a quantity that is not on the
s
- **pfdhfr/pfmdr2/pfcrt zone differences exist but separate cleanly into temporal and spatial components; neither is reported** (Biological interpretation, claimed high) — The pipeline's own matrix contains an informative, interpretable temporal/spatial decomposition at
the SP and CQ markers that the manuscript never computes. pfcrt N75K is a textbook post-chloroquine-
withdrawal decline whose apparent zone signal is purely temporal; pfdhfr C59R is a temporal rise
whose zone signal also collapses under year control; pfdhfr N51I and pfmdr2 S208N retain a marginal
zon

---

## Refuted

21 findings did not survive. Titles only, for the record:

- step09's call-quality safeguard is structurally unable to fire for the gene classes actually recovered (Code: never-reviewed scripts)
- The load-bearing "every PASS site is RegionType = Core" claim has no surviving evidence on disk (Code: never-reviewed scripts)
- Zone Mantel r swings 0.41-0.60 on an arbitrary choice of how to place the one multi-region zone (Code: the prior agent’s own fixes)
- 'Mixed calls remain' fallback silently propagates doubled counts; no het-policy provenance in the cached counts (Code: the prior agent’s own fixes)
- step05a's chromosome-recode justification ('ADMIXTURE rejects non-integer codes') is unverified and probably unnecessary (Code: the prior agent’s own fixes)
- Block-jackknife F_ST CIs are anticonservative at large n: 17% empirical type-I error against a within-zone null (Statistical validity)
- No ADMIXTURE CV standard error; and two Mantel tests reported with the significant one chosen post hoc (Statistical validity)
- Abstract calls TreeMix variance explained monotonic; it declines after m = 3, as Section 6.7 states (Numerical audit)
- Stated analysis window (03:25-04:07, 41 min) ends before the last reported outputs were written (Numerical audit)
- The one hit promoted hardest is the one most exposed to the documented year-zone confound (Manuscript honesty and overclaiming)
- The thesis hypothesis was tested with the statistic its own proposal predicted would be null (Manuscript honesty and overclaiming)
- Bhatia 2013 is cited for the estimator, then its central warning is ignored in the cross-study FST comparison (Manuscript honesty and overclaiming)
- Stage-3 pre-QC disclosure is dropped exactly where the ordination result is used as evidence (Manuscript honesty and overclaiming)
- §3.5 declares the core-genome warning "a false alarm" while the reviewer notes concede no artefact check was done (Manuscript honesty and overclaiming)
- GQ-disablement rationale is falsified: low GQ is a 10x sequencing-study effect, not diploid-model ambiguity (Filtering and QC decisions)
- Fws filter biases F_ST downward ~2-fold, the opposite of what section 4.3 implies; direction and magnitude now measured (Filtering and QC decisions)
- The Fws filter's stated mechanism cannot operate on Pf8 GT data, and is independently closed by the het-resolution step (Filtering and QC decisions)
- Section 5.3 misreads the log: the "residual" heterozygous call rate of 0.0000 is printed before mixed calls are resolved (Filtering and QC decisions)
- Section 4.2.4 says the clonal-distance data offer "no clean break" when the pipeline's own histogram found a clear trough (Filtering and QC decisions)
- Every stage-4 artefact on disk is newer than the stage 6-8 results derived from it (Reproducibility and engineering)
- Near-panmixia is biologically expected and the manuscript should cite that rather than present it as a surprise (Biological interpretation)

---

## Not verified (rate limit)

The reproducibility dimension raised 16 findings; its verification agents were lost to the weekly
limit and the server then went off-LAN. These are **unverified reviewer claims**, not confirmed findings:
- `The sample-QC figure embedded in the manuscript…` — reviewer raised this; verification never ran.
- `The pipeline logged that its own Stage 8…` — reviewer raised this; verification never ran.
- `'Skip if output exists' guards in three…` — reviewer raised this; verification never ran.
- `No version control: 14 of 23 scripts dif…` — reviewer raised this; verification never ran.
- `ghanaAEZ.geojson provenance is substanti…` — reviewer raised this; verification never ran.
- `Determinism verified for ADMIXTURE and t…` — reviewer raised this; verification never ran.
- `check_env.py validates almost nothing it…` — reviewer raised this; verification never ran.
- `environment.yml does not describe the en…` — reviewer raised this; verification never ran.
- `step03a's resume state is sound, but sil…` — reviewer raised this; verification never ran.
- `Parallel mode over-subscribes the machin…` — reviewer raised this; verification never ran.

---

## How to read this

The audit was deliberately hostile: every verifier was told to refute by default and to re-derive
the evidence itself rather than trust the reviewer. Twenty-one findings died that way. What is left
has been checked against the actual code, data and outputs by at least two independent agents.

Two findings in the high-severity list were **not** independently re-verified by me afterwards,
because the server went off-LAN mid-session: finding 13 (canonical markers excluded at ingest) and
finding 14 (AAT1 S258L). Both carry detailed Zarr queries in their evidence and both were confirmed
3/3 and 2/3 respectively, but they are the two that most change the conclusions, so re-check them
first when the server is reachable again.
