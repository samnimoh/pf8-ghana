#!/usr/bin/env python3
"""Check archived audit-log arithmetic and static selection scope, without network access.

Uses only Python's standard library. Does not import or execute any scientific/audit
script, reconstruct residues, inspect remote data, or modify pipeline sources.
"""
from __future__ import annotations

import ast
import collections
import csv
import datetime
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = Path(__file__).with_name("static_audit_log_validation.json")


def load(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def identity(relative: str) -> dict:
    p = ROOT / relative
    data = p.read_bytes()
    return {"path": str(p), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def count_after(text: str, pattern: str) -> int:
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        raise ValueError(f"Missing expected log field: {pattern}")
    return int(match.group(1))


def main() -> None:
    domain = load("provenance_final/audit_logs/domain.log")
    coverage = load("provenance_final/audit_logs/coverage.log")
    source = load("provenance_final/audit_scripts/check_domain.py")
    with (ROOT / "corrected/codon_panel_residues.csv").open(newline="", encoding="utf-8") as stream:
        residues = list(csv.DictReader(stream))
    panel = {(r["contig"], int(p)) for r in residues for p in r["positions"].split(";")}
    codons = {(r["gene"], int(r["codon"])): int(r["n_variant_records"]) for r in residues}

    n_indel = count_after(domain, r"^\(1\).*length-changing ALT\s*:\s*(\d+)")
    n_mnp = count_after(domain, r"^\(2\).*multi-base REF.*:\s*(\d+)")
    n_span = count_after(domain, r"^\(4\).*off-anchor records.*:\s*(\d+)")
    metadata = [(int(m[1]), m[2], int(m[3])) for m in re.finditer(
        r"^\s+row (\d+) (\S+):(\d+) REF=", domain, re.MULTILINE)]

    # The source emits indel + mnp + span metadata in this order. Verify that
    # premise statically before partitioning the captured stdout accordingly.
    tree = ast.parse(source)
    print_order = any(isinstance(n, ast.For) and ast.unparse(n.iter) ==
                      "indel + mnp + [a for a, _ in span]" for n in ast.walk(tree))
    if not print_order or len(metadata) != n_indel + n_mnp + n_span:
        raise ValueError("Source/log metadata ordering or category counts changed")
    spans = metadata[n_indel + n_mnp:]
    meta_by_row = {row: (contig, position) for row, contig, position in metadata}
    spans_at_panel = [row for row, contig, position in spans if (contig, position) in panel]
    spans_off_panel = [row for row, contig, position in spans if (contig, position) not in panel]

    calls = {int(m[1]): {"homozygous_alt": int(m[2]), "mixed": int(m[3])}
             for m in re.finditer(r"^\s+row (\d+): homozygous-ALT carriers=(\d+)\s+mixed=(\d+)",
                                  domain, re.MULTILINE)}
    selected = {row: value for row, value in calls.items() if meta_by_row[row] in panel}
    off_anchor = {row: value for row, value in calls.items() if meta_by_row[row] not in panel}
    hom_sum = sum(r["homozygous_alt"] for r in calls.values())
    mixed_sum = sum(r["mixed"] for r in calls.values())
    selected_mixed = sum(r["mixed"] for r in selected.values())
    off_anchor_mixed = sum(r["mixed"] for r in off_anchor.values())

    distribution_match = re.search(r"carrying a record:\s*(\{[^\n]+\})", coverage)
    if distribution_match is None:
        raise ValueError("Coverage-log distribution missing")
    distribution = ast.literal_eval(distribution_match[1])
    csv_distribution = dict(sorted(collections.Counter(codons.values()).items()))
    n_positions = count_after(coverage, r"^panel positions\s*:\s*(\d+)")
    with_records = count_after(coverage, r"^positions WITH >=1 record\s*:\s*(\d+)")
    without_records = count_after(coverage, r"^positions with NO record\s*:\s*(\d+)")
    total_records = count_after(coverage, r"^total records at panel pos\s*:\s*(\d+)")
    record_free = count_after(coverage, r"^codons with all 3 positions record-free:\s*(\d+)")

    checks = {
        "source_metadata_print_order_matches_parser": print_order,
        "metadata_count_matches_logged_categories": len(metadata) == n_indel + n_mnp + n_span,
        "unique_domain_metadata_rows_match_genotype_rows": set(meta_by_row) == set(calls),
        "genotype_rows_match_logged_count": len(calls) == count_after(domain, r"^rows needing genotype check:\s*(\d+)"),
        "homozygous_alt_sum_matches_logged_total": hom_sum == count_after(domain, r"^\s*TOTAL homozygous-ALT carriers.*:\s*(\d+)"),
        "mixed_sum_matches_logged_total": mixed_sum == count_after(domain, r"^\s*TOTAL mixed.*:\s*(\d+)"),
        "mixed_partition_reconciles": selected_mixed + off_anchor_mixed == mixed_sum,
        "span_partition_reconciles": len(spans_at_panel) + len(spans_off_panel) == n_span,
        "panel_position_count_matches_saved_csv": len(panel) == n_positions,
        "coverage_position_counts_reconcile": with_records + without_records == n_positions,
        "coverage_distribution_codons_match_saved_csv": sum(distribution.values()) == len(codons),
        "coverage_distribution_weighted_positions_reconcile": sum(k * v for k, v in distribution.items()) == with_records,
        "saved_csv_record_distribution_matches_logged_distribution": csv_distribution == distribution,
        "saved_csv_record_total_matches_logged_total": sum(codons.values()) == total_records,
        "record_free_count_matches_saved_csv": sum(v == 0 for v in codons.values()) == record_free,
    }
    inputs = [
        "provenance_final/audit_scripts/check_domain.py",
        "provenance_final/audit_scripts/check_coverage.py",
        "provenance_final/audit_scripts/README.md",
        "provenance_final/audit_logs/domain.log",
        "provenance_final/audit_logs/coverage.log",
        "provenance_final/scripts/step12_codon_panel.py",
        "provenance_final/VERIFICATION_NOTES.md",
        "corrected/codon_panel_residues.csv",
    ]
    result = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "Static source/log inspection and local aggregate arithmetic; no scientific or audit script execution, network access, sequence reconstruction or pipeline edits.",
        "status": "completed_with_findings" if all(checks.values()) else "consistency_check_failed",
        "checks": checks,
        "check_summary": {"passed": sum(checks.values()), "total": len(checks)},
        "domain": {
            "printed_metadata_entries_including_repeats": len(metadata),
            "unique_metadata_records": len(meta_by_row),
            "logged_span_records": n_span,
            "span_records_anchored_at_panel_positions": len(spans_at_panel),
            "span_records_anchored_outside_panel": len(spans_off_panel),
            "span_record_rows_already_at_panel": spans_at_panel,
            "homozygous_alt_record_level_call_sum": hom_sum,
            "mixed_record_level_call_sum": mixed_sum,
            "mixed_calls_at_records_selected_by_anchor_rule": selected_mixed,
            "mixed_calls_at_records_outside_anchor_selection": off_anchor_mixed,
            "off_anchor_rows_with_mixed_calls": [{"row": row, "mixed": value["mixed"]}
                for row, value in off_anchor.items() if value["mixed"]],
            "count_unit": "Record-level calls, not counts of distinct isolates.",
        },
        "callability": {
            "panel_positions": n_positions, "positions_with_records": with_records,
            "positions_without_records": without_records, "codons": len(codons),
            "logged_codons_by_number_of_recorded_positions": distribution,
            "saved_csv_codons_by_n_variant_records": csv_distribution,
            "record_free_codons": record_free,
            "interpretation": "Saved aggregate record counts match the logged position distribution. This does not independently measure per-isolate coverage or inspect remote variant records.",
        },
        "findings": [
            {"id": "span_category_label", "evidence": "The logged span category contains 19 records, but 3 anchor at panel positions, leaving 16 genuinely off-anchor records.",
             "source": "check_domain.py:83-88", "published_result_error_proven": False},
            {"id": "mixed_exclusion_scope", "evidence": "Four of 62 logged mixed record-level calls occur outside step12's anchor-position selection. The blanket statement that all 62 are excluded by its mixed-call rule is not established.",
             "source": "step12_codon_panel.py:282-285; check_domain.py:130", "published_result_error_proven": False},
        ],
        "limitations": [
            "Captured logs are evidence supplied by another agent; this checker does not authenticate their generation from the archived audit scripts or exact remote inputs.",
            "Anchor membership is compared against positions in the saved residue CSV and the stated source selection rule; it does not prove actual per-isolate downstream effects.",
            "No conclusion is drawn that published numerical frequencies are incorrect. Per-isolate input/output evidence remains necessary to assess the impact.",
            "Passing these checks establishes arithmetic consistency and exposes category/scope errors, not end-to-end reproducibility or formal verification.",
        ],
        "input_identities": [identity(p) for p in inputs],
        "checker_identity": identity(str(Path(__file__).relative_to(ROOT))),
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "checks": result["check_summary"],
                      "off_anchor_span_records": len(spans_off_panel), "off_anchor_mixed_calls": off_anchor_mixed}))


if __name__ == "__main__":
    main()
