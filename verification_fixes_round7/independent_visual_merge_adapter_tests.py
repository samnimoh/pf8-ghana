import copy,datetime,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
repo=Path('/Users/samnimoh/Desktop/chromo')
script=repo/'verification_fixes_round7/merge_visual_reviews.py'
source_bytes=script.read_bytes()
source_hash=hashlib.sha256(source_bytes).hexdigest()
results=[]
def identity(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
with tempfile.TemporaryDirectory(prefix='pf8-visual-merge-review-',dir='/private/tmp') as temp:
 work=Path(temp);(work/'merge_visual_reviews.py').write_bytes(source_bytes)
 manifests=[];parts={};files={}
 for label,n in [('article',18),('manuscript',197),('supplement',198)]:
  folder=work/label;folder.mkdir()
  src=folder/f'{label}.docx';pdf=folder/f'{label}.pdf'
  src.write_bytes(f'scratch source {label}'.encode());pdf.write_bytes(f'scratch PDF {label}'.encode())
  images=[]
  for number in range(1,n+1):
   p=folder/f'page-{number}.png';p.write_bytes(f'scratch image {label} {number}'.encode());images.append(identity(p));files[p]=p.read_bytes()
  files[src]=src.read_bytes();files[pdf]=pdf.read_bytes()
  m={'label':label,'source':identity(src),'rendered_pdf':identity(pdf),'pages':n,'page_images':images};manifests.append(m)
  if label=='article':continue
  for first,last in ([(1,100),(101,150),(151,n)] if label=='manuscript' else [(1,100),(101,n)]):
   parts[f'visual_{label}_part_{first}_{last}.json']={'reviewer':'scratch-reviewer','status':'bounded_pass','findings':[], 'source':m['source'],'rendered_pdf':m['rendered_pdf'],'pages':n,'original_detail_pages_inspected':list(range(first,last+1)),'page_images_inspected':images[first-1:last], 'observations':['scratch-only validation fixture']}
 def execute(name,mutator=None,optimize=False,expect_success=False,expected_existing=()):
  m=copy.deepcopy(manifests);p=copy.deepcopy(parts)
  for file,b in files.items():file.write_bytes(b)
  for label in ['manuscript','supplement']:
   out=work/f'visual_{label}_review.json'
   if out.exists():out.unlink()
  if mutator:mutator(m,p)
  (work/'render_results.json').write_text(json.dumps(m))
  for filename,record in p.items():(work/filename).write_text(json.dumps(record))
  cmd=[sys.executable,'-I']+(['-O'] if optimize else [])+[str(work/'merge_visual_reviews.py')]
  cp=subprocess.run(cmd,cwd='/private/tmp',capture_output=True,text=True)
  written=[label for label in ['manuscript','supplement'] if (work/f'visual_{label}_review.json').exists()]
  success=cp.returncode==0
  assert success==expect_success,(name,cp.returncode,cp.stderr)
  if expect_success:
   assert written==['manuscript','supplement']
   for label,n in [('manuscript',197),('supplement',198)]:
    out=json.loads((work/f'visual_{label}_review.json').read_text())
    assert out['original_detail_pages_inspected']==list(range(1,n+1))
    assert len(out['page_images_inspected'])==n
  else:assert written==list(expected_existing),(name,written)
  results.append({'case':name,'passed':True,'returncode':cp.returncode,'outputs_written':written,'error_tail':cp.stderr.strip().splitlines()[-1] if cp.stderr.strip() else None})
 def first(p):return p['visual_manuscript_part_1_100.json']
 def second(p):return p['visual_manuscript_part_101_150.json']
 def change_bytes(key):
  def mutate(m,p):Path(m[1][key]['path']).write_bytes(b'changed actual scratch bytes')
  return mutate
 execute('complete ordinary isolated execution',expect_success=True)
 execute('optimized Python refused before any output',optimize=True)
 execute('source actual bytes changed',change_bytes('source'))
 execute('PDF actual bytes changed',change_bytes('rendered_pdf'))
 execute('PNG actual bytes changed',lambda m,p:Path(m[1]['page_images'][0]['path']).write_bytes(b'changed PNG bytes'))
 execute('part source identity mismatch',lambda m,p:first(p)['source'].update(sha256='0'*64))
 execute('part PDF identity mismatch',lambda m,p:first(p)['rendered_pdf'].update(bytes=1))
 execute('part page count mismatch',lambda m,p:first(p).update(pages=196))
 execute('missing original-detail page',lambda m,p:first(p)['original_detail_pages_inspected'].pop())
 execute('duplicate original-detail page',lambda m,p:first(p)['original_detail_pages_inspected'].append(100))
 execute('extra original-detail page',lambda m,p:first(p)['original_detail_pages_inspected'].append(101))
 execute('duplicate inspected PNG added',lambda m,p:first(p)['page_images_inspected'].append(copy.deepcopy(first(p)['page_images_inspected'][0])))
 execute('duplicate inspected PNG replaces expected page',lambda m,p:first(p)['page_images_inspected'].__setitem__(-1,copy.deepcopy(first(p)['page_images_inspected'][0])))
 execute('inspected PNG hash disagrees with render',lambda m,p:first(p)['page_images_inspected'][0].update(sha256='1'*64))
 execute('missing PNG file',lambda m,p:Path(m[1]['page_images'][0]['path']).unlink())
 execute('duplicate render label added',lambda m,p:m.append(copy.deepcopy(m[1])))
 execute('duplicate render label within expected count',lambda m,p:m[0].update(label='manuscript'))
 execute('extra duplicate render PNG added',lambda m,p:m[1]['page_images'].append(copy.deepcopy(m[1]['page_images'][0])))
 execute('duplicate render path replaces expected path',lambda m,p:m[1]['page_images'].__setitem__(-1,copy.deepcopy(m[1]['page_images'][0])))
 def duplicate_page_unique_path(m,p):
  bad=work/'shadow';bad.mkdir(exist_ok=True);image=bad/'page-1.png';image.write_bytes(b'shadow image')
  m[1]['page_images'][-1]=identity(image)
 execute('duplicate page number under a unique path',duplicate_page_unique_path)
 execute('overlapping second range',lambda m,p:second(p)['original_detail_pages_inspected'].__setitem__(0,100))
 execute('nonpassing part status',lambda m,p:first(p).update(status='needs_fix'))
 execute('part with unresolved finding',lambda m,p:first(p)['findings'].append({'description':'scratch unresolved finding'}))
 execute('third main range missing original-detail page',lambda m,p:p['visual_manuscript_part_151_197.json']['original_detail_pages_inspected'].pop())
 execute('third main range image hash mismatch',lambda m,p:p['visual_manuscript_part_151_197.json']['page_images_inspected'][0].update(sha256='2'*64))
 execute('later artifact invalid does not publish its record',lambda m,p:p['visual_supplement_part_101_198.json']['original_detail_pages_inspected'].pop(),expected_existing=('manuscript',))
 assert script.read_bytes()==source_bytes,'Merger source changed during review'
 report={
  'reviewer':'/root/final_document_check',
  'reviewed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'source':identity(script),
  'status':'bounded_pass',
  'scope':'Read-only adversarial inspection of the final visual-review merger. 26 narrow scratch-only identity and coverage fixtures were executed with the bundled Python runtime in isolated mode. Dummy scratch DOCX/PDF/PNG byte files exercise identity checks and are not scientific or rendered-document artifacts. No manuscript/source deliverables or scientific analyses were changed/executed.',
  'tests':results,
  'test_count':len(results),
  'pass_count':sum(r['passed'] for r in results),
  'findings':[],
  'resolved_during_review':[
   {'description':'All validation assertions could have been disabled with Python -O. Parent added an explicit non-assert __debug__ guard. Final scratch test demonstrates RuntimeError before any merged output is written.'},
   {'description':'Duplicate render labels and extra duplicate page entries could previously be discarded by dict construction. Parent added expected render count/label set and page_images length/unique-path checks. Final scratch tests reject duplicate labels, duplicate entries, duplicate paths, and duplicate page numbers using distinct paths.'}
  ],
  'conclusions':[
   'The final merger verifies actual source and PDF bytes before processing the artifact, and requires each part to match those identities and the final page count.',
   'Every part has exactly its assigned original-detail page range and exactly one inspected image identity per expected page; the final union is exactly pages 1 through the artifact page count with no overlap.',
   'Every approved image identity must equal both the render manifest identity and current filesystem bytes before that artifact merged record is written.'
  ],
  'limits':[
   'The gate checks assertions of visual inspection; it cannot itself prove a human or agent actually viewed an image. The parent verifies independently created review records.',
   'Validation is per artifact: a passing manuscript record can be written before a later supplement validation fails. The failing supplement is not written, and this is not an all-artifact atomic transaction.',
   'Source/PDF/image bytes are checked once during the merge; the publisher performs another validation before publishing to address later file changes.',
   'Merged JSON writes are direct and are not atomic replacement writes. A write failure can leave a partial QA JSON record, which must be rejected by downstream parsing/identity validation.',
   'The merger does not validate visual aesthetics, scientific meaning, provenance of scientific inputs, schema validity of actual DOCX/PDF/PNG formats, or completeness of publication placeholders.'
  ]
 }
 target=repo/'verification_fixes_round7/independent_visual_merge_adapter_review.json'
 target.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'report':str(target),'source_sha256':source_hash,'tests':len(results),'passed':sum(r['passed'] for r in results),'status':report['status']},indent=2))
