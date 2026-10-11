#!/usr/bin/env python3
"""Check saved article statistics without rerunning scientific inference.

Uses only Python's standard library. Passed assertions confirm the identified
inconsistencies and expected-cell arithmetic; they do not certify the article.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import platform
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).with_name("article_statistics_validation.json")
SOURCES = {
    "article": "article/Pf8_Ghana_article.docx",
    "article_markdown": "article/article.md",
    "canonical_facts": "article/CANONICAL_FACTS_FOR_ARTICLE.md",
    "ordination_4905": "evaluation/server_snapshot/results/dimred_comparison.csv",
    "ordination_1900": "corrected/dimred_comparison_qcset.csv",
    "analysis_samples": "evaluation/server_snapshot/interim/analysis_samples.csv",
    "pre_Fws_QC": "evaluation/server_snapshot/results/sample_qc_full.csv",
    "residues": "corrected/codon_panel_residues.csv",
}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NUMBER = r"-?(?:\d+(?:\.\d+)?|\.\d+)"


def read_csv(data):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


def text(node):
    return "".join(part.text or "" for part in node.iter(W + "t")).strip()


def rounded_match(literal, saved):
    decimals = len(literal.split(".", 1)[1]) if "." in literal else 0
    return round(float(saved), decimals) == float(literal)


def main():
    blobs = {key: (ROOT / rel).read_bytes() for key, rel in SOURCES.items()}
    hashes = {key: {"path": str(ROOT / SOURCES[key]), "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "md5": hashlib.md5(data).hexdigest()}
              for key, data in blobs.items()}
    tables = {key: read_csv(blobs[key]) for key in SOURCES if SOURCES[key].endswith(".csv")}
    document = ET.fromstring(zipfile.ZipFile(io.BytesIO(blobs["article"])).read("word/document.xml"))
    body = document.find(W + "body")
    paragraphs = [(i + 1, text(node)) for i, node in enumerate(body) if node.tag == W + "p"]
    body_index, ordination = next((i, value) for i, value in paragraphs
                                  if value.startswith("Three ordinations of the published"))
    reports = []
    for method, pattern in [
        ("UMAP", rf"UMAP achieved a trustworthiness of ({NUMBER}) and a Spearman correlation of ({NUMBER})"),
        ("t-SNE", rf"t-SNE reached ({NUMBER}) and ({NUMBER})"),
        ("PCoA", rf"PCoA reached ({NUMBER}) and ({NUMBER})"),
    ]:
        match = re.search(pattern, ordination)
        if not match:
            raise ValueError(f"Cannot identify {method} article metrics.")
        reports.extend((method, metric, value) for metric, value in zip(
            ("trustworthiness", "distance_spearman"), match.groups()))
    silhouettes = re.search(
        rf"({NUMBER}) on the original distances, ({NUMBER}) for UMAP, ({NUMBER}) for t-SNE and ({NUMBER}) for PCoA",
        ordination)
    if not silhouettes:
        raise ValueError("Cannot identify article silhouette metrics.")
    reports.extend((method, "silhouette_by_zone", value) for method, value in zip(
        ("original distances", "UMAP", "t-SNE", "PCoA"), silhouettes.groups()))
    old = {row["method"]: row for row in tables["ordination_4905"]}
    new = {row["method"]: row for row in tables["ordination_1900"]}
    metric_comparisons = [
        {"method": method, "metric": metric, "article_literal": value,
         "saved_4905": float(old[method][metric]), "saved_1900": float(new[method][metric]),
         "matches_4905_at_reported_precision": rounded_match(value, old[method][metric]),
         "matches_1900_at_reported_precision": rounded_match(value, new[method][metric])}
        for method, metric, value in reports]

    composition = None
    caption = ""
    for i, node in enumerate(body):
        if node.tag == W + "p" and text(node):
            caption = text(node)
        elif node.tag == W + "tbl":
            rows = [[text(cell) for cell in row.findall(W + "tc")]
                    for row in node.findall(W + "tr")]
            if rows and "Polyclonal fraction" in rows[0]:
                composition = {"body_child_index": i + 1, "caption": caption,
                               "header": rows[0], "rows": rows[1:]}
                break
    if composition is None:
        raise ValueError("Cannot identify article composition table.")
    samples = tables["analysis_samples"]
    qc = tables["pre_Fws_QC"]
    zones = []
    for row in composition["rows"]:
        label = row[0]
        zone = label.replace("Deciduous", "Decidous")
        analysed = [sample for sample in samples if sample["zone"] == zone]
        before = [sample for sample in qc if sample["zone"] == zone]
        after_count = sum(float(sample["Fws"]) < .95 for sample in analysed)
        before_count = sum(float(sample["Fws"]) < .95 for sample in before)
        stated_n = int(row[1].replace(",", ""))
        stated_fraction = row[6]
        zones.append({"zone": label, "table_n": stated_n,
                      "analysis_n": len(analysed), "pre_Fws_QC_n": len(before),
                      "table_polyclonal_fraction": float(stated_fraction),
                      "analysis_polyclonal_count": after_count,
                      "analysis_polyclonal_fraction": after_count / len(analysed),
                      "pre_Fws_QC_polyclonal_count": before_count,
                      "pre_Fws_QC_polyclonal_fraction": before_count / len(before),
                      "table_n_matches_analysis": stated_n == len(analysed),
                      "fraction_matches_QC_at_reported_precision": rounded_match(
                          stated_fraction, before_count / len(before)),
                      "fraction_matches_analysis_at_reported_precision": rounded_match(
                          stated_fraction, after_count / len(analysed))})

    expected = []
    targets = {("pfdhps", "540", "E"), ("pfdhps", "581", "G"), ("pfmdr1", "1246", "Y")}
    zone_prefixes = ("Coastal_savanna", "Decidous_forest", "Guinea_savanna", "Transitional_zone")
    for row in tables["residues"]:
        if (row["gene"], row["codon"], row["residue"]) not in targets:
            continue
        n, carriers = int(row["n_called"]), int(row["count"])
        cells = []
        for zone in zone_prefixes:
            nz = int(row[zone + "_n"])
            observed_carriers = round(nz * float(row[zone + "_freq"]))
            expected_carriers = nz * carriers / n
            cells.append({"zone": zone, "n_called": nz,
                          "observed_carriers": observed_carriers,
                          "observed_noncarriers": nz - observed_carriers,
                          "expected_carriers": expected_carriers,
                          "expected_noncarriers": nz - expected_carriers})
        all_expected = [value for cell in cells for value in
                        (cell["expected_carriers"], cell["expected_noncarriers"])]
        expected.append({"gene": row["gene"], "codon": int(row["codon"]),
                         "label": row["label"], "n_called": n, "carriers": carriers,
                         "saved_asymptotic_p_value": float(row["chi2_p"]),
                         "cells": cells, "minimum_expected": min(all_expected),
                         "cells_expected_below_5": sum(value < 5 for value in all_expected),
                         "cells_expected_below_1": sum(value < 1 for value in all_expected),
                         "n_margins_reconcile": sum(cell["n_called"] for cell in cells) == n,
                         "carrier_margins_reconcile": sum(cell["observed_carriers"] for cell in cells) == carriers})

    assertions = {
        "article_ordination_claims_1900": "for the 1,900 isolates" in ordination,
        "all_ten_article_metrics_match_4905_output": len(metric_comparisons) == 10 and all(
            item["matches_4905_at_reported_precision"] for item in metric_comparisons),
        "none_of_ten_article_metrics_match_1900_output": not any(
            item["matches_1900_at_reported_precision"] for item in metric_comparisons),
        "table_caption_claims_analysis_set": "Composition of the analysis set" in composition["caption"],
        "all_four_table_counts_match_1900_cohort": len(zones) == 4 and all(
            item["table_n_matches_analysis"] for item in zones),
        "all_four_fractions_match_QC_not_analysis": all(
            item["fraction_matches_QC_at_reported_precision"] and
            not item["fraction_matches_analysis_at_reported_precision"] for item in zones),
        "all_analysis_samples_are_nonpolyclonal_at_cut": len(samples) == 1900 and all(
            float(sample["Fws"]) >= .95 for sample in samples),
        "three_sparse_marker_margins_reconcile": len(expected) == 3 and all(
            item["n_margins_reconcile"] and item["carrier_margins_reconcile"] for item in expected),
        "three_markers_have_three_expected_cells_below5_and_one_below1": all(
            item["cells_expected_below_5"] == 3 and item["cells_expected_below_1"] == 1 for item in expected),
    }
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "checker_path": str(Path(__file__).resolve()),
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runtime": {"executable": sys.executable,
                    "resolved_executable": str(Path(sys.executable).resolve()),
                    "version": sys.version, "platform": platform.platform(),
                    "libraries": {"csv": csv.__file__, "math": getattr(math, "__file__", "builtin"),
                                  "xml.etree.ElementTree": ET.__file__, "zipfile": zipfile.__file__},
                    "third_party_dependencies": []},
        "inputs": hashes,
        "assertion_meaning": "Passing confirms the recorded inconsistency/arithmetic, not statistical validity of the article.",
        "assertions": assertions,
        "ordination": {"article_body_child_index": body_index, "article_paragraph": ordination,
                       "matching_rule": "CSV values rounded to decimal places printed in article",
                       "comparisons": metric_comparisons},
        "table_1": {**composition, "cohort_comparisons": zones,
                    "zone_alias": "Article 'Deciduous forest' maps to saved CSV 'Decidous forest'."},
        "sparse_expected_cells": {"method": "Expected carrier count = zone called n * total carriers / total called n; noncarriers by subtraction.",
                                  "markers": expected,
                                  "p_values_recomputed": False,
                                  "interpretation": "Sparse expected cells raise an asymptotic-approximation concern; this checker does not establish the exact p-values."},
        "marker_test_inventory": {"rows_with_numeric_p_values": sum(bool(row["chi2_p"]) for row in tables["residues"]),
                                  "distinct_tested_codons": len({(row["gene"], row["codon"]) for row in tables["residues"] if row["chi2_p"]}),
                                  "note": "Includes complementary residue tests; this inventory does not define a multiplicity family."},
        "limits": ["No inferential pipeline rerun, installation, network call or scientific source edit.",
                   "Local snapshot checks do not establish remote final input byte identity.",
                   "Sparse-cell evidence is arithmetic only; no exact or resampling test was run."]}
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{sum(assertions.values())}/{len(assertions)} evidence assertions passed; {OUT}")
    return 0 if all(assertions.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
