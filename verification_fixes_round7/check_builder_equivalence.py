"""Confirm the metadata lookup followup produces the exact current package parts."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    source = ROOT / 'article/Pf8_Ghana_article.docx'
    source_bytes = source.read_bytes()
    with tempfile.TemporaryDirectory(prefix='pf8_round7_builder_equivalence_') as name:
        scratch = Path(name)
        package = scratch / 'template'
        with zipfile.ZipFile(ROOT / 'article/Additional_file_1.docx') as z:
            z.extractall(package)
        destination = scratch / 'rebuilt.docx'
        env = dict(os.environ, ARTICLE_TEMPLATE=str(package),
            ARTICLE_MD=str(ROOT/'article/article.md'), ARTICLE_DOCX=str(destination))
        result = subprocess.run([sys.executable, '-I', '-B', str(ROOT/'tools/build_article.py')],
            cwd=scratch, env=env, capture_output=True, text=True, check=True)
        with zipfile.ZipFile(source) as old, zipfile.ZipFile(destination) as new:
            previous = {p: sha(old.read(p)) for p in old.namelist()}
            rebuilt = {p: sha(new.read(p)) for p in new.namelist()}
            equivalent = previous == rebuilt and new.testzip() is None
            differences = sorted(p for p in set(previous) | set(rebuilt) if previous.get(p) != rebuilt.get(p))
        if not equivalent or source.read_bytes() != source_bytes:
            raise ValueError({'different_package_parts': differences})
        report = {'status': 'bounded_pass', 'all_passed': True,
            'current_article_sha256': sha(source_bytes),
            'builder_sha256': sha((ROOT/'tools/build_article.py').read_bytes()),
            'all_uncompressed_package_parts_identical': True, 'package_parts': previous,
            'current_article_unmodified': True, 'stdout': result.stdout,
            'scope': 'Scratch document assembly using the final helper and current canonical template/source. Every part equals the current article; ZIP timestamps need not match.'}
        (OUT/'builder_equivalence_results.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Final assembler and current article have identical contents in all package parts.')

if __name__ == '__main__':
    main()
