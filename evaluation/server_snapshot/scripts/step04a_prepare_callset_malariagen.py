#!/usr/bin/env python3
"""
STEP 4a (alternative) — Build the genotype matrix from Google Cloud via the
malariagen_data package, with no VCF download.

Drop-in replacement for step04a_prepare_callset.py. Same outputs, same names, so
everything from Step 4b onward is unchanged.

Three things this buys you beyond skipping the download. Region type comes with
the callset, so `variant_RegionType == "Core"` replaces the core-genome BED the
VCF route needs you to supply separately. Fws can be computed from `call_AD` in
the same network pass, which is by far the most expensive part, so you are not
paying for it twice. And `pf8.genome_features()` gives the 3D7 annotation
directly, removing the PlasmoDB download at Step 9.

Prerequisites:
    pip install malariagen_data
    # GCS access requires registration; see
    # https://malariagen.github.io/parasite-data/cloud_data_access/parasite-cloud-data-access.html

Because of the cost of that network pass, sample QC runs against the result
rather than before it. The sequence is:

    python step04a_prepare_callset_malariagen.py          # network pass
    python step03b_sample_qc.py --from-npz \
           --fws-from interim/pf8_fws.csv                 # local
    python step04a_prepare_callset_malariagen.py --refilter   # local, no network

--refilter subsets the cached .npz against the QC table without touching GCS.

Usage:
    python step04a_prepare_callset_malariagen.py
    python step04a_prepare_callset_malariagen.py --snp-only
    python step04a_prepare_callset_malariagen.py --no-fws --block 100000
    python step04a_prepare_callset_malariagen.py --dump-genome-features
    python step04a_prepare_callset_malariagen.py --refilter
"""

from __future__ import annotations

import argparse

import allel
import numpy as np
import pandas as pd

import config as C

SNP_ONLY_URL = "https://pf8-release.cog.sanger.ac.uk/snp-only"
FWS_CSV = C.INTERIM_DIR / "pf8_fws.csv"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--snp-only", action="store_true",
                   help="Use the SNP-only callset (10.8M SNPs, indels removed).")
    p.add_argument("--region-type", default="Core",
                   help="variant_RegionType to keep. 'any' disables the filter.")
    p.add_argument("--cds-only", action="store_true",
                   help="Restrict to coding variants (variant_CDS).")
    p.add_argument("--block", type=int, default=50_000,
                   help="Variants fetched per network round trip.")

    p.add_argument("--min-maf", type=float, default=C.MIN_MAF)
    p.add_argument("--max-missing", type=float, default=C.MAX_MISSING)
    p.add_argument("--max-sample-missing", type=float, default=C.MAX_SAMPLE_MISSING)
    p.add_argument("--min-dp", type=int, default=C.MIN_GENOTYPE_DP)
    p.add_argument("--min-gq", type=int, default=C.MIN_GENOTYPE_GQ)
    p.add_argument("--het-to-missing", action="store_true")

    p.add_argument("--no-fws", action="store_true",
                   help="Skip the Fws pass (saves fetching call_AD).")
    p.add_argument("--min-ad-depth", type=int, default=5)

    p.add_argument("--dump-genome-features", action="store_true",
                   help="Write the 3D7 annotation as GFF to data/, for Step 9.")
    p.add_argument("--refilter", action="store_true",
                   help="Local only: subset the cached .npz against the Step 3b "
                        "QC table. No network access.")
    return p.parse_args()


# ---------------------------------------------------------------------------

def refilter() -> None:
    """Apply the Step 3b QC table to an already-downloaded matrix."""
    C.banner("STEP 4a (--refilter) — applying sample QC locally")

    data = np.load(C.require(C.CALLSET_NPZ,
                             "Run this script without --refilter first."),
                   allow_pickle=False)
    qc = pd.read_csv(C.require(C.SAMPLES_QC_CSV, "Run step03b_sample_qc.py first."))

    gt = allel.GenotypeArray(data["gt"])
    samples = data["samples"].astype(str)
    keep_ids = set(qc[C.COL_SAMPLE].astype(str))
    keep = np.array([s in keep_ids for s in samples])
    print(f"Samples: {len(samples):,} -> {int(keep.sum()):,} after QC")

    gt = gt.compress(keep, axis=1)
    meta = qc.set_index(qc[C.COL_SAMPLE].astype(str)).reindex(samples[keep]).reset_index(drop=True)

    chrom, pos = data["chrom"].astype(str), data["pos"]
    ref, alt = data["ref"].astype(str), data["alt"].astype(str)

    # Dropping samples changes which variants clear MAF and missingness.
    var_missing = 1.0 - (gt.count_called(axis=1) / gt.n_samples)
    keep_var = var_missing <= C.MAX_MISSING
    ac = gt.compress(keep_var, axis=0).count_alleles(max_allele=1)
    maf = ac.to_frequencies()[:, 1]
    maf = np.minimum(maf, 1 - maf)
    keep_maf = maf >= C.MIN_MAF

    sub = np.flatnonzero(keep_var)[keep_maf]
    gt = gt.take(sub, axis=0)
    chrom, pos, ref, alt = chrom[sub], pos[sub], ref[sub], alt[sub]
    print(f"SNPs: {len(data['pos']):,} -> {gt.n_variants:,} after re-filtering")

    write_outputs(gt, chrom, pos, ref, alt, meta)


