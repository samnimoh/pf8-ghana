#!/usr/bin/env python3
"""Review aggregate document consistency and saved-file identities only.

Does not execute project scripts, query biological stores, or regenerate inference.
Evidence assertions confirm fixes or remaining findings, not scientific certification.
"""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SOURCES = {
    "article": "article/Pf8_Ghana_article.docx",
    "article_markdown": "article/article.md",
    "canonical_facts": "article/CANONICAL_FACTS_FOR_ARTICLE.md",
    "manuscript": "Pf8_Ghana_manuscript_REVISED.docx",
    "supplement": "article/Additional_file_1.docx",
    "notes": "provenance_final/VERIFICATION_NOTES.md",
    "audit_readme": "provenance_final/audit_scripts/README.md",
    "old_ordination": "evaluation/server_snapshot/results/dimred_comparison.csv",
    "newly_named_ordination": "corrected/dimred_comparison_analysisset.csv",
    "corrected_ordination": "corrected/dimred_comparison_qcset.csv",
    "old_ordination_log": "evaluation/server_snapshot/logs/step03_dimred.log",
    "analysis_samples": "evaluation/server_snapshot/interim/analysis_samples.csv",
    "pre_Fws_QC": "evaluation/server_snapshot/results/sample_qc_full.csv",
    "corrected_figure": "corrected/dimred_comparison_zone_qcset.png",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def text(node):
    return "".join(p.text or "" for p in node.iter(W + "t")).strip()


def parse_document(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        tree = ET.fromstring(archive.read("word/document.xml"))
        media = [{"member": n, "sha256": digest(archive.read(n))}
                 for n in archive.namelist() if n.startswith("word/media/")]
    body = tree.find(W + "body")
    paragraphs = [text(p) for p in body if p.tag == W + "p"]
    pairs, caption = [], ""
    for index, node in enumerate(body):
        if node.tag == W + "p" and text(node):
            caption = text(node)
        elif node.tag == W + "tbl":
            rows = [[text(cell) for cell in row.findall(W + "tc")]
                    for row in node.findall(W + "tr")]
            following = next((text(p) for p in list(body)[index + 1:]
                              if p.tag == W + "p" and text(p)), "")
            pairs.append({"caption": caption, "following_paragraph": following, "rows": rows})
    return {"paragraphs": paragraphs, "tables": pairs, "media": media}


def read_csv(data):
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


def rounded_match(literal, value):
    digits = len(literal.split(".", 1)[1]) if "." in literal else 0
    return round(float(value), digits) == float(literal)


def main():
    blobs = {key: (ROOT / rel).read_bytes() for key, rel in SOURCES.items()}
    inputs = {key: {"path": str(ROOT / SOURCES[key]), "bytes": len(data),
                    "sha256": digest(data)} for key, data in blobs.items()}
    docs = {key: parse_document(blobs[key]) for key in ("article", "manuscript", "supplement")}
    article = "\n".join(docs["article"]["paragraphs"])
    main_text = "\n".join(docs["manuscript"]["paragraphs"])
    supp_text = "\n".join(docs["supplement"]["paragraphs"])
    notes = blobs["notes"].decode().replace("**", "")
    readme = blobs["audit_readme"].decode()
    old = {r["method"]: r for r in read_csv(blobs["old_ordination"])}
    corrected = {r["method"]: r for r in read_csv(blobs["corrected_ordination"])}
    ordinal = next(p for p in docs["article"]["paragraphs"]
                   if p.startswith("Three ordinations of the published"))
    number = r"-?(?:\d+(?:\.\d+)?|\.\d+)"
    reports = []
    for method, pattern in [
        ("UMAP", rf"UMAP achieved a trustworthiness of ({number}) and a Spearman correlation of ({number})"),
        ("t-SNE", rf"t-SNE reached ({number}) and ({number})"),
        ("PCoA", rf"PCoA reached ({number}) and ({number})"),
    ]:
        match = re.search(pattern, ordinal)
        if match is None:
            raise ValueError(method)
        reports.extend((method, metric, value) for metric, value in zip(
            ("trustworthiness", "distance_spearman"), match.groups()))
    silhouettes = re.search(
        rf"({number}) on the original distances, ({number}) for UMAP, ({number}) for t-SNE and ({number}) for PCoA", ordinal)
    reports.extend((method, "silhouette_by_zone", value) for method, value in zip(
        ("original distances", "UMAP", "t-SNE", "PCoA"), silhouettes.groups()))
    comparisons = [{"method": method, "metric": metric, "article_literal": literal,
                    "saved_4905": float(old[method][metric]),
                    "saved_1900": float(corrected[method][metric]),
                    "matches_4905": rounded_match(literal, old[method][metric]),
                    "matches_1900": rounded_match(literal, corrected[method][metric])}
                   for method, metric, literal in reports]

    composition = next(t for t in docs["article"]["tables"]
                       if t["rows"] and any("Polyclonal fraction" in c for c in t["rows"][0]))
    samples, qc = [read_csv(blobs[key]) for key in ("analysis_samples", "pre_Fws_QC")]
    zones = []
    for row in composition["rows"][1:]:
        zone = row[0].replace("Deciduous", "Decidous")
        after = [r for r in samples if r["zone"] == zone]
        before = [r for r in qc if r["zone"] == zone]
        reported = re.fullmatch(r"([\d.]+)\s*\(n\s*=\s*([\d,]+)\)", row[6])
        if reported is None:
            raise ValueError(row[6])
        f = sum(float(r["Fws"]) < .95 for r in before) / len(before)
        zones.append({"zone": row[0], "reported_analysis_n": int(row[1].replace(",", "")),
                      "actual_analysis_n": len(after), "reported_QC_n": int(reported[2].replace(",", "")),
                      "actual_QC_n": len(before), "reported_QC_fraction": reported[1],
                      "actual_QC_fraction": f,
                      "all_analysis_Fws_at_least_095": all(float(r["Fws"]) >= .95 for r in after),
                      "counts_correct": int(row[1].replace(",", "")) == len(after)
                          and int(reported[2].replace(",", "")) == len(before),
                      "fraction_correct_at_printed_precision": rounded_match(reported[1], f)})

    captions = {kind: [re.match(rf"^{kind}\s+(S\d+[a-z]?)\.", p)[1]
                       for p in docs["supplement"]["paragraphs"]
                       if re.match(rf"^{kind}\s+(S\d+[a-z]?)\.", p)]
                for kind in ("Table", "Figure")}
    references = {kind: sorted(set(re.findall(rf"\b{kind}\s+(S\d+[a-z]?)\b", supp_text)))
                  for kind in ("Table", "Figure")}
    dangling = {kind: [r for r in values if r not in captions[kind]]
                for kind, values in references.items()}
    s24 = next(t for t in docs["supplement"]["tables"]
               if t["following_paragraph"].startswith("Table S24."))
    s24_metrics = []
    for row in s24["rows"][1:]:
        name, method = row[0].rsplit(", ", 1)
        metric = {"Silhouette by zone": "silhouette_by_zone", "Trustworthiness": "trustworthiness",
                  "Distance Spearman rho": "distance_spearman"}[name]
        s24_metrics.append({"method": method, "metric": metric,
                            "printed_4905": row[1], "printed_1900": row[2],
                            "matches_old": rounded_match(row[1], old[method][metric]),
                            "matches_corrected": rounded_match(row[2], corrected[method][metric])})
    figure_matches = [m for m in docs["article"]["media"]
                      if m["sha256"] == inputs["corrected_figure"]["sha256"]]
    inventory = json.loads((OUT / "change_inventory.json").read_text())
    unchanged_scientific = [r for r in inventory["files"]
                            if any(token in r["path"] for token in
                                   ("/provenance_final/scripts/", "/provenance_final/audit_logs/",
                                    "/corrected/", "/verification_audit/"))]
    statements = {
        "article_ordination_explicitly_claims_1900": "for the 1,900 isolates" in ordinal,
        "all_ten_article_metrics_match_old_4905_csv": len(comparisons) == 10 and all(r["matches_4905"] for r in comparisons),
        "no_article_metric_matches_corrected_1900_csv": not any(r["matches_1900"] for r in comparisons),
        "newly_named_analysisset_csv_is_byte_identical_to_old_csv": blobs["newly_named_ordination"] == blobs["old_ordination"],
        "saved_old_run_log_explicitly_records_4905_matrix_and_output_path":
            "Ghana submatrix (4905, 4905)" in blobs["old_ordination_log"].decode()
            and "Scores -> /media/biodataA/pf8/gyadu/results/dimred_comparison.csv" in blobs["old_ordination_log"].decode(),
        "article_embeds_corrected_cohort_figure_byte_for_byte": len(figure_matches) == 1,
        "table1_header_labels_QC_cohort": "Polyclonal fraction (QC cohort)" in composition["rows"][0],
        "table1_caption_explains_QC_analysis_difference": "pre-filter quality-control cohort of 4,905" in composition["caption"]
            and "polyclonal fraction is zero" in composition["caption"],
        "all_four_table1_counts_and_fractions_correct": len(zones) == 4 and all(r["counts_correct"] and r["fraction_correct_at_printed_precision"] for r in zones),
        "all_1900_analysis_samples_satisfy_Fws_cut": len(samples) == 1900 and all(r["all_analysis_Fws_at_least_095"] for r in zones),
        "supplement_table_captions_unique_and_sequential_S1_S52": captions["Table"] == [f"S{i}" for i in range(1,53)],
        "supplement_figure_captions_unique_and_sequential_S1_S23": captions["Figure"] == [f"S{i}" for i in range(1,24)],
        "supplement_singular_S_references_resolve": not any(dangling.values()),
        "supplement_S24_correctly_distinguishes_ten_old_and_corrected_metrics": len(s24_metrics) == 10
            and all(r["matches_old"] and r["matches_corrected"] for r in s24_metrics),
        "article_still_advertises_old_44_table_22_figure_ranges": "Figure S1–S22 and Table S1–S44" in article,
        "article_q_value_statement_conditional_on_calibration": "conditional on that null being adequately calibrated" in article,
        "article_sparse_tests_and_nominal_multiplicity_disclosed": "asymptotically unreliable" in article and "no correction was applied across the many residues tested" in article,
        "article_mantel_transform_corrected": "FST/(1 − FST)" in article and "logarithm of great-circle distance" in article,
        "article_excesshet_difference_corrected": "ExcessHet is zero at the second" in article,
        "notes_domain_count_and_mixed_call_scope_corrected": "16 are genuinely anchored outside the panel and three" in notes
            and "58 fall at records the reconstruction actually selects" in notes
            and "remaining four fall at genuinely off-anchor" in notes,
        "main_and_supplement_still_claim_19_off_anchor_and_all_62_excluded": all(
            "a further 19 records anchored outside the panel" in t
            and "62 mixed calls at these records are removed by the mixed-call rule regardless" in t
            for t in (main_text, supp_text)),
        "audit_readme_portability_statement_corrected": "not portable as written" in readme,
        "audit_readme_table_still_says_19_off_anchor": "19 off-anchor spanning records" in readme,
        "main_and_supplement_still_assert_conservative_final_calibration": all(
            "the direction of the error is known" in t for t in (main_text, supp_text)),
        "main_and_supplement_still_infer_two_directions_of_exchange": all(
            "two directions of exchange are statistically supported" in t for t in (main_text, supp_text)),
        "main_and_supplement_still_use_free_gene_flow": all("on top of free gene flow" in t for t in (main_text, supp_text)),
        "precision_accounting_now_qualified_in_main_supplement_and_notes": all(
            "twelve of them" in t and "full displayed precision" in t for t in (main_text, supp_text))
            and "twelve of\nthe fifteen" in notes and "does not identify a particular build" in notes,
        "older_notes_precision_claim_and_read_level_heading_still_present":
            "Every printed value, sentinels included" in notes and "confirmed genuine at read level" in notes,
        "article_archive_Doi_still_placeholder": "REPOSITORY DOI TO BE SUPPLIED" in article,
        "known_scientific_and_lean_artifacts_in_scope_unchanged": len(unchanged_scientific) > 0
            and not any(r["changed"] for r in unchanged_scientific),
    }
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "checker": {"path": str(Path(__file__).resolve()), "sha256": digest(Path(__file__).read_bytes())},
        "runtime": {"executable": sys.executable, "version": sys.version, "platform": platform.platform(),
                    "third_party_dependencies": []},
        "input_identities": inputs,
        "assertion_meaning": "Passing confirms the recorded fix or remaining finding; not a validity certificate.",
        "assertions": statements,
        "ordination": {"article_paragraph": ordinal, "reported_precision_comparisons": comparisons,
                       "alias_identity": {k: inputs[k] for k in ("old_ordination", "newly_named_ordination", "corrected_ordination")},
                       "figure_matches": figure_matches,
                       "limits": "Saved log establishes the archived cohort attribution, not authenticated final generating lineage."},
        "table1": {**composition, "cohort_comparisons": zones},
        "supplementary_numbering": {"captions": captions, "singular_references": references,
                                    "unresolved_singular_references": dangling,
                                    "scope": "Caption uniqueness/order and existence of singular S references; not an exhaustive semantic mapping of every plural/range reference."},
        "supplement_analysis_cohort_comparison_table": {"caption": s24["following_paragraph"],
                                                        "rows": s24["rows"], "metric_checks": s24_metrics},
        "known_unchanged_scientific_and_lean_files_checked": len(unchanged_scientific),
        "limits": ["No project script, remote audit, biological query or scientific inference was run.",
                   "Existing earlier numerical-check evidence is retained only where inputs are unchanged.",
                   "No claim is made that complete pipeline provenance or implementation proof exists."]}
    (OUT / "revision_validation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"passed": sum(statements.values()), "total": len(statements),
                      "failures": [k for k,v in statements.items() if not v],
                      "unchanged_scientific_and_lean_files": len(unchanged_scientific)}))
    return 0 if all(statements.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
