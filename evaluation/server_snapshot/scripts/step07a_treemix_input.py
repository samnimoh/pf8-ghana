#!/usr/bin/env python3
"""
STEP 7a — Build the TreeMix input file from the zone allele counts cached at
Step 4b.

TreeMix wants a gzipped, space-delimited table: one header row of population
names, then one row per SNP with `ref,alt` counts per population. Population
labels cannot contain whitespace, so zone names are slugified — and the same
slug is reused for the root argument in Step 7b, which is where a mismatch would
otherwise surface as an unhelpful segfault.

SNPs monomorphic across every population contribute nothing and are dropped;
so are SNPs with zero total counts in any population, which TreeMix cannot use.

Usage:
    python step07a_treemix_input.py
    python step07a_treemix_input.py --min-total 4
"""

from __future__ import annotations

import argparse
import gzip

import numpy as np

import config as C


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--min-total", type=int, default=2,
                   help="Minimum called alleles per population per SNP.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    C.banner("STEP 7a — TreeMix input")

    data = np.load(C.require(C.ALLELE_COUNTS_NPZ, "Run step04b_fst.py first."))
    zones = [str(z) for z in data["zones"]]
    slugs = [C.slugify_zone(z) for z in zones]

    ac = np.stack([data[f"ac__{s}"] for s in slugs], axis=0)  # (n_pop, n_snp, 2)
    n_pop, n_snp, _ = ac.shape
    print(f"{n_pop} populations x {n_snp:,} SNPs")
    for z, s in zip(zones, slugs):
        print(f"  {z:<28} -> {s}")

    totals = ac.sum(axis=2)                       # (n_pop, n_snp)
    keep = (totals >= args.min_total).all(axis=0)
    print(f"\nSNPs with >= {args.min_total} alleles in every population: "
          f"{int(keep.sum()):,}")

    alt_freq = np.divide(ac[:, :, 1], np.maximum(totals, 1))
    polymorphic = ~(np.isclose(alt_freq, alt_freq[0], atol=0).all(axis=0)
                    & np.isin(alt_freq[0], [0.0, 1.0]))
    keep &= polymorphic
    print(f"After dropping globally monomorphic sites: {int(keep.sum()):,}")

    if keep.sum() < 1000:
        print("\nWARNING: very few informative SNPs. TreeMix standard errors")
        print("         will be unstable and the block size in Step 7b too large.")

    idx = np.flatnonzero(keep)
    print(f"\nWriting {C.TREEMIX_INPUT} ...")
    with gzip.open(C.TREEMIX_INPUT, "wt") as fh:
        fh.write(" ".join(slugs) + "\n")
        block = 50_000
        for start in range(0, idx.size, block):
            chunk = idx[start:start + block]
            rows = [
                " ".join(f"{ac[p, k, 0]},{ac[p, k, 1]}" for p in range(n_pop))
                for k in chunk
            ]
            fh.write("\n".join(rows) + "\n")
            print(f"  {min(start + block, idx.size):,}/{idx.size:,}",
                  end="\r", flush=True)

    size_mb = C.TREEMIX_INPUT.stat().st_size / 1e6
    print(f"\nWrote {idx.size:,} SNPs ({size_mb:.1f} MB gzipped)")

    root = C.TREEMIX_ROOT
    if root not in slugs:
        print(f"\nWARNING: configured root '{root}' is not among the population")
        print(f"         labels. Available: {slugs}")
        print("         Set TREEMIX_ROOT in config.py or pass -root explicitly.")
    else:
        print(f"Root population '{root}' present and usable.")

    print("\nNext: bash step07b_treemix.sh")


if __name__ == "__main__":
    main()
