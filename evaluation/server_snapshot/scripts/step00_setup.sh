#!/usr/bin/env bash
# =============================================================================
# PHASE 0 — Environment setup, no root required
# =============================================================================
# Written for a shared institutional server where you have no sudo. Every
# dependency comes from conda-forge and bioconda, compilers included, so
# nothing is installed system-wide and nothing needs an administrator.
#
#   bash scripts/step00_setup.sh
#   source activate.sh
#
# Re-running is safe; each block checks before acting.
#
# Paths you can override:
#   CONDA_ROOT    where Miniforge goes        default $HOME/miniforge3
#   ENV_NAME      environment name            default pf8ghana
#   BAYPASS_DIR   where BayPass is built      default $HOME/tools/baypass
#
# With a small home quota, put them on the project volume instead:
#   CONDA_ROOT=/media/biodataA/pf8/gyadu/opt/miniforge3 \
#   BAYPASS_DIR=/media/biodataA/pf8/gyadu/opt/baypass \
#   bash scripts/step00_setup.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ENV_NAME="${ENV_NAME:-pf8ghana}"
CONDA_ROOT="${CONDA_ROOT:-$HOME/miniforge3}"
BAYPASS_DIR="${BAYPASS_DIR:-$HOME/tools/baypass}"
ENV_YML="$PROJECT_ROOT/environment.yml"

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m    %s\033[0m\n' "$*"; }
die()  { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

log "Pf8 Ghana pipeline — environment setup"
echo "  project     : $PROJECT_ROOT"
echo "  conda root  : $CONDA_ROOT"
echo "  environment : $ENV_NAME"
echo "  baypass     : $BAYPASS_DIR"

# -----------------------------------------------------------------------------
# 1. Space check — the environment plus BayPass needs roughly 6 GB
# -----------------------------------------------------------------------------
log "Checking available space"
for d in "$(dirname "$CONDA_ROOT")" "$(dirname "$BAYPASS_DIR")" "$PROJECT_ROOT"; do
    mkdir -p "$d" 2>/dev/null || true
    avail=$(df -BG --output=avail "$d" 2>/dev/null | tail -1 | tr -dc '0-9' || true)
    printf '  %-48s %s GB free\n' "$d" "${avail:-?}"
    if [ -n "${avail:-}" ] && [ "$avail" -lt 10 ] 2>/dev/null; then
        warn "under 10 GB here — consider pointing CONDA_ROOT at the project volume"
    fi
done

# -----------------------------------------------------------------------------
# 2. Find or install conda
# -----------------------------------------------------------------------------
log "Locating conda"

CONDA_SH=""
# A conda the server already provides is preferable — it is already configured
# for this filesystem, and it saves a 500 MB download.
if [ -n "${CONDA_EXE:-}" ] && [ -x "${CONDA_EXE:-}" ]; then
    CONDA_SH="$(dirname "$(dirname "$CONDA_EXE")")/etc/profile.d/conda.sh"
    echo "  active conda found: $CONDA_EXE"
elif command -v conda >/dev/null 2>&1; then
    CONDA_SH="$(dirname "$(dirname "$(command -v conda)")")/etc/profile.d/conda.sh"
    echo "  conda on PATH: $(command -v conda)"
elif [ -f "$CONDA_ROOT/etc/profile.d/conda.sh" ]; then
    CONDA_SH="$CONDA_ROOT/etc/profile.d/conda.sh"
    echo "  earlier Miniforge found at $CONDA_ROOT"
fi

if [ -z "$CONDA_SH" ] || [ ! -f "$CONDA_SH" ]; then
    log "Installing Miniforge to $CONDA_ROOT (user-level, no root)"
    TMPD="$(mktemp -d)"
    URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"
    if command -v wget >/dev/null 2>&1; then
        wget -q -O "$TMPD/miniforge.sh" "$URL" \
            || die "download failed — if this server sits behind a proxy, set http_proxy/https_proxy first"
    elif command -v curl >/dev/null 2>&1; then
        curl -fsSL -o "$TMPD/miniforge.sh" "$URL" \
            || die "download failed — if this server sits behind a proxy, set http_proxy/https_proxy first"
    else
        die "neither wget nor curl found; download Miniforge manually from $URL"
    fi
    bash "$TMPD/miniforge.sh" -b -p "$CONDA_ROOT"
    rm -rf "$TMPD"
    CONDA_SH="$CONDA_ROOT/etc/profile.d/conda.sh"
fi

# shellcheck disable=SC1090
source "$CONDA_SH"
echo "  conda $(conda --version 2>/dev/null | awk '{print $2}')"

# mamba resolves this environment in a fraction of conda's time.
SOLVER="conda"
if command -v mamba >/dev/null 2>&1; then
    SOLVER="mamba"
else
    log "Installing mamba into base (much faster dependency solving)"
    if conda install -y -n base -c conda-forge mamba >/dev/null 2>&1; then
        SOLVER="mamba"
        hash -r
    else
        warn "mamba install failed; using conda instead (slower, still correct)"
    fi
fi
echo "  solver: $SOLVER"

# -----------------------------------------------------------------------------
# 3. The environment
# -----------------------------------------------------------------------------
[ -f "$ENV_YML" ] || die "environment.yml not found at $ENV_YML"

if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    log "Environment '$ENV_NAME' exists — updating from environment.yml"
    $SOLVER env update -n "$ENV_NAME" -f "$ENV_YML" --prune
else
    log "Creating environment '$ENV_NAME' from environment.yml"
    echo "  expect 10-20 minutes; the dependency solve is the slow part"
    $SOLVER env create -f "$ENV_YML"
fi

conda activate "$ENV_NAME"
echo "  active: ${CONDA_PREFIX:-unknown}"

# -----------------------------------------------------------------------------
# 4. BayPass — Fortran source, built once with conda's gfortran
# -----------------------------------------------------------------------------
log "BayPass"

if [ -x "$BAYPASS_DIR/g_baypass" ]; then
    echo "  already built at $BAYPASS_DIR/g_baypass"
else
    mkdir -p "$BAYPASS_DIR"
    cd "$BAYPASS_DIR"

    TARBALL="baypass_public-master.tar.gz"
    URL="https://forgemia.inra.fr/mathieu.gautier/baypass_public/-/archive/master/$TARBALL"
    if [ ! -f "$TARBALL" ]; then
        echo "  downloading source..."
        if command -v wget >/dev/null 2>&1; then
            wget -q -O "$TARBALL" "$URL" || warn "download failed"
        else
            curl -fsSL -o "$TARBALL" "$URL" || warn "download failed"
        fi
    fi

    if [ -s "$TARBALL" ]; then
        tar -xzf "$TARBALL"
        cd baypass_public-master/sources

        # The shipped Makefile defaults to Intel's ifort, which is not here.
        # $FC is exported by conda's gfortran_linux-64 activation hook.
        FORT="${FC:-gfortran}"
        echo "  compiling with $FORT ..."
        make clean >/dev/null 2>&1 || true
        if make FC="$FORT" > "$BAYPASS_DIR/build.log" 2>&1; then
            cp g_baypass "$BAYPASS_DIR/g_baypass"
            cp -r ../utils "$BAYPASS_DIR/utils" 2>/dev/null || true
            echo "  built -> $BAYPASS_DIR/g_baypass"
        else
            warn "BayPass build failed; see $BAYPASS_DIR/build.log"
            warn "Steps 1-7 and 9 are unaffected — only Step 8 needs this."
            warn "Retry:  cd $BAYPASS_DIR/baypass_public-master/sources && make FC=gfortran"
        fi
        cd "$BAYPASS_DIR"
    else
        warn "no BayPass source downloaded; Step 8 will not run until it is built"
    fi
fi

# -----------------------------------------------------------------------------
# 5. Verify
# -----------------------------------------------------------------------------
log "Verification"

set +e
python - <<'PY'
import importlib, sys

checks = [
    ("numpy", None), ("pandas", None), ("scipy", None), ("matplotlib", None),
    ("geopandas", None), ("pyproj", None), ("shapely", None),
    ("allel", None), ("skbio", None), ("umap", None),
    ("zarr", "lt3"), ("numba", None), ("dask", None),
]
bad = []
for mod, rule in checks:
    try:
        m = importlib.import_module(mod)
        v = getattr(m, "__version__", "ok")
        note = ""
        if rule == "lt3" and int(str(v).split(".")[0]) >= 3:
            note = "   <-- TOO NEW; need zarr<3 or Step 4a cannot convert"
            bad.append(mod)
        print(f"  {mod:<12} {v}{note}")
    except Exception as e:
        print(f"  {mod:<12} FAILED: {type(e).__name__}: {e}")
        bad.append(mod)

if bad:
    print("\n  Unresolved: " + ", ".join(bad), file=sys.stderr)
    sys.exit(1)
print("\n  Python stack OK")
PY
PY_OK=$?
set -e

echo
for tool in plink admixture treemix bedtools bcftools Rscript; do
    if command -v "$tool" >/dev/null 2>&1; then
        printf '  %-12s %s\n' "$tool" "$(command -v "$tool")"
    else
        printf '  %-12s MISSING\n' "$tool"
    fi
done
if [ -x "$BAYPASS_DIR/g_baypass" ]; then
    printf '  %-12s %s\n' "g_baypass" "$BAYPASS_DIR/g_baypass"
else
    printf '  %-12s MISSING (Step 8 only)\n' "g_baypass"
fi

# -----------------------------------------------------------------------------
# 6. An activation snippet, so every later session is one command
# -----------------------------------------------------------------------------
ACT="$PROJECT_ROOT/activate.sh"
cat > "$ACT" <<EOF
# Source this before running the pipeline:   source activate.sh
source "$CONDA_SH"
conda activate $ENV_NAME
export PF8_GHANA_ROOT="$PROJECT_ROOT"
export BAYPASS_BIN="$BAYPASS_DIR/g_baypass"
echo "pf8ghana active | root=\$PF8_GHANA_ROOT"
EOF
log "Wrote $ACT"

cat <<EOF

Setup complete. Every later session starts with:

    cd $PROJECT_ROOT
    source activate.sh
    python scripts/config.py          # confirms which inputs it can see

Then:

    bash scripts/run_all.sh           # everything
    bash scripts/run_all.sh --only 1  # one step at a time

Two things specific to a shared server. Steps 5 and 8 run for hours, so start
them inside tmux or screen — otherwise an SSH drop kills the run. And set
thread counts to your actual allocation rather than trusting nproc, which
reports the whole machine instead of your share of it:

    THREADS=4 bash scripts/step05b_admixture.sh
    NTHREADS=4 bash scripts/step08b_baypass.sh
EOF

exit $PY_OK
