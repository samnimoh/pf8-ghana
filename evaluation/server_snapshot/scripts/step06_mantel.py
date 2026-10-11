#!/usr/bin/env python3
"""
STEP 6 — Isolation-by-distance: linearised FST against log geographic distance.

Three corrections to the draft are baked in. SciPy has never shipped a Mantel
test, so `skbio.stats.distance.mantel` is used, which demands symmetric
DistanceMatrix objects with zero diagonals. The regression uses FST/(1 - FST),
not raw FST. And geographic distance is computed on the WGS84 ellipsoid via
pyproj.Geod rather than a planar approximation.

Power is the real constraint. With k zones you get k(k-1)/2 pairs and k!
permutations; at k = 5 or 6 the permutation distribution is coarse enough that
a non-significant result means very little. The optional --level region mode
runs the same test on admin-1 populations instead, which is the finest grain
Pf8's metadata honestly supports.

Usage:
    python step06_mantel.py
    python step06_mantel.py --level region
    python step06_mantel.py --permutations 9999 --method spearman
"""

from __future__ import annotations

import argparse
import itertools
import json
import math

import allel
import matplotlib
import numpy as np
import pandas as pd
from pyproj import Geod

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import callset_io as cio  # noqa: E402
import config as C  # noqa: E402

GEOD = Geod(ellps="WGS84")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--level", choices=["zone", "region"], default="zone")
    p.add_argument("--permutations", type=int, default=999)
    p.add_argument("--method", choices=["pearson", "spearman"], default="pearson")
    p.add_argument("--min-n", type=int, default=10)
    p.add_argument("--log-transform", choices=["log", "log1p"], default="log",
                   help="log matches the method spec. log1p is safer if any "
                        "pairwise distance can be zero.")
    return p.parse_args()


def great_circle_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """a, b are (lon, lat)."""
    _, _, dist_m = GEOD.inv(a[0], a[1], b[0], b[1])
    return dist_m / 1000.0


def zone_centroids(meta: pd.DataFrame, zones: list[str]) -> pd.DataFrame:
    """Place each zone where its isolates were sampled.

    Pf8 geolocates isolates to admin-1 centroids, so the mean over a zone's
    isolates is the n-weighted mean of the region points inside it. A polygon
    centroid would put the zone where nobody sampled.
    """
    g = meta.groupby("zone")[[C.COL_LON, C.COL_LAT]].mean()
    missing = [z for z in zones if z not in g.index]
    if missing:
        raise KeyError(f"No samples for zone(s) {missing} in the analysis table.")
    g = g.loc[zones]
    print("Zone locations (sample-weighted) and the regions behind them:")
    for z in zones:
        regions = meta.loc[meta["zone"] == z, C.COL_ADMIN1].value_counts()
        parts = ", ".join(f"{r} {n}" for r, n in regions.items())
        print(f"  {z:<20} {g.loc[z, C.COL_LAT]:7.3f}N {g.loc[z, C.COL_LON]:8.3f}E  ({parts})")
    return pd.DataFrame({"lon": g[C.COL_LON].to_numpy(),
                         "lat": g[C.COL_LAT].to_numpy()}, index=zones)


def region_centroids(meta: pd.DataFrame, pops: list[str]) -> pd.DataFrame:
    g = meta.groupby(C.COL_ADMIN1)[[C.COL_LON, C.COL_LAT]].mean().loc[pops]
    return pd.DataFrame({"lon": g[C.COL_LON].to_numpy(),
                         "lat": g[C.COL_LAT].to_numpy()}, index=pops)


def fst_from_genotypes(meta: pd.DataFrame, group_col: str,
                       pops: list[str]) -> np.ndarray:
    data = np.load(C.require(C.CALLSET_NPZ), allow_pickle=False)
    ac = cio.isolate_allele_counts(
        data["gt"], {p: np.flatnonzero((meta[group_col] == p).to_numpy()) for p in pops})
    n = len(pops)
    m = np.zeros((n, n))
    for i, j in itertools.combinations(range(n), 2):
        num, den = allel.hudson_fst(ac[pops[i]], ac[pops[j]])
        m[i, j] = m[j, i] = float(np.nansum(num) / np.nansum(den))
    return m


