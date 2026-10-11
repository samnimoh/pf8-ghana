#!/usr/bin/env python3
"""Read-only source review plus scratch package and failure tests for layout fixes."""
from pathlib import Path
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
BUILDER = ROOT/'tools/build_article.py'
GIT = '/Users/samnimoh/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/git'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = 'http://schemas.openxmlformats.org/package/2006/relationships'
D = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
SCRATCH = Path(tempfile.mkdtemp(prefix='pf8_independent_layout_', dir='/private/tmp'))
ROWS = []


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(root):
    return {str(p.relative_to(root)): sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}


def package(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.testzip() is None
        return {name:z.read(name) for name in z.namelist() if not name.endswith('/')}


source_before = sha(BUILDER.read_bytes())
template_bytes = (ROOT/'article/Additional_file_1.docx').read_bytes()
article_bytes = (ROOT/'article/Pf8_Ghana_article.docx').read_bytes()
markdown_bytes = (ROOT/'article/article.md').read_bytes()
reference_bytes = (ROOT/'tools/references_apa.txt').read_bytes()
base = SCRATCH/'template'
base.mkdir()
with zipfile.ZipFile(io.BytesIO(template_bytes)) as z:
    z.extractall(base)
md, refs = SCRATCH/'input.md', SCRATCH/'references.txt'
md.write_bytes(markdown_bytes)
refs.write_bytes(reference_bytes)
old_builder = SCRATCH/'previous_builder.py'
old_builder.write_bytes(subprocess.check_output([GIT, '-C', str(ROOT), 'show', 'bb1b8db:tools/build_article.py']))
wrapper = SCRATCH/'fault_driver.py'
wrapper.write_text('''import os,sys,runpy,zipfile
phase=sys.argv[1]
if phase=='write':
    original=zipfile.ZipFile.write
    counter=[0]
    def fail(*args,**kwargs):
        counter[0]+=1
        if counter[0]==5:raise OSError('independent write failure')
        return original(*args,**kwargs)
    zipfile.ZipFile.write=fail
elif phase=='crc':
    zipfile.ZipFile.testzip=lambda z:'independent CRC failure'
elif phase=='fsync':
    def fail(*args,**kwargs):raise OSError('independent fsync failure')
    os.fsync=fail
elif phase=='replace':
    def fail(*args,**kwargs):raise OSError('independent replacement failure')
    os.replace=fail
elif phase=='skip_image':
    original=zipfile.ZipFile.write
    def skip(z,path,*args,**kwargs):
        if str(path).endswith('218857879d6287b87460540cea2d8ec053df7685.png'):return
        return original(z,path,*args,**kwargs)
    zipfile.ZipFile.write=skip
runpy.run_path(sys.argv[2],run_name='__main__')
''')


def build(name, *, builder=BUILDER, mutate=None, fault=None, diagnostic=None):
    folder = SCRATCH/name
    folder.mkdir()
    template = folder/'source'
    shutil.copytree(base, template)
    if mutate:
        mutate(template)
    before_source = snapshot(template)
    output = folder/'article.docx'
    output.write_bytes(article_bytes)
    command = [sys.executable, '-I', str(builder)]
    if fault:
        command = [sys.executable, '-I', str(wrapper), fault, str(builder)]
    env = dict(os.environ, ARTICLE_TEMPLATE=str(template), ARTICLE_MD=str(md),
               ARTICLE_REFS=str(refs), ARTICLE_DOCX=str(output))
    cp = subprocess.run(command, env=env, cwd=folder, capture_output=True, text=True)
    preserved_inputs = snapshot(template)==before_source and md.read_bytes()==markdown_bytes and refs.read_bytes()==reference_bytes
    after = output.read_bytes()
    temporary_absent = not Path(str(output)+'.tmp-build').exists()
    row = {'name':name,'command':command,'cwd':str(folder),'returncode':cp.returncode,
           'stdout':cp.stdout,'stderr':cp.stderr,'all_source_bytes_preserved':preserved_inputs,
           'temporary_archive_absent':temporary_absent,'destination_sha256':sha(after)}
    if diagnostic:
        row['destination_preserved'] = after==article_bytes
        row['expected_diagnostic'] = diagnostic
        row['passed'] = preserved_inputs and temporary_absent and after==article_bytes and cp.returncode!=0 and diagnostic in cp.stderr
    else:
        row['passed'] = preserved_inputs and temporary_absent and cp.returncode==0
        if row['passed']:
            package(after)
    ROWS.append(row)
    return after


old_data = build('previous_builder_control', builder=old_builder)
new_data = build('final_builder_normal')
old_parts, new_parts = package(old_data), package(new_data)
old_xml, new_xml = old_parts['word/document.xml'], new_parts['word/document.xml']
plain_new = new_xml.replace(b'<w:keepNext/><w:keepLines/>', b'').replace(b'<w:trPr><w:tblHeader/></w:trPr>', b'')
ROWS.append({'name':'only_declared_heading_and_header_XML_changes',
             'passed':plain_new==old_xml and b'<w:keepNext/><w:keepLines/>' not in old_xml and b'<w:tblHeader/>' not in old_xml,
             'heading_flag_pairs_added':new_xml.count(b'<w:keepNext/><w:keepLines/>'),
             'repeat_header_flags_added':new_xml.count(b'<w:tblHeader/>'),
             'previous_xml_sha256':sha(old_xml),'final_xml_sha256':sha(new_xml)})
old_tree, new_tree = ET.fromstring(old_xml), ET.fromstring(new_xml)
old_text = [''.join(t.text or '' for t in p.iter(W+'t')) for p in old_tree.iter(W+'p')]
new_text = [''.join(t.text or '' for t in p.iter(W+'t')) for p in new_tree.iter(W+'p')]
other_parts_equal = {name:old_parts[name]==new_parts.get(name) for name in old_parts if name!='word/document.xml'}
ROWS.append({'name':'paragraph_text_and_other_package_parts_preserved','passed':old_text==new_text and all(other_parts_equal.values()) and old_parts.keys()==new_parts.keys(),
             'paragraph_count':len(new_text),'non_document_parts_compared':len(other_parts_equal)})
heading_counts = {'Heading1':0,'Heading2':0}
bad_properties = []
for i,p in enumerate(new_tree.iter(W+'p')):
    prop = p.find(W+'pPr')
    style = prop.find(W+'pStyle') if prop is not None else None
    identifier = style.get(W+'val') if style is not None else None
    flags = [] if prop is None else [x.tag for x in prop if x.tag in {W+'keepNext',W+'keepLines'}]
    if identifier in heading_counts:
        heading_counts[identifier] += 1
        if flags != [W+'keepNext',W+'keepLines']:
            bad_properties.append(i)
    elif flags:
        bad_properties.append(i)
ROWS.append({'name':'heading_flags_have_correct_scope_and_values','passed':not bad_properties and all(heading_counts.values()),
             'heading_counts':heading_counts,'bad_paragraph_indices':bad_properties})
tables = list(new_tree.iter(W+'tbl'))
bad_headers = []
for i,tbl in enumerate(tables):
    rows = tbl.findall(W+'tr')
    for j,row in enumerate(rows):
        header = row.find('./'+W+'trPr/'+W+'tblHeader')
        if (j==0 and header is None) or (j>0 and header is not None):
            bad_headers.append([i,j])
ROWS.append({'name':'only_first_table_rows_repeat_as_headers','passed':bool(tables) and not bad_headers,
             'table_count':len(tables),'bad_header_rows':bad_headers})
actual_parts = package((ROOT/'article/Pf8_Ghana_article.docx').read_bytes())
ROWS.append({'name':'actual_article_matches_final_builder_content','passed':actual_parts['word/document.xml']==new_xml,
             'actual_article_sha256':sha((ROOT/'article/Pf8_Ghana_article.docx').read_bytes())})
figure = 'word/media/218857879d6287b87460540cea2d8ec053df7685.png'
build('missing_required_figure',mutate=lambda t:(t/figure).unlink(),diagnostic='missing or empty ARTICLE_TEMPLATE part')


def absent_font_relationship(template):
    path = template/'word/_rels/fontTable.xml.rels'
    tree = ET.parse(path)
    ET.SubElement(tree.getroot(),'{'+R+'}Relationship',{'Id':'rIdIndependentMissing', 'Type':D+'/font', 'Target':'fonts/absent.odttf'})
    tree.write(path,encoding='utf-8',xml_declaration=True)


def duplicate_root(template):
    path = template/'_rels/.rels'
    tree = ET.parse(path)
    ET.SubElement(tree.getroot(),'{'+R+'}Relationship',{'Id':'rIdIndependentRoot', 'Type':D+'/officeDocument', 'Target':'word/styles.xml'})
    tree.write(path,encoding='utf-8',xml_declaration=True)


build('missing_transitive_font',mutate=absent_font_relationship,diagnostic='missing relationship target')
build('duplicate_root_document',mutate=duplicate_root,diagnostic='exactly one office document')
for phase,diagnostic in [('write','independent write failure'),('crc','archive failed its own integrity check'),
                         ('fsync','independent fsync failure'),('replace','independent replacement failure'),
                         ('skip_image','article package is missing required parts')]:
    build('failure_'+phase,fault=phase,diagnostic=diagnostic)
source_after = sha(BUILDER.read_bytes())
report = {'scope':'Independent focused layout and scratch package/failure regression. No source or deliverable edited; no scientific code executed.',
          'builder_sha256_before':source_before,'builder_sha256_after':source_after,'source_hash_stable':source_before==source_after,
          'template_snapshot_sha256':sha(template_bytes),'article_snapshot_sha256':sha(article_bytes),
          'markdown_snapshot_sha256':sha(markdown_bytes),'references_snapshot_sha256':sha(reference_bytes),
          'driver':str(Path(__file__).resolve()),'driver_sha256':sha(Path(__file__).read_bytes()),
          'python':sys.executable,'scratch':str(SCRATCH),'tests':ROWS,'test_count':len(ROWS),
          'all_passed':source_before==source_after and all(row['passed'] for row in ROWS),
          'failed_checks':[row['name'] for row in ROWS if not row['passed']],
          'limits':['No full OOXML schema or rendering validation; parent performs final PDF/layout QA.',
                    'Tests are scoped regressions for document helpers, not analysis reproducibility or statistical validity.']}
(OUT/'independent_builder_layout_followup.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['builder_sha256_before','builder_sha256_after','source_hash_stable','test_count','all_passed','failed_checks']},indent=2))
if not report['all_passed']:
    sys.exit(1)
