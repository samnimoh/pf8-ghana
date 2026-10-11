#!/usr/bin/env python3
"""Read-only local QC/batch/Mantel arithmetic; no scientific pipeline execution.

Kruskal H is computed from pooled average ranks with the usual tie correction.
For the three archived comparisons, df is 1, 3 or 5: chi-square survival is
computed from erfc and the upper incomplete-gamma recurrence. No scipy,
pandas, numpy, network access or external executable is required.
These checks establish properties of local snapshots, not remote byte identity.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).with_name("batch_mantel_validation.json")
INPUTS = {
    "qc": "evaluation/server_snapshot/results/sample_qc_full.csv",
    "qc_release": "evaluation/results/qc_with_release_fws.csv",
    "analysis": "evaluation/server_snapshot/interim/analysis_samples.csv",
    "batch_tests": "corrected/batch_within_zone_tests.csv",
    "study_zone": "corrected/batch_study_by_zone.csv",
    "mantel": "corrected/mantel_jackknife_region.csv",
}


def read_csv(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def numeric(value):
    return float(value) if value.strip() else float("nan")


def observed(value):
    return bool(value.strip()) and math.isfinite(float(value))


def field_equivalent(a, b):
    if a == b:
        return True
    try:
        fa, fb = numeric(a), numeric(b)
        return math.isclose(fa, fb, rel_tol=0, abs_tol=1e-15) or (math.isnan(fa) and math.isnan(fb))
    except ValueError:
        return False


def kruskal(groups):
    """Average ranks, tie-corrected H and asymptotic chi-square p-value."""
    tagged = sorted((v, i) for i, group in enumerate(groups) for v in group)
    n = len(tagged)
    rank_sums = [0.0] * len(groups)
    tie_sum = 0
    start = 0
    while start < n:
        stop = start + 1
        while stop < n and tagged[stop][0] == tagged[start][0]:
            stop += 1
        rank = ((start + 1) + stop) / 2
        for _, group_index in tagged[start:stop]:
            rank_sums[group_index] += rank
        tie_count = stop - start
        tie_sum += tie_count**3 - tie_count
        start = stop
    correction = 1 - tie_sum / (n**3 - n)
    h = (12 / (n * (n + 1)) *
         sum(rs**2 / len(group) for rs, group in zip(rank_sums, groups)) -
         3 * (n + 1)) / correction
    df = len(groups) - 1
    if df not in (1, 3, 5):
        raise ValueError("This checker implements only the archived odd df=1,3,5.")
    x = h / 2
    p_value = math.erfc(math.sqrt(x))
    a = 0.5
    for _ in range((df - 1) // 2):
        p_value += math.exp(a * math.log(x) - x - math.lgamma(a + 1))
        a += 1
    return {"H": h, "p_value": p_value, "df": df,
            "n_observed": n, "tie_correction": correction,
            "group_sizes": [len(group) for group in groups]}


def main():
    tables = {key: read_csv(ROOT / rel) for key, rel in INPUTS.items()}
    hashes = {}
    for key, rel in INPUTS.items():
        path = ROOT / rel
        data = path.read_bytes()
        hashes[key] = {"path": str(path), "bytes": len(data),
                       "rows": len(tables[key]),
                       "sha256": hashlib.sha256(data).hexdigest(),
                       "md5": hashlib.md5(data).hexdigest()}
    qc = tables["qc"]
    release = {row["Sample"]: row for row in tables["qc_release"]}
    full = {row["Sample"]: row for row in qc}
    analysis = tables["analysis"]
    shared_match = (len(qc) == len(release) and all(
        row["Sample"] in release and all(field_equivalent(v, release[row["Sample"]][k])
                                        for k, v in row.items()) for row in qc))
    missing = {key: {column: sum(not observed(row[column]) for row in tables[key])
                     for column in ("Fws", "call_rate") if column in tables[key][0]}
               for key in ("qc", "qc_release", "analysis")}
    analysis_match = all(row["Sample"] in full and
                         field_equivalent(row["Fws"], full[row["Sample"]]["Fws"])
                         for row in analysis)
    fws_roundoff = {}
    for label, table in (("release_join", tables["qc_release"]), ("analysis", analysis)):
        deltas = [abs(numeric(row["Fws"]) - numeric(full[row["Sample"]]["Fws"]))
                  for row in table]
        fws_roundoff[label] = {"nonidentical_float_values": sum(delta != 0 for delta in deltas),
                               "maximum_absolute_difference": max(deltas),
                               "interpretation": "CSV decimal serialization differs at machine-roundoff scale."}
    results = []
    saved = {row["zone"]: row for row in tables["batch_tests"]}
    min_n = 20
    for zone in sorted({row["zone"] for row in qc}):
        members = [row for row in qc if row["zone"] == zone]
        counts = Counter(row["Study"] for row in members)
        studies = sorted(study for study, count in counts.items() if count >= min_n)
        if len(studies) < 2:
            continue
        f_groups = [[numeric(row["Fws"]) for row in members
                     if row["Study"] == study and observed(row["Fws"])] for study in studies]
        c_groups = [[numeric(row["call_rate"]) for row in members
                     if row["Study"] == study and observed(row["call_rate"])] for study in studies]
        f_stat, c_stat = kruskal(f_groups), kruskal(c_groups)
        fractions = [sum(value < 0.95 for value in group) / len(group) for group in f_groups]
        values = {"n_studies": len(studies), "n_isolates": sum(counts[s] for s in studies),
                  "fws_kruskal_H": f_stat["H"], "fws_p": f_stat["p_value"],
                  "polyclonal_min": min(fractions), "polyclonal_max": max(fractions),
                  "callrate_kruskal_H": c_stat["H"], "callrate_p": c_stat["p_value"]}
        differences = {key: {"recomputed": value, "saved": numeric(saved[zone][key]),
                             "absolute_difference": abs(value - numeric(saved[zone][key])),
                             "matches": math.isclose(value, numeric(saved[zone][key]),
                                                     rel_tol=1e-10,
                                                     abs_tol=0 if key.endswith("_p") else 1e-15),
                             "tolerance": {"relative": 1e-10,
                                           "absolute": 0 if key.endswith("_p") else 1e-15}}
                       for key, value in values.items()}
        results.append({"zone": zone, "studies": studies, "Fws": f_stat,
                        "call_rate": c_stat, "comparisons": differences})
    zone_summary = {}
    for zone in sorted({row["zone"] for row in qc}):
        members = [row for row in qc if row["zone"] == zone]
        called = [numeric(row["Fws"]) for row in members if observed(row["Fws"])]
        count = sum(value < 0.95 for value in called)
        zone_summary[zone] = {"n_isolates": len(members), "n_Fws_observed": len(called),
                              "n_polyclonal": count, "fraction": count / len(called)}
    study_zone = Counter((row["Study"], row["zone"]) for row in qc)
    study_matches = all(
        int(row[zone]) == study_zone[(row["Study"], zone)]
        for row in tables["study_zone"] for zone in zone_summary)
    study_totals_match = all(int(row["TOTAL"]) == sum(study_zone[(row["Study"], zone)]
                                                   for zone in zone_summary)
                            for row in tables["study_zone"])
    expected_mantel = {"Ashanti": .0140, "Brong Ahafo": .0398, "Central": .0427,
                       "Eastern": .1355, "Greater Accra": .2324,
                       "Upper East": .2180, "Volta": .0097}
    mantel = {row["dropped"]: numeric(row["p_value"]) for row in tables["mantel"]}
    mantel_matches = mantel == expected_mantel
    checks = {
        "local_QC_4905_no_missing_Fws": len(qc) == 4905 and missing["qc"]["Fws"] == 0,
        "local_analysis_1900_no_missing_Fws": len(analysis) == 1900 and missing["analysis"]["Fws"] == 0,
        "release_join_shared_fields_agree": shared_match,
        "analysis_sample_Fws_values_agree": analysis_match,
        "all_local_batch_statistics_match": len(results) == len(saved) and all(
            item["matches"] for result in results for item in result["comparisons"].values()),
        "study_zone_counts_match": study_matches and study_totals_match,
        "revised_Mantel_values_match": mantel_matches,
    }
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "checker": str(Path(__file__).resolve()),
              "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "runtime": {"executable": sys.executable, "resolved_executable": str(Path(sys.executable).resolve()),
                          "python_version": sys.version, "platform": platform.platform(),
                          "libraries": {"csv": csv.__file__, "math": getattr(math, "__file__", "builtin"),
                                        "json": json.__file__},
                          "third_party_dependencies": []},
              "method": {"Kruskal": "pooled average ranks and tie-corrected H",
                         "p_value": "asymptotic chi-square survival; odd df 1/3/5, erfc plus upper-gamma recurrence",
                         "minimum_group_size": min_n, "Fws_threshold": 0.95,
                         "cross_snapshot_field_tolerance": {"relative": 0, "absolute": 1e-15},
                         "comparison_tolerances": {
                             "p_values": {"relative": 1e-10, "absolute": 0},
                             "H_counts_and_fractions": {"relative": 1e-10, "absolute": 1e-15}}},
              "inputs": hashes, "checks": checks, "missingness": missing,
              "Fws_cross_snapshot_roundoff": fws_roundoff,
              "analysis_zone_counts": dict(Counter(row["zone"] for row in analysis)),
              "zone_polyclonality": zone_summary, "batch_results": results,
              "mantel_p_values": mantel,
              "mantel_counts": {"p_lt_0_05": sum(p < .05 for p in mantel.values()),
                                "p_lt_0_10": sum(p < .1 for p in mantel.values())},
              "interpretation": "The missing-Fws denominator defect is dormant for these complete local snapshots; this is not a repair of the code.",
              "limits": ["Remote final input byte identity is unavailable and not established.",
                         "Input/output arithmetic does not identify study differences as technical batch effects.",
                         "No scientific pipeline, installation, or network call was run."]}
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{sum(checks.values())}/{len(checks)} checks passed; {OUT}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
