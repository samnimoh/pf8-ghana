#!/usr/bin/env python3
"""Scratch-only regression for an encoded core-properties override."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
BUILDER = ROOT / 'tools/build_article.py'
CT = '{http://schemas.openxmlformats.org/package/2006/content-types}'
DC = '{http://purl.org/dc/elements/1.1/}'


def identity(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    source = identity(BUILDER)
    protected = [ROOT / p for p in ('article/Pf8_Ghana_article.docx', 'article/Additional_file_1.docx',
                                   'Pf8_Ghana_manuscript_REVISED.docx')]
    protected_before = [identity(p) for p in protected]
    with tempfile.TemporaryDirectory(prefix='pf8_encoded_core_followup_') as name:
        scratch = Path(name)
        template = scratch / 'template'
        with zipfile.ZipFile(ROOT / 'article/Additional_file_1.docx') as z:
            z.extractall(template)
        ct_path = template / '[Content_Types].xml'
        tree = ET.parse(ct_path)
        item = next(n for n in tree.getroot() if n.tag == CT+'Override' and n.get('PartName') == '/docProps/core.xml')
        item.set('PartName', '/docProps/%63ore.xml')
        tree.write(ct_path, encoding='utf-8', xml_declaration=True)
        before_template = {str(p.relative_to(template)): identity(p) for p in template.rglob('*') if p.is_file()}
        markdown = scratch / 'article.md'
        markdown.write_text('# Encoded core regression\nHarmless scratch body.\n[[TABLE2]]\n')
        refs = scratch / 'refs.txt'
        refs.write_text('Scratch reference.\n')
        destination = scratch / 'article.docx'
        destination.write_bytes(b'prior scratch destination\n')
        environment = dict(os.environ, ARTICLE_TEMPLATE=str(template), ARTICLE_MD=str(markdown),
                           ARTICLE_REFS=str(refs), ARTICLE_DOCX=str(destination))
        process = subprocess.run([sys.executable, '-I', str(BUILDER)], env=environment, cwd=scratch,
                                 capture_output=True, text=True, timeout=30)
        checks = []
        checks.append(dict(name='encoded core override build succeeds', passed=process.returncode == 0,
                           returncode=process.returncode, stderr=process.stderr[-1500:]))
        if process.returncode == 0:
            with zipfile.ZipFile(destination) as z:
                checks.append(dict(name='output archive CRC valid', passed=z.testzip() is None))
                content_types = ET.fromstring(z.read('[Content_Types].xml'))
                from urllib.parse import unquote
                core = [n for n in content_types if n.tag == CT+'Override' and unquote(n.get('PartName','')) == '/docProps/core.xml']
                checks.append(dict(name='one decoded core override retained with original URI',
                                   passed=len(core) == 1 and core[0].get('PartName') == '/docProps/%63ore.xml'))
                metadata = ET.fromstring(z.read('docProps/core.xml'))
                checks.append(dict(name='metadata equals visible scratch title',
                                   passed=[n.text for n in metadata.findall(DC+'title')] == ['Encoded core regression']))
        checks.append(dict(name='scratch template bytes unchanged', passed=before_template == {
            str(p.relative_to(template)): identity(p) for p in template.rglob('*') if p.is_file()}))
        checks.append(dict(name='no owned temporary file remains', passed=not list(scratch.glob('article.docx.tmp-build-*.tmp'))))
    checks.append(dict(name='shipping DOCX deliverables unchanged by regression', passed=protected_before == [identity(p) for p in protected]))
    checks.append(dict(name='tested builder source unchanged during run', passed=source == identity(BUILDER)))
    result = dict(generated_utc=datetime.now(timezone.utc).isoformat(), status='bounded_pass' if all(c['passed'] for c in checks) else 'findings',
                  all_passed=all(c['passed'] for c in checks), checks=len(checks), builder=source,
                  driver=identity(Path(__file__).resolve()), results=checks,
                  scope='One encoded core PartName scratch-package regression and eight resulting checks. No prior evidence overwritten; no shipping document or scientific pipeline modified.')
    target = OUT / 'builder_encoded_core_followup_results.json'
    target.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(path=str(target), checks=len(checks), all_passed=result['all_passed'], builder=source)))
    if not result['all_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
