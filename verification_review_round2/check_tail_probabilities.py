#!/usr/bin/env python3
"""Compare normal-tail formulations against saved TreeMix edge statistics.

This establishes numerical compatibility, not executable or command provenance.
Uses only the standard library and the displayed mean/SE precision.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "provenance_final/results/treemix_treeout_all.txt"
OUTPUT = Path(__file__).with_name("tail_probability_review.json")


def main():
    rows = []
    model = edge = 0
    for line_number, line in enumerate(INPUT.read_text().splitlines(), 1):
        if line.startswith("=="):
            model = int(line.split("=")[-1])
            edge = 0
            continue
        parts = line.split()
        if len(parts) != 6:
            continue
        edge += 1
        mean, se = float(parts[1]), float(parts[2])
        z = mean / se
        stable = 0.5 * math.erfc(z / math.sqrt(2))
        rounded_cdf_tail = 1 - (1 - stable)
        erf_cdf_tail = 1 - 0.5 * (1 + math.erf(z / math.sqrt(2)))
        token = parts[3]
        printed = float(token.lstrip("<"))
        censored = token.startswith("<")
        rows.append({
            "m": model, "edge": edge, "line": line_number,
            "z": z, "printed": token, "stable": stable,
            "one_minus_rounded_cdf_tail": rounded_cdf_tail,
            "erf_cdf_tail": erf_cdf_tail,
            "stable_matches_3sf": not censored and format(stable, ".3g") == format(printed, ".3g"),
            "rounded_cdf_matches_3sf": rounded_cdf_tail == 0 if censored else
                format(rounded_cdf_tail, ".3g") == format(printed, ".3g"),
            "printed_censoring_bound_contains_stable_tail": stable < printed if censored else None,
        })
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Numerical evaluation from displayed mean/SE. Does not identify actual TreeMix source/build or recover unrounded statistics.",
        "runtime": {"executable": sys.executable, "python_version": sys.version,
                    "third_party_dependencies": []},
        "input": {"path": str(INPUT), "sha256": hashlib.sha256(INPUT.read_bytes()).hexdigest()},
        "checker": {"path": str(Path(__file__).resolve()),
                    "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "edge_count": len(rows),
        "finite_printed_count": sum(not row["printed"].startswith("<") for row in rows),
        "stable_3sf_matches": sum(row["stable_matches_3sf"] for row in rows),
        "rounded_cdf_3sf_matches_including_zero_sentinels": sum(row["rounded_cdf_matches_3sf"] for row in rows),
        "edges": rows,
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in
                     ("edge_count", "finite_printed_count", "stable_3sf_matches",
                      "rounded_cdf_3sf_matches_including_zero_sentinels")}))


if __name__ == "__main__":
    main()
