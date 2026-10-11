#!/usr/bin/env python3
"""Add only heading pagination flags, preserving every other package member."""
import hashlib
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / 'Pf8_Ghana_manuscript_REVISED.docx'
EXPECTED = '6b81fcb360f2412f1787a1e23a7cff3d84ba021ec2ce576b6306166b8de3a135'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    before = SOURCE.read_bytes()
    assert sha(before) == EXPECTED, 'Source differs from independently reviewed editorial revision'
    with zipfile.ZipFile(SOURCE) as archive:
        infos = archive.infolist()
        original = {info.filename: archive.read(info) for info in infos}
        archive_comment = archive.comment
    styles = original['word/styles.xml'].decode('utf-8')
    adjusted = styles
    changes = []
    for style_id in ('Heading1', 'Heading2', 'Heading3'):
        pattern = re.compile(r'<w:style\b[^>]*\bw:styleId="' + style_id + r'"[^>]*>.*?</w:style>', re.S)
        matches = list(pattern.finditer(adjusted))
        assert len(matches) == 1, style_id
        old = matches[0].group()
        assert old.count('<w:pPr>') == 1 and '<w:keepNext' not in old and '<w:keepLines' not in old
        new = old.replace('<w:pPr>', '<w:pPr><w:keepNext/><w:keepLines/>', 1)
        adjusted = adjusted[:matches[0].start()] + new + adjusted[matches[0].end():]
        changes.append({'style_id': style_id, 'before_xml': old, 'after_xml': new})
    assert adjusted.replace('<w:keepNext/><w:keepLines/>', '') == styles
    ET.fromstring(adjusted)
    temporary = SOURCE.with_suffix('.docx.pending-layout')
    try:
        with zipfile.ZipFile(temporary, 'w') as archive:
            archive.comment = archive_comment
            for info in infos:
                archive.writestr(info, adjusted.encode('utf-8') if info.filename == 'word/styles.xml' else original[info.filename])
        with zipfile.ZipFile(temporary) as archive:
            assert archive.testzip() is None
            assert all(archive.read(name) == data for name, data in original.items() if name != 'word/styles.xml')
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, SOURCE)
    finally:
        temporary.unlink(missing_ok=True)
    result = {'source': str(SOURCE), 'before_sha256': sha(before), 'after_sha256': sha(SOURCE.read_bytes()),
              'scope': 'Only keepNext/keepLines flags added to the three used heading styles; no text, figures or analysis changes.',
              'styles_before_sha256': sha(styles.encode()), 'styles_after_sha256': sha(adjusted.encode()),
              'all_other_members_preserved': True, 'changes': changes}
    (OUT/'heading_layout_results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('after_sha256', 'all_other_members_preserved', 'scope')}))


if __name__ == '__main__':
    main()
