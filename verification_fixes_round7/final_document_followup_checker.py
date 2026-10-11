"""Independent final seven-edit comparison; no document authorship or scientific execution."""
from pathlib import Path
import collections, datetime, hashlib, html, io, json, re, subprocess, zipfile
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
GIT = Path('/Users/samnimoh/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/git')
BASE = 'e7c4cd41b1f631209d25f2ff35eed6ba9c0ec6cd'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
DC = '{http://purl.org/dc/elements/1.1/}'
PARA = re.compile(r'<w:p\b[^>]*(?<!/)>(.*?)</w:p>', re.S)
RUN = re.compile(r'<w:t\b[^>]*(?<!/)>(.*?)</w:t>', re.S)
checks = []
def test(name, value, detail=None):
    checks.append({'check':name, 'pass':bool(value), 'detail':detail})
def sha(b): return hashlib.sha256(b).hexdigest()
def gitbytes(path): return subprocess.check_output([str(GIT), '-C', str(ROOT), 'show', BASE+':'+path])
def parts(b):
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(set(z.namelist()))
        return {i.filename:z.read(i.filename) for i in z.infolist()}
def paragraphs(xml): return [''.join(html.unescape(t.group(1)) for t in RUN.finditer(m.group())) for m in PARA.finditer(xml.decode())]
def shape(xml): return re.sub(r'(<w:t\b[^>]*(?<!/)>).*?(</w:t>)',r'\1\2',xml.decode(),flags=re.S)
def digits(text):return re.findall(r'\d+(?:[.,–-]\d+)*',text)
def core_fields(b):
    x=ET.fromstring(b)
    return {n.tag:n.text for n in x}
def title(p):return core_fields(p['docProps/core.xml']).get(DC+'title')
def ordered_tables(p):
    x=ET.fromstring(p['word/document.xml']); body=x.find(W+'body'); current=None; tables={}; order=[]
    for node in body:
        if node.tag==W+'p':
            t=''.join(n.text or '' for n in node.iter(W+'t'))
            m=re.match(r'Table ([1-4])(?:\s|\.)',t)
            if m: current=m.group(1)
        elif node.tag==W+'tbl':
            assert current and current not in tables, 'Table preceding label is ambiguous'
            tables[current]=[[''.join(n.text or '' for n in cell.iter(W+'t')) for cell in row.findall(W+'tc')] for row in node.findall(W+'tr')]
            order.append(current);current=None
    return order,tables

