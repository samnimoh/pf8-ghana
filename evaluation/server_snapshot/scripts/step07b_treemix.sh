#!/usr/bin/env bash
# =============================================================================
# STEP 7b — TreeMix: population splits and migration edges
# =============================================================================
# -k groups adjacent SNPs into blocks so that linkage is accounted for. Leave it
# out and the standard errors come back anticonservative — every edge looks
# better supported than it is.
#
# Rooting is a modelling decision, not a default. Guinea Savanna is defensible
# for Ghana, but the defence belongs in your methods section.
#
# The sweep runs m = 0..MAX_M as the method specifies. With four populations
# only about two edges are identifiable, so m = 0..2 is the range to interpret
# and m > 2 is run for completeness; Step 7c keeps the two views apart. A failed
# run at any m (or a failed bootstrap replicate) is logged and skipped rather
# than ending the sweep, and results/treemix/run_status.tsv says which m made it.
#
# ROOT, MAX_M and BLOCK default to TREEMIX_ROOT, TREEMIX_MAX_M and
# TREEMIX_BLOCK_SIZE in config.py, so this script cannot drift from the labels
# Step 7a writes. Environment variables still override them.
#
# JOBS (default 6) is how many TreeMix processes run at once; TreeMix is
# single-threaded, so that is also the number of cores used. Every fit and
# every bootstrap replicate keeps its own seed, -o prefix and log, and the
# tables are written only after all of them finish, so JOBS changes the wall
# time and nothing else. JOBS=1 runs them one after another.
#
# Usage:
#   bash step07b_treemix.sh
#   MAX_M=8 BLOCK=1000 ROOT=Coastal_savanna bash step07b_treemix.sh
#   BOOTSTRAP=100 bash step07b_treemix.sh        # bootstrap the m=0 topology
#   JOBS=20 BOOTSTRAP=100 bash step07b_treemix.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${PF8_GHANA_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
INPUT="$ROOT_DIR/interim/ghana_treemix_input.gz"
OUTDIR="$ROOT_DIR/results/treemix"
LOGDIR="$ROOT_DIR/logs"
STATUS_TSV="$OUTDIR/run_status.tsv"

# Edges beyond this are poorly identifiable with four populations. Keep in step
# with IDENTIFIABLE_MAX_M in step07c_plot_treemix.py.
IDENT_MAX_M=2

# Same interpreter choice as run_all.sh (which does not export PYTHON).
if [ -z "${PYTHON:-}" ]; then
    if command -v python >/dev/null 2>&1; then PYTHON=python
    elif command -v python3 >/dev/null 2>&1; then PYTHON=python3
    else PYTHON=""; fi
fi

# Defaults from config.py — only consulted for whatever is not set already.
CFG_MAX_M=""; CFG_BLOCK=""; CFG_ROOT=""
if [ -z "${MAX_M:-}" ] || [ -z "${BLOCK:-}" ] || [ -z "${ROOT:-}" ]; then
    [ -n "$PYTHON" ] || {
        echo "ERROR: no python or python3 on PATH to read config.py." >&2
        echo "       Set MAX_M, BLOCK and ROOT explicitly, or PYTHON=..." >&2; exit 1; }
    CFG=$("$PYTHON" -c 'import sys; sys.path.insert(0, sys.argv[1]); import config as C; print(C.TREEMIX_MAX_M, C.TREEMIX_BLOCK_SIZE, C.TREEMIX_ROOT)' \
          "$SCRIPT_DIR" | tail -n 1) || {
        echo "ERROR: could not read TreeMix defaults from $SCRIPT_DIR/config.py ($PYTHON)." >&2
        echo "       Set MAX_M, BLOCK and ROOT explicitly, or PYTHON=..." >&2; exit 1; }
    read -r CFG_MAX_M CFG_BLOCK CFG_ROOT <<<"$CFG"
fi

MAX_M="${MAX_M:-$CFG_MAX_M}"
BLOCK="${BLOCK:-$CFG_BLOCK}"
ROOT="${ROOT:-$CFG_ROOT}"
BOOTSTRAP="${BOOTSTRAP:-0}"
SEED="${SEED:-42}"
JOBS="${JOBS:-6}"       # TreeMix processes at once (1 core each)
if ! [[ "$JOBS" =~ ^[0-9]+$ ]] || [ "$JOBS" -lt 1 ]; then
    echo "ERROR: JOBS must be a whole number >= 1 (got '$JOBS')." >&2; exit 1