def write_outputs(gt, chrom, pos, ref, alt, meta: pd.DataFrame) -> None:
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


# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    if args.refilter:
        refilter()
        return

    C.banner("STEP 4a (malariagen_data) — callset from Google Cloud")

    try:
        import malariagen_data
    except ImportError:
        raise SystemExit("pip install malariagen_data")

    pf8 = malariagen_data.Pf8(SNP_ONLY_URL) if args.snp_only else malariagen_data.Pf8()
    print("Callset:", "SNP-only (10,821,552 SNPs)" if args.snp_only
          else "full (12,493,205 positions)")

    if args.dump_genome_features:
        C.banner("Genome features")
        gf = pf8.genome_features()
        out = C.DATA_DIR / "pf8_genome_features.gff"
        cols = ["contig", "source", "type", "start", "end",
                "score", "strand", "phase"]
        attrs = gf.apply(lambda r: ";".join(
            f"{k}={r[k]}" for k in ("ID", "Parent", "Name") if pd.notna(r.get(k))
        ), axis=1)
        gf.assign(attributes=attrs)[cols + ["attributes"]].to_csv(
            out, sep="\t", header=False, index=False, na_rep=".")
        print(f"{len(gf):,} features -> {out}")
        print(f"Point PLASMODB_GFF in config.py at it to skip the download.")

    # ---- sample selection -------------------------------------------------
    C.banner("Sample selection")
    meta_source = C.SAMPLES_QC_CSV if C.SAMPLES_QC_CSV.exists() else C.SAMPLES_AEZ_CSV
    meta = pd.read_csv(C.require(meta_source, "Run step02_assign_aez.py first."))
    print(f"Target samples from {meta_source.name}: {len(meta):,}")

    pf8_meta = pf8.sample_metadata()
    print(f"Pf8 metadata: {len(pf8_meta):,} samples")

    wanted = set(meta[C.COL_SAMPLE].astype(str))
    sample_mask = pf8_meta["Sample"].astype(str).isin(wanted).to_numpy()
    print(f"Matched in the callset: {int(sample_mask.sum()):,}")
    if sample_mask.sum() < len(meta):
        missing = wanted - set(pf8_meta.loc[sample_mask, "Sample"].astype(str))
        print(f"  absent from Pf8: {len(missing)}, e.g. {list(missing)[:5]}")

    # Genotype columns follow sample-metadata row order, so the mask defines
    # the column order of everything fetched below.
    ordered_ids = pf8_meta.loc[sample_mask, "Sample"].astype(str).to_numpy()
    meta = (meta.set_index(meta[C.COL_SAMPLE].astype(str))
                .reindex(ordered_ids).reset_index(drop=True))

    need_extended = (args.region_type.lower() != "any"
                     or args.min_dp > 0 or args.min_gq > 0)
    ds = pf8.variant_calls(extended=need_extended)
    ds = ds.isel(samples=sample_mask)
    print(f"Dataset: {ds.sizes['variants']:,} variants x {ds.sizes['samples']:,} samples")

    # ---- variant filtering on the small 1-D arrays ------------------------
    C.banner("Variant filtering")
    var_mask = ds["variant_filter_pass"].data.compute().astype(bool)
    print(f"  {'FILTER=PASS':<28} {int(var_mask.sum()):>10,}")

    var_mask &= ds["variant_is_snp"].data.compute().astype(bool)
    print(f"  {'SNP only':<28} {int(var_mask.sum()):>10,}")

    var_mask &= ds["variant_numalt"].data.compute() == 1
    print(f"  {'biallelic':<28} {int(var_mask.sum()):>10,}")

    if args.region_type.lower() != "any":
        if "variant_RegionType" in ds:
            rt = ds["variant_RegionType"].data.compute().astype(str)
            print(f"\n  Region types present: {sorted(set(rt))}")
            var_mask &= rt == args.region_type
            print(f"  {'RegionType == ' + args.region_type:<28} "
                  f"{int(var_mask.sum()):>10,}")
            print("  This replaces the core-genome BED the VCF route needs.")
        else:
            print("  variant_RegionType unavailable — region filter skipped.")

    if args.cds_only and "variant_CDS" in ds:
        var_mask &= ds["variant_CDS"].data.compute().astype(bool)
        print(f"  {'coding only':<28} {int(var_mask.sum()):>10,}")

    idx = np.flatnonzero(var_mask)
    if idx.size == 0:
        raise RuntimeError("No variants survived filtering.")

    alleles = ds["variant_allele"].isel(variants=idx, alleles=slice(0, 2))
    alleles = alleles.data.compute().astype(str)
    ref, alt = alleles[:, 0], alleles[:, 1]
    chrom = ds["variant_chrom"].isel(variants=idx).data.compute().astype(str)
    pos = ds["variant_position"].isel(variants=idx).data.compute()

    # ---- the expensive pass ----------------------------------------------
    C.banner(f"Fetching {idx.size:,} variants in blocks of {args.block:,}")
    print("This is the network-bound step. Run it once; everything downstream")
    print("reads the cached .npz. Expect a few GB over the wire.\n")

    n_smp = int(sample_mask.sum())
    want_fws = not args.no_fws and "call_AD" in ds
    gt_blocks = []
    sum_hw = np.zeros(n_smp)
    sum_hs = np.zeros(n_smp)

    for start in range(0, idx.size, args.block):
        sel = idx[start:start + args.block]
        sub = ds.isel(variants=sel)

        g = sub["call_genotype"].data.compute()

        if args.min_dp > 0 or args.min_gq > 0:
            low = np.zeros(g.shape[:2], dtype=bool)
            if args.min_dp > 0 and "call_DP" in sub:
                low |= sub["call_DP"].data.compute() < args.min_dp
            if args.min_gq > 0 and "call_GQ" in sub:
                low |= sub["call_GQ"].data.compute() < args.min_gq
            g[low] = -1

        gt_blocks.append(g.astype(np.int8))

        if want_fws:
            ad = sub["call_AD"].isel(alleles=slice(0, 2)).data.compute()
            ad = np.asarray(ad, dtype=np.float64)
            ad[ad < 0] = 0.0
            depth = ad.sum(axis=2)
            ok = depth >= args.min_ad_depth
            with np.errstate(invalid="ignore", divide="ignore"):
                q_w = np.where(ok, ad[:, :, 1] / np.maximum(depth, 1), np.nan)
            h_w = 2.0 * q_w * (1.0 - q_w)
            alt_pool = np.where(ok, ad[:, :, 1], 0).sum(axis=1)
            tot_pool = np.where(ok, depth, 0).sum(axis=1)
            q_s = np.where(tot_pool > 0, alt_pool / np.maximum(tot_pool, 1), np.nan)
            h_s = 2.0 * q_s * (1.0 - q_s)
            sum_hw += np.nansum(np.where(ok, h_w, 0.0), axis=0)
            sum_hs += np.nansum(np.where(ok, h_s[:, None], 0.0), axis=0)

        done = min(start + args.block, idx.size)
        print(f"  {done:,}/{idx.size:,} variants", end="\r", flush=True)
    print()

    gt = allel.GenotypeArray(np.concatenate(gt_blocks, axis=0))
    del gt_blocks
    print(f"In-memory genotype array: {gt.shape}, {gt.nbytes / 1e6:.0f} MB")

    # ---- Fws for Step 3b --------------------------------------------------
    if want_fws:
        with np.errstate(invalid="ignore", divide="ignore"):
            fws = 1.0 - np.divide(sum_hw, np.where(sum_hs > 0, sum_hs, np.nan))
        fws = np.clip(fws, 0.0, 1.0)
        pd.DataFrame({"Sample": ordered_ids, "Fws": fws}).to_csv(FWS_CSV, index=False)
        print(f"\nFws -> {FWS_CSV}")
        print(f"  median {np.nanmedian(fws):.3f}; "
              f"{int((fws >= C.MIN_FWS).sum()):,}/{len(fws):,} monoclonal "
              f"at Fws >= {C.MIN_FWS}")

    # ---- polyclonality ----------------------------------------------------
    if gt.ploidy > 1:
        het_rate = float(gt.is_het().sum()) / max(gt.count_called(), 1)
        print(f"\nHeterozygous call rate: {het_rate:.4f}")
        if args.het_to_missing:
            gt[gt.is_het()] = -1
            print("--het-to-missing applied.")

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
        print(f"  dropping {int((~keep_smp).sum())} high-missingness samples")
        gt = gt.compress(keep_smp, axis=1)
        meta = meta.loc[keep_smp].reset_index(drop=True)

    ac = gt.count_alleles(max_allele=1)
    maf = ac.to_frequencies()[:, 1]
    maf = np.minimum(maf, 1 - maf)
    keep_maf = maf >= args.min_maf
    print(f"  MAF >= {args.min_maf}: {int(keep_maf.sum()):,}")
    gt = gt.compress(keep_maf, axis=0)
    chrom, pos, ref, alt = chrom[keep_maf], pos[keep_maf], ref[keep_maf], alt[keep_maf]

    write_outputs(gt, chrom, pos, ref, alt, meta)

    if want_fws and not C.SAMPLES_QC_CSV.exists():
        print("\nNext, now that Fws exists:")
        print(f"  python step03b_sample_qc.py --from-npz --fws-from {FWS_CSV}")
        print("  python step04a_prepare_callset_malariagen.py --refilter")


if __name__ == "__main__":
    main()
