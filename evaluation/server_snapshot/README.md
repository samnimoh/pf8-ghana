# Spatial Population Genomics of *Plasmodium falciparum* in Ghana — WSL edition

A step-per-script rewrite of the Colab workflow (v2.0). Each stage runs as a
standalone command, reads its inputs from disk and writes its outputs back, so
nothing depends on a live kernel holding state.

## Quick start

```bash
cd /media/biodataA/pf8/gyadu          # wherever the project lives

bash scripts/step00_setup.sh          # once: conda, tools, BayPass. No sudo needed.
source activate.sh                    # every session after that

python scripts/config.py              # confirms which inputs it can see
bash scripts/run_all.sh               # or run steps individually
```

Setup needs no root. Compilers, PLINK, ADMIXTURE, TreeMix and bedtools all come
from conda-forge and bioconda, so nothing is installed system-wide. If your home
directory is small, put conda on the project volume instead:

```bash
CONDA_ROOT=/media/biodataA/pf8/gyadu/opt/miniforge3 \
BAYPASS_DIR=/media/biodataA/pf8/gyadu/opt/baypass \
bash scripts/step00_setup.sh
```

`step00_setup.sh` writes `activate.sh` at the project root, which activates the
environment and exports `PF8_GHANA_ROOT` and `BAYPASS_BIN` in one command.

**The project is relocatable.** `config.py` derives the root from its own
location (`scripts/../`), so moving the whole folder between a laptop, WSL and a
server needs no edits. Set `PF8_GHANA_ROOT` only to override that.

## Directory layout

```
pf8_ghana/
├── scripts/      the pipeline
├── data/         your downloads (see below)
├── interim/      intermediate artefacts — safe to delete and regenerate
├── results/      tables, matrices, per-tool output
├── figures/      publication-bound PNGs
└── logs/         stdout from the compiled tools
```

## Inputs you supply in `data/`

| File | Notes |
|---|---|
| `Pf8_samples.txt` | MalariaGEN Pf8 sample manifest |
| `ghanaAEZ.geojson` | Ghana agro-ecological zone polygons |
| `Pf8_mean_genotype_distance.npy` | ~4.4 GB; keep on the Linux filesystem |
| `Pf8_Ghana_PF3D7_*_v3.vcf.gz` (+ `.tbi`) | Ghana subset, one VCF per chromosome |
| `PlasmoDB-71_Pfalciparum3D7.gff` | 3D7 annotation |
| `pf_core_regions.bed` *(optional but recommended)* | core-genome intervals |

Filenames live in `scripts/config.py`. Change them there, not in the step
scripts.

## Run order

| Step | Command | Produces |
|---|---|---|
| 0 | `bash scripts/step00_setup.sh` | environment, `g_baypass` |
| 1 | `python scripts/step01_filter_samples.py` | `ghana_samples.csv` with `pf8_row` |
| 2 | `python scripts/step02_assign_aez.py` | zone assignments, map |
| 3 | `python scripts/step03_umap.py` | UMAP embedding + figure |
| 3b | `python scripts/step03b_sample_qc.py` | Fws, clonal groups, `qc_pass` table |
| — | `scripts/callset_io.py` | *(module)* finds and converts the per-chromosome VCFs |
| 4a | `python scripts/step04a_prepare_callset.py` | filtered genotype `.npz` |
| 4b | `python scripts/step04b_fst.py` | FST matrix, zone allele counts |
| 5a | `python scripts/step05a_export_plink.py` | `.tped`/`.tfam` |
| 5b | `bash scripts/step05b_admixture.sh` | pruned PLINK set, Q matrices |
| 5c | `python scripts/step05c_plot_admixture.py` | CV curve, ancestry barplots |
| 6 | `python scripts/step06_mantel.py [--level region]` | Mantel r, p, IBD scatter |
| 7a | `python scripts/step07a_treemix_input.py` | `ghana_treemix_input.gz` |
| 7b | `bash scripts/step07b_treemix.sh` | trees for m = 0–5 |
| 7c | `python scripts/step07c_plot_treemix.py` | variance explained, residuals |
| 8a | `python scripts/step08a_baypass_input.py` | `.geno` + aligned positions |
| 8b | `bash scripts/step08b_baypass.sh` | XtX per SNP, POD null |
| 8c | `python scripts/step08c_calibrate_xtx.py` | threshold, outlier BED |
| 9 | `python scripts/step09_annotate.py` | annotated outlier genes |