fi

mkdir -p "$OUTDIR" "$LOGDIR"
log() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

command -v treemix >/dev/null 2>&1 || {
    echo "ERROR: treemix not on PATH. conda activate pf8ghana" >&2; exit 1; }
[ -f "$INPUT" ] || {
    echo "ERROR: $INPUT missing. Run step07a_treemix_input.py" >&2; exit 1; }

# head closes the pipe after one line; under pipefail the SIGPIPE that zcat then
# takes would end the script right here, so pipefail is off for this one read.
HEADER=$(set +o pipefail; zcat "$INPUT" | head -1)
NSNP=$(( $(zcat "$INPUT" | wc -l) - 1 ))
echo "Populations: $HEADER"
echo "SNPs:        $NSNP"
echo "Root:        $ROOT"
echo "Block size:  $BLOCK"
echo "Edges:       m = 0..$MAX_M  (identifiable with 4 populations: m <= $IDENT_MAX_M)"
echo "Jobs:        $JOBS TreeMix run(s) at a time"

if ! grep -qw "$ROOT" <<<"$HEADER"; then
    echo "ERROR: root '$ROOT' is not one of the populations above." >&2
    echo "       Labels are case-sensitive. Fix TREEMIX_ROOT in config.py, or" >&2
    echo "       override with ROOT=<label> bash step07b_treemix.sh" >&2
    exit 1
fi

if [ "$NSNP" -lt $(( BLOCK * 20 )) ]; then
    echo "WARNING: $NSNP SNPs against a block size of $BLOCK gives few blocks."
    echo "         Consider BLOCK=$(( NSNP / 50 )) or lower."
fi

cd "$OUTDIR"

# Everything Step 7c reads for one m. The likelihood file is optional.
m_complete() {
    local s="treemix_m$1"
    [ -f "$s.treeout.gz" ] && [ -f "$s.cov.gz" ] && [ -f "$s.modelcov.gz" ]
}

# Final log likelihood for one m, or nothing. TreeMix 1.13 writes <stem>.llik
# uncompressed, so both spellings are read. Never fails, so set -e is safe.
llik_of() {
    local s="treemix_m$1"
    if [ -f "$s.llik.gz" ]; then
        zcat "$s.llik.gz" 2>/dev/null | awk 'NF {v = $NF} END {if (v != "") print v}' || true
    elif [ -f "$s.llik" ]; then
        awk 'NF {v = $NF} END {if (v != "") print v}' "$s.llik"
    fi
}

# This replicate's Newick tree, or nothing. Never fails, so set -e is safe.
bs_tree() {
    zcat "$OUTDIR/bootstrap/bs_$1.treeout.gz" 2>/dev/null | grep '^(' || true
}

# -----------------------------------------------------------------------------
# Running TreeMix side by side. Each job runs one m (or one bootstrap replicate)
# with the same command line, seed, -o prefix and log as a sequential run, so
# it writes only its own files, plus a one-line status file (id, status, exit
# code). run_status.tsv, bootstrap_status.tsv and bootstrap_trees.nwk are built
# from those after every job has finished, in m / replicate order — nothing
# shared is ever written by two jobs at once.

# wait -n (bash >= 4.3) sleeps until a job ends; older bash polls instead.
if (( BASH_VERSINFO[0] > 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] >= 3) )); then
    HAVE_WAIT_N=1
else
    HAVE_WAIT_N=0
fi

# Return once fewer than JOBS jobs are running. Counting live jobs each time
# (rather than keeping a counter) cannot drift if wait -n misses a job.
throttle() {
    local n p
    while :; do
        n=0
        for p in $(jobs -rp); do n=$((n + 1)); done
        [ "$n" -ge "$JOBS" ] || return 0
        if [ "$HAVE_WAIT_N" -eq 1 ]; then wait -n || true; else sleep 1; fi
    done
}

