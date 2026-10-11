#!/usr/bin/env python3
"""Compare supplied PDFs with freshly converted DOCX PDFs on selected pages.

This is a limited presentation check, not a complete layout certification.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
RENDERS = Path("/private/tmp/pf8_review_round5")


def normalized(value):
    return re.sub(r"\s+", " ", value).strip()


def identity(path):
    return {"path": str(path), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    documents = []
    for label, relative, pages in [
        ("article", "article/Pf8_Ghana_article", list(range(1, 19))),
        ("manuscript", "Pf8_Ghana_manuscript_REVISED", [1, 2, 31, 95, 111, 116, 143, 176, 196]),
        ("supplement", "article/Additional_file_1", [1, 2, 96, 105, 112, 120, 144, 177, 197]),
    ]:
        supplied = ROOT / (relative + ".pdf")
        fresh = RENDERS / label / (Path(relative).name + ".pdf")
        a, b = PdfReader(supplied), PdfReader(fresh)
        cached = OUT / (label + "_rendered_page_texts.json")
        cache = json.loads(cached.read_text()) if cached.exists() else None
        comparisons = []
        for number in pages:
            if number > min(len(a.pages), len(b.pages)):
                comparisons.append({"page": number, "exists_in_both": False})
                continue
            old_text = a.pages[number - 1].extract_text() or ""
            new_text = cache[number - 1] if cache is not None else b.pages[number - 1].extract_text() or ""
            comparisons.append({"page": number, "exists_in_both": True,
                                "normalized_text_equal": normalized(old_text) == normalized(new_text),
                                "supplied_characters": len(old_text), "fresh_characters": len(new_text)})
        documents.append({"label": label, "source_docx": identity(ROOT / (relative + ".docx")),
                          "supplied_pdf": identity(supplied), "fresh_pdf": identity(fresh),
                          "supplied_page_count": len(a.pages), "fresh_page_count": len(b.pages),
                          "selected_page_comparisons": comparisons})
        print(label, len(a.pages), len(b.pages), sum(p.get("normalized_text_equal", False) for p in comparisons), len(comparisons), flush=True)
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Fresh DOCX conversion; all article page texts and selected long-report/supplement page texts compared with supplied PDFs. Representative PNG inspection recorded separately; no claim of inspection of every page.",
        "runtime": {"python": sys.executable, "pypdf_version": __import__("pypdf").__version__,
                    "compiler": "Bundled LibreOffice through documents/render_docx.py",
                    "rasterizer": "Bundled Poppler"},
        "documents": documents,
        "full_rasterization": {"article": "completed, 18 pages", "manuscript": "completed, 196 pages",
                               "supplement": "Fresh PDF conversion completed; full rasterization interrupted, representative pages rasterized separately."},
    }
    (OUT / "render_review.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
