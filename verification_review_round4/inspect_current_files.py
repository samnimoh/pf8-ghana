#!/usr/bin/env python3
"""Snapshot changed documents and compare their content with the last review."""
import difflib
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def identity(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    prior = ROOT / "verification_review_round3"
    inv = json.loads((prior / "change_inventory.json").read_text())
    manifest = json.loads((prior / "review_manifest.json").read_text())
    known = {x["path"]: x.get("current_sha256", x.get("sha256")) for x in inv["files"] + inv["new_source_files"]}
    known.update({x["path"]: x["sha256"] for x in manifest["artifact_hashes"]})
    comparisons = []
    for path, old in sorted(known.items()):
        p = Path(path)
        current = identity(p) if p.exists() else {"path": path, "bytes": None, "sha256": None}
        comparisons.append({**current, "baseline_sha256": old, "changed": current["sha256"] != old})
    new = ROOT / "corrected/dimred_comparison_analysisset.csv"
    inventory = {"generated_utc": datetime.now(timezone.utc).isoformat(),
                 "baseline_review": str(prior / "review_manifest.json"),
                 "baseline_review_utc": manifest["generated_utc"], "known_files_compared": len(comparisons),
                 "files": comparisons, "changed_files": [x for x in comparisons if x["changed"]],
                 "newly_observed_source_files": [identity(new)],
                 "new_file_scope": "The newly observed CSV has an mtime after the preceding review. Unmanifested historical server-snapshot files are not asserted to be new."}
    (OUT / "change_inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    documents = []
    for label, relative in [("article", "article/Pf8_Ghana_article.docx"),
                            ("manuscript", "Pf8_Ghana_manuscript_REVISED.docx"),
                            ("supplement", "article/Additional_file_1.docx")]:
        path = ROOT / relative
        with zipfile.ZipFile(path) as z:
            tree = ET.fromstring(z.read("word/document.xml"))
            body = tree.find(W + "body")
            text = lambda p: "".join(n.text or "" for n in p.iter(W + "t"))
            paragraphs = [text(p) for p in body if p.tag == W + "p"]
            full = [text(p) for p in body.iter(W + "p")]
            current_text = "\n\n".join(paragraphs) + "\n"
            (OUT / (label + "_body.txt")).write_text(current_text)
            (OUT / (label + "_full_text.txt")).write_text("\n".join(full) + "\n")
            old = (prior / (label + "_body.txt")).read_text().splitlines()
            clean_old = [p for p in old if p.strip()]
            clean_new = [p for p in paragraphs if p.strip()]
            edits = []
            for op, a, b, c, d in difflib.SequenceMatcher(None, clean_old, clean_new, autojunk=False).get_opcodes():
                if op != "equal":
                    edits.append({"kind": op, "old_paragraph_range": [a+1,b], "new_paragraph_range": [c+1,d],
                                  "old": clean_old[a:b], "new": clean_new[c:d]})
            (OUT / (label + "_semantic_changes.json")).write_text(json.dumps(edits, indent=2, ensure_ascii=False) + "\n")
            captions = {kind: [] for kind in ["Table", "Figure"]}
            for line, value in enumerate(full, 1):
                for kind in captions:
                    match = re.match(rf"^{kind}\s+(S\d+[a-z]?)\.", value)
                    if match:
                        captions[kind].append({"label": match[1], "line": line, "caption": value})
            duplicates = {kind: {lab: [p for p in items if p["label"] == lab]
                                 for lab in {p["label"] for p in items}
                                 if sum(p["label"] == lab for p in items) > 1}
                          for kind, items in captions.items()}
            tables = [[[text(cell) for cell in row.findall(W + "tc")] for row in t.findall(W + "tr")]
                      for t in body.iter(W + "tbl")]
            documents.append({"label": label, "identity": identity(path), "body_words": len(current_text.split()),
                              "paragraphs": len(paragraphs), "tables": len(tables), "semantic_changed_blocks": len(edits),
                              "tracked_change_elements": sum(1 for n in tree.iter() if n.tag in {W+"ins", W+"del"}),
                              "captions": captions, "duplicate_labels": duplicates,
                              "table_contents": tables if label == "article" else []})
    (OUT / "document_validation.json").write_text(json.dumps(documents, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"known": len(comparisons), "changed": len(inventory["changed_files"]),
                      "documents": [{"label": d["label"], "changes": d["semantic_changed_blocks"],
                                     "supplementary_caption_counts": {k: len(v) for k,v in d["captions"].items()},
                                     "duplicate_labels": {k: list(v) for k,v in d["duplicate_labels"].items()}}
                                    for d in documents]}))


if __name__ == "__main__":
    main()
