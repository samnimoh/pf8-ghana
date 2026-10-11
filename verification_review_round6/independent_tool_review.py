"""Read-only review of document helper safety using scratch-only test inputs."""
import hashlib, json, os, pathlib, shutil, subprocess, tempfile, zipfile
from xml.etree import ElementTree as ET

ROOT = pathlib.Path('/Users/samnimoh/Desktop/chromo')
PYTHON = pathlib.Path('/Users/samnimoh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3')
SCRATCH = pathlib.Path(tempfile.mkdtemp(prefix='pf8_round6_independent_tools_', dir='/private/tmp'))
FILES = [ROOT/'tools'/n for n in ('build_article.py','apply_edits.py','make_supplement.py','README.md','references_apa.txt')]
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
before = {str(p): sha(p) for p in FILES}
results = []
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def run(script, cwd, env):
    args = [str(PYTHON), '-I', str(ROOT/'tools'/script)]
    cp = subprocess.run(args, cwd=cwd, env=dict(os.environ, **env), capture_output=True, text=True)
    return {'command': args, 'cwd': str(cwd), 'environment_overrides': env, 'returncode': cp.returncode,
            'stdout': cp.stdout, 'stderr': cp.stderr}

def editor_case(name, paragraphs, edits, **overrides):
    folder=SCRATCH/name; (folder/'word').mkdir(parents=True)
    xmlpath = folder/'word/document.xml'
    xml = '<w:document xmlns:w="'+W+'"><w:body>'+''.join('<w:p><w:r><w:t>'+p+'</w:t></w:r></w:p>' for p in paragraphs)+'</w:body></w:document>'
    xmlpath.write_text(xml)
    editpath=folder/'edits.json'; editpath.write_text(json.dumps(edits))
    initial=sha(xmlpath)
    record=run('apply_edits.py', folder, {'EDITS': str(editpath), 'DRY':'0', **overrides})
    record.update({'name':name,'edits':edits,'before_sha256':initial,'after_sha256':sha(xmlpath),
                   'document_unchanged':initial==sha(xmlpath), 'result_paragraphs':[''.join(p.itertext()) for p in ET.fromstring(xmlpath.read_text()).findall('.//{'+W+'}p')]})
    results.append(record)
    return record

editor_case('optional_metadata', ['one good phrase'], [{'quote':'good','repl':'better'}])
editor_case('unmatched_no_write', ['one good phrase'], [{'quote':'good','repl':'better'},{'quote':'absent','repl':'present'}])
editor_case('exact_duplicates_rejected', ['alpha beta', 'alpha beta'], [{'quote':'alpha beta','repl':'new phrase'}])
editor_case('exact_occurrence2', ['alpha beta', 'alpha beta'], [{'quote':'alpha beta','repl':'new phrase','occurrence':2}])
editor_case('whitespace_duplicates', ['alpha  beta', 'alpha   beta'], [{'quote':'alpha beta','repl':'new phrase'}])
editor_case('whitespace_occurrence2', ['alpha  beta', 'alpha   beta'], [{'quote':'alpha beta','repl':'new phrase','occurrence':2}])
editor_case('unique_bad_occurrence', ['one good phrase'], [{'quote':'good','repl':'better','occurrence':2}])
editor_case('cross_paragraph_quote', ['end of one', 'start of next'], [{'quote':'one'+'start','repl':'merged'}])
editor_case('same_run_conflict', ['alpha beta'], [{'quote':'alpha','repl':'A'},{'quote':'beta','repl':'B'}], LEFTOVER=str(SCRATCH/'deferred_edits.json'))

template = SCRATCH/'template'; template.mkdir()
with zipfile.ZipFile(ROOT/'article/Additional_file_1.docx') as z: z.extractall(template)
normal=SCRATCH/'normal_builder'; normal.mkdir()
output=normal/'article.docx'
baseenv={'ARTICLE_TEMPLATE':str(template),'ARTICLE_MD':str(ROOT/'article/article.md'),'ARTICLE_DOCX':str(output)}
rec=run('build_article.py', normal, baseenv)
rec.update({'name':'normal_build_from_unrelated_directory','output_exists':output.exists(),'output_sha256':sha(output) if output.exists() else None})
if output.exists():
    with zipfile.ZipFile(output) as z:
        rec['zip_crc_error']=z.testzip()
        rec['reference_list_present']='World Health Organization' in z.read('word/document.xml').decode()
        rec['generated_document_xml_sha256']=hashlib.sha256(z.read('word/document.xml')).hexdigest()
    with zipfile.ZipFile(ROOT/'article/Pf8_Ghana_article.docx') as z:
        rec['current_document_xml_sha256']=hashlib.sha256(z.read('word/document.xml')).hexdigest()
    rec['exact_current_document_xml_match']=rec['generated_document_xml_sha256']==rec['current_document_xml_sha256']
results.append(rec)

missing=SCRATCH/'missing_figure'; missing.mkdir()
out=missing/'article.docx'; shutil.copy2(ROOT/'article/Pf8_Ghana_article.docx',out)
initial=sha(out)
image=template/'word/media/218857879d6287b87460540cea2d8ec053df7685.png'
image.unlink()
rec=run('build_article.py', missing, dict(baseenv,ARTICLE_DOCX=str(out)))
rec.update({'name':'required_figure_missing','removed_template_input':str(image),'before_sha256':initial,'after_sha256':sha(out), 'destination_preserved':initial==sha(out)})
if out.exists():
    with zipfile.ZipFile(out) as z:
        rec['zip_crc_error']=z.testzip()
        ns={'r':'http://schemas.openxmlformats.org/package/2006/relationships'}
        rels=ET.fromstring(z.read('word/_rels/document.xml.rels'))
        rec['unresolved_document_relationships']=[r.attrib for r in rels if r.attrib.get('TargetMode')!='External' and 'word/'+r.attrib['Target'] not in z.namelist()]
