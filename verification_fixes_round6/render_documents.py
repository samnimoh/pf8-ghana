#!/usr/bin/env python3
"""Render every page with the bundled document renderer; keep QA in temp."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from PIL import Image, ImageDraw
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
QA = Path('/private/tmp/pf8_round6_fixed_render')
PACKAGE = Path('/Users/samnimoh/.codex/plugins/cache/openai-primary-runtime/documents/26.1009.11318/skills/documents/render_docx.py')


def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def normalized(text):
    return re.sub(r'\s+', '', re.sub(r'Page\s+\d+\s+of\s+\d+', '', text))


def main():
    spec = importlib.util.spec_from_file_location('packaged_renderer', PACKAGE)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    assert '/dependencies/bin/override/' in renderer._resolve_soffice()
    selected = set(sys.argv[1:])
    if selected:
        assert selected <= {'article', 'manuscript', 'supplement'}
    report_path = OUT / 'render_results.json'
    results = json.loads(report_path.read_text()) if selected and report_path.exists() else []
    for name, relative in [('article', 'article/Pf8_Ghana_article.docx'),
                           ('manuscript', 'Pf8_Ghana_manuscript_REVISED.docx'),
                           ('supplement', 'article/Additional_file_1.docx')]:
        if selected and name not in selected:
            continue
        source = ROOT / relative
        folder = QA / name
        folder.mkdir(parents=True, exist_ok=True)
        renderer.rasterize(str(source), str(folder), dpi=100, verbose=False, emit_pdf=True)
        pdf = folder / source.with_suffix('.pdf').name
        reader = PdfReader(pdf)
        images = [folder / f'page-{i}.png' for i in range(1, len(reader.pages) + 1)]
        assert all(p.exists() for p in images)
        old = PdfReader(source.with_suffix('.pdf'))
        changed_pages = [i + 1 for i, page in enumerate(reader.pages)
                         if i >= len(old.pages) or normalized(page.extract_text()) != normalized(old.pages[i].extract_text())]
        contacts = []
        for start in range(0, len(images), 16):
            sheet = Image.new('RGB', (1080, 1620), 'white')
            draw = ImageDraw.Draw(sheet)
            for offset, page in enumerate(images[start:start + 16]):
                with Image.open(page) as full:
                    full.thumbnail((258, 375))
                    x, y = (offset % 4) * 270, (offset // 4) * 405
                    sheet.paste(full, (x + 6, y + 22))
                    draw.text((x + 6, y + 3), f'{name} page {start + offset + 1}', fill='black')
            target = folder / f'contact-{start // 16 + 1}.png'
            sheet.save(target)
            contacts.append(identity(target))
        results = [record for record in results if record['label'] != name]
        results.append({'label': name, 'source': identity(source), 'rendered_pdf': identity(pdf),
            'pages': len(reader.pages), 'prior_pdf_pages': len(old.pages),
            'page_text_changed_from_prior_pdf': changed_pages,
            'page_images': [identity(p) for p in images], 'contact_sheets': contacts,
            'renderer': str(PACKAGE), 'dpi': 100})
        print(name, len(reader.pages), 'pages rendered; changed text pages:', changed_pages, flush=True)
    report_path.write_text(json.dumps(results, indent=2) + '\n')


if __name__ == '__main__':
    main()
