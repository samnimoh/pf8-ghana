#!/usr/bin/env python3
"""Check saved marker aggregates against published residue calls, using stdlib.

This does not run the unavailable step10/11/12 sources, reconstruct DNA codons,
or independently validate sequencing. It joins the saved analysis sample IDs to
the local MalariaGEN published call table, rejects missing/mixed residue strings,
and checks the resulting aggregate counts against the newer corrected CSVs.
"""

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).with_name("marker_validation.json")
ZONES = ("Coastal savanna", "Decidous forest", "Guinea savanna", "Transitional zone")
EXPECTED_ZONE_COUNTS = dict(zip(ZONES, (204, 337, 1334, 25)))
PATHS = {
    "analysis_samples": ROOT / "evaluation/server_snapshot/interim/analysis_samples.csv",
    "published_calls": ROOT / "evaluation/inputs/Pf8_drug_resistance_marker_genotypes.tsv",
    "corrected_residues": ROOT / "corrected/codon_panel_residues.csv",
    "corrected_haplotypes": ROOT / "corrected/codon_panel_haplotypes.csv",
    "corrected_concordance": ROOT / "corrected/codon_panel_concordance.csv",
    "canonical_facts": ROOT / "corrected/CANONICAL_FACTS.txt",
}

# WHO compendium v1.0, December 2025; verified against the official summary table
# on 2026-10-10. The dated list is an input specification, not inferred from data.
WHO_SOURCE = (
    "https://cdn.who.int/media/docs/default-source/malaria/drug-resistance/"
    "compendium-molecular-markers-summary-tables.pdf?sfvrsn=e40fca23_9"
)
WHO_VALIDATED = (
    "F446I", "N458Y", "C469Y", "M476I", "Y493H", "G533S", "R539T",
    "I543T", "P553L", "R561H", "P574L", "C580Y", "R622I", "A675V",
)
WHO_CANDIDATES = ("E252Q", "P441L", "C469F", "N537I", "G538V", "V568G")


def read_rows(path, delimiter=","):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def single_residue(value):
    return len(value) == 1 and value in "ACDEFGHIKLMNPQRSTVWY"


def zone_slug(zone):
    return zone.replace(" ", "_")