def main():
    if not __debug__:raise RuntimeError('Review assertions require ordinary Python without -O.')
    initial=json.loads((ROOT/'verification_review_round7/proposed_document_edits.json').read_text())
    follow=json.loads((OUT/'proposed_document_followup_edits.json').read_text())
    edits=initial['manuscript_edits']+follow['manuscript_edits']
    current={}
    for path in ['Pf8_Ghana_manuscript_REVISED.docx','article/Additional_file_1.docx']:
        old=parts(gitbytes(path)); new=parts((ROOT/path).read_bytes()); current[path]=new
        op=paragraphs(old['word/document.xml']); np=paragraphs(new['word/document.xml']); expected=op.copy()
        for e in edits:
            test(path+': baseline unique quote '+e['concept'],op.count(e['quote'])==e['expected_count'])
            if op.count(e['quote'])==1:expected[op.index(e['quote'])]=e['repl']
            test(path+': final unique replacement '+e['concept'],np.count(e['repl'])==e['expected_count'] and e['quote'] not in np)
            test(path+': paragraph digit preservation '+e['concept'],digits(e['quote'])==digits(e['repl']))
        changed=[i for i,(a,b) in enumerate(zip(op,np)) if a!=b]
        test(path+': exactly seven proposed full paragraph replacements',len(changed)==7 and expected==np,changed)
        test(path+': every numeric token retained in order',[digits(p) for p in op]==[digits(p) for p in np])
        test(path+': all nontext document XML exact',shape(old['word/document.xml'])==shape(new['word/document.xml']))
        permitted={'word/document.xml'} | ({'docProps/core.xml'} if path.startswith('article/') else set())
        differences=[k for k in old.keys()|new.keys() if old.get(k)!=new.get(k)]
        test(path+': exact package census retained',old.keys()==new.keys())
        test(path+': only authorised package parts changed',set(differences)<=permitted,differences)
        if path.startswith('article/'):
            visible=[p for p in np if p.startswith('Additional file 1 — Supplementary material for:')]
            test('supplement core title equals unique nonempty visible title',len(visible)==1 and bool(visible[0]) and title(new)==visible[0])
            a=core_fields(old['docProps/core.xml']);b=core_fields(new['docProps/core.xml']);a.pop(DC+'title',None);b.pop(DC+'title',None)
            test('supplement other core fields retained',a==b)
    path='article/article.md';md=gitbytes(path).decode();plan=initial['article_ordering_plan']
    for e in [plan['introductory_citation_edit'],plan['table_marker_move']['remove_context'],plan['table_marker_move']['insert_context']]:
        test('Markdown source original unique accepted operation',md.count(e['quote'])==1);md=md.replace(e['quote'],e['repl'])
    actual=(ROOT/path).read_text();test('Markdown source exactly three authorised operations',actual==md)
    test('Markdown physical table marker order',re.findall(r'\[\[TABLE(\d+)\]\]',actual)==['1','2','3','4'])
    refs=re.findall(r'\bTable ([1-4])\b',actual);test('Markdown first unique table citation order',list(dict.fromkeys(refs))==['1','2','3','4'])
    path='article/Pf8_Ghana_article.docx';old=parts(gitbytes(path));new=parts((ROOT/path).read_bytes());current[path]=new
    oldorder,ot=ordered_tables(old);neworder,nt=ordered_tables(new)
    test('article actual physical table order',neworder==['1','2','3','4'],neworder)
    for n in ['1','2','3','4']:
        test('article Table '+n+' every scientific cell exact',ot[n][1:]==nt[n][1:])
        expected=ot[n][0].copy()
        if n=='2': expected=[('n (first zone)' if i==1 else 'n (second zone)' if i==2 else c) for i,c in enumerate(expected)]
        test('article Table '+n+' exact authorised header text',expected==nt[n][0],nt[n][0])
    op=paragraphs(old['word/document.xml']);np=paragraphs(new['word/document.xml']);oldc=collections.Counter(op);newc=collections.Counter(np)
    expected_removed={p:c for p,c in (oldc-newc).items()};expected_added={p:c for p,c in (newc-oldc).items()}
    intro=next(p for p in op if p.startswith('This study addresses three questions.'))
    repl=intro.replace('define the analysis set (Table 4)?','define the analysis set?')
    test('article paragraph multiset exact except intro and two zone headers',expected_removed=={intro:1,'n':2} and expected_added=={repl:1,'n (first zone)':1,'n (second zone)':1}, {'removed':expected_removed,'added':expected_added})
    test('article core title matches visible title',title(new)==np[0] and bool(np[0]))
    a=core_fields(old['docProps/core.xml']);b=core_fields(new['docProps/core.xml']);a.pop(DC+'title',None);b.pop(DC+'title',None)
    test('article other core metadata unchanged',a==b)
    for k in set(old)&set(new):
        if k.startswith('word/media/'):test('article unchanged figure '+k,old[k]==new[k])
    mainps=paragraphs(current['Pf8_Ghana_manuscript_REVISED.docx']['word/document.xml'])
    candidates=[]
    for i,p in enumerate(mainps):
        if re.search(r'pfk13',p,re.I) and re.search(r'(every one|all\s+23|each)',p,re.I) and re.search(r'fixed|monomorphic',p,re.I):candidates.append({'main_paragraph_index_zero_based':i,'text':p})
    helpers=['tools/build_article.py','tools/make_supplement.py','verification_fixes_round7/apply_document_fixes.py','verification_fixes_round7/apply_followup_document_fixes.py','verification_fixes_round7/rebuild_deliverables.py','verification_fixes_round7/rebuild_followup_deliverables.py','verification_fixes_round7/render_documents.py']
    sources=['Pf8_Ghana_manuscript_REVISED.docx','article/Additional_file_1.docx','article/Pf8_Ghana_article.docx','article/article.md']+helpers
    findings=[c for c in checks if not c['pass']]
    result={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewer':'/root/final_document_check','baseline_git_commit':BASE,'status':'bounded_pass' if not findings else 'failed','source_sha256':{p:sha((ROOT/p).read_bytes()) for p in sources},'checks':checks,'findings':findings,'pfk13_scope_sweep_candidates':candidates,'scope_bounds':'Exact seven substitutions and propagation, digit and OOXML structure preservation, article table/citation/metadata checks. These are editorial consistency checks only. No scientific pipeline or Lean execution; no whole-document scientific certification; visual QA is separate.','historical_record_preserved':'verification_fixes_round7/final_document_review.json retains the initial55check revision and is not treated as the final source review.'}
    result['review_checker']={'path':str(Path(__file__).resolve()),'sha256':sha(Path(__file__).read_bytes())}
    result['manual_concept_review']={
        'near_panmixia':{'main_indices':[981,3607,3977],'disposition':'The only current occurrences explicitly reject the estimate or identify the label as withdrawn while preserving historical account.'},
        'surveillance':{'main_indices':[146,3211,3213,3217,3606,3649,4054],'disposition':'Common-variant scope, statistically detectable differentiation, and rejection of sparse-sampling adequacy are explicit and consistent in the conclusion/body/correction record. The old TableF.2 defect-description quotation is historical and preserved.'},
        'fixed_codon_followup':{'main_indices':[1499,1537,2786,3628],'disposition':'All now explicitly count twenty-two fixed codons, preserving the codon458 exception, recorded rounded values, historical period and per-codon denominator. The Section6.9.8 exception was already explicit and is clarified, not a new finding.'},
        'remaining_pfk13_candidates':'All listed broad-search candidates were read in paragraph context; they either correctly distinguish the screened-resistance negative from codon fixation or describe other panel counts/historical subsets, not all23 fixed.'}
    result['scope_note']='The initial55check report is preserved as an intermediate record; its focused sweep missed two equivalent unqualified claims subsequently found during page review. This final review binds the complete seven-proposal delta and does not repeat the initial only-one contradiction assertion.'
    (OUT/'final_document_followup_review.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'status':result['status'],'checks':len(checks),'failed':len(findings),'report':str(OUT/'final_document_followup_review.json')}))
    if findings:raise ValueError([c['check'] for c in findings])
if __name__=='__main__':main()
