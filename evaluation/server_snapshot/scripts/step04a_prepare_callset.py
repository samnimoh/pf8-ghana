#!/usr/bin/env python3
"""
STEP 4a — Build the filtered genotype matrix that Steps 4b, 5, 7 and 8 all assume.

The workflow document introduces `gt` at Step 4 without ever constructing it.
This script closes that gap: VCF to Zarr, variant and sample filtering, sample
reordering to match the Step 2 table, and a compact .npz that every downstream
step reads instead of touching the VCF again.

Input is the per-chromosome Ghana subset in data/ — one VCF per contig,
Pf8_Ghana_PF3D7_01_v3.vcf.gz through _14_v3. callset_io handles finding and
converting them; nothing here needs a merged VCF.

Memory is the reason conversion and filtering both proceed contig by contig.
Fourteen chromosomes of genotypes at once would be gigabytes; one at a time is
comfortable even on a shared server.

Usage:
    python step04a_prepare_callset.py
    python step04a_prepare_callset.py --force-zarr        # rebuild the Zarr store
    python step04a_prepare_callset.py --het-policy missing  # mask mixed calls instead
    python step04a_prepare_callset.py --max-missing 0.05 --min-maf 0.02
    python step04a_prepare_callset.py --vcf 'Pf8_Ghana_PF3D7_0[1-4]_v3.vcf.gz'
"""

from __future__ import annotations

import argparse

import allel
import numpy as np
import pandas as pd

import callset_io as cio
import config as C


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--vcf", default=None,
                   help="Single VCF, or a glob. Defaults to config.GHANA_VCF_GLOB.")
    p.add_argument("--force-zarr", action="store_true")
    p.add_argument("--min-maf", type=float, default=C.MIN_MAF)
    p.add_argument("--max-missing", type=float, default=C.MAX_MISSING)
    p.add_argument("--max-sample-missing", type=float, default=C.MAX_SAMPLE_MISSING)
    p.add_argument("--het-policy", choices=["major", "missing", "keep"], default="major",
                   help="Mixed (0/1) calls from polyclonal infections: 'major' keeps the "
                        "allele with more reads (ties become missing), 'missing' masks "
                        "them, 'keep' leaves them for diploid counting.")
    p.add_argument("--het-to-missing", action="store_true",
                   help="Same as --het-policy missing (kept for older commands).")
    p.add_argument("--ignore-sample-qc", action="store_true",
                   help="Use the Step 2 table even if Step 3b produced a QC table.")
    p.add_argument("--min-dp", type=int, default=C.MIN_GENOTYPE_DP,
                   help="Mask genotypes below this read depth. 0 disables.")
    p.add_argument("--min-gq", type=int, default=C.MIN_GENOTYPE_GQ,
                   help="Mask genotypes below this quality. 0 disables.")
    p.add_argument("--keep-subtelomeric", action="store_true",
                   help="Skip the core-region BED filter even if the BED exists.")
    return p.parse_args()


def load_core_regions() -> dict[str, np.ndarray] | None:
    if not C.CORE_GENOME_BED.exists():
        return None
    bed = pd.read_csv(C.CORE_GENOME_BED, sep="\t", header=None,
                      names=["chrom", "start", "end"], comment="#")
    return {c: g[["start", "end"]].to_numpy() for c, g in bed.groupby("chrom")}


def in_core(chrom: np.ndarray, pos: np.ndarray, regions: dict) -> np.ndarray:
    keep = np.zeros(len(pos), dtype=bool)
    for c, iv in regions.items():
        m = chrom == c
        if not m.any():
            continue
        p = pos[m]
        hit = np.zeros(len(p), dtype=bool)
        for start, end in iv:
            hit |= (p > start) & (p <= end)  # BED is 0-based half-open
        keep[m] = hit
    return keep


def resolve_mixed_calls(gt: allel.GenotypeArray, root, selection: pd.DataFrame,
                        cols: np.ndarray, block: int = 20_000) -> None:
    """Replace each mixed (0/1) call with the allele that has more reads.

    Ties, including calls with no usable read depth, become missing. AD is read
    only for SNPs where some kept sample has a mixed call, a block at a time, so
    this adds little to the memory the genotype matrix already takes. `gt` is
    modified in place; its rows follow `selection` and its columns `cols`.
    """
    if not cio.has_field(root, "calldata/AD"):
        raise RuntimeError("--het-policy major needs calldata/AD in the store. "
                           "Use --het-policy missing instead.")
    g = gt.values
    n_mixed = n_ref = n_alt = n_tie = 0
    for start in range(0, g.shape[0], block):
        blk = g[start:start + block]                 # a view: edits land in gt
        mixed = ((blk[:, :, 0] != blk[:, :, 1])
                 & (blk[:, :, 0] >= 0) & (blk[:, :, 1] >= 0))
        rows = np.flatnonzero(mixed.any(axis=1))
        if rows.size:
            ad = cio.take_calldata(root, selection.iloc[start + rows],
                                   "calldata/AD", n_alleles=2)[:, cols]
            ad = np.where(ad < 0, 0, ad)
            m = mixed[rows]
            to_ref = m & (ad[:, :, 0] > ad[:, :, 1])
            to_alt = m & (ad[:, :, 1] > ad[:, :, 0])
            tie = m & (ad[:, :, 0] == ad[:, :, 1])
            sub = blk[rows]
            sub[to_ref] = 0
            sub[to_alt] = 1
            sub[tie] = -1
            blk[rows] = sub
            n_mixed += int(m.sum())
            n_ref += int(to_ref.sum())
            n_alt += int(to_alt.sum())
            n_tie += int(tie.sum())
        print(f"  {min(start + block, g.shape[0]):,}/{g.shape[0]:,} SNPs",
              end="\r", flush=True)
    print()
    print(f"Mixed calls resolved by read depth: {n_mixed:,}")
    print(f"  -> REF (more REF reads)  {n_ref:>12,}")
    print(f"  -> ALT (more ALT reads)  {n_alt:>12,}")
    print(f"  -> missing (tied)        {n_tie:>12,}")


