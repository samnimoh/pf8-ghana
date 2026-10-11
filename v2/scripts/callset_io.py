"""
callset_io.py — one place that knows how the VCFs are laid out on disk.

The Pf8 Ghana subset arrives as one VCF per chromosome:

    data/Pf8_Ghana_PF3D7_01_v3.vcf.gz   (+ .tbi)
    ...
    data/Pf8_Ghana_PF3D7_14_v3.vcf.gz

Converting each chromosome into its own Zarr group, rather than merging first,
has two advantages on a shared server. Peak memory stays at one chromosome's
worth instead of fourteen, and a conversion that dies on chromosome 9 leaves
chromosomes 1-8 done — rerun and it skips them.

Both step03b_sample_qc.py and step04a_prepare_callset.py import from here, so
the two can never disagree about what the callset looks like.

Layout of the Zarr store:

    interim/pf8_ghana.zarr/
    ├── Pf3D7_01_v3/
    │   ├── samples
    │   ├── variants/{CHROM,POS,REF,ALT,numalt,is_snp,FILTER_PASS}
    │   └── calldata/{GT,AD,DP,GQ}
    ├── Pf3D7_02_v3/
    └── ...

A single merged VCF still works; it just produces one group per contig found
inside it.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import allel
import numpy as np
import pandas as pd
import zarr

import config as C

# Sort key that puts Pf3D7_02_v3 before Pf3D7_10_v3 (lexical sort does not).
_NUM = re.compile(r"(\d+)")


def _natural_key(name: str) -> tuple:
    return tuple(int(t) if t.isdigit() else t.lower() for t in _NUM.split(str(name)))


def check_zarr_version() -> None:
    """scikit-allel's writer uses zarr 2.x APIs that zarr 3 removed.

    Failing here with instructions beats failing deep inside vcf_to_zarr with
    'Group object has no attribute create_dataset', which looks like a bug in
    this pipeline and is not.
    """
    major = int(str(zarr.__version__).split(".")[0])
    if major >= 3:
        raise RuntimeError(
            f"zarr {zarr.__version__} is installed, but scikit-allel "
            f"{allel.__version__} needs zarr 2.x to write a store.\n"
            f"  Fix:  mamba install -y -c conda-forge 'zarr<3'\n"
            f"  (or:  pip install 'zarr<3')\n"
            f"Reading an existing store is unaffected; only conversion breaks."
        )


# ---------------------------------------------------------------------------
# Finding the VCFs
# ---------------------------------------------------------------------------

def resolve_vcfs(spec: str | Path | None = None) -> list[Path]:
    """Return the VCF files to convert, in chromosome order.

    `spec` may be a single file, a glob, or None (use config's default glob).
    """
    if spec is None:
        spec = C.GHANA_VCF_GLOB

    spec_path = Path(spec)
    if spec_path.exists() and spec_path.is_file():
        return [spec_path]

    # Treat as a glob, relative to DATA_DIR unless it is already absolute.
    pattern = str(spec)
    if Path(pattern).is_absolute():
        base, pat = Path(pattern).parent, Path(pattern).name
    else:
        base, pat = C.DATA_DIR, pattern

    hits = sorted(base.glob(pat), key=lambda p: _natural_key(p.name))
    if not hits:
        raise FileNotFoundError(
            f"No VCF matched '{pat}' in {base}.\n"
            f"  Expected files such as Pf8_Ghana_PF3D7_01_v3.vcf.gz\n"
            f"  Adjust GHANA_VCF_GLOB in config.py, or pass --vcf."
        )

    missing_index = [p for p in hits
                     if not (p.with_suffix(p.suffix + ".tbi").exists()
                             or p.with_suffix(p.suffix + ".csi").exists())]
    if missing_index:
        print(f"  note: {len(missing_index)} VCF(s) have no .tbi/.csi index. "
              f"Conversion still works; region queries would not.")
    return hits


# ---------------------------------------------------------------------------
# Building the store
# ---------------------------------------------------------------------------

def _format_fields(vcf: Path) -> set[str]:
    """Probe the header. Requesting an absent FORMAT field aborts conversion."""
    try:
        return set(allel.read_vcf_headers(str(vcf)).formats.keys())
    except Exception as exc:
        print(f"  (header probe failed on {vcf.name}: {exc}; assuming GT only)")
        return {"GT"}


def _group_name(vcf: Path) -> str:
    """Contig name taken from the file's first data row, not its filename.

    Filenames say PF3D7_01_v3 while the contig inside is Pf3D7_01_v3. Reading
    the real value keeps the Zarr groups consistent with the GFF in Step 9.
    """
    try:
        head = allel.read_vcf(str(vcf), fields=["variants/CHROM"], numbers={"CHROM": 1})
        if head and len(head["variants/CHROM"]):
            return str(head["variants/CHROM"][0])
    except Exception:
        pass
    return vcf.name.split(".")[0]


def build_zarr(vcfs: list[Path] | None = None, force: bool = False,
               want_ad: bool = True) -> zarr.Group:
    """Convert each VCF into its own group. Already-converted groups are skipped."""
    check_zarr_version()

    store = C.CALLSET_ZARR
    if store.exists() and force:
        print(f"Removing existing Zarr store {store}")
        shutil.rmtree(store)

    if vcfs is None:
        vcfs = resolve_vcfs()

    print(f"{len(vcfs)} VCF file(s) to convert:")
    for v in vcfs:
        size = v.stat().st_size / 1e6
        print(f"  {v.name:<40} {size:>8.0f} MB")

    root = zarr.open_group(str(store), mode="a")

    for vcf in vcfs:
        grp = _group_name(vcf)

        if grp in root and "calldata/GT" in root[grp]:
            if want_ad and "calldata/AD" not in root[grp]:
                print(f"  {grp}: cached but has no AD — reconverting for Fws")
                del root[grp]
            else:
                print(f"  {grp}: already converted, skipping")
                continue

        fmt = _format_fields(vcf)
        fields = [
            "samples", "calldata/GT",
            "variants/CHROM", "variants/POS", "variants/REF", "variants/ALT",
            "variants/numalt", "variants/is_snp", "variants/FILTER_PASS",
        ]
        for optional in ("AD", "DP", "GQ"):
            if optional in fmt and (optional != "AD" or want_ad):
                fields.append(f"calldata/{optional}")

        print(f"  {grp}: converting ({sorted(fmt)}) ...", flush=True)
        allel.vcf_to_zarr(str(vcf), str(store), group=grp, fields=fields,
                          alt_number=1, log=None, overwrite=True)

    return zarr.open_group(str(store), mode="r")


def open_callset(spec: str | Path | None = None, force: bool = False,
                 want_ad: bool = True) -> zarr.Group:
    """Open the store, building any missing chromosome groups first."""
    store = C.CALLSET_ZARR
    if store.exists() and not force:
        root = zarr.open_group(str(store), mode="r")
        groups = chrom_groups(root)
        if groups:
            missing_ad = want_ad and any("calldata/AD" not in root[g] for g in groups)

            # Only rebuild for AD if the source VCFs actually carry it. Without
            # this check a callset genotyped without AD would be reconverted on
            # every single run, never gaining the field it cannot supply.
            if missing_ad:
                probe = resolve_vcfs(spec)
                if probe and "AD" not in _format_fields(probe[0]):
                    print("Note: the VCFs carry no AD field, so Fws cannot be")
                    print("computed from them. Supply precomputed values with")
                    print("--fws-from (MalariaGEN publishes Fws for Pf8).")
                    missing_ad = False

            if not missing_ad:
                print(f"Using cached Zarr store {store} ({len(groups)} contigs)")
                return root

            print("Cached store lacks calldata/AD — reconverting affected contigs,")
            print("since Fws needs read depths rather than called genotypes.")
    return build_zarr(resolve_vcfs(spec), force=force, want_ad=want_ad)


# ---------------------------------------------------------------------------
# Reading across groups
# ---------------------------------------------------------------------------

def chrom_groups(root: zarr.Group) -> list[str]:
    """Group names in chromosome order."""
    return sorted((k for k in root.group_keys() if "calldata/GT" in root[k]),
                  key=_natural_key)


def samples(root: zarr.Group) -> np.ndarray:
    """Sample IDs. Verified identical across groups — they must be."""
    groups = chrom_groups(root)
    if not groups:
        raise RuntimeError(f"No usable contig groups in {C.CALLSET_ZARR}")

    first = np.asarray(root[groups[0]]["samples"][:]).astype(str)
    for g in groups[1:]:
        other = np.asarray(root[g]["samples"][:]).astype(str)
        if not np.array_equal(first, other):
            raise ValueError(
                f"Sample lists differ between {groups[0]} and {g}. The "
                f"per-chromosome VCFs were not subset from the same callset; "
                f"genotype columns would not line up."
            )
    return first


def variant_table(root: zarr.Group) -> pd.DataFrame:
    """Variant-level metadata across every contig, with row provenance.

    Only the small 1-D arrays are read, so this is cheap even genome-wide.
    `group` and `local` say where each row lives, which is what take_calldata
    needs to fetch genotypes without loading whole chromosomes.
    """
    frames = []
    for g in chrom_groups(root):
        v = root[g]["variants"]
        n = v["POS"].shape[0]
        alt = np.asarray(v["ALT"][:])
        alt = alt[:, 0] if alt.ndim == 2 else alt

        frames.append(pd.DataFrame({
            "group": g,
            "local": np.arange(n, dtype=np.int64),
            "chrom": np.asarray(v["CHROM"][:]).astype(str),
            "pos": np.asarray(v["POS"][:]),
            "ref": np.asarray(v["REF"][:]).astype(str),
            "alt": alt.astype(str),
            "numalt": (np.asarray(v["numalt"][:]) if "numalt" in v
                       else np.ones(n, dtype=np.int8)),
            "is_snp": (np.asarray(v["is_snp"][:]).astype(bool) if "is_snp" in v
                       else np.ones(n, dtype=bool)),
            "filter_pass": (np.asarray(v["FILTER_PASS"][:]).astype(bool)
                            if "FILTER_PASS" in v else np.ones(n, dtype=bool)),
        }))

    table = pd.concat(frames, ignore_index=True)
    table["global"] = np.arange(len(table), dtype=np.int64)
    return table


def has_field(root: zarr.Group, field: str) -> bool:
    """True when every contig group carries `field` (e.g. 'calldata/AD')."""
    groups = chrom_groups(root)
    return bool(groups) and all(field in root[g] for g in groups)


def take_calldata(root: zarr.Group, selection: pd.DataFrame, field: str,
                  n_alleles: int | None = None) -> np.ndarray:
    """Fetch one calldata field for the selected rows, contig by contig.

    `selection` is a slice of variant_table(), and the returned array follows
    its row order exactly.
    """
    if selection.empty:
        raise ValueError("Empty selection passed to take_calldata.")

    # Track each row's position in `selection` itself, not its global index.
    # Restoring by global order would silently reorder the output whenever the
    # caller passes rows in any order but sorted — the exact class of
    # misalignment this pipeline is built to avoid.
    sel = selection.reset_index(drop=True)
    sel = sel.assign(_row=np.arange(len(sel), dtype=np.int64))

    out, order = [], []
    for g, part in sel.groupby("group", sort=False):
        arr = root[g][field]
        rows = part["local"].to_numpy()
        if arr.ndim == 3:
            last = slice(None) if n_alleles is None else slice(0, n_alleles)
            block = arr.get_orthogonal_selection((rows, slice(None), last))
        else:
            block = arr.get_orthogonal_selection((rows, slice(None)))
        out.append(np.asarray(block))
        order.append(part["_row"].to_numpy())

    stacked = np.concatenate(out, axis=0)
    result = np.empty_like(stacked)
    result[np.concatenate(order)] = stacked
    return result


# ---------------------------------------------------------------------------
# Ploidy
# ---------------------------------------------------------------------------

def _count_mixed(g: np.ndarray, block: int = 100_000) -> int:
    n = 0
    for start in range(0, g.shape[0], block):
        b = g[start:start + block]
        n += int(((b[:, :, 0] != b[:, :, 1]) & (b[:, :, 0] >= 0) & (b[:, :, 1] >= 0)).sum())
    return n


def isolate_allele_counts(gt, subpops: dict, max_allele: int = 1) -> dict:
    """Allele counts per population with one allele per isolate.

    Blood-stage P. falciparum is haploid, but Pf8 records calls as diploid:
    0/0 or 1/1 for a clonal call, 0/1 for a mixed infection. Once Step 4a has
    resolved the mixed calls both copies agree, and the first copy is the
    isolate's allele. Counting both copies would double every sample size that
    FST, TreeMix and BayPass rely on. If mixed calls remain (--het-policy keep)
    the diploid count is returned instead, with a warning.
    """
    g = np.asarray(gt)
    if g.ndim == 3 and g.shape[2] > 1:
        mixed = _count_mixed(g)
        if mixed:
            raise ValueError(f"{mixed:,} mixed calls remain. Resolve or mask them before "
                             "haploid population analyses; diploid fallback is invalid.")
        partial = (g >= 0).any(axis=2) & ~(g >= 0).all(axis=2)
        if partial.any():
            raise ValueError("Partially missing diploid encodings must be fully masked.")
        g = g[:, :, 0]
    hap = allel.HaplotypeArray(np.ascontiguousarray(g))
    return {k: hap.count_alleles(max_allele=max_allele, subpop=idx)
            for k, idx in subpops.items()}


def summarise(root: zarr.Group) -> None:
    """One-line-per-contig report, printed before the expensive work starts."""
    groups = chrom_groups(root)
    ids = samples(root)
    total = 0
    print(f"\nCallset: {len(groups)} contigs x {len(ids):,} samples")
    for g in groups:
        n = root[g]["variants/POS"].shape[0]
        total += n
        extras = [f for f in ("AD", "DP", "GQ") if f"calldata/{f}" in root[g]]
        print(f"  {g:<16} {n:>10,} variants   {'+'.join(extras) if extras else 'GT only'}")
    print(f"  {'TOTAL':<16} {total:>10,} variants")
