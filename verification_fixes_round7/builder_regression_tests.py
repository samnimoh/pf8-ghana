"""Round-seven article builder checks; all writes are scratch-only."""
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
BUILDER = ROOT/'tools/build_article.py'
OUT = Path(__file__).resolve().parent
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
CP = '{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}'
DC = '{http://purl.org/dc/elements/1.1/}'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
CT = '{http://schemas.openxmlformats.org/package/2006/content-types}'
CORE_REL = REL[1:-1]+'/metadata/core-properties'


def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main():
    assert __debug__, 'Run without optimization'
    protected = [ROOT/name for name in ('Pf8_Ghana_manuscript_REVISED.docx', 'Pf8_Ghana_manuscript_REVISED.pdf',
        'article/Additional_file_1.docx', 'article/Additional_file_1.pdf',
        'article/Pf8_Ghana_article.docx', 'article/Pf8_Ghana_article.pdf')]
    protected_before = [identity(path) for path in protected]
    builder_before = identity(BUILDER)
    results = []
    with tempfile.TemporaryDirectory(prefix='pf8-round7-builder-', dir='/private/tmp') as tmp:
        tmp = Path(tmp)
        baseline = tmp/'template'
        with zipfile.ZipFile(ROOT/'article/Additional_file_1.docx') as z:
            z.extractall(baseline)
        original_title = ET.parse(baseline/'docProps/core.xml').getroot().find(DC+'title').text
        original_creator = ET.parse(baseline/'docProps/core.xml').getroot().find(DC+'creator').text
        driver = tmp/'fault_driver.py'
        driver.write_text('''import os, pathlib, runpy, sys, tempfile, zipfile
phase, builder, record, sentinel = sys.argv[1:]
saved_mkstemp=tempfile.mkstemp
def capture(*a,**kw):
 if phase=='temp_create': raise OSError('injected temporary creation failure')
 fd,name=saved_mkstemp(*a,**kw)
 pathlib.Path(record).write_text(name)
 return fd,name
tempfile.mkstemp=capture
if phase=='archive':
 saved=zipfile.ZipFile.write
 n=0
 def fail(z,*a,**kw):
  global n
  n+=1
  if n==5: raise OSError('injected archive-write failure')
  return saved(z,*a,**kw)
 zipfile.ZipFile.write=fail
elif phase=='fsync':
 def fail(*a,**kw): raise OSError('injected fsync failure')
 os.fsync=fail
elif phase=='integrity':
 zipfile.ZipFile.testzip=lambda z:'injected bad CRC member'
elif phase=='semantic':
 saved=zipfile.ZipFile.write
 def skip(z,filename,*a,**kw):
  if str(filename).endswith('218857879d6287b87460540cea2d8ec053df7685.png'): return
  return saved(z,filename,*a,**kw)
 zipfile.ZipFile.write=skip
elif phase=='replace':
 def fail(*a,**kw): raise OSError('injected replacement failure')
 os.replace=fail
elif phase=='temp_swap':
 saved=os.fsync
 def swap(fd):
  saved(fd)
  name=pathlib.Path(record).read_text()
  os.rename(name,name+'.moved')
  os.symlink(sentinel,name)
 os.fsync=swap
runpy.run_path(builder,run_name='__main__')
''')
        def case(name, legacy=None, fault='', mutate=None, title='# Scratch title', expected_success=True):
            folder = tmp/name
            folder.mkdir()
            template = folder/'template'
            shutil.copytree(baseline, template)
            if mutate: mutate(template)
            markdown = folder/'scratch.md'
            markdown.write_text(title+'\nHarmless scratch body.\n[[TABLE2]]\n')
            refs = folder/'refs.txt';refs.write_text('Harmless scratch reference.\n')
            destination = folder/'article.docx'
            destination.write_bytes((ROOT/'article/Pf8_Ghana_article.docx').read_bytes())
            destination.chmod(0o640)
            destination_before = identity(destination)
            sentinel = folder/'unrelated.txt'
            sentinel.write_text('Unrelated sentinel must retain exactly these bytes.\n')
            sentinel_before = identity(sentinel)
            old_temp = Path(str(destination)+'.tmp-build')
            if legacy=='unrelated': old_temp.symlink_to(sentinel)
            elif legacy=='destination': old_temp.symlink_to(destination)
            elif legacy=='dangling': old_temp.symlink_to(folder/'absent-target.txt')
            elif legacy=='regular': old_temp.write_text('Unrelated legacy regular file.\n')
            old_temp_state = ('symlink',os.readlink(old_temp)) if old_temp.is_symlink() else ('regular',old_temp.read_bytes()) if old_temp.exists() else None
            record = folder/'created_temp.txt'
            command = [sys.executable,'-I',str(driver),fault,str(BUILDER),str(record),str(sentinel)]
            environment = dict(os.environ,ARTICLE_TEMPLATE=str(template),ARTICLE_MD=str(markdown),
                ARTICLE_REFS=str(refs),ARTICLE_DOCX=str(destination))
            cp = subprocess.run(command,cwd=folder,env=environment,capture_output=True,text=True)
            created = Path(record.read_text()) if record.exists() else None
            after_old = ('symlink',os.readlink(old_temp)) if old_temp.is_symlink() else ('regular',old_temp.read_bytes()) if old_temp.exists() else None
            item = {'case':name,'command':command,'returncode':cp.returncode,'stdout':cp.stdout,'stderr':cp.stderr,
                'destination_before':destination_before,'destination_after':identity(destination),
                'destination_is_regular':not destination.is_symlink() and destination.is_file(),
                'destination_mode':oct(stat.S_IMODE(destination.stat().st_mode)),
                'unrelated_sentinel_preserved':identity(sentinel)==sentinel_before,
                'legacy_path_preserved':old_temp_state==after_old,
                'created_temporary':str(created) if created else None,
                'created_temporary_lexists_after':os.path.lexists(created) if created else False}
            assert (cp.returncode==0)==expected_success,(name,cp.stderr)
            assert item['unrelated_sentinel_preserved'] and item['legacy_path_preserved'],name
            assert item['destination_mode']=='0o640',name
            if expected_success:
                assert item['destination_is_regular'],name
                assert created and created.name.startswith(destination.name+'.tmp-build-') and created.parent==destination.parent
                assert not item['created_temporary_lexists_after'],name
                with zipfile.ZipFile(destination) as z:
                    assert z.testzip() is None
                    document = ET.fromstring(z.read('word/document.xml'))
                    visible = ''.join(document.find(W+'body').find(W+'p').itertext())
                    rels = ET.fromstring(z.read('_rels/.rels'))
                    core_rels = [r for r in rels if r.get('Type')==CORE_REL]
                    assert len(core_rels)==1
                    core_part = core_rels[0].get('Target').lstrip('/')
                    core = ET.fromstring(z.read(core_part))
                    titles = core.findall(DC+'title')
                    assert len(titles)==1 and titles[0].text==visible
                    assert core.find(DC+'creator').text==original_creator if core.find(DC+'creator') is not None else name=='core_absent_unreferenced'
                    table = document.find('.//'+W+'tbl')
                    headers = [''.join(cell.itertext()) for cell in table.find(W+'tr').findall(W+'tc')]
                    assert headers==['Zone pair','n (first zone)','n (second zone)','FST','95% CI','Excludes zero']
                    counts = [[ ''.join(cell.itertext()) for cell in row.findall(W+'tc')[1:3]] for row in table.findall(W+'tr')[1:]]
                    assert counts==[['204','1,334'],['204','25'],['337','25'],['337','1,334'],['1,334','25'],['204','337']]
                    item.update(core_title=titles[0].text,visible_title=visible,table_2_headers=headers,table_2_count_columns=counts,
                        inherited_title_changed=titles[0].text!=original_title,creator_preserved=core.find(DC+'creator').text==original_creator if core.find(DC+'creator') is not None else None)
            else:
                assert item['destination_after']==destination_before,name
                if fault=='temp_swap':
                    assert created.is_symlink() and os.readlink(created)==str(sentinel)
                else:assert not item['created_temporary_lexists_after'],name
            item['passed']=True
            results.append(item)
        case('normal_metadata_headers_mode')
        case('unrelated_legacy_symlink_success',legacy='unrelated')
        case('unrelated_legacy_symlink_failure',legacy='unrelated',fault='archive',expected_success=False)
        case('destination_alias_rejected',legacy='destination',expected_success=False)
        case('dangling_legacy_symlink_untouched',legacy='dangling')
        case('regular_legacy_temp_untouched',legacy='regular')
        for fault in ['archive','fsync','integrity','semantic','replace','temp_create']:
            case('failure_'+fault,fault=fault,expected_success=False)
        case('swapped_unique_temp_never_followed_or_unlinked',fault='temp_swap',expected_success=False)
        case('missing_title_rejected',title='Harmless untitled text.',expected_success=False)
        case('formatted_title_matches_visible',title='# **A & B** and *C* F~ST~ <plain>')
        def core_without_title(template):
            path=template/'docProps/core.xml';tree=ET.parse(path)
            for title in tree.getroot().findall(DC+'title'):tree.getroot().remove(title)
            tree.write(path)
        case('missing_core_title_added',mutate=core_without_title)
        def duplicate_title(template):
            path=template/'docProps/core.xml';tree=ET.parse(path)
            ET.SubElement(tree.getroot(),DC+'title').text='Another stale title'
            tree.write(path)
        case('duplicate_core_titles_replaced',mutate=duplicate_title)
        def absent_unreferenced_core(template):
            (template/'docProps/core.xml').unlink()
            for relpath in [template/'_rels/.rels',template/'[Content_Types].xml']:
                tree=ET.parse(relpath)
                for node in list(tree.getroot()):
                    if node.get('Type')==CORE_REL or node.get('PartName')=='/docProps/core.xml':tree.getroot().remove(node)
                tree.write(relpath)
        case('core_absent_unreferenced',mutate=absent_unreferenced_core)
        def custom_core_location(template):
            (template/'docProps/core.xml').rename(template/'docProps/custom-core.xml')
            for relpath in [template/'_rels/.rels',template/'[Content_Types].xml']:
                tree=ET.parse(relpath)
                for node in tree.getroot():
                    if node.get('Type')==CORE_REL:node.set('Target','docProps/custom-core.xml')
                    if node.get('PartName')=='/docProps/core.xml':node.set('PartName','/docProps/custom-core.xml')
                tree.write(relpath)
        case('custom_core_properties_target_preserved',mutate=custom_core_location)
        case('missing_referenced_core_rejected',mutate=lambda t:(t/'docProps/core.xml').unlink(),expected_success=False)
        case('invalid_core_root_rejected',mutate=lambda t:(t/'docProps/core.xml').write_text('<wrong/>'),expected_success=False)
    protected_after = [identity(path) for path in protected]
    assert protected_before==protected_after
    assert identity(BUILDER)==builder_before
    report={'builder':builder_before,'driver':identity(Path(__file__).resolve()),'tests':results,
        'tests_passed':len(results),'all_passed':True,'protected_before':protected_before,'protected_after':protected_after,
        'scope':'Scratch document assembly only; no scientific runs or deliverable writes. File identity/mode, legacy and unique temporary paths, failure preservation, metadata title and unchanged Table 2 counts checked.'}
    (OUT/'builder_regression_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'tests_passed':len(results),'all_passed':True,'builder_sha256':builder_before['sha256'],'protected_bytes_unchanged':True}))


if __name__=='__main__':
    main()
