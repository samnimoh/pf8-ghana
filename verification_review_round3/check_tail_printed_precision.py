#!/usr/bin/env python3
"""Check the new exact-reproduction claim using displayed TreeMix statistics.

This evaluates numeric compatibility. It neither identifies the original build
nor recovers unrounded means and standard errors.
"""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "provenance_final/results/treemix_treeout_all.txt"
NOTES = ROOT / "provenance_final/VERIFICATION_NOTES.md"


def identity(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    model = edge = 0
    rows = []
    for number, line in enumerate(SOURCE.read_text().splitlines(), 1):
        if line.startswith("=="):
            model = int(line.split("=")[-1])
            edge = 0
            continue
        fields = line.split()
        if len(fields) != 6:
            continue
        edge += 1
        z = float(fields[1]) / float(fields[2])
        stable = 0.5 * math.erfc(z / math.sqrt(2))
        subtractive = 1 - (1 - stable)
        token = fields[3]
        sentinel = token.startswith("<")
        significant_digits = len(Decimal(token.lstrip("<")).as_tuple().digits)
        rounded = format(subtractive, f".{significant_digits}g")
        matches = subtractive == 0 if sentinel else float(rounded) == float(token)
        rows.append({"model": model, "edge": edge, "source_line": number,
                     "displayed_p": token, "z_from_displayed_mean_se": z,
                     "stable_tail": stable, "rounded_cdf_subtraction_tail": subtractive,
                     "subtraction_at_displayed_p_precision": rounded,
                     "matches_displayed_precision_or_zero_sentinel": matches,
                     "subtraction_matches_3sf_or_zero_sentinel": subtractive == 0 if sentinel else
                         format(subtractive, ".3g") == format(float(token), ".3g"),
                     "sentinel_contains_stable_tail": stable < float(token[1:]) if sentinel else None})
    assert len(rows) == 15
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Displayed mean/SE arithmetic; no scientific pipeline or executable-provenance validation.",
        "runtime": {"executable": sys.executable, "version": sys.version, "third_party_dependencies": []},
        "inputs": [identity(SOURCE), identity(NOTES)],
        "checker": identity(Path(__file__).resolve()),
        "new_notes_claim_present": "printed values now reproduce exactly" in NOTES.read_text(),
        "edges": rows,
        "summary": {
            "edge_count": len(rows),
            "finite_printed_count": sum(not r["displayed_p"].startswith("<") for r in rows),
            "matches_at_displayed_precision_including_zero_sentinels": sum(r["matches_displayed_precision_or_zero_sentinel"] for r in rows),
            "finite_matches_at_displayed_precision": sum(r["matches_displayed_precision_or_zero_sentinel"] and not r["displayed_p"].startswith("<") for r in rows),
            "matches_at_3sf_including_zero_sentinels": sum(r["subtraction_matches_3sf_or_zero_sentinel"] for r in rows),
        },
        "interpretation": "Cancellation explains the tiny printed tails and two zero sentinels. Three moderate p-values differ at the full displayed precision when recomputed from displayed means/SEs; rounding of those inputs may explain the residual. All fifteen are numerically compatible to three significant figures under CDF subtraction. This does not prove all-digit or bitwise reproduction or the generating invocation.",
    }
    Path(__file__).with_name("tail_printed_precision_validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
