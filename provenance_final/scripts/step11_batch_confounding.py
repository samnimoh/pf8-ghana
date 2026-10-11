#!/usr/bin/env python3
"""
STEP 11 — Is agro-ecological zone separable from sequencing study?

The manuscript lists three design confounders: zone is collinear with
administrative region, coordinates resolve only to admin level 1, and collection
year differs between zones. A fourth was missed. Pf8 isolates arrive through
named partner studies, and in Ghana those studies are almost perfectly nested
within zones. If no study contributes isolates to both zones of a comparison,
then that comparison is also a between-batch comparison and nothing in the data
can separate the two.

This script quantifies it rather than asserting it:

  1. study x zone crosstab, and which zone pairs have NO study in common
  2. whether studies differ in Fws within a zone, where zone is held constant
     and only batch varies — the clean test for a batch effect
  3. whether studies differ in call rate within a zone
  4. for the zone pairs that do share a study, whether the within-study
     difference agrees in sign with the overall between-zone difference

Read-only. Writes a crosstab and a summary table; changes no pipeline output.

Usage:
    python step11_batch_confounding.py
"""

from __future__ import annotations

import argparse
import itertools

import numpy as np
import pandas as pd
from scipy import stats

import config as C

STUDY_COL_CANDIDATES = ["Study", "study", "Partner study", "Sample set", "Exclusion reason"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--min-n", type=int, default=20,
                   help="Minimum isolates for a study x zone cell to be tested.")
    return p.parse_args()


def find_study_column(df: pd.DataFrame) -> str:
    for c in STUDY_COL_CANDIDATES:
        if c in df.columns:
            return c
    # fall back to any column whose values look like MalariaGEN study codes
    for c in df.columns:
        v = df[c].astype(str)
        if v.str.match(r"^\d{4}-PF-[A-Z]{2}-").mean() > 0.5:
            return c
    raise SystemExit(f"No study column found. Columns: {list(df.columns)}")


