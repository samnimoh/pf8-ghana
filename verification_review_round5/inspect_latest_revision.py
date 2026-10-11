#!/usr/bin/env python3
"""Compare current documents and file identities with the preceding review."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
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


def text(node):
    return "".join(n.text or "" for n in node.iter(W + "t")).strip()


def main():
    prior = ROOT / "verification_review_round4"
    manifest = json.loads((prior / "review_manifest.json").read_text())
    known = {r["path"]: r["sha256"] for r in
             manifest["current_source_and_baseline_artifact_identities"] + manifest["artifact_hashes"]}
    comparisons = []
    for path, old in sorted(known.items()):
        p = Path(path)
        now = identity(p) if p.exists() else {"path": path, "bytes": None, "sha256": None}
        comparisons.append({**now, "baseline_sha256": old, "changed": now["sha256"] != old})
    new_paths = [ROOT / "corrected" / name for name in
                 ("dimred_comparison_n1900_analysisset.csv", "dimred_comparison_n4905_qcpassset.csv", "DIMRED_FILENAME_WARNING.md")]
    inventory = {"generated_utc": datetime.now(timezone.utc).isoformat(),
                 "baseline_review_manifest": str(prior / "review_manifest.json"),
                 "baseline_review_utc": manifest["generated_utc"],
                 "known_files_compared": len(comparisons), "files": comparisons,
                 "changed_files": [r for r in comparisons if r["changed"]],
                 "new_source_files": [identity(p) for p in new_paths],
                 "scope": "Known source and review artifacts plus the three new correction-commit files; not an assertion that every unmanifested historical file is new."}
    (OUT / "change_inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    docs = []
    for label, relative in [("article", "article/Pf8_Ghana_article.docx"),
                            ("manuscript", "Pf8_Ghana_manuscript_REVISED.docx"),
                            ("supplement", "article/Additional_file_1.docx")]:
        source = ROOT / relative
        with zipfile.ZipFile(source) as z:
            body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
            paragraphs = [text(p) for p in body if p.tag == W + "p"]
            full = [text(p) for p in body.iter(W + "p")]
            (OUT / (label + "_body.txt")).write_text("\n\n".join(paragraphs) + "\n")
            (OUT / (label + "_full_text.txt")).write_text("\n".join(full) + "\n")
            old = [p for p in (prior / (label + "_body.txt")).read_text().splitlines() if p.strip()]
            new = [p for p in paragraphs if p.strip()]
            changes = [{"kind": op, "old_paragraphs": [a+1,b], "new_paragraphs": [c+1,d],
                        "old": old[a:b], "new": new[c:d]}
                       for op,a,b,c,d in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
                       if op != "equal"]
            (OUT / (label + "_semantic_changes.json")).write_text(json.dumps(changes, indent=2, ensure_ascii=False) + "\n")
            captions = {kind: [{"label": m[1], "caption": p, "line": i}
                               for i,p in enumerate(full,1)
                               if (m := re.match(rf"^{kind}\s+(S\d+[a-z]?)\.", p))]
                        for kind in ("Table", "Figure")}
            media = [{"member": n, "sha256": hashlib.sha256(z.read(n)).hexdigest()}
                     for n in z.namelist() if n.startswith("word/media/")]
            docs.append({"label": label, "source": identity(source), "semantic_change_blocks": len(changes),
                         "captions": captions, "media": media,
                         "body_words": len(" ".join(paragraphs).split())})
    (OUT / "document_validation.json").write_text(json.dumps(docs, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"known": len(comparisons), "changed": len(inventory["changed_files"]),
                      "new": len(new_paths), "changed_paths": [r["path"] for r in inventory["changed_files"]],
                      "documents": [{"label": d["label"], "changed_blocks": d["semantic_change_blocks"]} for d in docs]}))


if __name__ == "__main__":
    main()
