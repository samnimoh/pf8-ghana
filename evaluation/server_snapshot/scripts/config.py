"""
config.py — shared paths, constants and small helpers for the Pf8 Ghana pipeline.

Every step script imports from here, so there is exactly one place to change a
path. Override the project root without editing this file:

    export PF8_GHANA_ROOT=/mnt/d/projects/pf8_ghana

Expected layout (create it once, drop your downloads into data/):

    $PF8_GHANA_ROOT/
    ├── scripts/            <- these files
    ├── data/               <- inputs you downloaded
    │   ├── Pf8_samples.txt
    │   ├── ghanaAEZ.geojson
    │   ├── Pf8_mean_genotype_distance.npy
    │   ├── pf8_ghana.vcf.gz          (Ghana subset of the Pf8 callset)
    │   └── PlasmoDB-68_Pfalciparum3D7.gff
    ├── interim/            <- created by the scripts
    ├── results/            <- created by the scripts
    ├── figures/            <- created by the scripts
    └── logs/               <- created by the scripts
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------
# Roots
# --------------------------------------------------------------------------

_default_root = Path(__file__).resolve().parent.parent
PROJECT_ROOT = Path(os.environ.get("PF8_GHANA_ROOT", _default_root)).resolve()

DATA_DIR = PROJECT_ROOT / "data"
INTERIM_DIR = PROJECT_ROOT / "interim"
RESULTS_DIR = PROJECT_ROOT / "results"
FIG_DIR = PROJECT_ROOT / "figures"
LOG_DIR = PROJECT_ROOT / "logs"

for _d in (DATA_DIR, INTERIM_DIR, RESULTS_DIR, FIG_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Inputs you supply
# --------------------------------------------------------------------------

SAMPLE_MANIFEST = DATA_DIR / "Pf8_samples.txt"
AEZ_GEOJSON = DATA_DIR / "ghanaAEZ.geojson"
DIST_MATRIX = DATA_DIR / "Pf8_mean_genotype_distance.npy"
# The Ghana subset arrives as one VCF per chromosome. callset_io.resolve_vcfs()
# expands this glob against DATA_DIR and sorts it numerically, so 02 precedes 10.
# A single merged VCF also works — point GHANA_VCF at it and pass --vcf.
GHANA_VCF_GLOB = "Pf8_Ghana_*_v3.vcf.gz"
GHANA_VCF = DATA_DIR / "pf8_ghana.vcf.gz"   # only used if you merge them yourself

PLASMODB_GFF = DATA_DIR / "PlasmoDB-71_Pfalciparum3D7.gff"

# Optional. If present, variants outside these intervals are dropped in step 4a.
CORE_GENOME_BED = DATA_DIR / "pf_core_regions.bed"

# --------------------------------------------------------------------------
# Derived artefacts (written by the pipeline)
# --------------------------------------------------------------------------

GHANA_SAMPLES_CSV = INTERIM_DIR / "ghana_samples.csv"            # step 1
SAMPLES_AEZ_CSV = INTERIM_DIR / "ghana_samples_with_aez.csv"     # step 2
GHANA_DIST_NPY = INTERIM_DIR / "ghana_dist_submatrix.npy"        # step 3
UMAP_EMBEDDING_CSV = RESULTS_DIR / "umap_embedding.csv"          # step 3
TSNE_EMBEDDING_CSV = RESULTS_DIR / "tsne_embedding.csv"          # step 3
PCOA_COORDS_CSV = RESULTS_DIR / "pcoa_coordinates.csv"           # step 3
PCOA_EIGEN_CSV = RESULTS_DIR / "pcoa_eigenvalues.csv"            # step 3
DIMRED_COMPARISON_CSV = RESULTS_DIR / "dimred_comparison.csv"    # step 3

SAMPLE_QC_FULL_CSV = RESULTS_DIR / "sample_qc_full.csv"          # step 3b
SAMPLES_QC_CSV = INTERIM_DIR / "ghana_samples_qc_pass.csv"       # step 3b

CALLSET_ZARR = INTERIM_DIR / "pf8_ghana.zarr"                    # step 4a
CALLSET_NPZ = INTERIM_DIR / "ghana_core_snps.npz"                # step 4a
ANALYSIS_SAMPLES_CSV = INTERIM_DIR / "analysis_samples.csv"      # step 4a
ALLELE_COUNTS_NPZ = INTERIM_DIR / "allele_counts_by_zone.npz"    # step 4b

FST_NPY = RESULTS_DIR / "fst_matrix.npy"                         # step 4b
FST_CSV = RESULTS_DIR / "fst_matrix.csv"
ZONE_ORDER_TXT = INTERIM_DIR / "zone_order.txt"

PLINK_PREFIX = INTERIM_DIR / "ghana_snps"                        # step 5a
PLINK_PRUNED = INTERIM_DIR / "ghana_pruned"
ADMIXTURE_DIR = RESULTS_DIR / "admixture"

MANTEL_JSON = RESULTS_DIR / "mantel_result.json"                 # step 6

TREEMIX_INPUT = INTERIM_DIR / "ghana_treemix_input.gz"           # step 7a
TREEMIX_DIR = RESULTS_DIR / "treemix"

BAYPASS_DIR = RESULTS_DIR / "baypass"                            # step 8
BAYPASS_GENO = INTERIM_DIR / "ghana_baypass.geno"
BAYPASS_POSITIONS = INTERIM_DIR / "baypass_snp_positions.csv"
XTX_THRESHOLD_TXT = RESULTS_DIR / "baypass" / "xtx_threshold.txt"

ANNOTATED_OUTLIERS = RESULTS_DIR / "outliers_annotated.txt"      # step 9

# --------------------------------------------------------------------------
# Analysis constants
# --------------------------------------------------------------------------

COUNTRY = "Ghana"
RANDOM_SEED = 42

# Column in the AEZ GeoJSON holding the zone name.
AEZ_NAME_FIELD = "Name"

# Pf8 manifest column names. Adjust here if the release renames them.
COL_COUNTRY = "Country"
COL_SAMPLE = "Sample"
COL_LON = "Admin level 1 longitude"
COL_LAT = "Admin level 1 latitude"
COL_ADMIN1 = "Admin level 1"
COL_QC = "QC pass"
COL_YEAR = "Year"

# Sample QC (step 3b)
MIN_FWS = 0.95              # conventional monoclonality cut (Manske et al. 2012)
MIN_SAMPLE_CALL_RATE = 0.80
# Pairwise Pf8 genotype distance at or below which two isolates count as clonal.
# Chosen from the step 3b histogram (median Ghana distance 0.00112): essentially
# identical genomes. 0.0001 and 0.0003 remove 92 and 137 isolates instead of 77.
CLONAL_THRESHOLD = 0.00005

# Genotype-level masking (step 4a). Applied before missingness is measured, so a
# low-confidence call becomes missing data rather than a confident wrong answer.
MIN_GENOTYPE_DP = 5
# 0 disables the GQ mask. At GQ >= 20 half the common SNPs failed the 10%
# missingness bar (2,143 left vs ~3,400 with DP alone) while allele frequencies
# barely moved, so only the depth check is kept (decided 2026-10-09).
MIN_GENOTYPE_GQ = 0

# Variant filtering (step 4a)
MIN_MAF = 0.05              # method spec: MAF > 5%
MAX_MISSING = 0.10          # drop SNPs called in < 90% of samples
MAX_SAMPLE_MISSING = 0.20   # drop samples called at < 80% of retained SNPs

# UMAP (step 3)
UMAP_N_NEIGHBORS = 30
UMAP_MIN_DIST = 0.1

# t-SNE and PCoA (step 3) — compared against UMAP on the same distances
TSNE_PERPLEXITY = 30
PCOA_N_AXES = 10

# ADMIXTURE (step 5)
K_MIN, K_MAX = 2, 8
ADMIXTURE_CV_FOLDS = 10
LD_PRUNE_ARGS = ("50", "10", "0.2")

# TreeMix (step 7)
# SNPs per jackknife block. ~3,400 SNPs ~7 kb apart: 50-SNP blocks (~350 kb) far
# exceed Pf linkage and still give ~70 blocks for the standard errors.
TREEMIX_BLOCK_SIZE = 50
TREEMIX_MAX_M = 5
TREEMIX_ROOT = "Guinea_savanna"   # must match slugify_zone(zone) exactly, case included

# BayPass (step 8)
BAYPASS_THREADS = 4
XTX_POD_QUANTILE = 0.999

# Known resistance loci (step 9)
KNOWN_RESISTANCE_LOCI = {
    "PF3D7_0709000": "pfcrt",
    "PF3D7_0523000": "pfmdr1",
    "PF3D7_0417200": "pfdhfr",
    "PF3D7_0810800": "pfdhps",
    "PF3D7_1343700": "pfk13",
    "PF3D7_1447900": "pfmdr2",
    "PF3D7_1251200": "pfcoronin",
    "PF3D7_1218300": "pfap2mu",
}

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def require(path: Path, hint: str = "") -> Path:
    """Fail loudly and early rather than three steps later with a cryptic error."""
    p = Path(path)
    if not p.exists():
        msg = f"Required input not found: {p}"
        if hint:
            msg += f"\n  -> {hint}"
        raise FileNotFoundError(msg)
    return p


def banner(text: str) -> None:
    line = "=" * max(60, len(text) + 4)
    print(f"\n{line}\n  {text}\n{line}", flush=True)


def coerce_bool(series):
    """Pf8 boolean columns arrive variously as True/False, 'True', 'Yes', 1/0."""
    import pandas as pd

    if series.dtype == bool:
        return series
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "t", "yes", "y", "1", "pass"})
    )


def load_zone_order() -> list[str]:
    require(ZONE_ORDER_TXT, "Run step04b_fst.py first — it fixes the zone ordering.")
    return [ln.strip() for ln in ZONE_ORDER_TXT.read_text().splitlines() if ln.strip()]


def slugify_zone(name: str) -> str:
    """TreeMix and BayPass population labels cannot contain whitespace."""
    return "_".join(str(name).split())


def set_seeds() -> None:
    np.random.seed(RANDOM_SEED)


def check_python() -> None:
    if sys.version_info < (3, 9):
        raise RuntimeError("This pipeline assumes Python >= 3.9.")


if __name__ == "__main__":
    banner("pf8_ghana configuration")
    print(f"PROJECT_ROOT : {PROJECT_ROOT}")
    vcfs = sorted(DATA_DIR.glob(GHANA_VCF_GLOB))
    print(f"VCFs matching   : {len(vcfs)} files for '{GHANA_VCF_GLOB}'")
    if vcfs:
        total = sum(v.stat().st_size for v in vcfs) / 1e9
        print(f"                  {vcfs[0].name} .. {vcfs[-1].name}  ({total:.1f} GB)")
    else:
        print(f"                  none found in {DATA_DIR}")

    for label, p in [
        ("sample manifest", SAMPLE_MANIFEST),
        ("AEZ geojson", AEZ_GEOJSON),
        ("distance matrix", DIST_MATRIX),
        ("PlasmoDB GFF", PLASMODB_GFF),
        ("core regions BED", CORE_GENOME_BED),
    ]:
        state = "found" if p.exists() else "MISSING"
        print(f"  {label:<18} {state:>8}  {p}")
