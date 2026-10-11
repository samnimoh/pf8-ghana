#!/usr/bin/env python3
"""
Check whether this machine can actually run the pipeline.

Standard library only, so it runs on a bare system Python with nothing
installed. Run it before anything else:

    python3 scripts/check_env.py

It reports three things: which Python packages are importable and at what
version, which command-line tools are on PATH, and — where something is
missing — the exact step that will fail and the precise package name to ask
your administrator for.

"The server has everything" usually holds for numpy, pandas and scipy. The
specialist pieces (scikit-allel, scikit-bio, umap-learn, ADMIXTURE, TreeMix,
BayPass) are rarely preinstalled, and zarr is often present at a version that
breaks conversion. Checking takes ten seconds and saves a round trip.

Exit status is 0 when every requirement for Steps 1-9 is satisfied, 1 when
something is missing.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

# (module, friendly name, steps that need it, how to install)
PY_REQUIREMENTS = [
    ("numpy",     "NumPy",          "all",        "conda install -c conda-forge numpy"),
    ("pandas",    "pandas",         "all",        "conda install -c conda-forge pandas"),
    ("scipy",     "SciPy",          "3b, 6",      "conda install -c conda-forge scipy"),
    ("matplotlib", "Matplotlib",    "2,3,4b,5c,6,7c,8c", "conda install -c conda-forge matplotlib"),
    ("geopandas", "GeoPandas",      "2, 6",       "conda install -c conda-forge geopandas"),
    ("shapely",   "Shapely",        "2",          "conda install -c conda-forge shapely"),
    ("pyproj",    "pyproj",         "6",          "conda install -c conda-forge pyproj"),
    ("allel",     "scikit-allel",   "3b,4a,4b,5a,6", "pip install scikit-allel"),
    ("zarr",      "Zarr",           "3b, 4a",     "conda install -c conda-forge 'zarr<3'"),
    ("numcodecs", "numcodecs",      "3b, 4a",     "conda install -c conda-forge numcodecs"),
    ("skbio",     "scikit-bio",     "6",          "pip install scikit-bio"),
    ("umap",      "umap-learn",     "3",          "pip install umap-learn"),
    ("numba",     "Numba",          "3",          "conda install -c conda-forge numba"),
]

OPTIONAL_PY = [
    ("dask",            "Dask",            "4a (large callsets)", "conda install -c conda-forge dask"),
    ("malariagen_data", "malariagen_data", "4a alternative route", "pip install malariagen_data"),
]

CLI_REQUIREMENTS = [
    ("plink",     "PLINK",     "5a, 5b", "conda install -c bioconda plink"),
    ("admixture", "ADMIXTURE", "5b",     "conda install -c bioconda admixture"),
    ("treemix",   "TreeMix",   "7b",     "conda install -c bioconda treemix"),
    ("bedtools",  "bedtools",  "9",      "conda install -c bioconda bedtools"),
]

CLI_OPTIONAL = [
    ("bcftools", "bcftools", "VCF handling, merging",      "conda install -c bioconda bcftools"),
    ("tabix",    "tabix",    "VCF indexing",               "conda install -c bioconda htslib"),
    ("Rscript",  "R",        "8b POD calibration (else fallback)", "conda install -c conda-forge r-base"),
    ("tmux",     "tmux",     "keeping long runs alive",    "usually preinstalled"),
]

GREEN, RED, YELLOW, BOLD, DIM, OFF = (
    "\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[2m", "\033[0m"
) if sys.stdout.isatty() else ("", "", "", "", "", "")


def banner(text: str) -> None:
    print(f"\n{BOLD}{text}{OFF}\n" + "-" * 72)


def check_python_packages() -> list[tuple]:
    banner("Python packages")
    print(f"  interpreter: {sys.executable}")
    print(f"  version    : {sys.version.split()[0]}")
    if sys.version_info < (3, 9):
        print(f"  {RED}Python 3.9+ required{OFF}")
    print()

    missing = []
    for mod, name, steps, fix in PY_REQUIREMENTS:
        try:
            m = importlib.import_module(mod)
            ver = str(getattr(m, "__version__", "?"))

            # zarr 3 removed Group.create_dataset, which scikit-allel's writer
            # calls. Conversion dies partway through with an error that reads
            # like a bug in this pipeline.
            if mod == "zarr" and ver[0].isdigit() and int(ver.split(".")[0]) >= 3:
                print(f"  {RED}✗{OFF} {name:<16} {ver:<12} "
                      f"{RED}too new — scikit-allel needs zarr 2.x{OFF}")
                missing.append((name, steps, "conda install -c conda-forge 'zarr<3'"))
                continue

            if mod == "numpy" and ver[0].isdigit() and int(ver.split(".")[0]) >= 2:
                print(f"  {YELLOW}!{OFF} {name:<16} {ver:<12} "
                      f"{YELLOW}numpy 2 — scikit-allel 1.3.x may warn or fail{OFF}")
                continue

            print(f"  {GREEN}✓{OFF} {name:<16} {ver}")
        except Exception as exc:
            print(f"  {RED}✗{OFF} {name:<16} {'—':<12} "
                  f"{RED}missing{OFF} {DIM}({type(exc).__name__}){OFF}")
            missing.append((name, steps, fix))

    print()
    for mod, name, steps, fix in OPTIONAL_PY:
        try:
            m = importlib.import_module(mod)
            print(f"  {GREEN}✓{OFF} {name:<16} {getattr(m, '__version__', 'ok')}  {DIM}(optional){OFF}")
        except Exception:
            print(f"  {DIM}·  {name:<16} not installed — optional, for {steps}{OFF}")

    return missing


def check_cli_tools() -> list[tuple]:
    banner("Command-line tools")
    missing = []
    for cmd, name, steps, fix in CLI_REQUIREMENTS:
        path = shutil.which(cmd)
        if path:
            print(f"  {GREEN}✓{OFF} {name:<16} {path}")
        else:
            print(f"  {RED}✗{OFF} {name:<16} {RED}not on PATH{OFF}")
            missing.append((name, steps, fix))

    print()
    for cmd, name, steps, fix in CLI_OPTIONAL:
        path = shutil.which(cmd)
        if path:
            print(f"  {GREEN}✓{OFF} {name:<16} {path}  {DIM}(optional){OFF}")
        else:
            print(f"  {DIM}·  {name:<16} not found — {steps}{OFF}")
    return missing


def check_baypass() -> bool:
    banner("BayPass (Step 8)")
    candidates = []
    env_bin = os.environ.get("BAYPASS_BIN")
    if env_bin:
        candidates.append(Path(env_bin))
    candidates += [
        Path.home() / "tools/baypass/g_baypass",
        Path("/usr/local/bin/g_baypass"),
        Path("/opt/baypass/g_baypass"),
    ]
    which = shutil.which("g_baypass")
    if which:
        candidates.insert(0, Path(which))

    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            print(f"  {GREEN}✓{OFF} found at {c}")
            return True

    print(f"  {RED}✗{OFF} not found")
    print(f"  {DIM}BayPass is distributed as Fortran source, never as a package.{OFF}")
    print(f"  {DIM}It is almost never preinstalled, even on well-stocked servers.{OFF}")
    print("\n  Build it yourself (no root needed, ~2 minutes):")
    print("    mkdir -p ~/tools/baypass && cd ~/tools/baypass")
    print("    wget https://forgemia.inra.fr/mathieu.gautier/baypass_public/-/archive/master/baypass_public-master.tar.gz")
    print("    tar -xzf baypass_public-master.tar.gz")
    print("    cd baypass_public-master/sources && make FC=gfortran")
    print("    cp g_baypass ~/tools/baypass/ && cp -r ../utils ~/tools/baypass/")
    print("    export BAYPASS_BIN=~/tools/baypass/g_baypass")
    return False


def check_module_system() -> None:
    """Institutional servers often hide software behind Lmod rather than PATH."""
    if not (os.environ.get("MODULEPATH") or shutil.which("modulecmd")
            or Path("/usr/share/lmod").exists()):
        return
    banner("Environment modules detected")
    print("  This server uses a module system, so software may be installed but")
    print("  not yet loaded. Before concluding anything is missing, try:")
    print("    module avail 2>&1 | grep -iE 'python|conda|plink|admixture|treemix'")
    print("    module load <whatever that lists>")
    try:
        out = subprocess.run(["bash", "-lc", "module avail 2>&1 | head -40"],
                             capture_output=True, text=True, timeout=20)
        if out.stdout.strip():
            print(f"\n{DIM}  module avail (first lines):{OFF}")
            for line in out.stdout.strip().splitlines()[:15]:
                print(f"    {line}")
    except Exception:
        pass


def check_project() -> None:
    banner("Project layout")
    root = Path(os.environ.get("PF8_GHANA_ROOT",
                               Path(__file__).resolve().parent.parent)).resolve()
    print(f"  root: {root}")
    for sub in ("data", "scripts", "interim", "results", "figures", "logs"):
        d = root / sub
        print(f"  {GREEN + '✓' + OFF if d.is_dir() else DIM + '·' + OFF} {sub}")

    data = root / "data"
    if data.is_dir():
        vcfs = sorted(data.glob("Pf8_Ghana_*_v3.vcf.gz"))
        print(f"\n  per-chromosome VCFs: {len(vcfs)}")
        for label, pat in [("sample manifest", "Pf8_samples.txt"),
                           ("AEZ geojson", "ghanaAEZ.geojson"),
                           ("distance matrix", "Pf8_mean_genotype_distance*.npy"),
                           ("PlasmoDB GFF", "PlasmoDB-*_Pfalciparum3D7.gff*")]:
            hits = sorted(data.glob(pat))
            mark = GREEN + "✓" + OFF if hits else RED + "✗" + OFF
            detail = hits[0].name if hits else "missing"
            extra = f"  {DIM}(+{len(hits)-1} more){OFF}" if len(hits) > 1 else ""
            print(f"  {mark} {label:<18} {detail}{extra}")


def main() -> int:
    print(f"{BOLD}Pf8 Ghana pipeline — environment check{OFF}")
    print(f"{DIM}host: {os.uname().nodename}{OFF}")

    py_missing = check_python_packages()
    cli_missing = check_cli_tools()
    has_baypass = check_baypass()
    check_module_system()
    check_project()

    banner("Verdict")
    if not py_missing and not cli_missing and has_baypass:
        print(f"  {GREEN}Everything needed for Steps 1-9 is present.{OFF}")
        print("\n  Next:  python scripts/config.py")
        return 0

    blocked = set()
    print(f"  {RED}Missing pieces:{OFF}\n")
    for name, steps, fix in py_missing + cli_missing:
        print(f"    {name:<16} needed by step(s) {steps}")
        print(f"    {DIM}{'':<16} {fix}{OFF}")
        blocked.update(s.strip() for s in steps.replace("all", "1-9").split(","))
    if not has_baypass:
        print(f"    {'BayPass':<16} needed by step 8 (build from source; see above)")
        blocked.add("8")

    def step_key(s: str) -> tuple:
        digits = "".join(c for c in s if c.isdigit()) or "0"
        return (int(digits), s)

    print(f"\n  {YELLOW}Steps affected: "
          f"{', '.join(sorted(blocked, key=step_key))}{OFF}")
    print("\n  Two ways forward:")
    print("    1. Send the list above to your administrator — it names exact packages.")
    print("    2. Build your own environment, which needs no root and no waiting:")
    print("         bash scripts/step00_setup.sh")
    print(f"\n  {DIM}Steps whose requirements are met will still run. Nothing here{OFF}")
    print(f"  {DIM}blocks you from starting with Steps 1-3 today.{OFF}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
