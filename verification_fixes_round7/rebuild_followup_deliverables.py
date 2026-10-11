#!/usr/bin/env python3
"""Regenerate the supplement and article using the corrected local helpers."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
PYTHON = '/Users/samnimoh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if not __debug__:
        raise RuntimeError('Run without optimization; rebuild validation must remain enabled.')
    commands = []
    source = ROOT / 'Pf8_Ghana_manuscript_REVISED.docx'
    supplement = ROOT / 'article/Additional_file_1.docx'
    article = ROOT / 'article/Pf8_Ghana_article.docx'
    before = {str(p): sha(p) for p in (source, supplement, article)}
    with tempfile.TemporaryDirectory(prefix='pf8_round7_rebuild_', dir='/private/tmp') as scratch:
        scratch = Path(scratch)
        package = scratch / 'supplement'
        package.mkdir()
        with zipfile.ZipFile(source) as z:
            infos = z.infolist()
            z.extractall(package)
        command = [PYTHON, '-I', str(ROOT / 'tools/make_supplement.py')]
        result = subprocess.run(command, cwd=package, capture_output=True, text=True, check=True)
        commands.append({'command': command, 'stdout': result.stdout, 'stderr': result.stderr})
        ET.fromstring((package / 'word/document.xml').read_bytes())
        fd, name = tempfile.mkstemp(prefix=supplement.name + '.build-', suffix='.tmp', dir=supplement.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, 'w+b') as stream:
                with zipfile.ZipFile(stream, 'w') as z:
                    for info in infos:
                        z.writestr(info, b'' if info.is_dir() else (package / info.filename).read_bytes())
                stream.flush()
                os.fsync(stream.fileno())
                stream.seek(0)
                with zipfile.ZipFile(stream) as z:
                    if z.testzip() is not None:
                        raise ValueError('Supplement archive failed CRC validation')
            os.chmod(temporary, supplement.stat().st_mode & 0o777)
            os.replace(temporary, supplement)
        finally:
            temporary.unlink(missing_ok=True)
        environment = dict(os.environ, ARTICLE_TEMPLATE=str(package),
            ARTICLE_MD=str(ROOT / 'article/article.md'), ARTICLE_DOCX=str(article))
        command = [PYTHON, '-I', str(ROOT / 'tools/build_article.py')]
        result = subprocess.run(command, cwd=scratch, env=environment, capture_output=True, text=True, check=True)
        commands.append({'command': command, 'stdout': result.stdout, 'stderr': result.stderr})
    after = {str(p): sha(p) for p in (source, supplement, article)}
    record = {'before_sha256': before, 'after_sha256': after, 'commands': commands,
        'scope': 'Local document assembly only; scientific calculations and outputs unchanged.'}
    (OUT / 'document_followup_build_results.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'supplement': str(supplement), 'article': str(article), 'assemblies_passed': len(commands)}))


if __name__ == '__main__':
    main()
