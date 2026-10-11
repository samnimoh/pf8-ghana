#!/usr/bin/env python3
"""
STEP 5a — Export the filtered genotype matrix to PLINK transposed text format.

Going straight from the .npz rather than back to the VCF keeps one filtering
decision in one place. Whatever survived Step 4a is exactly what ADMIXTURE sees,
which is worth more than the few minutes a direct VCF conversion would save.

TFAM uses the zone as family ID. ADMIXTURE ignores it, but it makes the Q-matrix
merge in Step 5c trivial and keeps the PLINK files self-documenting.

Usage:
    python step05a_export_plink.py
    python step05a_export_plink.py --pseudo-diploid   # for haploid-coded input
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

import config as C


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out-prefix", default=str(C.PLINK_PREFIX))
    p.add_argument("--pseudo-diploid", action="store_true",
                   help="Duplicate the single allele if the input is haploid-coded.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    C.banner("STEP 5a — genotypes -> PLINK .tped/.tfam")

    C.require(C.CALLSET_NPZ, "Run step04a_prepare_callset.py first.")
    data = np.load(C.CALLSET_NPZ, allow_pickle=False)
    meta = pd.read_csv(C.ANALYSIS_SAMPLES_CSV)
    C.validate_sample_alignment(data, meta)

    gt = data["gt"]                       # (n_variants, n_samples, ploidy)
    chrom = data["chrom"].astype(str)
    pos = data["pos"]
    ref = data["ref"].astype(str)
    alt = data["alt"].astype(str)

    if gt.ndim == 2 or (args.pseudo_diploid and gt.shape[2] == 1):
        gt = gt.reshape(gt.shape[0], gt.shape[1], 1)
        gt = np.repeat(gt, 2, axis=2)
        print("Haploid calls duplicated to a pseudo-diploid encoding.")

    n_var, n_smp, ploidy = gt.shape
    print(f"{n_var:,} SNPs x {n_smp:,} samples, ploidy {ploidy}")

    # ADMIXTURE rejects non-integer chromosome codes, so contigs become 1..k in
    # genome order; the SNP IDs keep the real contig names, and a mapping file
    # records the translation.
    contigs = list(dict.fromkeys(chrom))
    code = {c: i + 1 for i, c in enumerate(contigs)}
    map_path = f"{args.out_prefix}_chrom_codes.tsv"
    with open(map_path, "w") as fh:
        fh.write("code\tcontig\n")
        fh.writelines(f"{code[c]}\t{c}\n" for c in contigs)
    print(f"Chromosome codes 1..{len(contigs)} -> {map_path}")

    tfam_path = f"{args.out_prefix}.tfam"
    tped_path = f"{args.out_prefix}.tped"

    # ---- TFAM -------------------------------------------------------------
    with open(tfam_path, "w") as fh:
        for _, row in meta.iterrows():
            fid = C.slugify_zone(row.get("zone", "NA"))
            iid = row[C.COL_SAMPLE]
            fh.write(f"{fid} {iid} 0 0 0 -9\n")
    print(f"TFAM -> {tfam_path}")

    # ---- TPED -------------------------------------------------------------
    # Allele code 0 is PLINK's missing marker; ref/alt letters keep the files
    # readable when something needs debugging by eye.
    print("Writing TPED (this is the slow part)...")
    chunk = 20_000
    with open(tped_path, "w") as fh:
        for start in range(0, n_var, chunk):
            stop = min(start + chunk, n_var)
            lines = []
            for i in range(start, stop):
                lut = np.array(["0", ref[i], alt[i]], dtype="<U1")
                alleles = lut[np.clip(gt[i] + 1, 0, 2)]      # -1 -> 0 -> "0"
                snp_id = f"{chrom[i]}:{pos[i]}"
                lines.append(
                    f"{code[chrom[i]]} {snp_id} 0 {pos[i]} "
                    + " ".join(" ".join(pair) for pair in alleles)
                )
            fh.write("\n".join(lines) + "\n")
            print(f"  {stop:,}/{n_var:,}", end="\r", flush=True)
    print(f"\nTPED -> {tped_path}")

    from pathlib import Path
    size_mb = Path(tped_path).stat().st_size / 1e6
    print(f"TPED size: {size_mb:.0f} MB — PLINK converts it to .bed next, "
          f"after which the text version can be deleted.")

    print("\nNext: bash step05b_admixture.sh")


if __name__ == "__main__":
    main()