run_m() {
    local m="$1" rc=0 status
    # `|| rc=$?` stops set -e from ending the job (and the sweep) on one bad m.
    treemix -i "$INPUT" -root "$ROOT" -m "$m" -k "$BLOCK" -seed "$SEED" \
            -o "treemix_m${m}" > "$LOGDIR/treemix_m${m}.log" 2>&1 || rc=$?
    if [ "$rc" -ne 0 ]; then
        status=failed
    elif ! m_complete "$m"; then
        status=incomplete       # exited 0 but left no cov/modelcov/treeout
    else
        status=ok
    fi
    printf '%s\t%s\t%s\n' "$m" "$status" "$rc" > "$OUTDIR/.status_m${m}"
    if [ "$status" = ok ]; then
        echo "  m=${m} ok (exit ${rc})"
    else
        echo "  m=${m} FAILED (${status}, exit ${rc}) — skipped; see $LOGDIR/treemix_m${m}.log"
    fi
}

run_bs() {
    local i="$1" rc=0 st tree=""
    treemix -i "$INPUT" -root "$ROOT" -k "$BLOCK" -bootstrap \
            -seed "$((SEED + i))" -o "$OUTDIR/bootstrap/bs_${i}" \
            > "$BS_PARTS/bs_${i}.log" 2>&1 || rc=$?
    # Only this run's successful replicates go into the tree file, so a
    # failed one or a stale bs_*.treeout.gz from an earlier run cannot.
    if [ "$rc" -eq 0 ]; then tree=$(bs_tree "$i"); fi
    if [ -n "$tree" ]; then st=ok
    elif [ "$rc" -ne 0 ]; then st=failed
    else st=incomplete; fi
    printf '%s\t%s\t%s\n' "$i" "$st" "$rc" > "$OUTDIR/bootstrap/.status_bs${i}"
    if [ "$st" = ok ]; then
        echo "  replicate ${i} ok (exit ${rc})"
    else
        echo "  replicate ${i} FAILED (${st}, exit ${rc}) — skipped; see $BS_LOG"
    fi
}

# Background jobs of a non-interactive shell ignore Ctrl-C, so without this an
# interrupted run would leave TreeMix going — and racing a rerun for the same
# output files. The treemix under each job is stopped, then the job itself.
stop_jobs() {
    trap - INT TERM
    echo "Interrupted — stopping the TreeMix runs still going." >&2
    local p
    for p in $(jobs -p); do
        pkill -TERM -P "$p" 2>/dev/null || true
        kill -TERM "$p" 2>/dev/null || true
    done
    wait || true
    rm -f "$OUTDIR"/.status_m* "$OUTDIR"/bootstrap/.status_bs*
    exit "$1"
}
trap 'stop_jobs 130' INT
trap 'stop_jobs 143' TERM

# -----------------------------------------------------------------------------
log "Migration edge sweep m = 0..${MAX_M}  (${JOBS} at a time)"
for m in $(seq 0 "$MAX_M"); do
    rm -f "$OUTDIR/.status_m${m}"       # never one left by an interrupted run
    if m_complete "$m"; then
        echo "  m=${m} already done — skipping"
        printf '%s\tcached\tNA\n' "$m" > "$OUTDIR/.status_m${m}"
    else
        throttle
        run_m "$m" &
    fi
done
wait

printf 'm\tstatus\texit_code\n' > "$STATUS_TSV"
OK_M=""; FAILED_M=""
for m in $(seq 0 "$MAX_M"); do
    sf="$OUTDIR/.status_m${m}"
    status=failed; rc=NA                # the job died before writing its status
    if [ -s "$sf" ]; then IFS=$'\t' read -r _id status rc < "$sf" || true; fi
    rm -f "$sf"
    printf '%s\t%s\t%s\n' "$m" "$status" "$rc" >> "$STATUS_TSV"
    case "$status" in
        ok|cached) OK_M="$OK_M $m" ;;
        *)         FAILED_M="$FAILED_M $m"
                   echo "  m=${m} ${status} (exit ${rc}); end of $LOGDIR/treemix_m${m}.log:"
                   tail -n 3 "$LOGDIR/treemix_m${m}.log" 2>/dev/null | sed 's/^/      | /' || true ;;
    esac
done

# -----------------------------------------------------------------------------
log "Likelihood by number of edges"
{
    echo -e "m\tlog_likelihood"
    for m in $(seq 0 "$MAX_M"); do
        LL=""
        # A failed m reports NA even if it left a partial .llik behind.
        case " $OK_M " in *" $m "*) LL=$(llik_of "$m") ;; esac
        echo -e "${m}\t${LL:-NA}"
    done
} | tee "$OUTDIR/likelihood_by_m.tsv"

