#!/usr/bin/env bash
# =============================================================================
# STEP 8b — BayPass core model, plus pseudo-observed data for XtX calibration
# =============================================================================
# Why not an FST outlier scan: demographic history alone produces heavy tails in
# the FST distribution, so the top 1% of an empirical distribution is a list of
# demography as much as of selection. BayPass estimates the neutral covariance
# structure among populations first, then asks which SNPs exceed what that
# structure predicts.
#
# Calibration follows the same logic. A threshold taken from your own XtX
# distribution assumes some fixed proportion of the genome is under selection.
# A threshold taken from data simulated under the estimated omega assumes only
# that your demographic model is right, which is the weaker and more defensible
# assumption.
#
# Usage:
#   NPOP=6 bash step08b_baypass.sh
#   NPOP=6 NTHREADS=8 NVAL=1000 bash step08b_baypass.sh
#   NPOP=6 EFILE=results/baypass/ghana.efile bash step08b_baypass.sh   # STD model
#   NPOP=6 SKIP_POD=1 bash step08b_baypass.sh
# =============================================================================

set -euo pipefail

ROOT_DIR="${PF8_GHANA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
GENO="$ROOT_DIR/interim/ghana_baypass.geno"
OUTDIR="$ROOT_DIR/results/baypass"
LOGDIR="$ROOT_DIR/logs"

BAYPASS_BIN="${BAYPASS_BIN:-$HOME/tools/baypass/g_baypass}"
NTHREADS="${NTHREADS:-4}"
SEED="${SEED:-42}"
# POD SNPs to simulate. The threshold is the 0.999 quantile of their XtX, so
# 1,000 would leave it resting on a single value; 100,000 puts ~100 above it.
NVAL="${NVAL:-100000}"
# The observed SNPs were filtered at MAF >= 5% (config.MIN_MAF); the POD must be
# filtered the same way or rare simulated SNPs drag the threshold around.
PI_MAF="${PI_MAF:-0.05}"
SKIP_POD="${SKIP_POD:-0}"
EFILE="${EFILE:-}"

mkdir -p "$OUTDIR" "$LOGDIR"
log() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

[ -x "$BAYPASS_BIN" ] || {
    echo "ERROR: g_baypass not found at $BAYPASS_BIN" >&2
    echo "       Set BAYPASS_BIN, or re-run step00_setup.sh" >&2; exit 1; }
[ -f "$GENO" ] || {
    echo "ERROR: $GENO missing. Run step08a_baypass_input.py" >&2; exit 1; }

# -npop is required and must match the .geno column count / 2.
NCOL=$(head -1 "$GENO" | awk '{print NF}')
NPOP="${NPOP:-$(( NCOL / 2 ))}"
if [ "$(( NPOP * 2 ))" -ne "$NCOL" ]; then
    echo "ERROR: NPOP=$NPOP implies $(( NPOP * 2 )) columns, file has $NCOL." >&2
    exit 1
fi
NSNP=$(wc -l < "$GENO")
echo "Populations: $NPOP    SNPs: $NSNP    threads: $NTHREADS"

cd "$OUTDIR"

# -----------------------------------------------------------------------------
log "Core model"
CORE_ARGS=(-npop "$NPOP" -gfile "$GENO" -outprefix ghana_core
           -nthreads "$NTHREADS" -seed "$SEED")
if [ -n "$EFILE" ]; then
    echo "Environmental covariate supplied — running the STD model as well."
fi

if [ -f "ghana_core_summary_pi_xtx.out" ]; then
    echo "  core model output already present — skipping"
else
    "$BAYPASS_BIN" "${CORE_ARGS[@]}" 2>&1 | tee "$LOGDIR/baypass_core.log"
fi

for f in ghana_core_summary_pi_xtx.out ghana_core_mat_omega.out; do
    [ -f "$f" ] || { echo "ERROR: expected output $f not produced." >&2; exit 1; }
done
echo "Core model outputs present."

# -----------------------------------------------------------------------------
if [ -n "$EFILE" ]; then
    log "STD model (environmental association)"
    "$BAYPASS_BIN" -npop "$NPOP" -gfile "$GENO" -efile "$ROOT_DIR/$EFILE" \
        -omegafile ghana_core_mat_omega.out \
        -outprefix ghana_std -nthreads "$NTHREADS" -seed "$SEED" \
        2>&1 | tee "$LOGDIR/baypass_std.log"
fi

# -----------------------------------------------------------------------------
if [ "$SKIP_POD" -eq 1 ]; then
    log "POD simulation skipped (SKIP_POD=1)"
    echo "Step 8c will fall back to an empirical quantile and say so loudly."
    exit 0
fi

log "Simulating pseudo-observed data under the estimated omega"

UTILS=""
for cand in "$(dirname "$BAYPASS_BIN")/utils/baypass_utils.R" \
            "$(dirname "$BAYPASS_BIN")/baypass_public-master/utils/baypass_utils.R"; do
    [ -f "$cand" ] && UTILS="$cand" && break
done

if [ -z "$UTILS" ] || ! command -v Rscript >/dev/null 2>&1; then
    echo "baypass_utils.R or Rscript unavailable."
    echo "Install R with:  mamba install -y -c conda-forge r-base"
    echo "Continuing without POD; Step 8c will use the empirical fallback."
    exit 0
fi

# An R error must fall through to the empirical fallback below, not end the step.
rm -f G.pod   # never fall through to a POD left over from an earlier run
Rscript - "$UTILS" "$GENO" "$NVAL" "$SEED" "$PI_MAF" <<'RSCRIPT' 2>&1 | tee "$LOGDIR/baypass_pod.log" || \
    echo "POD simulation failed — see $LOGDIR/baypass_pod.log"
args <- commandArgs(trailingOnly = TRUE)
source(args[1])
geno      <- as.matrix(read.table(args[2]))
nval      <- as.integer(args[3])
set.seed(as.integer(args[4]))
pimaf     <- as.numeric(args[5])

omega <- as.matrix(read.table("ghana_core_mat_omega.out"))
pibeta <- read.table("ghana_core_summary_beta_params.out", header = TRUE)$Mean

# The .geno file interleaves ref and alt counts per population (2*npop columns);
# simulate.baypass() wants npop columns of total haploid sample size per SNP.
# Passing every SNP lets it resample rows (with replacement) up to nsnp, so the
# POD inherits the genome-wide sample-size distribution and nval may exceed the
# number of observed SNPs.
nn <- geno[, seq(1, ncol(geno), 2), drop = FALSE] +
      geno[, seq(2, ncol(geno), 2), drop = FALSE]
stopifnot(ncol(nn) == nrow(omega))

cat("Simulating", nval, "POD SNPs under the estimated covariance...\n")
simu <- simulate.baypass(
  omega.mat = omega,
  nsnp      = nval,
  sample.size = nn,
  beta.pi   = pibeta,
  pi.maf    = pimaf,
  suffix    = "pod"
)
cat("POD written as G.pod\n")
RSCRIPT

if [ -f "G.pod" ]; then
    log "Running the core model on the POD"
    "$BAYPASS_BIN" -npop "$NPOP" -gfile G.pod -outprefix ghana_pod \
        -nthreads "$NTHREADS" -seed "$SEED" \
        2>&1 | tee "$LOGDIR/baypass_pod_run.log"
    echo "POD XtX distribution -> $OUTDIR/ghana_pod_summary_pi_xtx.out"
else
    echo "G.pod not produced; Step 8c will use the empirical fallback."
fi

echo
echo "Next: python step08c_calibrate_xtx.py"
