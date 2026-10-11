"""Scratch-only confirmation of round-seven temp-file and Git-path findings."""
import ast
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path('/Users/samnimoh/Desktop/chromo')
OUT = Path(__file__).resolve().parent
GIT = '/Users/samnimoh/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/git'
BUILDER = ROOT/'tools/build_article.py'


def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def git(*args):
    return subprocess.check_output([GIT, '-C', str(ROOT), *args])


def template(folder):
    image_names = ['93b6764f7192ce47a8c3257fe6d80a68d84833ff.png',
                   '218857879d6287b87460540cea2d8ec053df7685.png',
                   'c8eab09bbe813dc6fe1001e38fae01b5b7482cd0.png']
    parts = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/><Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/><Override PartName="/word/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/></Types>',
        '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        'word/document.xml': '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Harmless scratch document</w:t></w:r></w:p></w:body></w:document>',
        'word/styles.xml': '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>',
        'word/settings.xml': '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>',
        'word/fontTable.xml': '<w:fonts xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>',
        'word/theme/theme1.xml': '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Scratch"/>',
        'word/_rels/document.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
    }
    for name, text in parts.items():
        path = folder/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    pixel = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII=')
    for name in image_names:
        path = folder/'word/media'/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pixel)


def main():
    assert __debug__, 'Run without optimization'
    protected = [ROOT/name for name in ['Pf8_Ghana_manuscript_REVISED.docx', 'Pf8_Ghana_manuscript_REVISED.pdf',
                 'article/Additional_file_1.docx', 'article/Additional_file_1.pdf',
                 'article/Pf8_Ghana_article.docx', 'article/Pf8_Ghana_article.pdf']]
    before = [identity(path) for path in protected]
    code = BUILDER.read_bytes()
    old_code = git('show', 'd59bbf6:tools/build_article.py')
    tests = []
    with tempfile.TemporaryDirectory(prefix='pf8-round7-symlink-', dir='/private/tmp') as scratch:
        scratch = Path(scratch)
        old = scratch/'builder_d59bbf6.py'
        old.write_bytes(old_code)
        fault = scratch/'inject_fault.py'
        fault.write_text("import runpy, sys, zipfile\noriginal=zipfile.ZipFile.write\ncount=0\ndef failing(self,*a,**kw):\n global count\n count+=1\n if count==5: raise OSError('harmless injected fifth archive-write failure')\n return original(self,*a,**kw)\nzipfile.ZipFile.write=failing\nrunpy.run_path(sys.argv[1],run_name='__main__')\n")
        for version, builder in [('current', BUILDER), ('d59bbf6', old)]:
            for kind in ['unrelated_target_success', 'unrelated_target_write_failure', 'destination_alias_write_failure']:
                work = scratch/f'{version}_{kind}'
                work.mkdir()
                source = work/'template'
                template(source)
                md = work/'scratch.md'; md.write_text('# Scratch test\nHarmless document for filesystem verification.\n')
                refs = work/'scratch_refs.txt'; refs.write_text('Scratch reference only.\n')
                destination = work/'scratch.docx'
                with zipfile.ZipFile(destination, 'w') as z:
                    z.writestr('word/document.xml', '<scratch>Original destination</scratch>')
                target = destination if kind.startswith('destination_alias') else work/'unrelated_sentinel.txt'
                if target != destination:
                    target.write_text('Harmless unrelated sentinel; original bytes must not be overwritten.\n')
                temporary = Path(str(destination)+'.tmp-build')
                temporary.symlink_to(target)
                dest_before = identity(destination)
                target_before = identity(target)
                env = dict(os.environ, ARTICLE_TEMPLATE=str(source), ARTICLE_MD=str(md),
                           ARTICLE_REFS=str(refs), ARTICLE_DOCX=str(destination))
                args = [sys.executable, '-I']
                if 'failure' in kind:
                    args += [str(fault), str(builder)]
                else:
                    args += [str(builder)]
                cp = subprocess.run(args, cwd=work, env=env, capture_output=True, text=True)
                result = {'version': version, 'case': kind, 'returncode': cp.returncode,
                          'destination_preserved': identity(destination)['sha256']==dest_before['sha256'],
                          'target_preserved': identity(target)['sha256']==target_before['sha256'],
                          'destination_is_symlink': destination.is_symlink(),
                          'destination_link_target': os.readlink(destination) if destination.is_symlink() else None,
                          'temporary_lexists': os.path.lexists(temporary),
                          'unrelated_target_or_destination_is_zip': zipfile.is_zipfile(target),
                          'stderr_tail': cp.stderr.strip().splitlines()[-1] if cp.stderr.strip() else None,
                          'original_destination': dest_before, 'original_target': target_before,
                          'final_destination': identity(destination), 'final_target': identity(target)}
                if kind == 'unrelated_target_success':
                    assert cp.returncode==0 and not result['target_preserved'] and result['destination_is_symlink'] and not result['temporary_lexists']
                elif kind == 'unrelated_target_write_failure':
                    assert cp.returncode!=0 and result['destination_preserved'] and not result['target_preserved'] and not result['temporary_lexists']
                elif version == 'current':
                    assert cp.returncode!=0 and result['destination_preserved'] and result['temporary_lexists']
                else:
                    assert cp.returncode!=0 and not result['destination_preserved'] and not result['temporary_lexists']
                result['expectation_confirmed'] = True
                tests.append(result)
    hardcoded = []
    for folder in sorted(ROOT.glob('verification*')):
        if not folder.is_dir(): continue
        for path in sorted(folder.rglob('*.py')):
            if path==Path(__file__).resolve(): continue
            tree = ast.parse(path.read_bytes(), filename=str(path))
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GIT' for t in node.targets):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value,str) and node.value.value.startswith('/'):
                        rel = str(path.relative_to(ROOT))
                        probe = subprocess.run([GIT,'-C',str(ROOT),'cat-file','-e',f'd59bbf6:{rel}'],capture_output=True)
                        hardcoded.append({'path': str(path), 'line': node.lineno, 'git_literal': node.value.value,
                                          'present_at_d59bbf6': probe.returncode==0,
                                          'first_add_commit': git('log','--diff-filter=A','--format=%h','--',rel).decode().strip(),
                                          'source_identity': identity(path)})
    assert len(hardcoded)==9, len(hardcoded)
    version = subprocess.run([GIT,'--version'],capture_output=True,text=True)
    assert version.returncode==0
    after = [identity(path) for path in protected]
    assert before==after
    assert BUILDER.read_bytes()==code
    record = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'Independent confirmation only, using harmless scratch package assembly and read-only Git metadata. No deliverables, helper code, scientific analyses or server files were modified; no server contacted.',
              'builder': identity(BUILDER),
              'd59bbf6_builder': {'git_object': 'd59bbf6:tools/build_article.py', 'bytes': len(old_code), 'sha256': hashlib.sha256(old_code).hexdigest()},
              'tests': tests, 'test_driver': identity(Path(__file__).resolve()),
              'hardcoded_git_scripts': hardcoded,
              'git_probe': {'path': GIT, 'exists': Path(GIT).exists(), 'executable': os.access(GIT,os.X_OK),
                            'returncode': version.returncode, 'stdout': version.stdout.strip(), 'stderr':version.stderr.strip()},
              'deliverables_before': before, 'deliverables_after': after, 'all_protected_bytes_unchanged': True}
    (OUT/'independent_tool_hygiene_results.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'scratch_cases': len(tests), 'all_expectations_confirmed':True,
                      'hardcoded_git_scripts': len(hardcoded),
                      'preexisting_at_d59bbf6': sum(i['present_at_d59bbf6'] for i in hardcoded),
                      'git_current_probe': version.stdout.strip(), 'protected_bytes_unchanged': True}))


if __name__=='__main__':
    main()
