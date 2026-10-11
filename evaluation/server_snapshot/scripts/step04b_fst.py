#!/usr/bin/env python3
"""
STEP 4b — Pairwise Hudson's FST between agro-ecological zone populations.

Two estimator choices are deliberate. Numerator and denominator are summed
across loci before dividing — the ratio of averages — which is the correct
genome-wide summary; averaging per-locus ratios inflates the estimate. And a
block jackknife supplies standard errors, because a point estimate of 0.012
with no uncertainty attached tells a reader almost nothing.

Allele counts per zone are cached here for Steps 7 and 8, which need exactly
the same quantities. They count one allele per isolate: P. falciparum is
haploid in the human host, and Step 4a has already resolved mixed calls.

Usage:
    python step04b_fst.py
    python step04b_fst.py --min-zone-n 20 --blen 2000
"""

from __future__ import annotations

import argparse
import itertools

import allel
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import callset_io as cio  # noqa: E402
import config as C  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--min-zone-n", type=int, default=10,
                   help="Zones with fewer isolates are excluded outright.")
    p.add_argument("--blen", type=int, default=2000,
                   help="SNPs per jackknife block.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    C.banner("STEP 4b — pairwise Hudson FST")

    C.require(C.CALLSET_NPZ, "Run step04a_prepare_callset.py first.")
    C.require(C.ANALYSIS_SAMPLES_CSV, "Run step04a_prepare_callset.py first.")

    data = np.load(C.CALLSET_NPZ, allow_pickle=False)
    gt = allel.GenotypeArray(data["gt"])
    meta = pd.read_csv(C.ANALYSIS_SAMPLES_CSV)

    if gt.n_samples != len(meta):
        raise ValueError(
            f"Genotype columns ({gt.n_samples}) and sample table ({len(meta)}) "
            f"disagree. Re-run step04a."
        )
    print(f"{gt.n_variants:,} SNPs x {gt.n_samples:,} samples")

    counts = meta["zone"].value_counts(dropna=True)
    zones = sorted(counts[counts >= args.min_zone_n].index.tolist())
    dropped = counts[counts < args.min_zone_n]
    if len(dropped):
        print(f"\nZones below n={args.min_zone_n}, excluded:")
        print(dropped.to_string())
    if len(zones) < 2:
        raise RuntimeError("Fewer than two usable zones. Lower --min-zone-n.")

    print(f"\nZones analysed ({len(zones)}):")
    for z in zones:
        print(f"  {z:<28} n = {counts[z]}")

    # ---- allele counts per zone ------------------------------------------
    idx = {z: np.flatnonzero((meta["zone"] == z).to_numpy()) for z in zones}
    ac = cio.isolate_allele_counts(gt, idx)

    np.savez_compressed(
        C.ALLELE_COUNTS_NPZ,
        zones=np.array(zones, dtype="U64"),
        chrom=data["chrom"],
        pos=data["pos"],
        **{f"ac__{C.slugify_zone(z)}": np.asarray(ac[z]) for z in zones},
    )
    print(f"\nAllele counts cached -> {C.ALLELE_COUNTS_NPZ}")

    C.ZONE_ORDER_TXT.write_text("\n".join(zones) + "\n")
    print(f"Zone ordering fixed -> {C.ZONE_ORDER_TXT}")

    # ---- pairwise FST -----------------------------------------------------
    C.banner("Pairwise estimates")
    n = len(zones)
    fst = np.zeros((n, n), dtype=float)
    rows = []

    blen = min(args.blen, max(10, gt.n_variants // 20))
    for i, j in itertools.combinations(range(n), 2):
        num, den = allel.hudson_fst(ac[zones[i]], ac[zones[j]])
        point = float(np.nansum(num) / np.nansum(den))

        try:
            _, se, _, _ = allel.average_hudson_fst(ac[zones[i]], ac[zones[j]], blen)
        except Exception:
            se = np.nan

        fst[i, j] = fst[j, i] = point
        rows.append({
            "zone_a": zones[i],
            "zone_b": zones[j],
            "n_a": int(counts[zones[i]]),
            "n_b": int(counts[zones[j]]),
            "fst": point,
            "jackknife_se": float(se),
            "ci95_low": point - 1.96 * se if np.isfinite(se) else np.nan,
            "ci95_high": point + 1.96 * se if np.isfinite(se) else np.nan,
        })
        se_txt = f"{se:.4f}" if np.isfinite(se) else "n/a"
        print(f"  {zones[i][:22]:<22} vs {zones[j][:22]:<22}  "
              f"Fst = {point: .4f}  (SE {se_txt})")

    pairs = pd.DataFrame(rows).sort_values("fst", ascending=False)
    pairs.to_csv(C.RESULTS_DIR / "fst_pairwise.csv", index=False)
    np.save(C.FST_NPY, fst)
    pd.DataFrame(fst, index=zones, columns=zones).to_csv(C.FST_CSV)

    # ---- heatmap ----------------------------------------------------------
    fig, ax = plt.subplots(figsize=(1.2 * n + 3, 1.0 * n + 2.5))
    im = ax.imshow(fst, cmap="viridis")
    ax.set_xticks(range(n), [z[:18] for z in zones], rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(n), [z[:18] for z in zones], fontsize=8)
    for i in range(n):
        for j in range(n):
            if i != j:
                ax.text(j, i, f"{fst[i, j]:.4f}", ha="center", va="center",
                        fontsize=7, color="white")
    fig.colorbar(im, ax=ax, label="Hudson's $F_{ST}$", fraction=0.046)
    ax.set_title("Pairwise differentiation between agro-ecological zones")
    out_png = C.FIG_DIR / "fst_heatmap.png"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)

    C.banner("Output")
    print(f"  {C.FST_NPY}")
    print(f"  {C.FST_CSV}")
    print(f"  {C.RESULTS_DIR / 'fst_pairwise.csv'}")
    print(f"  {out_png}")
    print(f"\nMaximum pairwise Fst: {fst.max():.4f}")
    print("Within-country Fst for P. falciparum sits below 0.05 routinely. Read")
    print("the ranking of pairs, not whether any value clears a threshold.")


if __name__ == "__main__":
    main()
