#!/usr/bin/env python3
"""Publish only final renders whose source and full-page reviews still match."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent


def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main():
    if not __debug__:
        raise RuntimeError('Run without Python optimization; validation assertions must be enabled.')
    renders = json.loads((OUT/'render_results.json').read_text())
    assert len(renders) == 3
    assert {r['label'] for r in renders} == {'article', 'manuscript', 'supplement'}
    text_review = json.loads((OUT/'final_document_followup_review.json').read_text())
    checks = json.loads((OUT/'document_validation.json').read_text())
    assert text_review['status'] in {'pass', 'bounded_pass'} and not text_review['findings']
    assert all(checks['checks'].values())
    assert all(identity(ROOT/path)['sha256'] == digest for path, digest in text_review['source_sha256'].items())
    expected_sources = {'article': ROOT/'article/Pf8_Ghana_article.docx',
                        'manuscript': ROOT/'Pf8_Ghana_manuscript_REVISED.docx',
                        'supplement': ROOT/'article/Additional_file_1.docx'}
    plans = []
    for render in renders:
        label = render['label']
        source = expected_sources[label]
        pdf = Path(render['rendered_pdf']['path'])
        review = json.loads((OUT/f'visual_{label}_review.json').read_text())
        assert identity(source) == render['source'] == review['source'], label
        assert identity(pdf) == render['rendered_pdf'] == review['rendered_pdf'], label
        assert review['status'] == 'bounded_pass' and not review['findings'], label
        assert review['pages'] == render['pages'] == len(PdfReader(pdf).pages), label
        assert len(review['original_detail_pages_inspected']) == render['pages'], label
        assert set(review['original_detail_pages_inspected']) == set(range(1, render['pages']+1)), label
        assert len(render['page_images']) == len(review['page_images_inspected']) == render['pages'], label
        approved_images = {item['path']: item for item in review['page_images_inspected']}
        rendered_images = {item['path']: item for item in render['page_images']}
        assert len(approved_images) == len(rendered_images) == render['pages'], label
        assert approved_images == rendered_images, label
        assert all(identity(Path(item['path'])) == item for item in render['page_images']), label
        destination = source.with_suffix('.pdf')
        plans.append((render, pdf, destination))
    staged = []
    records = []
    try:
        # Stage and check every PDF before replacing any existing deliverable.
        for render, pdf, destination in plans:
            before = identity(destination) if destination.exists() else None
            fd, name = tempfile.mkstemp(prefix=destination.name+'.reviewed-', suffix='.tmp', dir=destination.parent)
            temporary = Path(name)
            staged.append((temporary, destination))
            with os.fdopen(fd, 'wb') as stream, pdf.open('rb') as incoming:
                shutil.copyfileobj(incoming, stream)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.chmod(stat.S_IMODE(destination.stat().st_mode) if destination.exists() else 0o644)
            assert identity(temporary)['sha256'] == render['rendered_pdf']['sha256']
            records.append({'label': render['label'], 'source': render['source'], 'before': before,
                            'rendered_pdf': render['rendered_pdf'], 'pages': render['pages'],
                            'destination': str(destination)})
        for temporary, destination in staged:
            os.replace(temporary, destination)
        for record in records:
            record['published_pdf'] = identity(Path(record['destination']))
            assert record['published_pdf']['sha256'] == record['rendered_pdf']['sha256']
        (OUT/'pdf_publication_results.json').write_text(json.dumps({
            'generated_utc': datetime.now(timezone.utc).isoformat(),
            'scope': 'All three final reviewed renders copied byte-identically beside their current source DOCX.',
            'results': records, 'all_passed': True}, indent=2)+'\n')
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
    print(json.dumps({'published': len(records), 'pages': [r['pages'] for r in records], 'all_passed': True}))


if __name__ == '__main__':
    main()
