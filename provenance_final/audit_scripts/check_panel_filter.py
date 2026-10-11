"""Audit: does any reported codon-panel residue depend on a variant record that
FAILS the Pf8 release filter? Read-only; writes nothing."""
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
            x=requests.Session()
            x.mount("https://",requests.adapters.HTTPAdapter(pool_connections=s.n,pool_maxsize=s.n))
            s._l.s=x
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
def arr(name,idx):
    za=md[f"{name}/.zarray"]; blob=R.get(f"{name}/{idx}")
    if blob is None: return None
    raw=blob if za.get("compressor") is None else numcodecs.get_codec(za["compressor"]).decode(blob)
    if np.dtype(za["dtype"]).kind=="O" or za.get("filters"):
        return np.asarray(numcodecs.get_codec(za["filters"][0]).decode(raw)).reshape(za["chunks"])
    return np.frombuffer(raw,dtype=np.dtype(za["dtype"])).reshape(za["chunks"])

res=pd.read_csv(RES)
need=set()
for _,r in res.iterrows():
    for p in str(r["positions"]).split(";"):
        need.add((r["contig"], int(p)))
print(f"panel positions: {len(need)}  across contigs: {sorted({c for c,_ in need})}")

nvar=md["variants/POS/.zarray"]["shape"][0]; nvc=-(-nvar//CHUNK)
contigs_needed={c for c,_ in need}
rows={}   # row -> (contig,pos)
print("scanning variant metadata ...",flush=True)
def scan(vc):
    pos=arr("variants/POS",vc)
    if pos is None: return vc,None,None
    ch=arr("variants/CHROM",vc).astype(str)
    m=np.isin(ch,list(contigs_needed))
    if not m.any(): return vc,None,None
    return vc,pos,ch
with cf.ThreadPoolExecutor(12) as ex:
    for vc,pos,ch in ex.map(scan,range(nvc)):
        if pos is None: continue
        for h in np.nonzero(np.isin(pos,[p for _,p in need]))[0]:
            k=(ch[h],int(pos[h]))
            if k in need: rows[int(vc*CHUNK+h)]=k
print(f"variant records at panel positions: {len(rows)}")

det=[]
for r,(c,p) in sorted(rows.items()):
    vc=r//CHUNK; off=r-vc*CHUNK
    det.append(dict(row=r,contig=c,pos=p,
        filter_pass=bool(arr("variants/FILTER_PASS",vc)[off]),
        numalt=int(arr("variants/numalt",vc)[off])))
d=pd.DataFrame(det)
print(f"\nFILTER_PASS=True : {int(d.filter_pass.sum())}")
print(f"FILTER_PASS=False: {int((~d.filter_pass).sum())}")
print(f"numalt distribution: {collections.Counter(d.numalt.tolist())}")
bad=d[~d.filter_pass]
print(f"\nnon-PASS records: {len(bad)} at {bad.pos.nunique()} distinct positions")

if len(bad):
    meta=pd.read_csv(SAMPLES)
    sc_=[c for c in meta.columns if c.lower() in ("sample","sample_id","id")][0]
    want=meta[sc_].astype(str).tolist()
    nsc=-(-md["samples/.zarray"]["shape"][0]//md["samples/.zarray"]["chunks"][0])
    ids=[]
    for i in range(nsc):
        a=arr("samples",i); ids.extend([x.decode() if isinstance(x,bytes) else str(x) for x in a])
    ids=np.array(ids[:md["samples/.zarray"]["shape"][0]])
    look={s:i for i,s in enumerate(ids)}
    gi=np.array([look[s] for s in want if s in look])
    sch=sorted({int(s)//SCHUNK for s in gi})
    brows=sorted(bad.row.tolist())
    print(f"fetching GT for {len(brows)} non-PASS records x {len(sch)} sample chunks ...",flush=True)
    GT=np.full((len(brows),len(ids),2),-1,dtype=np.int8)
    bi={r:i for i,r in enumerate(brows)}
    jobs=sorted({(r//CHUNK,sc) for r in brows for sc in sch})
    def g(j):
        vc,sc=j; return vc,sc,arr("calldata/GT",f"{vc}.{sc}.0")
    with cf.ThreadPoolExecutor(12) as ex:
        for vc,sc,a in ex.map(g,jobs):
            if a is None: continue
            for r in brows:
                if r//CHUNK!=vc: continue
                GT[bi[r],sc*SCHUNK:sc*SCHUNK+a.shape[1]]=a[r-vc*CHUNK,:,:]
    print(f"  {R.bytes/1e6:.0f} MB\n")
    print("=== do any of our 1,900 isolates carry a non-reference allele at a non-PASS record? ===")
    tot=0
    for r in brows:
        gg=GT[bi[r]][gi]
        nz=int(((gg[:,0]>0)|(gg[:,1]>0)).sum())
        rowinfo=bad[bad.row==r].iloc[0]
        if nz: print(f"  YES  {rowinfo.contig}:{rowinfo.pos} (numalt={rowinfo.numalt}) -> {nz} carrier(s)")
        tot+=nz
    print(f"\nTOTAL non-reference calls sourced from non-PASS records: {tot}")
    if tot==0:
        print("=> No reported panel residue depends on a filter-failing record.")
print(f"\ntotal fetched {R.bytes/1e6:.0f} MB")