def main() -> None:
    args = parse_args()
    C.banner("STEP 11 — zone versus sequencing study")

    qc = pd.read_csv(C.require(C.SAMPLE_QC_FULL_CSV, "Run step03b_sample_qc.py first."))
    study = find_study_column(qc)
    print(f"Study column: '{study}'")
    qc = qc[qc[study].notna() & qc["zone"].notna()].copy()
    qc[study] = qc[study].astype(str)
    print(f"Isolates with both a study and a zone: {len(qc):,}")

    # ---- 1. crosstab ------------------------------------------------------
    C.banner("Study x zone")
    ct = pd.crosstab(qc[study], qc["zone"])
    ct["TOTAL"] = ct.sum(axis=1)
    ct = ct.sort_values("TOTAL", ascending=False)
    print(ct.to_string())
    out_ct = C.RESULTS_DIR / "batch_study_by_zone.csv"
    ct.to_csv(out_ct)

    zones = sorted(qc["zone"].unique())
    zone_studies = {z: set(qc.loc[qc["zone"] == z, study]) for z in zones}
    print("\nDominance: the largest study's share of each zone")
    for z in zones:
        s = qc.loc[qc["zone"] == z, study].value_counts()
        print(f"  {z:<20} {s.index[0]:<28} {s.iloc[0]:>5} / {int(s.sum()):>5} "
              f"({s.iloc[0] / s.sum():.0%})")

    C.banner("Zone pairs with no study in common")
    print("A pair with no shared study cannot be separated from a batch contrast.")
    rows = []
    for a, b in itertools.combinations(zones, 2):
        shared = zone_studies[a] & zone_studies[b]
        rows.append({"zone_a": a, "zone_b": b, "n_shared_studies": len(shared),
                     "shared": ";".join(sorted(shared))})
        flag = "" if shared else "   <- NO within-study replication"
        print(f"  {a[:20]:<22} vs {b[:20]:<22} shared studies: {len(shared)}{flag}")
    pairs = pd.DataFrame(rows)

    # ---- 2. batch effect with zone held constant --------------------------
    C.banner("Do studies differ WITHIN a zone?")
    print("Zone is constant here, so any difference is batch, not ecology.")
    has_fws = "Fws" in qc.columns and qc["Fws"].notna().any()
    tests = []
    for z in zones:
        sub = qc[qc["zone"] == z]
        counts = sub[study].value_counts()
        keep = counts[counts >= args.min_n].index
        if len(keep) < 2:
            print(f"  {z:<20} only {len(keep)} study with n >= {args.min_n} — not testable")
            continue
        groups_f = [sub.loc[sub[study] == s, "Fws"].dropna().to_numpy() for s in keep] \
            if has_fws else []
        groups_c = [sub.loc[sub[study] == s, "call_rate"].dropna().to_numpy() for s in keep]
        rec = {"zone": z, "n_studies": len(keep), "n_isolates": int(counts[keep].sum())}
        if has_fws and all(len(g) > 1 for g in groups_f):
            h, p = stats.kruskal(*groups_f)
            rec["fws_kruskal_H"], rec["fws_p"] = h, p
            poly = [float((g < C.MIN_FWS).mean()) for g in groups_f]
            rec["polyclonal_min"], rec["polyclonal_max"] = min(poly), max(poly)
        if all(len(g) > 1 for g in groups_c):
            h2, p2 = stats.kruskal(*groups_c)
            rec["callrate_kruskal_H"], rec["callrate_p"] = h2, p2
        tests.append(rec)
        fp = rec.get("fws_p")
        cp = rec.get("callrate_p")
        mark = "  <- significant batch effect" if (fp is not None and fp < 0.05) else ""
        print(f"  {z:<20} {len(keep)} studies, n={rec['n_isolates']:>5}   "
              f"Fws p={fp:.4g}" if fp is not None else f"  {z:<20} {len(keep)} studies")
        if fp is not None:
            print(f"      polyclonal fraction across those studies: "
                  f"{rec['polyclonal_min']:.3f} – {rec['polyclonal_max']:.3f}"
                  f"   call-rate p={cp:.4g}{mark}")
    tdf = pd.DataFrame(tests)

    # ---- 3. within-study replication of the zone contrast -----------------
    C.banner("Within-study checks on the zone contrast")
    print("Where a study does span two zones, does it reproduce the overall")
    print("between-zone difference in polyclonality? This is the only evidence")
    print("that can distinguish an ecological gradient from a batch artefact.")
    if has_fws:
        overall = {z: float((qc.loc[qc["zone"] == z, "Fws"] < C.MIN_FWS).mean()) for z in zones}
        print("\n  Overall polyclonal fraction: " +
              ", ".join(f"{z.split()[0][:8]} {overall[z]:.3f}" for z in zones))
        found_any = False
        for s, sub in qc.groupby(study):
            zs = [z for z in zones if (sub["zone"] == z).sum() >= args.min_n]
            if len(zs) < 2:
                continue
            found_any = True
            print(f"\n  {s}")
            for z in zs:
                g = sub.loc[sub["zone"] == z, "Fws"]
                print(f"    {z:<20} n={len(g):>5}  polyclonal {float((g < C.MIN_FWS).mean()):.3f}"
                      f"   (overall for this zone: {overall[z]:.3f})")
            for a, b in itertools.combinations(zs, 2):
                wa = float((sub.loc[sub["zone"] == a, "Fws"] < C.MIN_FWS).mean())
                wb = float((sub.loc[sub["zone"] == b, "Fws"] < C.MIN_FWS).mean())
                agree = np.sign(wa - wb) == np.sign(overall[a] - overall[b])
                print(f"    {a[:16]} vs {b[:16]}: within-study "
                      f"{'agrees with' if agree else 'CONTRADICTS'} the overall direction")
        if not found_any:
            print(f"\n  No study spans two zones with n >= {args.min_n} in both.")

    # ---- output -----------------------------------------------------------
    C.banner("Output")
    out_pairs = C.RESULTS_DIR / "batch_zone_pair_overlap.csv"
    pairs.to_csv(out_pairs, index=False)
    out_tests = C.RESULTS_DIR / "batch_within_zone_tests.csv"
    tdf.to_csv(out_tests, index=False)
    for p_ in (out_ct, out_pairs, out_tests):
        print(f"  {p_}")

    n_unreplicated = int((pairs["n_shared_studies"] == 0).sum())
    print(f"\n{n_unreplicated} of {len(pairs)} zone pairs have no study in common.")
    if n_unreplicated:
        worst = pairs[pairs["n_shared_studies"] == 0]
        print("Those comparisons are confounded with sequencing batch and cannot be")
        print("disentangled by any reanalysis of these data:")
        for _, r in worst.iterrows():
            print(f"  {r['zone_a']} vs {r['zone_b']}")


if __name__ == "__main__":
    main()
