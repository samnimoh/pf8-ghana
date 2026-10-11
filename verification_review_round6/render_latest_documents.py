#!/usr/bin/env python3
"""Fresh DOCX conversions plus fast full-PDF text and selected image review."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
from pdf2image import convert_from_path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
RENDERS = Path("/private/tmp/pf8_review_round6_latest")
PACKAGE = Path("/Users/samnimoh/.codex/plugins/cache/openai-primary-runtime/documents/26.1009.11318/skills/documents/render_docx.py")


def main():
    spec = importlib.util.spec_from_file_location("packaged_renderer", PACKAGE)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    results = []
    for label, relative, pages in [
        ("article", "article/Pf8_Ghana_article.docx", [7, 15]),
        ("manuscript", "Pf8_Ghana_manuscript_REVISED.docx", [9, 60, 61, 79, 90, 99, 104, 109, 148, 165, 172, 177]),
        ("supplement", "article/Additional_file_1.docx", [2, 80, 100]),
    ]:
        source = ROOT / relative
        output = RENDERS / label
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="pf8_docx_profile_", dir="/private/tmp") as profile:
            with tempfile.TemporaryDirectory(prefix="pf8_docx_convert_", dir="/private/tmp") as conversion:
                pdf, log = renderer.convert_to_pdf(str(source), profile, conversion, source.stem, verbose=False)
                if not pdf:
                    raise RuntimeError(log)
                target = output / (source.stem + ".pdf")
                shutil.copy2(pdf, target)
        count = len(PdfReader(target).pages)
        for number in pages:
            images = convert_from_path(str(target), dpi=140, first_page=number, last_page=number, thread_count=1)
            images[0].save(output / f"page-{number}.png")
        for purpose, path in [("fresh", target), ("supplied", source.with_suffix(".pdf"))]:
            reader = PdfReader(path)
            (OUT / f"{label}_{purpose}_pdf_text.txt").write_text(
                "\f".join(page.extract_text() for page in reader.pages) + "\f")
        results.append({"label": label, "docx": str(source), "fresh_pdf": str(target),
                        "supplied_pdf": str(source.with_suffix('.pdf')), "pages": count,
                        "rasterized_review_pages": pages,
                        "converter": str(PACKAGE), "text_extractor": "Bundled pypdf; full page text"})
        print(label, count, flush=True)
    (OUT / "render_conversion.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
