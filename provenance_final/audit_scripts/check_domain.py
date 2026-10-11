"""step12 input-domain audit: do unsupported variant records occur in the ACTUAL panel inputs?
Answers: (1) length-changing ALTs, (2) multi-base REF (MNP) records, (3) record-free codons,
(4) records anchored outside the panel whose REF span overlaps a panel position.
Read-only."""
import json, threading, time, collections
import concurrent.futures as cf
import numpy as np, pandas as pd, requests, numcodecs
PF8="https://pf8-release.cog.sanger.ac.uk/zarr"; CHUNK,SCHUNK=131072,100
RES="/media/biodataA/pf8/gyadu/results/codon_panel_residues.csv"
SAMPLES="/media/biodataA/pf8/gyadu/interim/analysis_samples.csv"
class R0:
    def __init__(s,b,n=16):
        s.base=b.rstrip("/");s.n=n;s._l=threading.local();s.lock=threading.Lock();s.bytes=0
    def _s(s):
        x=getattr(s._l,"s",None)
        if x is None:
            x=requests.Session(); x.mount("https://",requests.adapters.HTTPAdapter(pool_connections=s.n,pool_maxsize=s.n)); s._l.s=x
        return x
    def get(s,k,at=5):
        for i in range(at):
            try:
                r=s._s().get(f"{s.base}/{k}",timeout=(30,600))
                if r.status_code==404: return None
                r.raise_for_status()
                with s.lock: s.bytes+=len(r.content)
                return r.content
            except requests.RequestException:
                if i==at-1: raise
                time.sleep(min(30,2*2**i))
R=R0(PF8); md=json.loads(R.get(".zmetadata"))["metadata"]
def arr(n,i):
    za=md[f"{n}/.zarray"]; b=R.get(f"{n}/{i}")
    if b is None: return None
    raw=b if za.get("compressor") is None else numcodecs.get_codec(za["compressor"]).decode(b)
    if np.dtype(za["dtype"]).kind=="O" or za.get("filters"):
        return np.asarray(numcodecs.get_codec(za["filters"][0]).decode(raw)).reshape(za["chunks"])
    return np.frombuffer(raw,dtype=np.dtype(za["dtype"])).reshape(za["chunks"])
dec=lambda b: b.decode() if isinstance(b,bytes) else str(b)

res=pd.read_csv(RES)
panel={}   # (contig,pos) -> list of "gene codon"
codons={}  # (gene,codon) -> (contig,[p1,p2,p3])
for _,r in res.iterrows():
    ps=[int(p) for p in str(r["positions"]).split(";")]
    codons[(r["gene"],int(r["codon"]))]=(r["contig"],ps)
    for p in ps: panel.setdefault((r["contig"],p),[]).append(f"{r['gene']}:{r['codon']}")
print(f"panel positions {len(panel)}  codons {len(codons)}")
allpos={p for _,p in panel}; contigs={c for c,_ in panel}
WIN=60   # look this far upstream for long-REF records that could span a panel position

