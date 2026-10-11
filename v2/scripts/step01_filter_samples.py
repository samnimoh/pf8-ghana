#!/usr/bin/env python3
"""
STEP 1 — Subset the Pf8 sample manifest to Ghana.

The one thing this step exists to protect is row order. `pf8_row` is captured
before any filtering, because Step 3 indexes the global distance matrix by
integer position and a pandas label index will not survive a filter plus a
spatial join intact.

Usage:
    python step01_filter_samples.py
    python step01_filter_samples.py --no-qc-filter      # keep QC failures
    python step01_filter_samples.py --country Ghana
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

import config as C


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--country", default=C.COUNTRY)
    p.add_argument("--no-qc-filter", action="store_true",
                   help="Retain samples that fail the Pf8 QC flag.")
    p.add_argument("--min-year", type=int, default=None)
    p.add_argument("--max-year", type=int, default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    C.banner(f"STEP 1 — Pf8 manifest -> {args.country} subset")

    C.require(
        C.SAMPLE_MANIFEST,
        "Place Pf8_samples.txt in data/. Source: "
        "https://www.malariagen.net/wp-content/uploads/2023/11/Pf8_samples.txt",
    )

    df = pd.read_csv(C.SAMPLE_MANIFEST, sep="\t", low_memory=False)
    print(f"Global manifest: {len(df):,} samples, {df.shape[1]} columns")

    # ---- the load-bearing line -------------------------------------------
    df["pf8_row"] = np.arange(len(df), dtype=np.int64)

    missing = [c for c in (C.COL_COUNTRY, C.COL_LON, C.COL_LAT) if c not in df.columns]
    if missing:
        raise KeyError(
            f"Manifest is missing expected column(s): {missing}\n"
            f"Available columns:\n  " + "\n  ".join(df.columns)
        )

    sub = df[df[C.COL_COUNTRY] == args.country].copy()
    print(f"{args.country} subset: {len(sub):,} samples")

    if not args.no_qc_filter and C.COL_QC in sub.columns:
        before = len(sub)
        sub = sub[C.coerce_bool(sub[C.COL_QC])].copy()
        print(f"QC filter: {before:,} -> {len(sub):,} ({before - len(sub)} dropped)")
    elif C.COL_QC not in sub.columns:
        print(f"No '{C.COL_QC}' column found — QC filtering skipped.")

    if C.COL_YEAR in sub.columns:
        year = pd.to_numeric(sub[C.COL_YEAR], errors="coerce")
        if args.min_year is not None:
            sub = sub[year >= args.min_year]
        if args.max_year is not None:
            sub = sub[year <= args.max_year]
        print("\nSamples per collection year:")
        print(pd.to_numeric(sub[C.COL_YEAR], errors="coerce")
              .value_counts().sort_index().to_string())

    if C.COL_ADMIN1 in sub.columns:
        print("\nSamples per admin level 1 region:")
        print(sub[C.COL_ADMIN1].value_counts().to_string())

    # Coordinates must exist for the spatial join to mean anything.
    no_coord = sub[C.COL_LON].isna() | sub[C.COL_LAT].isna()
    if no_coord.any():
        print(f"\nWARNING: {no_coord.sum()} samples lack coordinates — dropping them.")
        sub = sub[~no_coord].copy()

    # Sanity check the index invariant before anyone depends on it.
    assert sub["pf8_row"].is_unique, "pf8_row is not unique — manifest read is corrupt."
    assert sub["pf8_row"].max() < len(df), "pf8_row exceeds manifest length."

    sub.to_csv(C.GHANA_SAMPLES_CSV, index=False)
    print(f"\nWrote {len(sub):,} rows -> {C.GHANA_SAMPLES_CSV}")
    print(f"pf8_row range: {sub['pf8_row'].min()} .. {sub['pf8_row'].max()}")


if __name__ == "__main__":
    main()