# -----------------------------------------------------------------------------
if [ "$BOOTSTRAP" -gt 0 ]; then
    log "Bootstrapping the m=0 topology (${BOOTSTRAP} replicates, ${JOBS} at a time)"
    mkdir -p "$OUTDIR/bootstrap"
    BS_LOG="$LOGDIR/treemix_bootstrap.log"
    BS_STATUS="$OUTDIR/bootstrap_status.tsv"
    # Each replicate logs to its own file here while it runs; they are joined
    # into BS_LOG in replicate order at the end, so output never interleaves.
    BS_PARTS="$LOGDIR/treemix_bootstrap.parts"
    rm -rf "$BS_PARTS"; mkdir -p "$BS_PARTS"
    for i in $(seq 1 "$BOOTSTRAP"); do
        rm -f "$OUTDIR/bootstrap/.status_bs${i}"
        throttle
        run_bs "$i" &
    done
    wait

    : > "$BS_LOG"
    : > "$OUTDIR/bootstrap_trees.nwk"
    printf 'replicate\tstatus\texit_code\n' > "$BS_STATUS"
    BS_OK=0; BS_FAILED=""
    for i in $(seq 1 "$BOOTSTRAP"); do
        sf="$OUTDIR/bootstrap/.status_bs${i}"
        st=failed; rc=NA                # the job died before writing its status
        if [ -s "$sf" ]; then IFS=$'\t' read -r _id st rc < "$sf" || true; fi
        rm -f "$sf"
        TREE=""
        if [ "$st" = ok ]; then TREE=$(bs_tree "$i"); fi
        if [ -n "$TREE" ]; then
            printf '%s\n' "$TREE" >> "$OUTDIR/bootstrap_trees.nwk"
            BS_OK=$(( BS_OK + 1 ))
        else
            if [ "$st" = ok ]; then st=incomplete; fi   # tree gone since the job checked
            BS_FAILED="$BS_FAILED $i"
        fi
        printf '%s\t%s\t%s\n' "$i" "$st" "$rc" >> "$BS_STATUS"
        { echo "### replicate ${i} (seed $((SEED + i)))"
          cat "$BS_PARTS/bs_${i}.log" 2>/dev/null || true; } >> "$BS_LOG"
    done
    rm -rf "$BS_PARTS"
    echo "Bootstrap replicates: ${BS_OK}/${BOOTSTRAP} succeeded; failed:${BS_FAILED:- none}"
    echo "Bootstrap status -> $BS_STATUS"
    if [ "$BS_OK" -gt 0 ]; then
        echo "Bootstrap trees -> $OUTDIR/bootstrap_trees.nwk"
        echo "Summarise with your preferred consensus tool (e.g. RAxML -J MR)."
    else
        echo "WARNING: no bootstrap replicate succeeded; bootstrap_trees.nwk is empty."
    fi
fi

# -----------------------------------------------------------------------------
log "Run summary"
IDENT_OK=""; EXTRA_OK=""
for m in $OK_M; do
    if [ "$m" -le "$IDENT_MAX_M" ]; then IDENT_OK="$IDENT_OK $m"; else EXTRA_OK="$EXTRA_OK $m"; fi
done
echo "  succeeded: m =${OK_M:- none}"
echo "  failed:    m =${FAILED_M:- none}"
echo "  m = 0..${IDENT_MAX_M}  (identifiable with 4 populations) succeeded:${IDENT_OK:- none}"
if [ "$MAX_M" -gt "$IDENT_MAX_M" ]; then
    echo "  m = $(( IDENT_MAX_M + 1 ))..${MAX_M}  (run per method, poorly identifiable) succeeded:${EXTRA_OK:- none}"
fi
echo "Run status -> $STATUS_TSV"

if [ -z "$OK_M" ]; then
    echo "ERROR: no TreeMix run succeeded, so Step 7c has nothing to summarise." >&2
    echo "       Per-m logs: $LOGDIR/treemix_m*.log" >&2
    exit 1
fi

cat <<'EOF'

Stop adding edges where the variance explained plateaus, not where the
likelihood stops rising — likelihood rises monotonically with m by construction.

Next: python step07c_plot_treemix.py
EOF