def main() -> None:
    args = parse_args()
    if args.het_to_missing:
        args.het_policy = "missing"
    C.banner("STEP 4a — prepare the core-genome genotype matrix")

    if C.SAMPLES_QC_CSV.exists() and not args.ignore_sample_qc:
        meta = pd.read_csv(C.SAMPLES_QC_CSV)
        print(f"Using QC-passing samples from {C.SAMPLES_QC_CSV.name} "
              f"({len(meta):,} samples)")
    else:
        C.require(C.SAMPLES_AEZ_CSV, "Run step02_assign_aez.py first.")
        meta = pd.read_csv(C.SAMPLES_AEZ_CSV)
        if not args.ignore_sample_qc:
            print("No Step 3b QC table found — using the unfiltered Step 2 table.")
            print("Polyclonal and clonally redundant isolates are still in. For")
            print("ADMIXTURE in particular, run step03b_sample_qc.py first.")

    root = cio.open_callset(args.vcf, force=args.force_zarr, want_ad=False)
    cio.summarise(root)

    vcf_samples = cio.samples(root)
    variants = cio.variant_table(root)
    print(f"\nCallset: {len(variants):,} variants x {len(vcf_samples):,} samples")

    # ---- variant-level filters that need no genotypes ---------------------
    # These run on the small 1-D arrays gathered across every contig, so the
    # whole genome is screened before a single genotype is fetched.
    C.banner("Variant filtering")
    mask = np.ones(len(variants), dtype=bool)

    def report(name: str, m: np.ndarray) -> None:
        print(f"  {name:<28} {int(m.sum()):>10,} retained")

    mask &= variants["filter_pass"].to_numpy()
    report("FILTER=PASS", mask)

    mask &= variants["is_snp"].to_numpy()
    report("SNP only", mask)

    mask &= variants["numalt"].to_numpy() == 1
    report("biallelic", mask)

    chrom_all = variants["chrom"].to_numpy()
    pos_all = variants["pos"].to_numpy()

    regions = None if args.keep_subtelomeric else load_core_regions()
    if regions is not None:
        mask &= in_core(chrom_all, pos_all, regions)
        report("core genome (BED)", mask)
    elif not args.keep_subtelomeric:
        print("  No core-region BED found in data/ — subtelomeric var/rifin")
        print("  regions are NOT excluded. Genotyping there is unreliable and")
        print("  will dominate Step 8's outlier list. Supply pf_core_regions.bed.")

    selection = variants[mask].reset_index(drop=True)
    if selection.empty:
        raise RuntimeError("No variants survived filtering. Loosen the filters.")

    print("\nSurviving variants per contig:")
    print(selection["chrom"].value_counts().sort_index().to_string())

    # ---- pull only the surviving rows into memory -------------------------
    print(f"\nLoading {len(selection):,} variants into memory (contig by contig)...")
    gt = allel.GenotypeArray(cio.take_calldata(root, selection, "calldata/GT"))
    chrom = selection["chrom"].to_numpy()
    pos = selection["pos"].to_numpy()
    ref = selection["ref"].to_numpy()
    alt = selection["alt"].to_numpy()
    print(f"In-memory genotype array: {gt.shape}, {gt.nbytes / 1e6:.0f} MB")

    # ---- genotype-level masking ------------------------------------------
    # Ordering is deliberate: a low-confidence call becomes missing here, so the
    # missingness filter below sees it for what it is rather than counting it as
    # a confident call.
    if args.min_dp > 0 or args.min_gq > 0:
        C.banner("Genotype-level masking")
        before = int(gt.count_called())
        low = np.zeros((gt.n_variants, gt.n_samples), dtype=bool)

        if args.min_dp > 0 and cio.has_field(root, "calldata/DP"):
            dp = cio.take_calldata(root, selection, "calldata/DP")
            low |= dp < args.min_dp
            print(f"  DP < {args.min_dp}: {int((dp < args.min_dp).sum()):,} calls")
            del dp
        elif args.min_dp > 0:
            print("  No calldata/DP in the store — depth masking skipped.")

        if args.min_gq > 0 and cio.has_field(root, "calldata/GQ"):
            gq = cio.take_calldata(root, selection, "calldata/GQ")
            low |= gq < args.min_gq
            print(f"  GQ < {args.min_gq}: {int((gq < args.min_gq).sum()):,} calls")
            del gq
        elif args.min_gq > 0:
            print("  No calldata/GQ in the store — quality masking skipped.")

        if low.any():
            gt[low] = -1
            after = int(gt.count_called())
            print(f"  Called genotypes: {before:,} -> {after:,} "
                  f"({(before - after) / max(before, 1):.2%} masked)")

    # ---- align samples ----------------------------------------------------
    C.banner("Sample alignment")
    if C.COL_SAMPLE not in meta.columns:
        raise KeyError(f"'{C.COL_SAMPLE}' missing from {C.SAMPLES_AEZ_CSV}")

    meta_ids = meta[C.COL_SAMPLE].astype(str).to_numpy()
    pos_in_vcf = {s: i for i, s in enumerate(vcf_samples)}
    in_both = np.array([s in pos_in_vcf for s in meta_ids])

    if not in_both.all():
        missing = meta_ids[~in_both]
        print(f"{len(missing)} samples in the metadata are absent from the VCF, "
              f"e.g. {list(missing[:5])}")
    meta = meta.loc[in_both].reset_index(drop=True)
    col_order = np.array([pos_in_vcf[s] for s in meta[C.COL_SAMPLE].astype(str)])
    gt = gt.take(col_order, axis=1)
    print(f"Genotype columns reordered to match the metadata: {gt.shape[1]} samples")

    # ---- polyclonality ----------------------------------------------------
    # After alignment, so read depths are fetched only for the samples kept.
    if gt.ploidy > 1:
        C.banner("Mixed calls")
        het_rate = float(gt.is_het().sum()) / max(gt.count_called(), 1)
        print(f"Heterozygous call rate: {het_rate:.4f}")
        print("P. falciparum is haploid in the human host; heterozygous calls")
        print("indicate polyclonal infection, not true heterozygosity.")
        if not (C.SAMPLES_QC_CSV.exists() and not args.ignore_sample_qc):
            print("No Fws filtering has been applied. For ADMIXTURE this is the single")
            print("most consequential omission in the pipeline — run step03b_sample_qc.py.")
        if args.het_policy == "major":
            resolve_mixed_calls(gt, root, selection, col_order)
        elif args.het_policy == "missing":
            gt[gt.is_het()] = -1
            print("--het-policy missing: mixed calls masked.")
        else:
            print("--het-policy keep: mixed calls left in, so Step 4b will count both")
            print("gene copies per isolate rather than one.")

    # ---- missingness and MAF ---------------------------------------------
    C.banner("Missingness and MAF")
    var_missing = 1.0 - (gt.count_called(axis=1) / gt.n_samples)
    keep_var = var_missing <= args.max_missing
    print(f"  variant missingness <= {args.max_missing}: {int(keep_var.sum()):,}")

    gt = gt.compress(keep_var, axis=0)
    chrom, pos, ref, alt = chrom[keep_var], pos[keep_var], ref[keep_var], alt[keep_var]

    smp_missing = 1.0 - (gt.count_called(axis=0) / gt.n_variants)
    keep_smp = smp_missing <= args.max_sample_missing
    if not keep_smp.all():
        dropped = meta.loc[~keep_smp, C.COL_SAMPLE].tolist()
        print(f"  dropping {len(dropped)} high-missingness samples: {dropped[:8]}")
        gt = gt.compress(keep_smp, axis=1)
        meta = meta.loc[keep_smp].reset_index(drop=True)

    ac = gt.count_alleles(max_allele=1)
    maf = ac.to_frequencies()[:, 1:].max(axis=1)
    maf = np.minimum(maf, 1 - maf)
    keep_maf = maf >= args.min_maf
    print(f"  MAF >= {args.min_maf}: {int(keep_maf.sum()):,}")

    gt = gt.compress(keep_maf, axis=0)
    chrom, pos, ref, alt = chrom[keep_maf], pos[keep_maf], ref[keep_maf], alt[keep_maf]

    # ---- save -------------------------------------------------------------
    C.banner("Output")
    print(f"Final matrix: {gt.n_variants:,} SNPs x {gt.n_samples:,} samples")
    print("\nSNPs per chromosome:")
    print(pd.Series(chrom).value_counts().sort_index().to_string())
    print("\nSamples per zone:")
    print(meta["zone"].value_counts(dropna=False).to_string())

    np.savez_compressed(
        C.CALLSET_NPZ,
        gt=np.asarray(gt, dtype=np.int8),
        chrom=chrom.astype("U32"),
        pos=pos.astype(np.int64),
        ref=ref.astype("U1"),
        alt=alt.astype("U1"),
        samples=meta[C.COL_SAMPLE].astype(str).to_numpy(),
    )
    print(f"\nGenotypes -> {C.CALLSET_NPZ}")

    meta.to_csv(C.ANALYSIS_SAMPLES_CSV, index=False)
    print(f"Canonical sample table -> {C.ANALYSIS_SAMPLES_CSV}")
    print("Every step from here reads that table, so sample order is fixed once.")


if __name__ == "__main__":
    main()
