#!/usr/bin/env python3
"""Use the packaged DOCX converter, then rasterize only review pages.

This avoids rasterizing hundreds of long-report pages concurrently.
"""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
from pdf2image import convert_from_path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RENDERS = Path("/private/tmp/pf8_review_round6")
PACKAGE = Path("/Users/samnimoh/.codex/plugins/cache/openai-primary-runtime/documents/26.1009.11318/skills/documents/render_docx.py")


def main():
    spec = importlib.util.spec_from_file_location("packaged_docx_renderer", PACKAGE)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    results = []
    for label, relative, pages in [
        ("article", "article/Pf8_Ghana_article.docx", [1, 6, 7, 9, 10, 15, 18]),
        ("manuscript", "Pf8_Ghana_manuscript_REVISED.docx", [27, 44, 111, 142]),
        ("supplement", "article/Additional_file_1.docx", [1, 2, 110]),
    ]:
        source = ROOT / relative
        output = RENDERS / label
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="pf8_review_profile_", dir="/private/tmp") as profile:
            with tempfile.TemporaryDirectory(prefix="pf8_review_convert_", dir="/private/tmp") as conversion:
                pdf, log = renderer.convert_to_pdf(str(source), profile, conversion, source.stem, verbose=False)
                if not pdf:
                    raise RuntimeError(log)
                target = output / (source.stem + ".pdf")
                shutil.copy2(pdf, target)
        count = len(PdfReader(target).pages)
        for page in pages:
            if page <= count:
                images = convert_from_path(str(target), dpi=140, first_page=page, last_page=page, thread_count=1)
                images[0].save(output / f"page-{page}.png")
        results.append({"label": label, "docx": str(source), "fresh_pdf": str(target),
                        "pages": count, "rasterized_review_pages": pages,
                        "conversion": "Packaged documents converter using bundled LibreOffice",
                        "rasterization": "Bundled Poppler, one thread, selected pages"})
        print(label, count, flush=True)
    Path(__file__).with_name("render_conversion.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
