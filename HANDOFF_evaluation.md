# Handoff: evaluate the Pf8 Ghana spatial population-genomics analysis

Written 2026-10-09 by the agent that ran the analysis. For a successor agent on the same Mac
(`samnimoh`), asked to **evaluate this work for potential improvement**.

The pipeline ran end to end and produced results. Nothing here is broken. Your job is to find
what is weak, wrong, or improvable — not to re-run it for its own sake.

---

## 0. TL;DR for the evaluator

A 9-stage population-genomics pipeline was run on MalariaGEN Pf8 data for Ghana, on a remote
Linux server. Headline result: **Ghanaian *P. falciparum* is near-panmictic** (max pairwise
F_ST 0.0024). A 60-page working manuscript documents it.

**The four things most worth your attention, in order:**

1. **Four cheap sensitivity checks were proposed and never run** (§7). They use code that already
   exists and would address the most likely reviewer objections. This is the highest-value gap.
2. **Ten defects were found in the supplied pipeline in one review pass** (§5), two of which would
   have produced *silently wrong* results. The review was not exhaustive. More likely remain —
   especially in the stages nobody re-read: `step01`, `step02`, `step05c`, `step07a`, `step08a`,
   `step08c`, `step09`.
3. **A GQ-filter decision raised the SNP count 57%** on indirect evidence (§4.3). A direct
   genotype-concordance check was never done and would settle it.
4. **Two design limits cannot be fixed by any reanalysis** (§8). Confirm the manuscript states
   them honestly rather than hedging — and push back if you think it overclaims anywhere.

---

## 1. Access and environment

```bash
ssh gyadu            # alias → gyadu@192.168.0.152, key ~/.ssh/id_ed25519_gyadu, no passphrase
```

- Server `bacg2`, Ubuntu kernel 5.15, **40 cores, 629 GB RAM**. The user confirmed on 2026-10-09
  that **the server is theirs alone** — parallelise freely.
- Non-interactive ssh does not load conda. Always:
  ```bash
  source /home/tools/anaconda3/etc/profile.d/conda.sh && conda activate spatial
  ```
- Project root: `/media/biodataA/pf8/gyadu` (scripts detect it as `PF8_GHANA_ROOT`).
- Disk: `/media/biodataA` had 447 GB free after cleanup. Don't fill it.
- The env `spatial` was built with micromamba (`~/tools/micromamba/bin/micromamba`); the shared
  conda's classic solver is unusable at this dependency scale. **Don't run `conda install` there.**
- BayPass binary: `~/tools/baypass/g_baypass` (+ `utils/baypass_utils.R`).

**Operational lesson learned the hard way:** never `scp` over a bash script while it is executing.
Bash reads scripts lazily; overwriting `run_all.sh` mid-run made it execute a garbage fragment
(stage 4b silently skipped, exit 127). Check `tmux ls` and `pgrep -af step0` before uploading.

---

## 2. What the project is

Doctoral thesis component: **population genomic structure and signatures of antimalarial selection
in *P. falciparum* across Ghana's ecological zones.**

- Thesis proposal + literature review: `~/Downloads/genomic analysis of Consistent signatures of
  selection.docx` (145 paragraphs, ~11,400 words). **Read it** — it sets the biological framing,
  the resistance-marker panel, and the 9-step workflow the pipeline implements. The manuscript
  deliberately does *not* restate it.
- The analysis documented here addresses the thesis's **first** objective (quantify structure and
  gene flow) well, its second (barrier test) partially, and its third (zone-specific variants)
  only preliminarily.

---

## 3. What was actually done

Full pipeline, stages 1–9, completed 2026-10-09 (stages 4–9 in 41 min wall time with
`run_all.sh --from 4 --parallel`).

### Data cascade (every number verified against pipeline output)

| Stage | Result |
|---|---|
| Pf8 release | 33,325 samples, 12,493,205 variants |
| Ghana in manifest | 6,653 |
| Pf8 QC-pass (stage 1) | 4,905 |
| Zone assignment (stage 2) | 4 zones: Guinea savanna 3,605 / Decidous forest 815 / Coastal savanna 435 / Transitional 50 |
| PASS biallelic SNPs genome-wide | 2,190,026 (**all** RegionType = Core) |
| Isolate QC pass (stage 3b) | 2,017 |
| **Final matrix (stage 4a)** | **3,359 SNPs × 1,900 isolates**, 2.08% missing |

### Headline results