def main():
    samples = read_rows(PATHS["analysis_samples"])
    ids = [row["Sample"] for row in samples]
    metadata = {row["Sample"]: row for row in samples}
    all_published = read_rows(PATHS["published_calls"], "\t")
    published = [row for row in all_published if row["Sample"] in metadata]
    matched_ids = [row["Sample"] for row in published]
    zone_counts = dict(Counter(row["zone"] for row in samples))
    sample_checks = {
        "analysis_rows": len(samples),
        "unique_analysis_ids": len(set(ids)),
        "matched_published_rows": len(published),
        "unique_matched_published_ids": len(set(matched_ids)),
        "missing_ids": sorted(set(ids) - set(matched_ids)),
        "zone_counts": zone_counts,
        "expected_zone_counts": EXPECTED_ZONE_COUNTS,
        "pass": (
            len(samples) == len(set(ids)) == len(published) == len(set(matched_ids)) == 1900
            and set(ids) == set(matched_ids)
            and zone_counts == EXPECTED_ZONE_COUNTS
        ),
    }
    residue_rows = read_rows(PATHS["corrected_residues"])
    haplotype_rows = read_rows(PATHS["corrected_haplotypes"])
    marker_results = {}
    for name, gene, codon, target, column in (
        ("pfdhps_G437", "pfdhps", 437, "G", "dhps_437[G]"),
        ("pfcrt_N75E", "pfcrt", 75, "E", "crt_75[N]"),
    ):
        corrected = next(
            row for row in residue_rows
            if row["gene"] == gene and int(row["codon"]) == codon and row["residue"] == target
        )
        called = [row for row in published if single_residue(row[column])]
        zones = {}
        for zone in ZONES:
            selected = [row for row in called if metadata[row["Sample"]]["zone"] == zone]
            count = sum(row[column] == target for row in selected)
            prefix = zone_slug(zone)
            expected_n = int(corrected[prefix + "_n"])
            # The residue CSV saves frequencies and denominators, rather than zone counts.
            expected_count = round(expected_n * float(corrected[prefix + "_freq"]))
            zones[zone] = {
                "n_called": len(selected), "count": count,
                "corrected_n_called": expected_n, "corrected_count": expected_count,
                "pass": len(selected) == expected_n and count == expected_count,
            }
        count = sum(row[column] == target for row in called)
        expected_n, expected_count = int(corrected["n_called"]), int(corrected["count"])
        marker_results[name] = {
            "published_column": column, "target_residue": target,
            "n_called": len(called), "count": count, "frequency": count / len(called),
            "corrected_n_called": expected_n, "corrected_count": expected_count,
            "zones": zones,
            "pass": len(called) == expected_n and count == expected_count
                    and all(row["pass"] for row in zones.values()),
        }

    haplotype_results = {}
    for name, columns, target, is_published_motif in (
        ("pfdhfr_51_59_108", ("dhfr_51[N]", "dhfr_59[C]", "dhfr_108[S]"), "IRN", False),
        ("pfdhfr_quadruple", ("dhfr_51[N]", "dhfr_59[C]", "dhfr_108[S]", "dhfr_164[I]"), "IRNL", False),
        ("pfcrt_72_76", ("crt_72-76[CVMNK]",), "CVIET", True),
        ("pfdhps_437_540", ("dhps_437[G]", "dhps_540[K]"), "GE", False),
    ):
        selected = []
        for row in published:
            values = [row[column] for column in columns]
            if is_published_motif:
                callable_value = len(values[0]) == 5 and all(single_residue(x) for x in values[0])
            else:
                callable_value = all(single_residue(value) for value in values)
            if callable_value:
                selected.append((metadata[row["Sample"]]["zone"], "".join(values)))
        zones = {}
        for zone in ZONES:
            values = [value for row_zone, value in selected if row_zone == zone]
            count = sum(value == target for value in values)
            corrected = next(
                row for row in haplotype_rows if row["haplotype"] == name and row["zone"] == zone
            )
            expected_n, expected_count = int(corrected["n_complete"]), int(corrected["count"])
            zones[zone] = {
                "n_complete": len(values), "count": count,
                "corrected_n_complete": expected_n, "corrected_count": expected_count,
                "pass": len(values) == expected_n and count == expected_count and corrected["target"] == target,
            }
        count = sum(value == target for _, value in selected)
        expected_rows = [row for row in haplotype_rows if row["haplotype"] == name]
        expected_n = sum(int(row["n_complete"]) for row in expected_rows)
        expected_count = sum(int(row["count"]) for row in expected_rows)
        haplotype_results[name] = {
            "published_columns": list(columns), "target": target,
            "method": "published complete 72-76 motif" if is_published_motif else "conjunction of unambiguous published residue strings",
            "n_complete": len(selected), "count": count, "frequency": count / len(selected),
            "corrected_n_complete": expected_n, "corrected_count": expected_count,
            "residue_string_spectrum": dict(Counter(value for _, value in selected)),
            "zones": zones,
            "pass": len(selected) == expected_n and count == expected_count
                    and all(row["pass"] for row in zones.values()),
        }

    k13_rows = [row for row in residue_rows if row["gene"] == "pfk13"]
    covered_codons = sorted({int(row["codon"]) for row in k13_rows})
    tier_results = {}
    for tier, changes in (("validated", WHO_VALIDATED), ("candidate", WHO_CANDIDATES)):
        tier_results[tier] = {}
        for change in changes:
            codon, target = int(change[1:-1]), change[-1]
            at_codon = [row for row in k13_rows if int(row["codon"]) == codon]
            tier_results[tier][change] = {
                "codon_covered": bool(at_codon),
                "n_called": int(at_codon[0]["n_called"]) if at_codon else None,
                "target_count": sum(int(row["count"]) for row in at_codon if row["residue"] == target),
            }
    nonreference = [
        {"label": row["label"], "codon": int(row["codon"]), "residue": row["residue"],
         "count": int(row["count"]), "n_called": int(row["n_called"])}
        for row in k13_rows if row["is_reference_residue"] == "False" and int(row["count"]) > 0
    ]
    facts = PATHS["canonical_facts"].read_text(encoding="utf-8")
    k13 = {
        "dated_reference_list": "WHO compendium v1.0, December 2025",
        "source_url": WHO_SOURCE,
        "source_checked_date": "2026-10-10",
        "residue_table_codons": covered_codons,
        "distinct_codons": len(covered_codons),
        "marker_tiers": tier_results,
        "complete_validated_and_candidate_coverage": all(
            item["codon_covered"] for tier in tier_results.values() for item in tier.values()
        ),
        "screened_resistance_marker_targets_not_detected": all(
            item["target_count"] == 0 for tier in tier_results.values() for item in tier.values()
        ),
        "nonreference_residue_calls": nonreference,
        "canonical_facts_asserts_all_reference": "pfk13 all reference? True" in facts,
        "all_reference_claim_supported": not nonreference,
        "factual_inconsistency": (
            "CANONICAL_FACTS.txt:80 says all pfk13 residues are reference, but "
            "codon_panel_residues.csv:55 reports one N458D call among 1866 called. "
            "N458D is not N458Y and does not contradict the screened-marker negative."
        ) if nonreference else None,
    }
    numerical_pass = sample_checks["pass"] and all(
        item["pass"] for item in list(marker_results.values()) + list(haplotype_results.values())
    )
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "Recompute aggregates from saved published protein-residue calls for the saved 1900 analysis IDs. "
            "No DNA/codon reconstruction, new genotypes, sequencing validation, or missing-pipeline rerun."
        ),
        "input_artifacts": {
            name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for name, path in PATHS.items()
        },
        "samples": sample_checks,
        "markers": marker_results,
        "haplotypes": haplotype_results,
        "k13": k13,
        "aggregate_count_checks_pass": numerical_pass,
        "limitations": [
            "step10_resistance_panel.py, step11_batch_confounding.py and step12_codon_panel.py are absent locally.",
            "The 47012/47012 concordance assertion cannot be independently recomputed without per-isolate reconstructed calls.",
            "Published calls provide no per-codon k13 or pfaat1 comparison; k13 checks are saved-output coverage checks only.",
            "Input sample identities come from evaluation/server_snapshot; there is no locally saved corrected genotype callset.",
        ],
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Saved:", OUT)
    print("Samples:", len(samples), "matched IDs; zone counts match:", sample_checks["pass"])
    print("Aggregate marker/haplotype counts pass:", numerical_pass)
    for name, item in haplotype_results.items():
        print(name, str(item["count"]) + "/" + str(item["n_complete"]), "pass:", item["pass"])
    for name, item in marker_results.items():
        print(name, str(item["count"]) + "/" + str(item["n_called"]), "pass:", item["pass"])
    print("WHO k13 marker coverage complete:", k13["complete_validated_and_candidate_coverage"])
    print("Screened k13 marker targets not detected:", k13["screened_resistance_marker_targets_not_detected"])
    print("Canonical all-reference assertion supported:", k13["all_reference_claim_supported"])
    return 0 if numerical_pass and k13["complete_validated_and_candidate_coverage"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
