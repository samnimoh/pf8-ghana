#!/usr/bin/env python3
"""
STEP 8c — Calibrate the XtX threshold and emit the outlier SNP list as BED.

Preferred route: the POD XtX distribution simulated under the estimated neutral
covariance. Its upper quantile is a threshold that carries an explicit null.
Where the POD run is unavailable the script falls back to an empirical quantile
of the observed distribution and labels the result as such, because the two are
not interchangeable and a methods section should not pretend otherwise.

Usage:
    python step08c_calibrate_xtx.py
    python step08c_calibrate_xtx.py --quantile 0.99
    python step08c_calibrate_xtx.py --empirical-fallback-quantile 0.995
"""

from __future__ import annotations

import argparse
import json

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import config as C  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--quantile", type=float, default=C.XTX_POD_QUANTILE,
                   help="Upper quantile of the POD XtX distribution.")
    p.add_argument("--empirical-fallback-quantile", type=float, default=0.999)
    return p.parse_args()


def read_xtx(path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=r"\s+")
    col = next((c for c in ("M_XtX", "XtXst", "XtX") if c in df.columns), None)
    if col is None:
        raise KeyError(f"No XtX column in {path}. Columns: {list(df.columns)}")
    df = df.rename(columns={col: "xtx"})
    return df


def main() -> None:
    args = parse_args()
    C.banner("STEP 8c — XtX calibration")

    obs_path = C.require(C.BAYPASS_DIR / "ghana_core_summary_pi_xtx.out",
                         "Run step08b_baypass.sh first.")
    obs = read_xtx(obs_path)
    print(f"Observed SNPs: {len(obs):,}")
    print(f"XtX range: {obs['xtx'].min():.2f} – {obs['xtx'].max():.2f}")

    pod_path = C.BAYPASS_DIR / "ghana_pod_summary_pi_xtx.out"
    pod = None
    if pod_path.exists():
        pod = read_xtx(pod_path)
        threshold = float(np.quantile(pod["xtx"], args.quantile))
        method = f"POD quantile {args.quantile}"
        print(f"\nPOD SNPs: {len(pod):,}")
        print(f"Threshold from the simulated neutral distribution: {threshold:.3f}")
    else:
        threshold = float(np.quantile(obs["xtx"], args.empirical_fallback_quantile))
        method = f"EMPIRICAL quantile {args.empirical_fallback_quantile} (no POD)"
        print("\nNo POD output found.")
        print(f"Falling back to the empirical {args.empirical_fallback_quantile} "
              f"quantile: {threshold:.3f}")
        print("This assumes a fixed fraction of the genome is selected — a")
        print("weaker null. Report it as such, or re-run Step 8b with R available.")

    outliers = obs[obs["xtx"] > threshold].copy()
    frac = len(outliers) / len(obs)
    print(f"\nOutliers: {len(outliers):,} SNPs ({frac:.3%} of the scan)")
    if frac > 0.05:
        print("More than 5% of SNPs flagged — that is too many to be selection.")
        print("Suspect residual population structure or unfiltered subtelomeres.")

    # ---- align to coordinates --------------------------------------------
    positions = pd.read_csv(C.require(C.BAYPASS_POSITIONS,
                                      "Run step08a_baypass_input.py first."))
    if len(positions) != len(obs):
        raise ValueError(
            f"Position table has {len(positions):,} rows but the BayPass output "
            f"has {len(obs):,}. These must correspond row-for-row. Re-run Step 8a "
            f"and Step 8b together — mismatched files annotate the wrong genes."
        )

    obs = obs.reset_index(drop=True)
    merged = positions.join(obs[["xtx"]])
    merged["is_outlier"] = merged["xtx"] > threshold
    merged.to_csv(C.BAYPASS_DIR / "xtx_all_snps.csv", index=False)

    out = merged[merged["is_outlier"]].copy()
    out["start"] = out["pos"] - 1          # BED is 0-based half-open
    out["end"] = out["pos"]
    bed_path = C.BAYPASS_DIR / "outlier_snps.bed"
    (out.sort_values(["chrom", "start"])[["chrom", "start", "end", "xtx"]]
        .to_csv(bed_path, sep="\t", header=False, index=False))
    print(f"\nOutlier BED -> {bed_path}")

    C.XTX_THRESHOLD_TXT.write_text(f"{threshold}\n")
    (C.BAYPASS_DIR / "xtx_calibration.json").write_text(json.dumps({
        "threshold": threshold,
        "method": method,
        "n_snps": int(len(obs)),
        "n_outliers": int(len(outliers)),
        "outlier_fraction": float(frac),
    }, indent=2))

    # ---- plot -------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.2))
    ax1.hist(obs["xtx"], bins=120, color="#4c72b0", alpha=0.85,
             density=True, label="observed")
    if pod is not None:
        ax1.hist(pod["xtx"], bins=120, color="#c44e52", alpha=0.5,
                 density=True, label="POD (neutral)")
    ax1.axvline(threshold, color="black", ls="--", lw=1.4,
                label=f"threshold {threshold:.1f}")
    ax1.set_xlabel("XtX")
    ax1.set_ylabel("Density")
    ax1.set_title("XtX distribution")
    ax1.legend(fontsize=8)

    # Manhattan-style plot along the genome
    chrom_order = sorted(merged["chrom"].unique())
    offset, ticks, tick_labels = 0, [], []
    for i, ch in enumerate(chrom_order):
        m = merged["chrom"] == ch
        x = merged.loc[m, "pos"].to_numpy() + offset
        ax2.scatter(x, merged.loc[m, "xtx"], s=2,
                    color="#333" if i % 2 == 0 else "#999", rasterized=True)
        ticks.append(offset + merged.loc[m, "pos"].max() / 2)
        tick_labels.append(str(ch).replace("Pf3D7_", "").replace("_v3", ""))
        offset += int(merged.loc[m, "pos"].max()) + 50_000
    ax2.axhline(threshold, color="crimson", ls="--", lw=1.2)
    ax2.set_xticks(ticks)
    ax2.set_xticklabels(tick_labels, fontsize=7, rotation=90)
    ax2.set_ylabel("XtX")
    ax2.set_title("Genome-wide differentiation")
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "baypass_xtx.png", dpi=250, bbox_inches="tight")
    plt.close(fig)

    print(f"Figure -> {C.FIG_DIR / 'baypass_xtx.png'}")
    print(f"Threshold ({method}) -> {C.XTX_THRESHOLD_TXT}")
    print("\nNext: python step09_annotate.py")


if __name__ == "__main__":
    main()