Every script takes `--help`.

## What changed relative to the Colab document

**Environment.** `condacolab` and the kernel restart are gone; WSL keeps a
Miniforge install across sessions. `drive.mount` is replaced by ordinary paths
under `$PF8_GHANA_ROOT`. `%%bash` cell magics become real shell scripts, and
`!wget` becomes a one-off download you do yourself.

**State.** A notebook carries `gt`, `ac` and `samples_with_aez` in memory
between cells. Separate scripts cannot, so each stage serialises what the next
one needs — `ghana_core_snps.npz`, `allele_counts_by_zone.npz`,
`analysis_samples.csv`, `zone_order.txt`. Sample and population ordering is
fixed once, in Step 4a, and every later step reads it rather than recomputing
it. Most of the silent-misalignment failures this pipeline can suffer come from
ordering, and that is where they are headed off.

**Gaps in the source document that are now filled.**

- Step 4 used `gt` without ever constructing it. `step04a_prepare_callset.py`
  builds it: VCF to Zarr, FILTER/biallelic/SNP/core-region filtering, MAF and
  missingness thresholds, and sample reordering against the Step 2 table.
- Step 8 invoked `-gfile ghana_baypass.geno`, a file nothing created.
  `step08a_baypass_input.py` writes it, with a row-aligned position table —
  without which Step 9 annotates the wrong genes and gives no sign of it.
- `XTX_THRESHOLD` and `snp_positions` in Step 9 were undefined.
  `step08c_calibrate_xtx.py` derives both, preferring the POD-simulated null and
  labelling the empirical fallback as a weaker assumption when R is unavailable.
- `-npop 5` was hardcoded against six named AEZ zones. Population count is now
  derived from the data and cross-checked against the `.geno` column count.
- TreeMix ran without any summary of fit. Step 7c adds variance explained per
  m and a residual heatmap.

**Additions.** Block-jackknife standard errors on every FST estimate; a
region-level Mantel option, which is the finest spatial grain Pf8's admin-1
coordinates honestly support; polyclonality reporting with an optional
het-to-missing mask; contig-name validation before the bedtools intersection,
since a naming mismatch produces an empty result indistinguishable from a
genuine null; and a hypervariable-gene flag on the Step 9 output.

## Resources

`step03` memory-maps the distance matrix, so peak RSS stays in the hundreds of
megabytes rather than the gigabytes an eager load would take. This matters more
under WSL2 than under Colab, since WSL2 borrows its RAM from Windows and an
eager load can drag the whole machine into swap. Cap it if needed — create
`%UserProfile%\.wslconfig` with:

```ini
[wsl2]
memory=24GB
processors=8
swap=16GB
```

Keep large files under `/home/`, not `/mnt/c/`. The Windows drive mount goes
through a translation layer that makes random access to a memory-mapped array
painfully slow.

Rough costs: Steps 1–3, minutes. Step 4a, tens of minutes on first VCF-to-Zarr
conversion, fast thereafter. ADMIXTURE across K = 2–8, hours. BayPass, hours.
The last two are where an institutional HPC allocation earns its keep.

## Per-chromosome VCFs

