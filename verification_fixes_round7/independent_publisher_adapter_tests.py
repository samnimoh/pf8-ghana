"""Scratch-only publisher gate checks; never publish manuscript deliverables."""
import contextlib, copy, datetime, hashlib, io, json, runpy, shutil, subprocess, sys, tempfile, types
from pathlib import Path
from pypdf import PdfWriter
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'verification_fixes_round7/publish_reviewed_pdfs.py'
source_bytes=SCRIPT.read_bytes()
def identity(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
results=[]
with tempfile.TemporaryDirectory(prefix='pf8-publisher-adapter-',dir='/private/tmp') as d:
 project=Path(d);evidence=project/'evidence';evidence.mkdir();(project/'article').mkdir()
 copied=evidence/'publish_reviewed_pdfs.py';copied.write_bytes(source_bytes)
 manifest=[];visuals={};files={};destination_bytes={}
 for label,rel in [('article','article/Pf8_Ghana_article.docx'),('manuscript','Pf8_Ghana_manuscript_REVISED.docx'),('supplement','article/Additional_file_1.docx')]:
  src=project/rel;src.write_bytes(('dummy scratch source '+label).encode());files[src]=src.read_bytes()
  folder=project/'render'/label;folder.mkdir(parents=True);pdf=folder/(src.stem+'.pdf')
  writer=PdfWriter();writer.add_blank_page(width=72,height=72)
  with pdf.open('wb') as f:writer.write(f)
  files[pdf]=pdf.read_bytes();png=folder/'page-1.png';png.write_bytes(('dummy scratch image '+label).encode());files[png]=png.read_bytes()
  record={'label':label,'source':identity(src),'rendered_pdf':identity(pdf),'pages':1,'page_images':[identity(png)]};manifest.append(record)
  visuals[label]={'label':label,'source':record['source'],'rendered_pdf':record['rendered_pdf'],'pages':1,'status':'bounded_pass','findings':[],'original_detail_pages_inspected':[1],'page_images_inspected':record['page_images']}
  dest=src.with_suffix('.pdf');destination_bytes[dest]=('original scratch deliverable '+label).encode()
 review={'status':'bounded_pass','findings':[],'source_sha256':{str(p.relative_to(project)):identity(p)['sha256'] for p in files if p.suffix=='.docx'}}
 checks={'checks':{'scratch_check':True}}
 def execute(name,mutator=None,injection=None,optimize=False,success=False):
  m=copy.deepcopy(manifest);v=copy.deepcopy(visuals);r=copy.deepcopy(review);c=copy.deepcopy(checks)
  for p,b in files.items():p.write_bytes(b)
  for p,b in destination_bytes.items():p.write_bytes(b)
  (evidence/'pdf_publication_results.json').unlink(missing_ok=True)
  for p in project.rglob('*.reviewed-*.tmp'):p.unlink()
  if mutator:mutator(m,v,r,c)
  (evidence/'render_results.json').write_text(json.dumps(m));(evidence/'final_document_followup_review.json').write_text(json.dumps(r));(evidence/'document_validation.json').write_text(json.dumps(c))
  for label,record in v.items():(evidence/f'visual_{label}_review.json').write_text(json.dumps(record))
  if optimize:
   cp=subprocess.run([sys.executable,'-I','-O',str(copied)],capture_output=True,text=True);passed=cp.returncode==0;err=cp.stderr.strip().splitlines()[-1] if cp.stderr else None
  else:
   ns=runpy.run_path(str(copied));fn=ns['main'];globals_=fn.__globals__
   if injection=='stage_copy_failure':
    calls=[0]
    def failing_copy(incoming,outgoing):
     calls[0]+=1
     if calls[0]==2:outgoing.write(b'partial scratch stage');raise IOError('injected second stage failure')
     return shutil.copyfileobj(incoming,outgoing)
    globals_['shutil']=types.SimpleNamespace(copyfileobj=failing_copy)
   try:
    with contextlib.redirect_stdout(io.StringIO()):fn()
    passed=True;err=None
   except Exception as e:passed=False;err=type(e).__name__+': '+str(e)
  assert passed==success,(name,passed,err)
  if success:
   assert all(p.read_bytes()==files[Path(x['rendered_pdf']['path'])] for p,x in zip(destination_bytes,manifest))
   assert json.loads((evidence/'pdf_publication_results.json').read_text())['all_passed']
  else:
   assert all(p.read_bytes()==b for p,b in destination_bytes.items()),name
   assert not (evidence/'pdf_publication_results.json').exists(),name
  assert not list(project.rglob('*.reviewed-*.tmp')),name
  results.append({'case':name,'passed':True,'outcome':'success' if passed else 'refused/preserved','error':err})
 execute('complete final matching identities',success=True)
 execute('optimization refuses before publication',optimize=True)
 execute('stale text-reviewed source hash',lambda m,v,r,c:r['source_sha256'].update({'Pf8_Ghana_manuscript_REVISED.docx':'0'*64}))
 execute('nonpassing text review',lambda m,v,r,c:r.update(status='failed'))
 execute('unresolved text finding',lambda m,v,r,c:r['findings'].append({'issue':'scratch'}))
 execute('failed protection check',lambda m,v,r,c:c['checks'].update(scratch_check=False))
 execute('source bytes changed',lambda m,v,r,c:Path(m[1]['source']['path']).write_bytes(b'changed source'))
 execute('render PDF bytes changed',lambda m,v,r,c:Path(m[1]['rendered_pdf']['path']).write_bytes(b'changed pdf'))
 execute('actual image bytes changed',lambda m,v,r,c:Path(m[1]['page_images'][0]['path']).write_bytes(b'changed image'))
 execute('duplicate render label extra',lambda m,v,r,c:m.append(copy.deepcopy(m[0])))
 execute('duplicate render label at expected count',lambda m,v,r,c:m[0].update(label='manuscript'))
 execute('missing original-detail page',lambda m,v,r,c:v['manuscript']['original_detail_pages_inspected'].clear())
 execute('duplicate original-detail page',lambda m,v,r,c:v['manuscript']['original_detail_pages_inspected'].append(1))
 execute('unreviewed image identity',lambda m,v,r,c:v['manuscript']['page_images_inspected'][0].update(sha256='1'*64))
 execute('nonpassing visual review',lambda m,v,r,c:v['manuscript'].update(status='failed'))
 execute('unresolved visual finding',lambda m,v,r,c:v['manuscript']['findings'].append({'issue':'scratch'}))
 execute('PDF page count mismatch',lambda m,v,r,c:m[1].update(pages=2))
 execute('second staging copy failure preserves all originals',injection='stage_copy_failure')
 assert SCRIPT.read_bytes()==source_bytes
 report={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewer':'/root/final_document_check','status':'bounded_pass','source':identity(SCRIPT),'driver':identity(Path(__file__)),'findings':[],'tests':results,'test_count':len(results),'pass_count':sum(x['passed'] for x in results),'scope':'Current publisher was copied byte-identically into private scratch. Only synthetic byte sources/images, one-page PDF fixtures and scratch destinations were used; no shipping document or scientific pipeline executed.','limits':['Atomic replacement is per PDF, not a three-file transaction. A failure during later destination replacement could leave a mixed set; every PDF was staged and checked first.','The gate validates bound review assertions; it cannot independently prove an image was opened or scientific claims are correct.','Read/source hashing is not locking; concurrent source changes after gates require another check.']}
 (ROOT/'verification_fixes_round7/independent_publisher_adapter_review.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'tests':len(results),'passed':len(results),'publisher_sha256':report['source']['sha256'],'status':report['status']}))