results.append(rec)

with zipfile.ZipFile(ROOT/'article/Additional_file_1.docx') as z:
    image.write_bytes(z.read('word/media/'+image.name))
fault_wrapper=SCRATCH/'builder_fault_driver.py'
fault_wrapper.write_text('''import os, runpy, sys, zipfile
phase=sys.argv[1]
if phase=="archive_write":
    saved=zipfile.ZipFile.write
    n=[0]
    def fail(z,*a,**kw):
        n[0]+=1
        if n[0]==5: raise OSError("synthetic fifth archive write failure")
        return saved(z,*a,**kw)
    zipfile.ZipFile.write=fail
elif phase=="integrity_check":
    zipfile.ZipFile.testzip=lambda z: "synthetic_corrupt_member"
elif phase=="fsync":
    def fail(*a,**kw): raise OSError("synthetic fsync failure")
    os.fsync=fail
elif phase=="replace":
    def fail(*a,**kw): raise OSError("synthetic atomic replacement failure")
    os.replace=fail
runpy.run_path(sys.argv[2],run_name="__main__")
''')
for phase in ('archive_write','integrity_check','fsync','replace'):
    folder=SCRATCH/('builder_failure_'+phase); folder.mkdir()
    out=folder/'article.docx'; shutil.copy2(ROOT/'article/Pf8_Ghana_article.docx',out)
    initial=sha(out)
    args=[str(PYTHON),'-I',str(fault_wrapper),phase,str(ROOT/'tools/build_article.py')]
    env=dict(baseenv,ARTICLE_DOCX=str(out))
    cp=subprocess.run(args,cwd=folder,env=dict(os.environ,**env),capture_output=True,text=True)
    results.append({'name':'builder_failure_'+phase,'command':args,'cwd':str(folder),
                    'environment_overrides':env,'returncode':cp.returncode,'stdout':cp.stdout,'stderr':cp.stderr,
                    'before_sha256':initial,'after_sha256':sha(out),'destination_preserved':initial==sha(out),
                    'temporary_archive_exists':pathlib.Path(str(out)+'.tmp-build').exists()})

suppfolder=SCRATCH/'supplement_normal'; (suppfolder/'word').mkdir(parents=True)
with zipfile.ZipFile(ROOT/'Pf8_Ghana_manuscript_REVISED.docx') as z:
    (suppfolder/'word/document.xml').write_bytes(z.read('word/document.xml'))
rec=run('make_supplement.py',suppfolder,{})
rec['name']='normal_supplement_from_copied_manuscript_xml'
rec['generated_xml_sha256']=sha(suppfolder/'word/document.xml')
with zipfile.ZipFile(ROOT/'article/Additional_file_1.docx') as z:
    rec['supplied_supplement_xml_sha256']=hashlib.sha256(z.read('word/document.xml')).hexdigest()
rec['exact_xml_match']=rec['generated_xml_sha256']==rec['supplied_supplement_xml_sha256']
results.append(rec)

def paragraphs(docx):
    with zipfile.ZipFile(docx) as z:
        tree=ET.fromstring(z.read('word/document.xml'))
    return [''.join(t.text or '' for t in p.iter('{'+W+'}t')) for p in tree.iter('{'+W+'}p')]
mainpars=paragraphs(ROOT/'Pf8_Ghana_manuscript_REVISED.docx')
suppars=paragraphs(ROOT/'article/Additional_file_1.docx')
cascade_main=next((i,t) for i,t in enumerate(mainpars) if 'The cascade, defined once' in t)
cascade_supp=next((i,t) for i,t in enumerate(suppars) if 'The cascade, defined once' in t)
s29=next((i,t) for i,t in enumerate(suppars) if t.startswith('Table S29.'))
crossref={'finding':'The early canonical-panel cascade paragraph maps Table 6.8 to Table S29, which is the ADMIXTURE cross-validation error table, unrelated to that cascade.',
          'main_paragraph_zero_based':cascade_main[0],'main_paragraph_text':cascade_main[1],
          'supplement_paragraph_zero_based':cascade_supp[0],'supplement_paragraph_text':cascade_supp[1],
          's29_caption_paragraph_zero_based':s29[0],'s29_caption_text':s29[1],
          'scope':'Observed semantic mismatch; nearest-caption renumbering is reproduced exactly but does not validate intended meaning.'}
head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
final = {'scratch_directory':str(SCRATCH),'scope':'Document helper tests only; no scientific pipeline execution or real deliverable modification.',
         'git_head':head,'comparison_commit':'1afaf4b','reference_list_nonempty_lines':len([x for x in (ROOT/'tools/references_apa.txt').read_text().splitlines() if x.strip()]),
         'source_hashes_before':before,'source_hashes_after':{str(p):sha(p) for p in FILES},'results':results,
         'actual_document_cross_reference':crossref}
dest=ROOT/'verification_review_round6/independent_tool_review.json'
dest.write_text(json.dumps(final,indent=2)+'\n')
print(json.dumps({'evidence':str(dest),'scratch':str(SCRATCH),'tests':[{'name':r['name'],'returncode':r['returncode'],'result_paragraphs':r.get('result_paragraphs'),'destination_preserved':r.get('destination_preserved'),'unresolved_document_relationships':r.get('unresolved_document_relationships')} for r in results]},indent=2))
