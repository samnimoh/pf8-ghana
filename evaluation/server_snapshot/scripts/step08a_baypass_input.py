#!/usr/bin/env python3
"""
STEP 8a — Build the BayPass genotype file.

The workflow document invokes `g_baypass -gfile ghana_baypass.geno` without ever
constructing that file, so this step supplies it. Format: one row per SNP, two
whitespace-separated integers per population (reference count, alternate count),
populations in a fixed order that Step 8b's -npop must match.

A position table is written alongside, row-for-row aligned with the .geno file.
Step 9 depends on that alignment absolutely — BayPass output carries row indices
and nothing else, so if the two files fall out of step, every gene annotation
downstream is silently wrong.

Optionally emits a covariate file (--covariate) for the environmental
association model, built from per-zone values you supply as a two-column CSV.

Usage:
    python step08a_baypass_input.py
    python step08a_baypass_input.py --thin 5
    python step08a_baypass_input.py --covariate data/zone_rainfall.csv
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

import config as C


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--min-total", type=int, default=2)
    p.add_argument("--min-mac", type=int, default=2,
                   help="Minimum global minor allele count. Singletons are weakly "
                        "informative and mostly cost MCMC time.")
    p.add_argument("--thin", type=int, default=1,
                   help="Keep every Nth SNP. BayPass MCMC scales badly; 5–10 is common.")
    p.add_argument("--covariate", default=None,
                   help="CSV with columns zone,value — one row per population.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    C.banner("STEP 8a — BayPass input")

    C.BAYPASS_DIR.mkdir(parents=True, exist_ok=True)
    data = np.load(C.require(C.ALLELE_COUNTS_NPZ, "Run step04b_fst.py first."))

    zones = [str(z) for z in data["zones"]]
    slugs = [C.slugify_zone(z) for z in zones]
    chrom = data["chrom"].astype(str)
    pos = data["pos"]

    ac = np.stack([data[f"ac__{s}"] for s in slugs], axis=0)  # (n_pop, n_snp, 2)
    n_pop, n_snp, _ = ac.shape
    print(f"{n_pop} populations x {n_snp:,} SNPs")
    print("Population order (this fixes the column order in the .geno file):")
    for i, (z, s) in enumerate(zip(zones, slugs), start=1):
        print(f"  {i}. {z}  ->  {s}")

    # ---- filter ----------------------------------------------------------
    totals = ac.sum(axis=2)
    keep = (totals >= args.min_total).all(axis=0)
    print(f"\nSNPs with >= {args.min_total} alleles in every population: "
          f"{int(keep.sum()):,}")

    alt_tot = ac[:, :, 1].sum(axis=0)
    all_tot = totals.sum(axis=0)
    keep &= (alt_tot > 0) & (alt_tot < all_tot)
    print(f"After dropping globally fixed sites: {int(keep.sum()):,}")

    mac = np.minimum(alt_tot, all_tot - alt_tot)
    keep &= mac >= args.min_mac
    print(f"After minor allele count >= {args.min_mac}: {int(keep.sum()):,}")

    idx = np.flatnonzero(keep)
    if args.thin > 1:
        idx = idx[:: args.thin]
        print(f"Thinned 1-in-{args.thin}: {idx.size:,} SNPs retained")

    if idx.size == 0:
        raise RuntimeError("Nothing survived filtering.")
    if idx.size > 200_000:
        print(f"\n{idx.size:,} SNPs is a long MCMC run. Consider --thin.")

    # ---- write .geno ------------------------------------------------------
    # Interleave (ref, alt) per population: col order p1_ref p1_alt p2_ref ...
    block = ac[:, idx, :]                      # (n_pop, n_keep, 2)
    table = block.transpose(1, 0, 2).reshape(idx.size, n_pop * 2)
    np.savetxt(C.BAYPASS_GENO, table, fmt="%d", delimiter=" ")
    print(f"\nGenotype file -> {C.BAYPASS_GENO}  "
          f"({idx.size:,} rows x {n_pop * 2} columns)")

    # ---- aligned positions ------------------------------------------------
    positions = pd.DataFrame({
        "baypass_row": np.arange(idx.size, dtype=np.int64),
        "chrom": chrom[idx],
        "pos": pos[idx],
    })
    positions.to_csv(C.BAYPASS_POSITIONS, index=False)
    print(f"Position table -> {C.BAYPASS_POSITIONS}")
    assert len(positions) == idx.size, "Position table and .geno are out of step."

    # ---- population order, for the record ---------------------------------
    (C.BAYPASS_DIR / "population_order.txt").write_text("\n".join(slugs) + "\n")
    (C.BAYPASS_DIR / "npop.txt").write_text(f"{n_pop}\n")
    print(f"Population order -> {C.BAYPASS_DIR / 'population_order.txt'}")

    # ---- optional covariate ----------------------------------------------
    if args.covariate:
        cov = pd.read_csv(C.require(args.covariate))
        if not {"zone", "value"}.issubset(cov.columns):
            raise KeyError("Covariate CSV needs columns: zone,value")
        cov["slug"] = cov["zone"].map(C.slugify_zone)
        cov = cov.set_index("slug").reindex(slugs)
        if cov["value"].isna().any():
            raise ValueError(f"Missing covariate values for: "
                             f"{cov.index[cov['value'].isna()].tolist()}")
        # Standardised, one row per covariate, one column per population.
        vals = cov["value"].to_numpy(dtype=float)
        vals = (vals - vals.mean()) / vals.std(ddof=0)
        efile = C.BAYPASS_DIR / "ghana.efile"
        np.savetxt(efile, vals.reshape(1, -1), fmt="%.6f")
        print(f"\nCovariate file -> {efile}")
        print("Run the STD model in Step 8b with: EFILE=results/baypass/ghana.efile")

    print(f"\nNext: NPOP={n_pop} bash step08b_baypass.sh")


if __name__ == "__main__":
    main()
