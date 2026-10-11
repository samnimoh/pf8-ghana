#!/usr/bin/env python3
"""Seal review evidence with input identities, scope and a final source-drift check."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import runpy

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
# Anchor shared helper discovery to this script so Python -I works from any cwd.
GIT = runpy.run_path(str(ROOT / 'tools' / 'git_runtime.py'))['resolve_git']()


def identity(p):
    if not p.exists():
        return {"path": str(p), "bytes": None, "sha256": None}
    b = p.read_bytes()
    return {"path": str(p), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def git(*args):
    return subprocess.check_output([GIT, *args], cwd=ROOT).decode()


def main():
    inventory = json.loads((OUT / "change_inventory.json").read_text())
    checks = json.loads((OUT / "revision_validation.json").read_text())
    builds = json.loads((OUT / "build_tools_validation.json").read_text())
    independent = json.loads((OUT / "independent_build_review.json").read_text())
    sources = {r["path"]: {k: r.get(k) for k in ("path", "bytes", "sha256")} for r in inventory["files"] + inventory["new_source_files"]}
    added_project_paths = [p for p in git("diff", "--name-only", "--diff-filter=A", "e590ba7", "1afaf4b").splitlines() if not p.startswith("verification_review_round5/")]
    for rel in added_project_paths:
        r = identity(ROOT / rel)
        sources[r["path"]] = r
    drift = [p for p, r in sources.items() if identity(Path(p))["sha256"] != r["sha256"]]
    input_drift = [v["path"] for v in checks["input_identities"].values() if identity(Path(v["path"]))["sha256"] != v["sha256"]]
    helper_drift = [v["path"] for v in builds["sources"] + independent["source_identities"] if identity(Path(v["path"]))["sha256"] != v["sha256"]]
    tracked_edits = git("diff", "--name-only", "HEAD").splitlines()
    assert all(p.startswith("verification_review_round5/") for p in tracked_edits), tracked_edits
    assert not drift and not input_drift and not helper_drift, (drift, input_drift, helper_drift)
    assert all(checks["assertions"].values()) and all(builds["confirmed_findings"].values())
    manifest_path = OUT / "review_manifest.json"
    link_targets = []
    for target in re.findall(r"\]\((/[^)]+)\)", (OUT / "REVIEW_LATEST_REVISION.md").read_text()):
        target = re.sub(r":\d+$", "", target)
        p = Path(target)
        assert p.exists() or p == manifest_path, str(p)
        link_targets.append(str(p))
    visual = []
    selections = {"article": [1, 5, 7, 13, 15], "manuscript": [12, 47, 79, 83, 90, 111, 144], "supplement": [2, 48, 112]}
    for name, pages in selections.items():
        for page in pages:
            visual.append({"document": name, "page": page, "visually_inspected": True,
                           **identity(Path("/private/tmp/pf8_review_round5_latest") / name / f"page-{page}.png")})
    assert len(visual) == 15 and all(v["sha256"] for v in visual)
    artifacts = [identity(p) for p in sorted(OUT.rglob("*")) if p.is_file() and p != manifest_path and "__pycache__" not in p.parts]
    record = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "review_report": str(OUT / "REVIEW_LATEST_REVISION.md"),
        "baseline_review_manifest": inventory["baseline_review_manifest"],
        "baseline_review_utc": inventory["baseline_review_utc"],
        "git_reviewed_head": git("rev-parse", "HEAD").strip(),
        "git_history": git("log", "--format=%H%x09%aI%x09%s").splitlines(),
        "git_status_at_finalization": git("status", "--short").splitlines(),
        "tracked_local_edits_are_only_current_review": True,
        "scientific_sources_outputs_and_prior_reviews_unchanged_during_review": not drift,
        "input_drift": input_drift,
        "helper_source_drift": helper_drift,
        "known_round4_files_compared": inventory["known_files_compared"],
        "changes_since_round4": inventory["changed_files"],
        "new_scientific_correction_files": inventory["new_source_files"],
        "new_project_instruction_and_helper_paths": added_project_paths,
        "current_source_and_baseline_artifact_identities": list(sources.values()),
        "artifact_hashes": artifacts,
        "targeted_assertions": {"passed": sum(checks["assertions"].values()), "total": len(checks["assertions"]), "meaning": checks["assertion_meaning"]},
        "document_helper_synthetic_findings": builds["confirmed_findings"],
        "pdf_comparison": {"all_pages_checked": 413, "counts": [18, 197, 198], "method": "Full page text comparison after whitespace and page-footer normalization", "layout_certified_all_pages": False},
        "selected_visual_review": visual,
        "absolute_report_link_targets": link_targets,
        "scope_limits": [
            "No scientific pipeline or biological audit script was executed; remote operations read existing files and compute checksums.",
            "Document helper tests used disposable synthetic or copied Word source files; no original deliverable was overwritten.",
            "Server output identities and a cohort log strengthen provenance, but do not authenticate exact historical generating command and revision or complete missing raw inputs.",
            "Existing Lean source and validation are unchanged; no implementation-refinement proof or new Lean build was performed.",
            "The current review files were partly captured by a concurrent project commit; final report and validation refinements follow that commit and were not committed by this reviewer.",
            "Temporary page images have recorded hashes; supplied permanent PDFs are the source for cited page locations."
        ],
        "primary_reference_links": ["https://www.nature.com/articles/nrg2611", "https://journals.plos.org/plosgenetics/article?id=10.1371/journal.pgen.1002967"]
    }
    manifest_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    assert all(Path(p).exists() for p in link_targets)
    print(json.dumps({"report": record["review_report"], "source_identities": len(sources), "artifacts": len(artifacts), "source_drift": drift, "verified_links": len(link_targets), "visually_inspected_pages": len(visual)}))


if __name__ == "__main__":
    main()
