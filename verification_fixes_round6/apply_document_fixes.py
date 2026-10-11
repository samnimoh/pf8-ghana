#!/usr/bin/env python3
"""Apply asserted paragraph-local edits, preserving unrelated OOXML bytes."""
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
PARA = re.compile(r'<w:p\b[^>]*(?<!/)>(.*?)</w:p>', re.S)
RUN = re.compile(r'<w:t\b[^>]*(?<!/)>(.*?)</w:t>', re.S)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def patch_paragraph(xml, quote, replacement):
    spans = [(m.start(1), m.end(1), html.unescape(m.group(1))) for m in RUN.finditer(xml)]
    text = ''.join(value for _, _, value in spans)
    assert text.count(quote) == 1, (quote, text.count(quote))
    start = text.index(quote)
    end = start + len(quote)
    edits = []
    offset = 0
    inserted = False
    for a, b, value in spans:
        stop = offset + len(value)
        if start < stop and end > offset:
            lo, hi = max(start, offset) - offset, min(end, stop) - offset
            new = value[:lo] + (replacement if not inserted else '') + value[hi:]
            inserted = True
            edits.append((a, b, html.escape(new, quote=False)))
        offset = stop
    assert inserted
    for a, b, new in reversed(edits):
        xml = xml[:a] + new + xml[b:]
    actual = ''.join(html.unescape(t.group(1)) for t in RUN.finditer(xml))
    assert actual == text.replace(quote, replacement, 1)
    return xml


def main():
    plan_path = OUT / (sys.argv[1] if len(sys.argv) > 1 else 'accepted_document_edits.json')
    results_path = OUT / (sys.argv[2] if len(sys.argv) > 2 else 'document_edit_results.json')
    plan = json.loads(plan_path.read_text())
    source = ROOT / 'Pf8_Ghana_manuscript_REVISED.docx'
    original = source.read_bytes()
    assert sha(original) == plan['manuscript_before_sha256'], 'Source changed since edit plan'
    article = ROOT / 'article/article.md'
    old_article = article.read_bytes()
    assert sha(old_article) == plan['article_md_before_sha256']
    markdown = old_article.decode()
    for edit in plan['article_edits']:
        assert markdown.count(edit['quote']) == edit.get('expected_count', 1), edit['quote']
        markdown = markdown.replace(edit['quote'], edit['repl'])
    with zipfile.ZipFile(source) as z:
        xml = z.read('word/document.xml').decode()
        members = [(info, z.read(info.filename)) for info in z.infolist()]
    before_xml = sha(xml.encode())
    applied = []
    for edit in plan['manuscript_edits']:
        candidates = [(m.start(), m.end(), m.group()) for m in PARA.finditer(xml)
            if edit['quote'] in ''.join(html.unescape(t.group(1)) for t in RUN.finditer(m.group()))]
        assert len(candidates) == edit.get('expected_count', 1), (edit['concept'], len(candidates))
        for a, b, paragraph in reversed(candidates):
            xml = xml[:a] + patch_paragraph(paragraph, edit['quote'], edit['repl']) + xml[b:]
        applied.append({'concept': edit['concept'], 'quote': edit['quote'], 'repl': edit['repl'], 'occurrences': len(candidates)})
    ET.fromstring(xml)
    target = source.with_suffix('.docx.pending-fix')
    try:
        with zipfile.ZipFile(target, 'w') as z:
            for info, data in members:
                z.writestr(info, xml.encode() if info.filename == 'word/document.xml' else data)
        with zipfile.ZipFile(target) as z:
            assert z.testzip() is None
            assert all(z.read(info.filename) == data for info, data in members if info.filename != 'word/document.xml')
        with target.open('rb') as stream:
            os.fsync(stream.fileno())
        os.replace(target, source)
    finally:
        target.unlink(missing_ok=True)
    if plan['article_edits']:
        with tempfile.NamedTemporaryFile(dir=article.parent, prefix='article-edit-', delete=False) as temp:
            temp.write(markdown.encode())
            temp.flush()
            os.fsync(temp.fileno())
            temporary_article = Path(temp.name)
        os.replace(temporary_article, article)
    record = {'manuscript': str(source), 'before_sha256': sha(original), 'after_sha256': sha(source.read_bytes()),
        'document_xml_before_sha256': before_xml, 'document_xml_after_sha256': sha(xml.encode()),
        'unrelated_package_members_preserved': True, 'applied': applied,
        'article_md_before_sha256': sha(old_article), 'article_md_after_sha256': sha(article.read_bytes()),
        'article_edits': plan['article_edits']}
    results_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'manuscript_substitutions': len(applied), 'article_substitutions': len(plan['article_edits']), 'unrelated_package_members_preserved': True}))


if __name__ == '__main__':
    main()
