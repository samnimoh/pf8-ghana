"""Apply the reviewed local substitutions without rewriting unrelated OOXML."""
import difflib
import hashlib
import html
import json
import os
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
PARA = re.compile(r'<w:p\b[^>]*(?<!/)>(.*?)</w:p>', re.S)
RUN = re.compile(r'<w:t\b[^>]*(?<!/)>(.*?)</w:t>', re.S)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def text(xml):
    return ''.join(html.unescape(m.group(1)) for m in RUN.finditer(xml))

def splice(xml, start, end, replacement):
    spans = [(m.start(1), m.end(1), html.unescape(m.group(1))) for m in RUN.finditer(xml)]
    length = sum(len(value) for _, _, value in spans)
    if not 0 <= start <= end <= length:
        raise ValueError('Text splice is outside the original paragraph')
    offset, edits, inserted = 0, [], False
    for index, (a, b, value) in enumerate(spans):
        stop = offset + len(value)
        trailing = start == end == length and index == len(spans) - 1
        if (start < stop and end > offset) or (start == end and offset <= start < stop) or trailing:
            lo, hi = max(start, offset) - offset, min(end, stop) - offset
            new = value[:lo] + (replacement if not inserted else '') + value[hi:]
            inserted = True
            edits.append((a, b, html.escape(new, quote=False)))
        offset = stop
    if not inserted:
        raise ValueError('Cannot locate text splice in original runs')
    for a, b, new in reversed(edits):
        xml = xml[:a] + new + xml[b:]
    return xml

def patch(xml, old, new):
    if text(xml) != old:
        raise ValueError('Paragraph text does not equal the accepted quote')
    for tag, a, b, c, d in reversed(difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()):
        if tag != 'equal':
            xml = splice(xml, a, b, new[c:d])
    if text(xml) != new:
        raise ValueError('Patched paragraph differs from accepted replacement')
    return xml

def main():
    plan_path = ROOT / 'verification_review_round7/proposed_document_edits.json'
    plan = json.loads(plan_path.read_text())
    source = ROOT / 'Pf8_Ghana_manuscript_REVISED.docx'
    article = ROOT / 'article/article.md'
    original, old_article = source.read_bytes(), article.read_bytes()
    if sha(original) != plan['manuscript_before_sha256'] or sha(old_article) != plan['article_md_before_sha256']:
        raise ValueError('A source changed since the reviewed proposal')
    with zipfile.ZipFile(source) as z:
        members = [(info, z.read(info.filename)) for info in z.infolist()]
        original_xml = z.read('word/document.xml').decode()
    xml = original_xml
    applied = []
    for edit in plan['manuscript_edits']:
        matches = [m for m in PARA.finditer(xml) if text(m.group()) == edit['quote']]
        if len(matches) != edit['expected_count']:
            raise ValueError(f"Unexpected matches for {edit['concept']}: {len(matches)}")
        if re.findall(r'\d+(?:[.,–-]\d+)*', edit['quote']) != re.findall(r'\d+(?:[.,–-]\d+)*', edit['repl']):
            raise ValueError('Numeric text changed in manuscript substitution')
        for m in reversed(matches):
            xml = xml[:m.start()] + patch(m.group(), edit['quote'], edit['repl']) + xml[m.end():]
        applied.append(edit)
    ET.fromstring(xml)
    markdown = old_article.decode()
    article_plan = plan['article_ordering_plan']
    article_edits = [article_plan['introductory_citation_edit'],
        article_plan['table_marker_move']['remove_context'], article_plan['table_marker_move']['insert_context']]
    for edit in article_edits:
        if markdown.count(edit['quote']) != edit['expected_count']:
            raise ValueError('Unexpected article quote count')
        markdown = markdown.replace(edit['quote'], edit['repl'])
    if re.findall(r'\[\[TABLE(\d+)\]\]', markdown) != ['1', '2', '3', '4']:
        raise ValueError('Article table order incorrect')
    temp_paths = []
    try:
        fd, name = tempfile.mkstemp(prefix=source.name + '.fix-', suffix='.tmp', dir=source.parent)
        temp_paths.append(Path(name))
        with os.fdopen(fd, 'w+b') as stream:
            with zipfile.ZipFile(stream, 'w') as z:
                for info, data in members:
                    z.writestr(info, xml.encode() if info.filename == 'word/document.xml' else data)
            stream.flush()
            os.fsync(stream.fileno())
            stream.seek(0)
            with zipfile.ZipFile(stream) as z:
                if z.testzip() is not None:
                    raise ValueError('Temporary manuscript failed CRC validation')
                if any(z.read(info.filename) != data for info, data in members if info.filename != 'word/document.xml'):
                    raise ValueError('Unrelated package member changed')
        fd, name = tempfile.mkstemp(prefix=article.name + '.fix-', suffix='.tmp', dir=article.parent)
        temp_paths.append(Path(name))
        with os.fdopen(fd, 'wb') as stream:
            stream.write(markdown.encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_paths[0], source.stat().st_mode & 0o777)
        os.chmod(temp_paths[1], article.stat().st_mode & 0o777)
        os.replace(temp_paths[0], source)
        os.replace(temp_paths[1], article)
    finally:
        for path in temp_paths:
            path.unlink(missing_ok=True)
    record = {'manuscript_before_sha256': sha(original), 'manuscript_after_sha256': sha(source.read_bytes()),
        'document_xml_before_sha256': sha(original_xml.encode()), 'document_xml_after_sha256': sha(xml.encode()),
        'article_md_before_sha256': sha(old_article), 'article_md_after_sha256': sha(article.read_bytes()),
        'manuscript_edits': applied, 'article_edits': article_edits,
        'unrelated_package_members_preserved': True, 'numeric_manuscript_tokens_preserved': True}
    (OUT / 'document_edit_results.json').write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print('Applied four manuscript substitutions and three article source edits.')

if __name__ == '__main__':
    main()
