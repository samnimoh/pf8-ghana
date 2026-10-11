#!/usr/bin/env python3
"""Record completed review evidence, verify sources stayed stable, check links."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent


def identity(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    initial = json.loads((OUT / "change_inventory.json").read_text())
    expected = initial["files"] + initial["newly_observed_source_files"]
    changed_during = []
    current = []
    for record in expected:
        p = Path(record["path"])
        state = identity(p) if p.is_file() else {"path": str(p), "bytes": None, "sha256": None}
        current.append(state)
        if state["sha256"] != record["sha256"]:
            changed_during.append({"path": str(p), "initial_sha256": record["sha256"],
                                   "final_sha256": state["sha256"]})
    report_path = OUT / "REVIEW_LATEST_REVISION.md"
    report = report_path.read_text()
    links = []
    for target in re.findall(r"\]\((/[^)]+)\)", report):
        path = Path(re.sub(r":\d+$", "", target))
        links.append({"target": target, "exists": path.is_file()})
    conversions = json.loads((OUT / "render_conversion.json").read_text())
    images = []
    for conversion in conversions:
        for number in conversion["rasterized_review_pages"]:
            png = Path(conversion["fresh_pdf"]).parent / f"page-{number}.png"
            images.append({**identity(png), "document": conversion["label"],
                           "page": number, "visually_inspected": True})
    qa = {"generated_utc": datetime.now(timezone.utc).isoformat(),
          "images_inspected": images,
          "scope": "Fourteen selected page images; not an all-page certification of the long reports.",
          "findings": ["Article page 6 visibly supplies the corrected QC header and denominators.",
                       "Article page 7 visibly retains the older numerical ordination narrative beside the corrected cohort figure.",
                       "Article page 10 visibly supplies the conditional q-value interpretation and differentiated ExcessHet statement.",
                       "Article page 15 retains declaration and archive placeholders.",
                       "Supplement page 2 states sequential S1-S52 table and S1-S23 figure ranges.",
                       "Fresh main page 111 contains the narrower full-precision accounting.",
                       "Article page 1 strands the Background heading, and page 9 uses literal scientific-notation text."]}
    (OUT / "visual_review.json").write_text(json.dumps(qa, indent=2) + "\n")
    checks = json.loads((OUT / "revision_validation.json").read_text())
    renders = json.loads((OUT / "render_review.json").read_text())
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "review_report": str(report_path),
        "baseline_review_manifest": initial["baseline_review"],
        "baseline_review_utc": initial["baseline_review_utc"],
        "scope": "Review of changed documents, aggregate saved-file consistency, source identities, and selected rendered presentation. No scientific pipeline, remote biological query, inference, or new Lean compilation.",
        "known_files_compared": initial["known_files_compared"],
        "changed_source_paths": [r["path"] for r in initial["changed_files"]],
        "newly_observed_source_files": initial["newly_observed_source_files"],
        "source_files_stable_through_review": not changed_during,
        "source_files_rechecked": len(expected),
        "files_changed_during_review": changed_during,
        "current_source_and_baseline_artifact_identities": current,
        "runtime": {"python": sys.executable, "version": sys.version, "platform": platform.platform()},
        "revision_evidence_assertions": {"passed": sum(checks["assertions"].values()),
                                         "total": len(checks["assertions"]),
                                         "meaning": checks["assertion_meaning"]},
        "rendered_page_counts": {c["label"]: {"supplied": c["supplied_pages"], "fresh": c["fresh_pages"]}
                                 for c in renders["comparisons"]},
        "images_visually_inspected": len(images),
        "source_content_changed_by_review": False,
        "existing_review_reports_preserved": True,
        "report_link_validation": links,
        "artifact_hashes": [identity(p) for p in sorted(OUT.iterdir())
                            if p.is_file() and p.name != "review_manifest.json"],
        "fresh_conversion_pdf_hashes": [identity(Path(c["fresh_pdf"])) for c in conversions],
        "limitations": ["Lean validation and older numerical checks were retained with their original documented scope where inputs are unchanged.",
                        "The current review does not authenticate a complete final generating lineage.",
                        "Supplementary reference checking covers caption numbering and singular S-reference existence, not exhaustive semantic cross-reference mapping."]}
    (OUT / "review_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    failures = [x["target"] for x in links if not x["exists"]]
    print(json.dumps({"stable_source_files": len(expected) - len(changed_during), "source_count": len(expected),
                      "changes_during_review": changed_during, "link_failures": failures,
                      "evidence_assertions": manifest["revision_evidence_assertions"],
                      "images_inspected": len(images), "report_words": len(report.split()),
                      "report": str(report_path)}))
    return 1 if changed_during or failures or not all(checks["assertions"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