nvar=md["variants/POS/.zarray"]["shape"][0]; nvc=-(-nvar//CHUNK)
recs=[]
def scan(vc):
    pos=arr("variants/POS",vc)
    if pos is None: return None
    lo,hi=min(allpos)-WIN,max(allpos)+WIN
    cand=np.nonzero((pos>=lo)&(pos<=hi))[0]
    if cand.size==0: return None
    ch=arr("variants/CHROM",vc).astype(str)
    keep=[i for i in cand if ch[i] in contigs]
    if not keep: return None
    ref=arr("variants/REF",vc); alt=arr("variants/ALT",f"{vc}.0")
    na=arr("variants/numalt",vc); fp=arr("variants/FILTER_PASS",vc)
    out=[]
    for i in keep:
        out.append(dict(row=int(vc*CHUNK+i),contig=ch[i],pos=int(pos[i]),
            ref=dec(ref[i]),alts=[dec(a) for a in np.atleast_1d(alt[i]) if dec(a)],
            numalt=int(na[i]),fpass=bool(fp[i])))
    return out
with cf.ThreadPoolExecutor(12) as ex:
    for o in ex.map(scan,range(nvc)):
        if o: recs.extend(o)
print(f"records in window: {len(recs)}")

at_panel=[r for r in recs if (r["contig"],r["pos"]) in panel]
print(f"records exactly AT panel positions: {len(at_panel)}")

# (1) length-changing ALTs at panel positions
indel=[r for r in at_panel if any(len(a)!=len(r["ref"]) for a in r["alts"])]
# (2) multi-base REF (MNP / equal-length multi-base)
mnp=[r for r in at_panel if len(r["ref"])>1 and any(len(a)==len(r["ref"]) for a in r["alts"])]
# (4) records anchored elsewhere whose REF span covers a panel position
span=[]
for r in recs:
    if len(r["ref"])<=1: continue
    cov=set(range(r["pos"], r["pos"]+len(r["ref"])))
    hit=[(r["contig"],p) for p in cov if (r["contig"],p) in panel and p!=r["pos"]]
    if hit: span.append((r,hit))
print(f"\n(1) panel records with a length-changing ALT : {len(indel)}")
print(f"(2) panel records with multi-base REF (MNP)  : {len(mnp)}")
print(f"(4) off-anchor records spanning a panel pos  : {len(span)}")

# (3) record-free codons
withrec={(c,p) for c,p in panel if any(r["contig"]==c and r["pos"]==p for r in at_panel)}
free=[(g,cn) for (g,cn),(c,ps) in codons.items() if not any((c,p) in withrec for p in ps)]
print(f"(3) codons with ZERO variant records at all 3 positions: {len(free)}")
for g,cn in free[:20]: print(f"      {g} codon {cn}")

flag=sorted({r["row"] for r in indel}|{r["row"] for r in mnp}|{r["row"] for r,_ in span})
print(f"\nrows needing genotype check: {len(flag)}")
if flag:
    for r in indel+mnp+[a for a,_ in span]:
        if r["row"] in flag:
            print(f"   row {r['row']} {r['contig']}:{r['pos']} REF={r['ref']} ALT={r['alts']} "
                  f"numalt={r['numalt']} PASS={r['fpass']} codons={panel.get((r['contig'],r['pos']),'(off-anchor)')}")
    meta=pd.read_csv(SAMPLES)
    sc_=[c for c in meta.columns if c.lower() in ("sample","sample_id","id")][0]
    want=meta[sc_].astype(str).tolist()
    nsc=-(-md["samples/.zarray"]["shape"][0]//md["samples/.zarray"]["chunks"][0])
    ids=[]
    for i in range(nsc):
        a=arr("samples",i); ids.extend([dec(x) for x in a])
    ids=np.array(ids[:md["samples/.zarray"]["shape"][0]]); look={s:i for i,s in enumerate(ids)}
    gi=np.array([look[s] for s in want]); sch=sorted({int(s)//SCHUNK for s in gi})
    print(f"\nfetching GT for {len(flag)} rows x {len(sch)} sample chunks ...",flush=True)
    tot_hom=tot_het=0
    for row in flag:
        vc=row//CHUNK; off=row-vc*CHUNK
        GT=np.full((len(ids),2),-1,dtype=np.int8)
        def g(sc): return sc,arr("calldata/GT",f"{vc}.{sc}.0")
        with cf.ThreadPoolExecutor(12) as ex:
            for sc,a in ex.map(g,sch):
                if a is not None: GT[sc*SCHUNK:sc*SCHUNK+a.shape[1]]=a[off,:,:]
        gg=GT[gi]
        hom=int(((gg[:,0]>0)&(gg[:,0]==gg[:,1])).sum())
        het=int(((~((gg[:,0]<0)|(gg[:,1]<0)))&(gg[:,0]!=gg[:,1])).sum())
        tot_hom+=hom; tot_het+=het
        print(f"   row {row}: homozygous-ALT carriers={hom}  mixed={het}")
    print(f"\n TOTAL homozygous-ALT carriers at unsupported records: {tot_hom}")
    print(f" TOTAL mixed (would be excluded anyway):               {tot_het}")
    print("\n => homozygous-ALT carriers at an unsupported record are the ONLY ones that could be")
    print("    silently reported with the reference-derived residue.")
print(f"\nfetched {R.bytes/1e6:.0f} MB")