The Ghana subset ships as one VCF per chromosome
(`Pf8_Ghana_PF3D7_01_v3.vcf.gz` ... `_14_v3`). `callset_io.py` finds them with
the `GHANA_VCF_GLOB` pattern in `config.py`, sorts them numerically so 02
precedes 10, and converts each into its own Zarr group named after the contig as
it appears *inside* the file (`Pf3D7_01_v3`, not the filename's `PF3D7_01_v3`) —
which is what keeps Step 9's bedtools intersection matching the GFF.

Converting per chromosome rather than merging first is deliberate. Peak memory
stays at one chromosome's worth, and a conversion interrupted at chromosome 9
keeps 1-8; rerunning skips them. Variant filtering also runs on the small 1-D
arrays across every contig before any genotype is fetched, so the whole genome
is screened cheaply and only survivors are loaded.

A single merged VCF still works — pass `--vcf path/to/merged.vcf.gz`.

**zarr must be below 3.0.** scikit-allel's writer uses the zarr 2.x API; on
zarr 3 conversion dies with `'Group' object has no attribute 'create_dataset'`.
`step00_setup.sh` pins it, and `callset_io` checks the version up front with an
actionable message rather than letting it fail mid-conversion.

## Two routes to the genotypes

Steps 1–3 need only the manifest, your AEZ layer and the distance matrix.
Steps 4–9 need actual genotypes, and there are two ways to get them.

**Route A — local VCF.** Subset the Pf8 callset with bcftools (recipe in
`step04a_prepare_callset.py`), then run that script. Works offline once the
subset exists, but you have to obtain and subset a very large VCF first, and you
must supply `pf_core_regions.bed` yourself.

**Route B — Google Cloud, no download.** `step04a_prepare_callset_malariagen.py`
pulls the Ghana subset straight from GCS through the `malariagen_data` package.
Requires `pip install malariagen_data` and GCS registration. Three advantages
beyond skipping the download: `variant_RegionType == "Core"` ships with the
callset and replaces the core-genome BED; Fws is computed from `call_AD` in the
same network pass rather than a second one; and `--dump-genome-features` writes
the 3D7 annotation locally, removing the PlasmoDB download at Step 9.

Route B reverses the QC ordering, because the network pass is too expensive to
repeat:

```bash
python scripts/step04a_prepare_callset_malariagen.py            # network
python scripts/step03b_sample_qc.py --from-npz \
       --fws-from interim/pf8_fws.csv                           # local
python scripts/step04a_prepare_callset_malariagen.py --refilter # local
```

Both routes write the same `ghana_core_snps.npz` and `analysis_samples.csv`, so
Steps 4b through 9 are identical either way. `run_all.sh` assumes Route A;
Route B is three commands run by hand, then `bash run_all.sh --from 4`.

## Where QC happens

Step 4a is the checkpoint. Everything before it is metadata hygiene; everything
after it inherits whatever genotype matrix that step produces.

| Check | Where |
|---|---|
| Pf8 `QC pass` flag, coordinates present | Step 1 |
| Spatial join: unmatched points, seam duplicates, region × zone crosstab | Step 2 |
| Index validity against the distance matrix, symmetry, NaNs | Step 3 |
| Fws monoclonality, clonal pruning, call rate, heterozygosity outliers | Step 3b |
| Genotype-level DP/GQ masking | Step 4a |
| FILTER=PASS, biallelic SNPs, core-genome restriction | Step 4a |
| Variant and sample missingness, MAF | Step 4a |
| Sample-name reconciliation between metadata and VCF | Step 4a |
| LD pruning before ancestry estimation | Step 5b |
| Minor allele count before the MCMC | Step 8a |
| Outlier fraction sanity check | Step 8c |
| Contig-name agreement before intersection | Step 9 |

Step 3b writes `interim/ghana_samples_qc_pass.csv`, and Step 4a picks it up
automatically. Skip Step 3b and Step 4a falls back to the Step 2 table with a
warning — mechanically fine, scientifically not.

Fws needs read-level depths. If your Ghana subset was exported without the AD
field, either re-export it keeping AD or supply precomputed values with
`--fws-from`. Without Fws the monoclonality filter is unavailable, and
`--het-to-missing` in Step 4a is the blunt substitute: it masks the ambiguous
calls without removing the samples that generated them.

The clonal threshold is a judgement call. Step 3b suggests one from a trough in
the pairwise distance histogram and prints the figure, but look at
`figures/sample_qc.png` and set `--clonal-threshold` yourself before relying on
the heuristic.

Watch the per-zone survivor counts that Step 3b prints. Aggressive Fws and
clonal filtering can thin a zone below the point where FST means anything, and
merging it with an adjacent zone usually beats dropping the geography.

## Analytical cautions carried over from the source document

Pf8 geolocates to administrative level 1. Every isolate from Ashanti shares one
coordinate pair, so individual-level geographic distance collapses to a handful
of values and Step 6 is constrained accordingly. Brong-Ahafo (forest/transition)
and Volta (coastal/Guinea savanna) straddle zone boundaries; Step 2 prints the
region-by-zone crosstab so you can check them against the map.

Within-country FST for *P. falciparum* is routinely below 0.05. Rank the pairs;
do not ask whether any value clears a threshold.

Recovering *pfcrt* or *pfdhfr* in Step 9 is a positive control, not a result.
Outliers in subtelomeric *var* and *rifin* regions want a hard look at call
quality before they go near a manuscript.
