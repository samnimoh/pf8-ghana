"""Propagate the same codon-count correction into the remaining methods passages."""
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
HELPER = runpy.run_path(str(OUT/'apply_document_fixes.py'))

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    plan = json.loads((OUT/'proposed_document_followup_edits.json').read_text())
    source = ROOT/'Pf8_Ghana_manuscript_REVISED.docx'
    original = source.read_bytes()
    if sha(original) != plan['manuscript_before_sha256']:
        raise ValueError('Source changed since the followup proposal')
    with zipfile.ZipFile(source) as z:
        members = [(info, z.read(info.filename)) for info in z.infolist()]
        xml = z.read('word/document.xml').decode()
    before_xml = xml
    for edit in plan['manuscript_edits']:
        candidates = [m for m in HELPER['PARA'].finditer(xml) if HELPER['text'](m.group()) == edit['quote']]
        if len(candidates) != edit['expected_count']:
            raise ValueError(f'Unexpected followup match count: {edit["concept"]}')
        if re.findall(r'\d+(?:[.,–-]\d+)*', edit['quote']) != re.findall(r'\d+(?:[.,–-]\d+)*', edit['repl']):
            raise ValueError('Followup numeric tokens changed')
        for m in reversed(candidates):
            xml = xml[:m.start()] + HELPER['patch'](m.group(), edit['quote'], edit['repl']) + xml[m.end():]
    ET.fromstring(xml)
    fd, name = tempfile.mkstemp(prefix=source.name+'.followup-', suffix='.tmp', dir=source.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'w+b') as stream:
            with zipfile.ZipFile(stream, 'w') as z:
                for info, data in members:
                    z.writestr(info, xml.encode() if info.filename == 'word/document.xml' else data)
            stream.flush()
            os.fsync(stream.fileno())
            stream.seek(0)
            with zipfile.ZipFile(stream) as z:
                if z.testzip() is not None or any(z.read(info.filename) != data for info, data in members if info.filename != 'word/document.xml'):
                    raise ValueError('Temporary manuscript failed package validation')
        temporary.chmod(source.stat().st_mode & 0o777)
        os.replace(temporary, source)
    finally:
        temporary.unlink(missing_ok=True)
    record = {'before_sha256': sha(original), 'after_sha256': sha(source.read_bytes()),
        'document_xml_before_sha256': sha(before_xml.encode()), 'document_xml_after_sha256': sha(xml.encode()),
        'manuscript_edits': plan['manuscript_edits'], 'numeric_tokens_preserved': True,
        'unrelated_package_members_preserved': True, 'article_source_unmodified': True}
    (OUT/'document_followup_edit_results.json').write_text(json.dumps(record, indent=2, ensure_ascii=False)+'\n')
    print(f'Applied {len(plan["manuscript_edits"])} additional codon-scope substitutions.')

if __name__ == '__main__':
    main()
