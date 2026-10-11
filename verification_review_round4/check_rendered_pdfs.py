#!/usr/bin/env python3
"""Compare current DOCX conversions with supplied PDFs at reviewed pages."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent


def identity(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def normalized(text):
    text = re.sub(r"Page\s+\d+\s+of\s+\d+", "", text)
    return re.sub(r"\s+", "", text)


def main():
    conversions = json.loads((OUT / "render_conversion.json").read_text())
    supplied = {"article": "article/Pf8_Ghana_article.pdf", "manuscript": "Pf8_Ghana_manuscript_REVISED.pdf",
                "supplement": "article/Additional_file_1.pdf"}
    results = []
    for conversion in conversions:
        label = conversion["label"]
        old_path, fresh_path = ROOT / supplied[label], Path(conversion["fresh_pdf"])
        old, fresh = PdfReader(old_path), PdfReader(fresh_path)
        pages = list(range(1, len(fresh.pages) + 1)) if label == "article" else conversion["rasterized_review_pages"]
        comparisons = []
        for number in pages:
            ot, ft = old.pages[number - 1].extract_text(), fresh.pages[number - 1].extract_text()
            comparisons.append({"page": number, "matches_after_whitespace_and_footer_normalization": normalized(ot) == normalized(ft),
                                "supplied_text_sha256": hashlib.sha256(ot.encode()).hexdigest(),
                                "fresh_text_sha256": hashlib.sha256(ft.encode()).hexdigest()})
            (OUT / f"{label}_supplied_page_{number}.txt").write_text(ot + "\n")
            (OUT / f"{label}_fresh_page_{number}.txt").write_text(ft + "\n")
        entry = {"label": label, "docx": identity(Path(conversion["docx"])),
                 "supplied_pdf": identity(old_path), "fresh_pdf": identity(fresh_path),
                 "supplied_pages": len(old.pages), "fresh_pages": len(fresh.pages), "page_comparisons": comparisons,
                 "rasterized_pages": conversion["rasterized_review_pages"]}
        if label == "manuscript":
            old111 = (OUT / "manuscript_supplied_page_111.txt").read_text()
            new111 = (OUT / "manuscript_fresh_page_111.txt").read_text()
            entry["stale_pdf_evidence"] = {
                "supplied_page111_claims_exact_reproduction": "Every printed edge p-value is reproduced exactly" in old111,
                "fresh_page111_qualifies_twelve_at_full_precision": "twelve of" in new111 and "full displayed precision" in new111,
                "text_excerpt_supplied": old111[:700], "text_excerpt_fresh": new111[:700]}
        results.append(entry)
        print(label, "pages", len(old.pages), len(fresh.pages), "reviewed text matches", sum(c["matches_after_whitespace_and_footer_normalization"] for c in comparisons), "/", len(comparisons), flush=True)
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(), "runtime": sys.executable,
              "comparisons": results, "visual_inspection_scope": "Selected pages recorded separately; not an all-page certification of the long documents."}
    (OUT / "render_review.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
