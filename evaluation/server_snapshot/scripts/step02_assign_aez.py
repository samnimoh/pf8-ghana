#!/usr/bin/env python3
"""
STEP 2 (+2b) — Assign each Ghanaian isolate to an agro-ecological zone, audit the
join, and draw the map.

Two failure modes are being guarded against. Points falling just outside a
polygon edge vanish silently under an inner join, so a left join plus an explicit
NaN count is used instead. Points landing inside two overlapping polygons match
twice and quietly inflate every downstream sample count, so duplicates are
detected and resolved by an explicit rule rather than by whichever row pandas
happened to keep.

Usage:
    python step02_assign_aez.py
    python step02_assign_aez.py --snap-unmatched --snap-km 15
    python step02_assign_aez.py --name-field Zone
"""

from __future__ import annotations

import argparse

import geopandas as gpd
import matplotlib
import pandas as pd

matplotlib.use("Agg")  # no display in WSL by default
import matplotlib.pyplot as plt  # noqa: E402

import config as C  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name-field", default=C.AEZ_NAME_FIELD,
                   help="Attribute in the GeoJSON holding the zone name.")
    p.add_argument("--snap-unmatched", action="store_true",
                   help="Assign unmatched points to the nearest polygon within --snap-km.")
    p.add_argument("--snap-km", type=float, default=10.0)
    p.add_argument("--drop-unmatched", action="store_true",
                   help="Discard samples with no zone instead of carrying NaN forward.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    C.banner("STEP 2 — samples -> agro-ecological zones")

    C.require(C.GHANA_SAMPLES_CSV, "Run step01_filter_samples.py first.")
    C.require(C.AEZ_GEOJSON, "Place ghanaAEZ.geojson in data/.")

    ghana_df = pd.read_csv(C.GHANA_SAMPLES_CSV)
    aez = gpd.read_file(C.AEZ_GEOJSON)

    print(f"AEZ layer: {len(aez)} polygons, CRS = {aez.crs}")
    if args.name_field not in aez.columns:
        raise KeyError(
            f"'{args.name_field}' not in the AEZ layer. Columns: {list(aez.columns)}\n"
            f"Pass the right one with --name-field."
        )
    print("Zones present:", sorted(aez[args.name_field].dropna().unique()))

    if aez.crs is None:
        print("WARNING: AEZ layer has no CRS. Assuming EPSG:4326.")
        aez = aez.set_crs("EPSG:4326")
    aez = aez.to_crs("EPSG:4326")

    # ---- samples as point geometries -------------------------------------
    sample_gdf = gpd.GeoDataFrame(
        ghana_df,
        geometry=gpd.points_from_xy(ghana_df[C.COL_LON], ghana_df[C.COL_LAT]),
        crs="EPSG:4326",
    )

    join_cols = [args.name_field, "geometry"]
    joined = gpd.sjoin(sample_gdf, aez[join_cols], how="left", predicate="within")

    # ---- audit ------------------------------------------------------------
    C.banner("Join audit")
    print("Counts per zone (NaN shown deliberately):")
    print(joined[args.name_field].value_counts(dropna=False).to_string())

    dup_mask = joined.index.duplicated(keep=False)
    n_dup = int(dup_mask.sum())
    print(f"\nRows implicated in duplicate matches: {n_dup}")
    if n_dup:
        print("Samples matching more than one polygon (seam overlaps):")
        print(joined.loc[dup_mask, [C.COL_SAMPLE, args.name_field]]
              .head(20).to_string(index=False))
        # Deterministic resolution: keep the alphabetically first zone so the
        # choice is reproducible and reviewable, not order-of-file dependent.
        joined = (joined.sort_values(args.name_field)
                        .loc[~joined.sort_values(args.name_field).index.duplicated(keep="first")]
                        .sort_index())
        print(f"Resolved by keeping first zone alphabetically -> {len(joined)} rows")

    unmatched = joined[args.name_field].isna()
    print(f"\nUnmatched samples: {int(unmatched.sum())}")

    if unmatched.any() and args.snap_unmatched:
        deg = args.snap_km / 111.0  # crude but adequate at Ghana's latitude
        near = gpd.sjoin_nearest(
            sample_gdf.loc[unmatched.values, ["geometry"]],
            aez[join_cols],
            how="left",
            max_distance=deg,
            distance_col="_snap_deg",
        )
        near = near[~near.index.duplicated(keep="first")]
        joined.loc[near.index, args.name_field] = near[args.name_field]
        still = joined[args.name_field].isna().sum()
        print(f"Snapped within {args.snap_km} km; {int(still)} still unmatched")

    if args.drop_unmatched:
        before = len(joined)
        joined = joined[joined[args.name_field].notna()].copy()
        print(f"Dropped unmatched: {before} -> {len(joined)}")

    # ---- map (step 2b) ----------------------------------------------------
    C.banner("STEP 2b — map the join")
    fig, ax = plt.subplots(figsize=(8, 10))
    aez.plot(ax=ax, column=args.name_field, cmap="Set3", legend=True,
             alpha=0.6, edgecolor="white",
             legend_kwds={"fontsize": 7, "loc": "lower left"})
    joined.plot(ax=ax, color="black", markersize=14, alpha=0.7)
    ax.set_title("Ghana P. falciparum sample locations across agro-ecological zones")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    out_png = C.FIG_DIR / "ghana_samples_aez_map.png"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Map -> {out_png}")

    # ---- persist ----------------------------------------------------------
    out = joined.drop(columns=["geometry"])
    if "index_right" in out.columns:
        out = out.drop(columns=["index_right"])
    out = out.rename(columns={args.name_field: "zone"})
    out.to_csv(C.SAMPLES_AEZ_CSV, index=False)
    print(f"Assignments -> {C.SAMPLES_AEZ_CSV}  ({len(out):,} samples)")

    # ---- the caveat that matters for Step 6 -------------------------------
    if C.COL_ADMIN1 in out.columns:
        C.banner("Coordinate resolution check")
        distinct_coords = out[[C.COL_LON, C.COL_LAT]].drop_duplicates().shape[0]
        print(f"{len(out):,} samples occupy {distinct_coords} distinct coordinate pairs.")
        print("Pf8 geolocates to admin level 1, so isolates from one region share a")
        print("single point. Zone assignment tolerates this; individual-level")
        print("geographic distance does not. Step 6 is constrained accordingly.\n")

        cross = pd.crosstab(out[C.COL_ADMIN1], out["zone"], dropna=False)
        print("Region x zone (regions spanning two zones need manual review):")
        print(cross.to_string())
        straddlers = cross.index[(cross > 0).sum(axis=1) > 1].tolist()
        if straddlers:
            print(f"\nRegions assigned to >1 zone: {straddlers}")
        print("\nCheck Brong-Ahafo (forest/transition) and Volta (coastal/Guinea")
        print("savanna) against the map before treating the assignment as settled.")


if __name__ == "__main__":
    main()
