import re, html, sys, collections
P="word/document.xml"; x=open(P,encoding="utf-8").read()
LAB=r'[0-9A-F]+\.\d+[a-z]?'
PARA=re.compile(r'<w:p>.*?</w:p>', re.S)
RUNRE=re.compile(r'(<w:t(?: xml:space="preserve")?>)(.*?)(</w:t>)', re.S)

# ---- pass 1: captions, anchored at paragraph start, in document order ----
paras=[(m.start(), m.end(), m.group(0)) for m in PARA.finditer(x)]
def ptext(p): return "".join(html.unescape(q.group(2)) for q in RUNRE.finditer(p)).strip()
seq={"Figure":0, "Table":0}
capsites=collections.defaultdict(list)   # (kind,label) -> [(para_index, number)]
capnum={}                                # para_index -> (kind, number)
for i,(a,b,p) in enumerate(paras):
    t=ptext(p)
    m=re.match(rf'(Figure|Table) ({LAB})\.', t)
    if not m: continue
    kind, lab = m.group(1), m.group(2)
    seq[kind]+=1
    capsites[(kind,lab)].append((i, seq[kind]))
    capnum[i]=(kind, seq[kind])
print(f"captions: figures {seq['Figure']}, tables {seq['Table']}")
dups=sorted(l for (k,l),v in capsites.items() if len(v)>1)
print(f"original labels used more than once ({len(dups)}): {dups}")

# ---- pass 2: rewrite every mention, resolving to the nearest caption ----
n_rw=[0]
def fix_para(idx, ptxt):
    def one(m):
        kind, lab = m.group(1), m.group(2)
        sites=capsites.get((kind,lab))
        if not sites: return m.group(0)
        if idx in capnum and capnum[idx][0]==kind and any(s[0]==idx for s in sites):
            n=[s[1] for s in sites if s[0]==idx][0]
        else:
            n=min(sites, key=lambda s: abs(s[0]-idx))[1]
        n_rw[0]+=1
        return f"{kind} S{n}"
    return re.sub(rf'(Figure|Table) ({LAB})(?!\d)(?![a-z])(?!\.\d)', one, ptxt)

def enc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
out=[]; prev=0
for i,(a,b,p) in enumerate(paras):
    # rewrite within each run of this paragraph, but resolve using paragraph index
    def runsub(m):
        o,t,c = m.group(1), html.unescape(m.group(2)), m.group(3)
        nt=fix_para(i, t)
        return o+(enc(nt) if nt!=t else m.group(2))+c
    newp=RUNRE.sub(runsub, p)
    out.append(x[prev:a]); out.append(newp); prev=b
out.append(x[prev:]); x="".join(out)
print(f"mentions rewritten: {n_rw[0]}")

# ---- verify ----
paras2=[m.group(0) for m in PARA.finditer(x)]
flat2="".join(ptext(p) for p in paras2)
left=sorted(set(re.findall(rf'(?:Figure|Table) {LAB}(?!\d)(?![a-z])(?!\.\d)', flat2)))
if left: sys.exit(f"ABORT: old ids remain: {left[:10]}")
tl=[]; fl=[]
for p in paras2:
    m=re.match(r'(Figure|Table) (S\d+)\.', ptext(p))
    if m: (fl if m.group(1)=="Figure" else tl).append(m.group(2))
dt={k:v for k,v in collections.Counter(tl).items() if v>1}
df={k:v for k,v in collections.Counter(fl).items() if v>1}
if dt or df: sys.exit(f"ABORT: duplicates remain — tables {dt}, figures {df}")
NF, NT = len(fl), len(tl)
print(f"after renumbering: Figure S1–S{NF} ({NF} captions), Table S1–S{NT} ({NT} captions), no duplicates")
assert sorted(int(s[1:]) for s in fl)==list(range(1,NF+1)), "figure numbering not contiguous"
assert sorted(int(s[1:]) for s in tl)==list(range(1,NT+1)), "table numbering not contiguous"
print("numbering is contiguous and complete")

# ---- retitle + preamble ----
def sub1(o,n,l):
    global x
    c=x.count(o)
    if c!=1: sys.exit(f"ABORT [{l}]: found {c}")
    x=x.replace(o,n); print(f"  ok {l}")
sub1('<w:t xml:space="preserve">Fine-scale spatial population genomics of </w:t>',
 '<w:t xml:space="preserve">Additional file 1 — Supplementary material for: Population differentiation and antimalarial resistance-marker frequencies in </w:t>',"title 1")
sub1('<w:t xml:space="preserve"> across Ghana&apos;s agro-ecological zones: a Pf8 analysis</w:t>',
 '<w:t xml:space="preserve"> across the agro-ecological zones of Ghana, 2009–2021</w:t>',"title 2")
sub1('<w:t xml:space="preserve">Revised working analysis report — second edition</w:t>',
 '<w:t xml:space="preserve">Full analysis record: methods detail, complete results, robustness checks and correction history</w:t>',"subtitle")
sub1('<w:t xml:space="preserve">Revised working manuscript for internal review</w:t>',
 '<w:t xml:space="preserve">Supplementary material accompanying the main article</w:t>',"status")

def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def para(txt, lead=""):
    r=f'<w:r><w:rPr><w:b/><w:bCs/></w:rPr><w:t xml:space="preserve">{esc(lead)}</w:t></w:r>' if lead else ""
    r+=f'<w:r><w:t xml:space="preserve">{esc(txt)}</w:t></w:r>'
    return f'<w:p><w:pPr><w:spacing w:after="140" w:line="276"/></w:pPr>{r}</w:p>'
pre=(para("This document is the complete analysis record behind the main article: the full methods detail, every "
  "robustness check that was run, the limitations register, and the record of defects found and corrected during "
  "the analysis. It is supplied so that any number in the article can be traced to the output that produced it, "
  "and so that the corrections made along the way are on the record rather than invisible.", "What this document is. ")
 + para(f"Display items are numbered sequentially in the order they appear: Figure S1 to Figure S{NF} and Table S1 "
  f"to Table S{NT}. Every caption carries its own number. In the working report from which this document derives, "
  f"{len(dups)} labels had each been used for more than one display item and three carried letter suffixes, so a "
  f"cross-reference could be ambiguous. Captions here have unique labels. References to reused original labels "
  f"are assigned to the nearest matching caption; this rule does not by itself establish the intended referent, "
  f"which requires contextual review. Section numbering is unchanged, so references of the form "
  f"“Section 6.9” still resolve within this document.", "Numbering. ")
 + para("Section 11 is the reference list. Every entry was checked against a primary source — the publisher’s "
  "deposit, the journal’s record, the archive record or the issuing organisation’s page — rather than against a "
  "citation aggregator.", "References. ")
 + para("Sections 3 and 5 give the methods and analytical decisions in full; Section 6 the complete results; "
  "Section 8 the robustness checks, including the six-scenario threshold sensitivity analysis; Section 9 the "
  "limitations register; and Section 12 the appendices.", "Where to look. "))
i=x.index('<w:p><w:pPr><w:pStyle w:val="Heading1"/>')
x=x[:i]+pre+x[i:]
print("  ok preamble")
open(P,"w",encoding="utf-8").write(x)
print(f"document.xml {len(x)} bytes")
