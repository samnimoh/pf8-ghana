#!/usr/bin/env python3
"""Independent narrow article-builder checks; scratch packages and read-only source."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
BUILDER = ROOT / 'tools/build_article.py'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
CT = '{http://schemas.openxmlformats.org/package/2006/content-types}'
CP = '{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}'
DC = '{http://purl.org/dc/elements/1.1/}'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
CORE_REL = REL[1:-1] + '/metadata/core-properties'


def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main():
    helper_before = identity(BUILDER)
    documents = [ROOT / name for name in ('Pf8_Ghana_manuscript_REVISED.docx',
        'article/Additional_file_1.docx', 'article/Pf8_Ghana_article.docx')]
    protected_before = [identity(p) for p in documents]
    results = []
    with tempfile.TemporaryDirectory(prefix='pf8_round7_independent_builder_') as directory:
        scratch = Path(directory)
        baseline = scratch / 'base'
        with zipfile.ZipFile(ROOT / 'article/Additional_file_1.docx') as archive:
            archive.extractall(baseline)
        wrapper = scratch / 'wrapper.py'
        wrapper.write_text('''import os,pathlib,runpy,sys,tempfile,zipfile
mode,builder,temp_record,sentinel=sys.argv[1:]
old_create=tempfile.mkstemp
def create(*a,**kw):
 fd,name=old_create(*a,**kw)
 pathlib.Path(temp_record).write_text(name)
 return fd,name
tempfile.mkstemp=create
if mode=='archive':
 old_write=zipfile.ZipFile.write
 n=0
 def fail(z,*a,**kw):
  global n
  n+=1
  if n==3: raise OSError('independent archive write failure')
  return old_write(z,*a,**kw)
 zipfile.ZipFile.write=fail
elif mode=='fchmod':
 def fail(*a,**kw): raise OSError('independent fchmod failure')
 os.fchmod=fail
elif mode=='keyboard_interrupt':
 def fail(*a,**kw): raise KeyboardInterrupt('independent integrity interruption')
 zipfile.ZipFile.testzip=fail
elif mode in ('swap_regular','swap_hardlink','delete_temporary'):
 old_fsync=os.fsync
 def swap(fd):
  old_fsync(fd)
  name=pathlib.Path(temp_record).read_text()
  if mode=='delete_temporary': os.unlink(name)
  else:
   os.rename(name,name+'.owned-moved')
   if mode=='swap_regular': pathlib.Path(name).write_text('foreign replacement bytes')
   else: os.link(sentinel,name)
 os.fsync=swap
runpy.run_path(builder,run_name='__main__')
''')

        def case(name, expected_success, fault='', legacy=False, existing=True, mutate=None):
            directory = scratch / name
            directory.mkdir()
            template = directory / 'template'
            shutil.copytree(baseline, template)
            if mutate:
                mutate(template)
            template_before = {str(p.relative_to(template)): identity(p)['sha256']
                               for p in template.rglob('*') if p.is_file()}
            markdown = directory / 'article.md'
            markdown.write_text('# **Scratch & title** with *formatting* F~ST~\nHarmless body.\n[[TABLE2]]\n')
            refs = directory / 'refs.txt'
            refs.write_text('Scratch reference.\n')
            destination = directory / 'article.docx'
            if existing:
                destination.write_bytes(b'prior destination bytes\n')
                destination.chmod(0o604)
            destination_before = identity(destination) if existing else None
            sentinel = directory / 'unrelated.txt'
            sentinel.write_text('unrelated file bytes\n')
            sentinel_before = identity(sentinel)
            legacy_path = Path(str(destination) + '.tmp-build')
            if legacy:
                legacy_path.symlink_to(sentinel)
            record = directory / 'temp.json'
            environment = dict(os.environ, ARTICLE_TEMPLATE=str(template), ARTICLE_MD=str(markdown),
                               ARTICLE_REFS=str(refs), ARTICLE_DOCX=str(destination))
            process = subprocess.run([sys.executable, '-I', str(wrapper), fault, str(BUILDER), str(record), str(sentinel)],
                                     env=environment, cwd=directory, capture_output=True, text=True, timeout=30)
            temporary = Path(record.read_text()) if record.exists() else None
            item = {'name': name, 'returncode': process.returncode, 'expected_success': expected_success,
                    'stderr': process.stderr, 'destination_preserved': identity(destination) == destination_before if existing and process.returncode else None,
                    'sentinel_preserved': identity(sentinel) == sentinel_before,
                    'source_template_preserved': template_before == {str(p.relative_to(template)): identity(p)['sha256']
                        for p in template.rglob('*') if p.is_file()},
                    'legacy_link_preserved': not legacy or legacy_path.is_symlink() and os.readlink(legacy_path) == str(sentinel),
                    'temporary_present': bool(temporary and os.path.lexists(temporary))}
            normal_checks = ((process.returncode == 0) == expected_success and item['sentinel_preserved']
                             and item['source_template_preserved'] and item['legacy_link_preserved'])
            if process.returncode:
                normal_checks = normal_checks and (item['destination_preserved'] if existing else not destination.exists())
                if fault == 'swap_regular':
                    normal_checks = normal_checks and temporary.read_text() == 'foreign replacement bytes'
                elif fault == 'swap_hardlink':
                    normal_checks = normal_checks and os.path.samefile(temporary, sentinel)
                else:
                    normal_checks = normal_checks and not item['temporary_present']
            else:
                normal_checks = normal_checks and not destination.is_symlink() and not item['temporary_present']
                normal_checks = normal_checks and stat.S_IMODE(destination.stat().st_mode) == (0o604 if existing else 0o644)
                with zipfile.ZipFile(destination) as archive:
                    root_relationships = ET.fromstring(archive.read('_rels/.rels'))
                    core_target = next(n.get('Target') for n in root_relationships if n.get('Type') == CORE_REL)
                    core = ET.fromstring(archive.read(core_target.lstrip('/')))
                    text_title = core.find(DC + 'title').text
                    visible = ''.join(ET.fromstring(archive.read('word/document.xml')).find(W + 'body').find(W + 'p').itertext())
                    normal_checks = normal_checks and text_title == visible
                    item.update(core_target=core_target, core_title=text_title, visible_title=visible)
                    old_core_part = template / core_target.lstrip('/')
                    if old_core_part.exists():
                        old_core = ET.parse(old_core_part).getroot()
                        before_properties = [(n.tag, n.attrib, n.text) for n in old_core if n.tag != DC + 'title']
                        after_properties = [(n.tag, n.attrib, n.text) for n in core if n.tag != DC + 'title']
                        normal_checks = normal_checks and before_properties == after_properties
                        item['other_core_properties_preserved'] = before_properties == after_properties
                    headers = [''.join(c.itertext()) for c in ET.fromstring(archive.read('word/document.xml')).find('.//' + W + 'tbl').find(W + 'tr').findall(W + 'tc')]
                    item['headers'] = headers
                    normal_checks = normal_checks and headers == ['Zone pair', 'n (first zone)', 'n (second zone)', 'FST', '95% CI', 'Excludes zero']
            item['passed'] = bool(normal_checks)
            results.append(item)

        case('legacy_unrelated_link_success', True, legacy=True)
        case('legacy_unrelated_link_archive_failure', False, fault='archive', legacy=True)
        case('no_prior_destination_default_mode', True, existing=False)
        for fault in ('fchmod', 'keyboard_interrupt', 'swap_regular', 'swap_hardlink', 'delete_temporary'):
            case(fault, False, fault=fault)

        def duplicate_core_relationship(template):
            path = template / '_rels/.rels'
            tree = ET.parse(path)
            target = next(n.get('Target') for n in tree.getroot() if n.get('Type') == CORE_REL)
            ET.SubElement(tree.getroot(), REL + 'Relationship', {'Id': 'anotherCore', 'Type': CORE_REL, 'Target': target})
            tree.write(path)
        case('duplicate_core_relationship_rejected', False, mutate=duplicate_core_relationship)

        def external_core(template):
            path = template / '_rels/.rels'
            tree = ET.parse(path)
            rel = next(n for n in tree.getroot() if n.get('Type') == CORE_REL)
            rel.set('TargetMode', 'External')
            rel.set('Target', 'https://example.invalid/core.xml')
            tree.write(path)
        case('external_core_relationship_rejected', False, mutate=external_core)

        def alternate_title(template):
            path = template / 'docProps/core.xml'
            tree = ET.parse(path)
            ET.SubElement(tree.getroot(), DC + 'description').text = 'Independent sentinel description & text.'
            tree.write(path)
        case('unrelated_core_properties_retained', True, mutate=alternate_title)

        def encoded_override(template):
            path = template / '[Content_Types].xml'
            tree = ET.parse(path)
            for item in tree.getroot():
                if item.get('PartName') == '/docProps/core.xml':
                    item.set('PartName', '/docProps/%63ore.xml')
            tree.write(path)
        # Own validator resolves encoded PartName declarations. This probes whether
        # adding metadata introduces a second override for that same decoded part.
        case('encoded_core_override_supported_by_validator', True, mutate=encoded_override)

    stable = identity(BUILDER) == helper_before
    protected_after = [identity(p) for p in documents]
    output = {'generated_utc': datetime.now(timezone.utc).isoformat(),
              'builder': helper_before, 'driver': identity(Path(__file__).resolve()),
              'builder_stable': stable, 'protected_before': protected_before, 'protected_after': protected_after,
              'protected_bytes_unchanged': protected_before == protected_after,
              'tests': results, 'tests_passed': sum(r['passed'] for r in results),
              'all_passed': stable and protected_before == protected_after and all(r['passed'] for r in results),
              'scope': 'Independent scratch-only assembly checks; no scientific execution, shipping document changes, rendering or previous evidence overwrite.'}
    (OUT / 'independent_builder_followup_results.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'tests': len(results), 'passed': output['tests_passed'], 'all_passed': output['all_passed'],
                      'failed': [r['name'] for r in results if not r['passed']]}))
    return 0 if output['all_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
