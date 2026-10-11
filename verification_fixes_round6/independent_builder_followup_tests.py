import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path('/Users/samnimoh/Desktop/chromo')
BUILDER = ROOT / 'tools/build_article.py'
SOURCE = ROOT / 'article/Additional_file_1.docx'
RESULT = ROOT / 'verification_fixes_round6/independent_builder_followup.json'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
DOC = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
SCRATCH = Path(tempfile.mkdtemp(prefix='pf8_builder_independent_followup_', dir='/private/tmp'))
BASE = SCRATCH / 'baseline'
BASE.mkdir()
source_bytes = SOURCE.read_bytes()
with zipfile.ZipFile(io.BytesIO(source_bytes)) as archive:
    archive.extractall(BASE)
SOURCE_HASH = hashlib.sha256(BUILDER.read_bytes()).hexdigest()
md_bytes = (ROOT / 'article/article.md').read_bytes()
refs_bytes = (ROOT / 'tools/references_apa.txt').read_bytes()
ROWS = []

def manifest(folder):
    if not folder.exists():
        return None
    result = {}
    for parent, dirs, filenames in os.walk(folder, followlinks=False):
        for name in dirs + filenames:
            path = Path(parent) / name
            relative = str(path.relative_to(folder))
            if path.is_symlink():
                result[relative] = ['symlink', os.readlink(path)]
            elif path.is_file():
                result[relative] = ['file', hashlib.sha256(path.read_bytes()).hexdigest()]
            else:
                result[relative] = ['directory']
    return result

def whole_source(folder):
    for child in BASE.iterdir():
        destination = folder / child.name
        if child.is_dir():
            shutil.copytree(child, destination)
        else:
            shutil.copyfile(child, destination)

def duplicate_root(template, external=False):
    path = template / '_rels/.rels'
    tree = ET.parse(path)
    attrs = {'Id':'rIdIndependentExtra', 'Type': DOC + '/officeDocument',
             'Target':'https://example.invalid/document' if external else 'word/styles.xml'}
    if external:
        attrs['TargetMode'] = 'External'
    tree.getroot().insert(0, ET.Element('{' + REL + '}Relationship', attrs))
    tree.write(path, encoding='utf-8', xml_declaration=True)

def case(name, setup=None, semantic=False, normal=False):
    folder = SCRATCH / name
    folder.mkdir()
    template = folder / 'template'
    shutil.copytree(BASE, template)
    md, refs, output = folder / 'input.md', folder / 'references.txt', folder / 'prior.docx'
    md.write_bytes(md_bytes)
    refs.write_bytes(refs_bytes)
    output.write_bytes(b'prior independent destination sentinel')
    cfg = {'folder':folder, 'template':template, 'md':md, 'refs':refs, 'output':output,
           'work':folder / 'article_pkg'}
    if setup:
        setup(cfg)
    before_folder = manifest(folder)
    before_template = manifest(cfg['template'])
    before_output = cfg['output'].read_bytes()
    before_md, before_refs = cfg['md'].read_bytes(), cfg['refs'].read_bytes()
    env = dict(os.environ, ARTICLE_TEMPLATE=str(cfg['template']), ARTICLE_DOCX=str(cfg['output']),
               ARTICLE_MD=str(cfg['md']), ARTICLE_REFS=str(cfg['refs']))
    args = [sys.executable, '-I', str(BUILDER)]
    cp = subprocess.run(args, cwd=folder, env=env, capture_output=True, text=True)
    output_after = cfg['output'].read_bytes() if cfg['output'].exists() else None
    source_preserved = before_template == manifest(cfg['template'])
    md_preserved = cfg['md'].exists() and cfg['md'].read_bytes() == before_md
    refs_preserved = cfg['refs'].exists() and cfg['refs'].read_bytes() == before_refs
    destination_preserved = output_after == before_output
    folder_preserved = before_folder == manifest(folder)
    row = {'name':name, 'returncode':cp.returncode, 'stdout':cp.stdout, 'stderr':cp.stderr,
           'source_template_preserved':source_preserved, 'markdown_preserved':md_preserved,
           'references_preserved':refs_preserved, 'destination_preserved':destination_preserved,
           'entire_case_tree_preserved':folder_preserved, 'cwd':str(folder), 'command':args}
    if normal:
        row['passed'] = cp.returncode == 0 and source_preserved and md_preserved and refs_preserved
        if cp.returncode == 0:
            with zipfile.ZipFile(cfg['output']) as archive:
                row['zip_crc_error'] = archive.testzip()
                row['passed'] &= row['zip_crc_error'] is None
    else:
        expected_diagnostic = ('exactly one internal root officeDocument relationship' if semantic
                               else 'unsafe build paths')
        row['passed'] = (cp.returncode != 0 and source_preserved and md_preserved and refs_preserved
                         and destination_preserved and (semantic or folder_preserved))
        row['guard_diagnostic_present'] = ('unsafe build paths' in cp.stderr if not semantic
                                           else 'exactly one office document' in cp.stderr)
        row['passed'] &= row['guard_diagnostic_present']
    ROWS.append(row)