- **F_ST**: max 0.0024 (Coastal–Guinea, 95% CI 0.0014–0.0034). 3 of 6 pairs have CIs spanning zero.
- **Mantel IBD**: region level r=0.400, p=0.029 (7 pops, 21 pairs). Zone level r=0.578, p=0.090
  (4 pops → only 24 permutations, finest attainable p = 0.042).
- **ADMIXTURE**: CV minimised at K=2 (0.83736) but K=1 = 0.84199 — a 0.55% improvement. Components
  near-uniform across zones.
- **TreeMix**: variance explained 0.876 (m=0) → 0.935 (m=1) → 0.963 (m=2) → 0.9976 (m=3, plateau).
  Picks recorded for both the identifiable range (m=2) and the full sweep (m=3).
- **BayPass**: XtX 2.41–26.48; threshold 11.232 from 100k MAF-matched POD SNPs; **15 outliers**
  (0.45%) in **11 genes**, top hit AAT1 (PF3D7_0629500, 2 SNPs, max XtX 24.44 — published
  chloroquine-resistance link). **No validated resistance locus among them.**
- **Polyclonality gradient** (QC by-product, arguably the clearest ecological signal):
  Guinea 0.597 → Forest 0.539 → Transitional 0.500 → Coastal 0.444.

---

## 4. Decisions made (all put to the user interactively and answered)

| Decision | Chosen | Alternatives offered | Where documented |
|---|---|---|---|
| Genotype source | Pf8 Zarr over HTTPS (~300 GB transferred, 20.57 GB stored) | Resume truncated VCFs (~1.6 TB); re-download (~2.2 TB) | manuscript §5.1 |
| Fws threshold | **0.95** | 0.90 (2,341 isolates), 0.80 (2,924) | §4.2.2 |
| Call-rate rule | **MAD rule OFF**, absolute ≥0.80 | MAD on (1,566 pass); ≥0.90 | §4.2.3 |
| Clonal threshold | **0.00005** (77 removed) | 0.0001 (92), 0.0003 (137) | §4.2.4 |
| Mixed (het) calls | **Majority allele by AD**, ties→missing | →missing; leave diploid | §5.3 |
| Genotype mask | **DP≥5 only, GQ disabled** | DP≥5 & GQ≥20 (2,143 SNPs); GQ≥10; DP≥3 | §4.2.5 |
| TreeMix block size | **50 SNPs** (~67 blocks) | 100; 500 (default, ~7 blocks) | §5.5 |
| TreeMix m range | **Run 0–5, report both 0–2 and 0–5 picks** | Cap at 2 | §6.7 |
| Stage 4a memory | **Run as written** (~130–160 GB peak) | Refactor to chunked | — |
| Old VCFs | **13 truncated deleted**, chr10 kept | keep all; delete all | §5.1 |

### 4.3 The GQ decision — scrutinise this one

`config.MIN_GENOTYPE_GQ` was set from 20 to **0**. Evidence used:
- 12.6% of hom-ref and 12.4% of hom-alt calls fail GQ<20, but their **median depths are 46 and 40** —
  i.e. the failing population is not low-depth.
- At DP≥10, only 3.0% / 0.7% still fail.
- SNPs surviving missingness ≤10% fell from 74.3% (DP-only) to 51.0% (DP+GQ).
- Mean ALT frequency at common SNPs moved only 0.282 → 0.294.

**The inference** — that intermediate GQ reflects the diploid calling model's ambiguity in a
haploid organism — is *plausible but unverified*. A direct genotype-concordance check between the
two masks at the same sites was never done. **This is the single most consequential unvalidated
assumption in the analysis.**

---

## 5. Defects found and fixed in the supplied pipeline

All fixed on the server. Originals preserved in `pf8_ghana_pipeline.zip` at the project root.

| # | Defect | Would have caused |
|---|---|---|
| 1 | `TREEMIX_ROOT="Guinea_Savanna"` vs actual slug `Guinea_savanna` | Pipeline abort at stage 7 |
| 2 | step07c selection rule `gains.fillna(1).idxmax()` always returned m=0 | **Silently wrong** |
| 3 | TreeMix variance-explained included the matrix diagonal | **Silently wrong** |
| 4 | Allele counts doubled by diploid coding (4b, 7, 8) | **Silently anticonservative** |
| 5 | Zone Mantel used polygon centroids, not sample locations | Wrong geography |
| 6 | BayPass POD: wrong matrix shape, 1,000 SNPs, no MAF match | Calibration failure |
| 7 | `pfcoronin`/`pfap2mu` had wrong PlasmoDB IDs | Silent false negatives |
| 8 | PLINK export wrote string chromosome codes | Possible ADMIXTURE failure |
| 9 | PLINK had no `--threads`/`--memory` | Would claim all 40 cores + 314 GB |
| 10 | Failing zone Mantel would abort stages 7–9 | Fragility |

