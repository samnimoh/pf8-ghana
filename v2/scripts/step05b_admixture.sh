#!/usr/bin/env bash
# =============================================================================
# STEP 5b — PLINK conversion, LD pruning, ADMIXTURE cross-validation sweep
# =============================================================================
# Pruning is not optional. Linked SNPs carry redundant information, and feeding
# them to ADMIXTURE inflates apparent structure — you end up describing LD
# blocks rather than ancestry.
#
# Usage:
#   bash step05b_admixture.sh
#   K_MIN=2 K_MAX=6 THREADS=8 bash step05b_admixture.sh
#   JOBS_K=7 THREADS=4 bash step05b_admixture.sh     # all K at once, 28 cores
# =============================================================================

set -euo pipefail

ROOT="${PF8_GHANA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
INTERIM="$ROOT/interim"
OUTDIR="$ROOT/results/admixture"
LOGDIR="$ROOT/logs"

K_MIN="${K_MIN:-1}"
K_MAX="${K_MAX:-8}"
CV_FOLDS="${CV_FOLDS:-10}"
THREADS="${THREADS:-4}"
JOBS_K="${JOBS_K:-1}"   # K values fitted at once, each with THREADS cores
# PLINK 1.9 otherwise takes every core and reserves half the machine's RAM.
PLINK_MEM="${PLINK_MEM:-16000}"   # MB
PRUNE_WIN="${PRUNE_WIN:-50}"
PRUNE_STEP="${PRUNE_STEP:-10}"
PRUNE_R2="${PRUNE_R2:-0.2}"

mkdir -p "$OUTDIR" "$LOGDIR"

log() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

for tool in plink admixture; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "ERROR: $tool not on PATH. conda activate pf8ghana" >&2; exit 1; }
done

[ -f "$INTERIM/ghana_snps.tped" ] || {
    echo "ERROR: $INTERIM/ghana_snps.tped missing. Run step05a_export_plink.py" >&2
    exit 1; }

cd "$INTERIM"

# -----------------------------------------------------------------------------
log "Text PLINK -> binary"
# --allow-extra-chr: Pf contig names (Pf3D7_01_v3) are not human chromosomes.
# --double-id and --set-missing-var-ids guard against blank/duplicate SNP IDs.
plink --tfile ghana_snps \
      --threads "$THREADS" --memory "$PLINK_MEM" \
      --make-bed --out ghana_snps \
      --allow-extra-chr \
      --set-missing-var-ids '@:#' \
      --keep-allele-order \
      --silent
grep -E "variants|people" ghana_snps.log || true

# -----------------------------------------------------------------------------
log "LD pruning (window ${PRUNE_WIN}, step ${PRUNE_STEP}, r2 ${PRUNE_R2})"
plink --bfile ghana_snps \
      --threads "$THREADS" --memory "$PLINK_MEM" \
      --indep-pairwise "$PRUNE_WIN" "$PRUNE_STEP" "$PRUNE_R2" \
      --out prune --allow-extra-chr --silent

plink --bfile ghana_snps --extract prune.prune.in \
      --threads "$THREADS" --memory "$PLINK_MEM" \
      --make-bed --out ghana_pruned --allow-extra-chr \
      --keep-allele-order --silent

BEFORE=$(wc -l < ghana_snps.bim)
AFTER=$(wc -l < ghana_pruned.bim)
echo "SNPs: ${BEFORE} -> ${AFTER} after pruning"

if [ "$AFTER" -lt 1000 ]; then
    echo "WARNING: fewer than 1000 SNPs survive pruning. ADMIXTURE will be noisy."
    echo "         Consider a looser r2 (PRUNE_R2=0.5)."
fi

# -----------------------------------------------------------------------------
log "ADMIXTURE sweep K = ${K_MIN}..${K_MAX}"
cd "$OUTDIR"
cp "$INTERIM"/ghana_pruned.{bed,bim,fam} .

# Each K writes only ghana_pruned.K.{Q,P} and its own log, and keeps the same
# seed, so running several at once gives the same answers as one at a time.
echo "  ${JOBS_K} K value(s) at a time, ${THREADS} threads each"
run_k() {
    admixture --haploid="*" --cv="$CV_FOLDS" -j"$THREADS" -s "${SEED:-42}" \
        ghana_pruned.bed "$1" > "$LOGDIR/admixture_K$1.out" 2>&1
}
running=0
for K in $(seq "$K_MIN" "$K_MAX"); do
    if [ -f "ghana_pruned.${K}.Q" ]; then
        echo "  K=${K} already done — skipping"
        continue
    fi
    echo "  K=${K} started"
    run_k "$K" &
    running=$((running + 1))
    if [ "$running" -ge "$JOBS_K" ]; then
        wait -n || true
        running=$((running - 1))
    fi
done
wait || true

MISSING_K=""
for K in $(seq "$K_MIN" "$K_MAX"); do
    if [ -f "ghana_pruned.${K}.Q" ]; then
        grep "CV error" "$LOGDIR/admixture_K${K}.out" || true
    else
        MISSING_K="$MISSING_K $K"
    fi
done
if [ -n "$MISSING_K" ]; then
    echo "ERROR: ADMIXTURE produced no .Q for K =${MISSING_K}; see $LOGDIR/admixture_K*.out" >&2
    exit 1
fi

log "Cross-validation summary"
grep -h "CV error" "$LOGDIR"/admixture_K*.out | sort -t= -k2 -n | tee "$OUTDIR/cv_errors.txt"

cat <<'EOF'

The minimising K is a guide, not a verdict. Where the curve flattens across
several values, report the flat range and the biology that motivates your
choice rather than the nominal minimum.

Next: python step05c_plot_admixture.py
EOF
