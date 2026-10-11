#!/usr/bin/env bash
# =============================================================================
# run_all.sh — run the pipeline end to end, or from a given step
# =============================================================================
# Each stage writes its outputs to disk, so a crash at Step 7 costs you Step 7,
# not the afternoon. That is the main structural difference from the notebook
# version: there is no in-memory state carried between steps.
#
# Usage:
#   conda activate pf8ghana
#   bash run_all.sh                 # everything
#   bash run_all.sh --from 4        # resume at Step 4
#   bash run_all.sh --only 6        # just the Mantel test
#   bash run_all.sh --list
#   bash run_all.sh --from 4 --parallel   # stages 5-8 side by side after 4
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Shared server: numpy/BLAS and numba otherwise size their thread pools to every
# core. Export a different value before calling to override.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-8}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-$OMP_NUM_THREADS}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-$OMP_NUM_THREADS}"
export NUMBA_NUM_THREADS="${NUMBA_NUM_THREADS:-$OMP_NUM_THREADS}"
export PF8_GHANA_ROOT="${PF8_GHANA_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$SCRIPT_DIR"

# Some servers ship python3 with no `python` alias, so pick an interpreter
# rather than assuming one. Override with: PYTHON=/path/to/python bash run_all.sh
if [ -z "${PYTHON:-}" ]; then
    if command -v python >/dev/null 2>&1; then PYTHON=python
    elif command -v python3 >/dev/null 2>&1; then PYTHON=python3
    else echo "ERROR: no python or python3 on PATH" >&2; exit 1; fi
fi
echo "interpreter: $PYTHON ($("$PYTHON" --version 2>&1))"

FROM=1
ONLY=""
PARALLEL=0

while [ $# -gt 0 ]; do
    case "$1" in
        --from) FROM="$2"; shift 2 ;;
        --only) ONLY="$2"; shift 2 ;;
        --parallel) PARALLEL=1; shift ;;
        --list) sed -n 's/^# STAGE //p' "$SCRIPT_DIR/$(basename "$0")"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

run_stage() {
    local num="$1"; shift
    local desc="$1"; shift
    if [ -n "$ONLY" ] && [ "$ONLY" != "$num" ]; then return 0; fi
    if [ -z "$ONLY" ] && [ "${num%%[a-z]*}" -lt "$FROM" ]; then return 0; fi
    printf '\n\033[1;34m######## STAGE %s — %s ########\033[0m\n' "$num" "$desc"
    "$@"
}

START=$(date +%s)

# STAGE 1  Filter the Pf8 manifest to Ghana
run_stage 1 "Filter manifest"        "$PYTHON" step01_filter_samples.py
# STAGE 2  Spatial join to agro-ecological zones
run_stage 2 "Assign AEZ"             "$PYTHON" step02_assign_aez.py
# STAGE 3  UMAP, t-SNE and PCoA on the distance submatrix
run_stage 3 "UMAP / t-SNE / PCoA"    "$PYTHON" step03_umap.py
# STAGE 3a Ghana callset from the Pf8 Zarr on Sanger (skips itself once built)
# Replaces the per-chromosome VCF download: only Ghana samples, PASS biallelic
# SNPs and GT/AD/DP/GQ are fetched, straight into interim/pf8_ghana.zarr.
run_stage 3 "Fetch callset"          "$PYTHON" step03a_fetch_callset_zarr.py
# STAGE 3b Sample QC — Fws, clonality, call rate, heterozygosity
# Runs before Step 4a so the Zarr store is built once, with AD, rather than
# converted without it and then reconverted.
run_stage 3 "Sample QC"              "$PYTHON" step03b_sample_qc.py
# STAGE 4  Callset preparation and pairwise FST
run_stage 4 "Prepare callset"        "$PYTHON" step04a_prepare_callset.py
run_stage 4 "Pairwise FST"           "$PYTHON" step04b_fst.py
# STAGE 5  ADMIXTURE
stage5() {
    run_stage 5 "Export PLINK"           "$PYTHON" step05a_export_plink.py
    run_stage 5 "ADMIXTURE sweep"        bash   step05b_admixture.sh
    run_stage 5 "Plot ADMIXTURE"         "$PYTHON" step05c_plot_admixture.py
}
# STAGE 6  Isolation by distance
stage6() {
    run_stage 6 "Mantel (zone)"          "$PYTHON" step06_mantel.py --level zone || \
        echo "  zone-level Mantel failed (fewer than 4 zones left?) — continuing"
    run_stage 6 "Mantel (region)"        "$PYTHON" step06_mantel.py --level region || \
        echo "  region-level Mantel skipped (too few regions above the n threshold)"
}
# STAGE 7  TreeMix
stage7() {
    run_stage 7 "TreeMix input"          "$PYTHON" step07a_treemix_input.py
    run_stage 7 "TreeMix sweep"          bash   step07b_treemix.sh
    run_stage 7 "TreeMix summaries"      "$PYTHON" step07c_plot_treemix.py
}
# STAGE 8  BayPass
stage8() {
    run_stage 8 "BayPass input"          "$PYTHON" step08a_baypass_input.py
    run_stage 8 "BayPass run"            bash   step08b_baypass.sh
    run_stage 8 "XtX calibration"        "$PYTHON" step08c_calibrate_xtx.py
}

if [ "$PARALLEL" -eq 1 ]; then
    # Stages 5-8 read only Stage 4's outputs and write disjoint files, so they
    # can run side by side. The thread budgets add up to roughly 40 cores.
    export JOBS_K="${JOBS_K:-7}" THREADS="${THREADS:-4}"   # ADMIXTURE: 7 K x 4
    export JOBS="${JOBS:-6}"                               # TreeMix: 6 m at once
    export NTHREADS="${NTHREADS:-8}"                       # BayPass
    declare -A PIDS=()
    for s in 5 6 7 8; do
        "stage$s" > "$PF8_GHANA_ROOT/logs/stage${s}.log" 2>&1 &
        PIDS[$s]=$!
        echo "stage $s started -> logs/stage${s}.log"
    done
    FAILED=""
    for s in 5 6 7 8; do
        if wait "${PIDS[$s]}"; then
            echo "stage $s finished"
        else
            echo "stage $s FAILED — see logs/stage${s}.log"
            FAILED="$FAILED $s"
        fi
    done
    if [ -n "$FAILED" ]; then
        echo "Stopping before stage 9: stage(s)$FAILED failed." >&2
        exit 1
    fi
else
    stage5
    stage6
    stage7
    stage8
fi
# STAGE 9  Functional annotation
run_stage 9 "Annotate outliers"      "$PYTHON" step09_annotate.py

ELAPSED=$(( $(date +%s) - START ))
printf '\n\033[1;32mPipeline finished in %02d:%02d:%02d\033[0m\n' \
    $((ELAPSED/3600)) $(((ELAPSED%3600)/60)) $((ELAPSED%60))
echo "Figures : $PF8_GHANA_ROOT/figures"
echo "Results : $PF8_GHANA_ROOT/results"