**Defect 6 mattered materially:** threshold moved 8.375 → 11.232; outliers 40 → 15.

> **Evaluator: this is your richest vein.** Ten defects in one pass over the *unexecuted* stages.
> The review was explicitly not exhaustive. Scripts never systematically re-read:
> `step01_filter_samples.py`, `step02_assign_aez.py`, `step05c_plot_admixture.py`,
> `step07a_treemix_input.py`, `step08a_baypass_input.py`, `step08c_calibrate_xtx.py`,
> `step09_annotate.py`. Defects 2–4 were found by *reading*, not by any test — so the same class
> of silent error is plausible elsewhere.

### Scripts modified in this session
`config.py`, `callset_io.py`, `step03_umap.py`, `step03a_fetch_callset_zarr.py` (new),
`step03b_sample_qc.py`, `step04a_prepare_callset.py`, `step04b_fst.py`, `step05a_export_plink.py`,
`step05b_admixture.sh`, `step06_mantel.py`, `step07b_treemix.sh`, `step07c_plot_treemix.py`,
`step08b_baypass.sh`, `run_all.sh`. (Timestamps 10-08_21:08 onward distinguish them from originals
at 10-06.)

---

## 6. What was verified, and how

| Check | Outcome |
|---|---|
| Zarr store vs VCFs | **Exact match.** 3 windows (chr01/10/13), ~471 M values compared, 0 differences |
| Ploidy code | Synthetic 3×4 unit test incl. tie + missing call; diploid-fallback warning fires |
| F_ST invariance | MD5 of `fst_matrix.csv` unchanged after a cosmetic label-only rerun |
| Clonal threshold | Sensitivity table over 7 thresholds; chaining starts only well above the chosen value |
| Genotype mask | Quantified on 40k- and 300k-SNP panels |
| ADMIXTURE K=1 | Run separately as the no-structure reference |
| BayPass recalibration | Re-run after correction; both thresholds recorded |
| References (manuscript) | All 26 verified via Crossref/PubMed; 4 of my own assumptions were wrong and corrected |
| Manuscript arithmetic | Final audit caught 4 slips in my own draft; all corrected |

---

## 7. **Proposed but NOT run** — the main gap

None of these has been executed. Listed in the order I'd prioritise.

1. **Fws sensitivity** (0.90, 0.80). Largest single exclusion (2,810 isolates, 57%) *and* it has a
   documented zone-dependent bias. Code exists; just change `--min-fws`.
2. **MAF ≥1% sensitivity** (projected 8,500–12,400 SNPs vs 3,359). Would ~3× the scan's power.
3. **Single-year analysis** (2018: n=773 across 3 zones — the only year that can support it).
   Tests whether zone differences survive temporal control.
4. **Mapping-quality check at the 15 outlier positions.** Several hits are in exported-protein
   families, which are repetitive and alignment-prone. Cheap; either kills the objection or
   identifies which hits to drop.
5. **Direct genotyping of the resistance panel.** The thesis's actual marker questions are
   answerable from these data — XtX simply doesn't measure them. Needs new code.
6. **Re-run stage 3 on the QC set.** Currently the ordinations describe 4,905 pre-QC isolates while
   everything else describes 1,900. An internal inconsistency in the manuscript's figures.
7. **Fws by zone/year as a transmission phenotype** in its own right.
8. **Functional enrichment** of the 11 outlier genes vs length/density-matched random sets.
9. **Demographic inference** (Ne, divergence times) to separate "ongoing gene flow" from "recent
   common ancestry" — the manuscript's surveillance claim rests on this distinction.
10. **Manual review of Brong Ahafo and Volta zone assignments** — step 2's own output recommends it;
    never done.

---

## 8. Hard limits (no reanalysis fixes these)

1. **Zone ≡ region for 3 of 4 zones.** Guinea savanna = Upper East (1,334). Coastal = Greater Accra
   (204). Transitional = Brong Ahafo (25). Only Decidous forest aggregates 4 regions. **Zone and
   region effects are collinear by construction.**
2. **Geolocation is admin-level-1 only** — 1,900 isolates occupy **7 distinct coordinates**. No
   sub-regional spatial analysis is possible, ever, with this metadata.
3. **Year is confounded with zone.** Median year: Transitional 2012, Forest 2015, Guinea 2017,
   Coastal 2018. Transitional has nothing after 2013; Coastal nothing before 2016. Not fixable by
   reweighting.