def source_is_work(c):
    c['template'].rename(c['work'])
    c['template'] = c['work']

def source_under_work(c):
    c['work'].mkdir()
    c['template'].rename(c['work'] / 'source')
    c['template'] = c['work'] / 'source'

def source_contains_work(c):
    whole_source(c['folder'])
    c['template'] = c['folder']

def source_link_to_work(c):
    source_is_work(c)
    link = c['folder'] / 'linked_source'
    link.symlink_to(c['template'], target_is_directory=True)
    c['template'] = link

def work_is_link(c):
    target = c['folder'] / 'other_directory'
    target.mkdir()
    (target / 'preserve.txt').write_bytes(b'protected work symlink target')
    c['work'].symlink_to(target, target_is_directory=True)

def output_under_work(c, nested=False):
    location = c['work'] / 'nested' if nested else c['work']
    location.mkdir(parents=True)
    c['output'].rename(location / 'prior.docx')
    c['output'] = location / 'prior.docx'

def output_link_to_work(c, hard=False):
    c['work'].mkdir()
    target = c['work'] / 'kept.docx'
    target.write_bytes(b'protected aliased work destination')
    c['output'].unlink()
    if hard:
        os.link(target, c['output'])
    else:
        c['output'].symlink_to(target)

def input_under_work(c, key, hard=False):
    c['work'].mkdir()
    target = c['work'] / c[key].name
    target.write_bytes(c[key].read_bytes())
    if hard:
        c[key].unlink()
        os.link(target, c[key])
    else:
        c[key] = target

def output_under_source(c, hard=False):
    if hard:
        c['output'].unlink()
        os.link(c['template'] / 'word/styles.xml', c['output'])
    else:
        c['output'].rename(c['template'] / 'prior.docx')
        c['output'] = c['template'] / 'prior.docx'

def output_alias_input(c, key, mode):
    c['output'].unlink()
    if mode == 'direct':
        c['output'] = c[key]
    elif mode == 'hard':
        os.link(c[key], c['output'])
    else:
        c['output'].symlink_to(c[key])

def temporary_alias(c, key, hard=False):
    temporary = Path(str(c['output']) + '.tmp-build')
    if hard:
        os.link(c[key], temporary)
    else:
        temporary.symlink_to(c[key])

case('normal_separate_paths', normal=True)
case('source_equals_work', source_is_work)
case('source_below_work', source_under_work)
case('source_contains_work', source_contains_work)
case('source_symlink_to_work', source_link_to_work)
case('work_is_symlink', work_is_link)
case('destination_inside_work', output_under_work)
case('destination_nested_in_work', lambda c: output_under_work(c, nested=True))
case('destination_symlink_to_work_file', output_link_to_work)
case('destination_hardlink_to_work_file', lambda c: output_link_to_work(c, hard=True))
for key in ('md','refs'):
    case(key + '_inside_work', lambda c, key=key: input_under_work(c, key))
    case(key + '_hardlink_to_work', lambda c, key=key: input_under_work(c, key, hard=True))
case('destination_inside_source', output_under_source)
case('destination_hardlink_to_source_part', lambda c: output_under_source(c, hard=True))
for key in ('md','refs'):
    for mode in ('direct','symlink','hard'):
        case('destination_' + mode + '_aliases_' + key, lambda c, key=key, mode=mode: output_alias_input(c,key,mode))
for key in ('output','md','refs'):
    case('temporary_symlink_alias_' + key, lambda c,key=key: temporary_alias(c,key))
    case('temporary_hardlink_alias_' + key, lambda c,key=key: temporary_alias(c,key,hard=True))
case('two_internal_root_documents', lambda c: duplicate_root(c['template']), semantic=True)
case('extra_external_root_document', lambda c: duplicate_root(c['template'],external=True), semantic=True)

after_hash = hashlib.sha256(BUILDER.read_bytes()).hexdigest()
report = {'scope':'Independent scratch-only path-alias and root-office-document follow-up; no tools or deliverables changed.',
          'builder_sha256_before':SOURCE_HASH, 'builder_sha256_after':after_hash,
          'source_hash_stable':SOURCE_HASH == after_hash, 'python':sys.executable,
          'driver':str(Path(__file__).resolve()), 'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'template_snapshot_sha256':hashlib.sha256(source_bytes).hexdigest(),
          'scratch':str(SCRATCH), 'tests':ROWS, 'test_count':len(ROWS),
          'all_passed':SOURCE_HASH == after_hash and all(r['passed'] for r in ROWS),
          'failed_checks':[r['name'] for r in ROWS if not r['passed']],
          'limits':['No full OOXML schema, image decoding, concurrent-write or filesystem-race certification.',
                    'Original adverse review remains unchanged in independent_builder_review.json.']}
RESULT.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key:report[key] for key in ('builder_sha256_before','builder_sha256_after','source_hash_stable','test_count','all_passed','failed_checks')},indent=2))