def main() -> None:
    args = parse_args()
    C.banner(f"STEP 6 — Mantel test for isolation by distance ({args.level} level)")

    meta = pd.read_csv(C.require(C.ANALYSIS_SAMPLES_CSV,
                                 "Run step04a_prepare_callset.py first."))

    if args.level == "zone":
        pops = C.load_zone_order()
        fst = np.load(C.require(C.FST_NPY, "Run step04b_fst.py first."))
        cent = zone_centroids(meta, pops)
        group_col = "zone"
    else:
        if C.COL_ADMIN1 not in meta.columns:
            raise KeyError(f"'{C.COL_ADMIN1}' not in the sample table.")
        counts = meta[C.COL_ADMIN1].value_counts()
        pops = sorted(counts[counts >= args.min_n].index.tolist())
        print(f"Regions with n >= {args.min_n}: {len(pops)}")
        for p in pops:
            print(f"  {p:<24} n = {counts[p]}")
        fst = fst_from_genotypes(meta, C.COL_ADMIN1, pops)
        cent = region_centroids(meta, pops)
        group_col = C.COL_ADMIN1

    n = len(pops)
    n_pairs = n * (n - 1) // 2
    print(f"\nPopulations: {n}   pairwise comparisons: {n_pairs}")
    if n < 4:
        raise RuntimeError("A Mantel test on fewer than 4 populations is meaningless.")

    # ---- geographic distance ---------------------------------------------
    geo = np.zeros((n, n))
    for i, j in itertools.combinations(range(n), 2):
        d = great_circle_km((cent.lon.iloc[i], cent.lat.iloc[i]),
                            (cent.lon.iloc[j], cent.lat.iloc[j]))
        geo[i, j] = geo[j, i] = d
    print(f"Geographic distances: {geo[geo > 0].min():.0f}–{geo.max():.0f} km")

    # ---- linearise and test ----------------------------------------------
    with np.errstate(divide="ignore", invalid="ignore"):
        lin_fst = fst / (1.0 - fst)
    lin_fst = np.nan_to_num(lin_fst, nan=0.0, posinf=0.0)
    lin_fst = (lin_fst + lin_fst.T) / 2.0
    np.fill_diagonal(lin_fst, 0.0)
    lin_fst[lin_fst < 0] = 0.0   # DistanceMatrix rejects negatives

    if args.log_transform == "log":
        off = geo[~np.eye(n, dtype=bool)]
        if (off <= 0).any():
            print("Zero-distance pair present — two populations share a centroid.")
            print("Falling back to log1p, which is defined at zero.")
            log_geo = np.log1p(geo)
        else:
            log_geo = np.log(geo, out=np.zeros_like(geo), where=geo > 0)
    else:
        log_geo = np.log1p(geo)
    np.fill_diagonal(log_geo, 0.0)

    from skbio.stats.distance import DistanceMatrix, mantel

    ids = [C.slugify_zone(p) for p in pops]
    corr, p_value, n_obs = mantel(
        DistanceMatrix(lin_fst, ids=ids),
        DistanceMatrix(log_geo, ids=ids),
        method=args.method,
        permutations=args.permutations,
        alternative="greater",   # IBD predicts a positive association
    )

    C.banner("Result")
    print(f"  Mantel r  = {corr:.4f}")
    print(f"  p         = {p_value:.4f}  ({args.permutations} permutations, one-sided)")
    print(f"  n         = {n_obs} populations, {n_pairs} pairs")

    max_perm = float(math.factorial(min(n, 12)))
    print(f"\n  Distinct orderings available: {max_perm:,.0f}")
    print(f"  Finest attainable p-value:    {1 / min(max_perm, args.permutations + 1):.4f}")
    if n <= 6:
        print("\n  The permutation distribution is coarse at this k. A null result")
        print("  here is weak evidence against IBD, not evidence for panmixia.")
        print("  Pf8 resolves coordinates to admin level 1, so per-sample distance")
        print("  is unavailable; --level region is the finer grain you can claim.")

    # ---- scatter ----------------------------------------------------------
    iu = np.triu_indices(n, k=1)
    x, y = log_geo[iu], lin_fst[iu]
    fig, ax = plt.subplots(figsize=(6.5, 5))
    ax.scatter(x, y, s=45, color="#1f4e79", alpha=0.85)
    if len(x) > 2:
        slope, intercept = np.polyfit(x, y, 1)
        xs = np.linspace(x.min(), x.max(), 50)
        ax.plot(xs, slope * xs + intercept, "--", color="crimson", lw=1.4)
    for (i, j), xi, yi in zip(zip(*iu), x, y):
        ax.annotate(f"{pops[i][:8]}–{pops[j][:8]}", (xi, yi),
                    fontsize=6, alpha=0.6,
                    xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel("log(1 + geographic distance, km)" if args.log_transform == "log1p"
                  or (geo[~np.eye(n, dtype=bool)] <= 0).any()
                  else "log(geographic distance, km)")
    ax.set_ylabel(r"$F_{ST}/(1-F_{ST})$")
    ax.set_title(f"Isolation by distance ({args.level} level)\n"
                 f"Mantel r = {corr:.3f}, p = {p_value:.3f}")
    out_png = C.FIG_DIR / f"mantel_ibd_{args.level}.png"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)

    result = {
        "level": args.level,
        "method": args.method,
        "populations": pops,
        "n_populations": int(n),
        "n_pairs": int(n_pairs),
        "permutations": args.permutations,
        "mantel_r": float(corr),
        "p_value": float(p_value),
    }
    out_json = C.RESULTS_DIR / f"mantel_result_{args.level}.json"
    out_json.write_text(json.dumps(result, indent=2))
    pd.DataFrame(geo, index=pops, columns=pops).to_csv(
        C.RESULTS_DIR / f"geographic_distance_km_{args.level}.csv")

    print(f"\nFigure -> {out_png}")
    print(f"Result -> {out_json}")


if __name__ == "__main__":
    main()