4. **Only 4 of Ghana's 5 zones sampled** — no Sudan savanna, i.e. one end of the thesis's
   ecological gradient is absent.
5. **~5,500 SNPs is the genome-wide ceiling** at MAF≥5% in Ghana, even unmasked. The low SNP count
   is the organism, not the pipeline.
6. **Transitional zone n=25** — all 3 of its F_ST comparisons have CIs spanning zero.

---

## 9. Known unknowns (flagged, never resolved)

- **`data/ghanaAEZ.geojson` provenance is undocumented.** Source, vintage, CRS all unknown. This
  blocks third-party reproduction of stage 2 and must be fixed before publication.
- Why the Pf8 QC flag drops isolates unevenly by region (Central loses 55%, Volta 0%).
- Whether the majority-allele rule introduces reference bias (2.3 REF per ALT resolved — expected,
  but not formally tested).
- LD decay distance in this population (the 50-SNP block choice assumes <350 kb; never measured).
- Whether ADMIXTURE/BayPass are bitwise reproducible across thread counts.
- Who, if anyone, reviewed the original pipeline before this session.
- The "Decidous forest" misspelling originates in the GeoJSON. Retained deliberately in data keys;
  **should not** be reproduced in prose/figure labels in a final version.

---

## 10. Deliverables and where they live

**On this Mac:**
- `~/Desktop/chromo/Pf8_Ghana_spatial_genomics_working_manuscript.docx` — 60 pp, 12 sections,
  11 figures, 26 tables, 26 verified refs, plus a separated **Reviewer Notes** section (A–H) with
  12 questions for the author and an objection/response table.
- `~/Desktop/chromo/pf8_proof/` — all figures + key result CSV/JSON files.
- `~/Downloads/genomic analysis of Consistent signatures of selection.docx` — the thesis
  proposal/lit review (user-supplied).
- Manuscript build script: in the previous session's scratchpad (ephemeral — if you need to
  regenerate the .docx, the script may be gone; `npm install docx` in a scratch dir and rebuild).

**On the server** (`/media/biodataA/pf8/gyadu`):
- `interim/pf8_ghana.zarr` (20.57 GB), `interim/ghana_core_snps.npz` (final matrix),
  `interim/analysis_samples.csv` (canonical sample order)
- `results/` — fst_pairwise.csv, dimred_comparison.csv, mantel_result_{zone,region}.json,
  admixture/, treemix/, baypass/, outlier_genes.csv
- `figures/`, `logs/` (incl. the Zarr-fetch verification log)
- `HANDOFF.md` at the project root is **stale** (predates this session's work) — ignore it.

**Reproduce:**
```bash
source /home/tools/anaconda3/etc/profile.d/conda.sh && conda activate spatial
cd /media/biodataA/pf8/gyadu/scripts
python check_env.py
bash run_all.sh --from 4 --parallel     # stages 5-8 concurrent; ~41 min
```
Seeds fixed at 42 throughout (config, ADMIXTURE `-s`, TreeMix `-seed`, BayPass `-seed`).

---

## 11. Working conventions the user has set

- **Ask interactively.** On any issue or genuine fork, use `AskUserQuestion` (multiple choice,
  recommended option first) — not prose, and don't just pick.
- **Show proof.** Send figures/outputs with `SendUserFile` as they're produced, not batched.
- **Use subagents** for parallelisable work.
- **Don't touch files outside this pipeline.**
- No AI attribution anywhere (commits, PRs, docs).

---

## 12. Suggested evaluation plan

If I were evaluating this, in order:

1. **Read the manuscript's §9 (Limitations) and Reviewer Notes D** first, then check whether the
   rest of the document lives up to that candour — or quietly overclaims elsewhere.
2. **Code review the 7 never-re-read scripts** (§5) hunting specifically for the *silent* class of
   error: wrong axis, wrong denominator, fillna masking a NaN, off-by-one in an index map.
3. **Run proposed checks 1–4** (§7). ~1–2 h of compute, and they're what a thesis examiner will ask for.
4. **Settle the GQ question** (§4.3) with a direct concordance check.
5. **Challenge the ploidy fix.** It's the correction I'm most confident in and therefore the one
   least examined by anyone else. `callset_io.isolate_allele_counts` + `step04a.resolve_mixed_calls`.
6. **Sanity-check the manuscript's numbers** against `results/` independently. I audited my own
   draft and found 4 slips; assume I missed some.

Don't take anything in this file on trust — every number here is reproducible from `results/`
and `logs/` on the server, and you should spot-check rather than inherit my claims.
