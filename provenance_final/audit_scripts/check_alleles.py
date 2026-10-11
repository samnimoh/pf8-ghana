"""Per-ALT-index homozygous carrier counts at the two panel records that carry
BOTH supported and unsupported ALT alleles. Read-only."""
import json, threading, time
import concurrent.futures as cf
import numpy as np, pandas as pd, requests, numcodecs
PF8="https://pf8-release.cog.sanger.ac.uk/zarr"; CHUNK,SCHUNK=131072,100
ROWS={3745867:("pfcrt",76,[403624,403625,403626]), 3746508:("pfcrt",271,[404836,404837,404838])}
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
meta=pd.read_csv("/media/biodataA/pf8/gyadu/interim/analysis_samples.csv")
sc_=[c for c in meta.columns if c.lower() in ("sample","sample_id","id")][0]
want=meta[sc_].astype(str).tolist()
nsc=-(-md["samples/.zarray"]["shape"][0]//md["samples/.zarray"]["chunks"][0])
ids=[]
for i in range(nsc):
    a=arr("samples",i); ids.extend([dec(x) for x in a])
ids=np.array(ids[:md["samples/.zarray"]["shape"][0]]); look={s:i for i,s in enumerate(ids)}
gi=np.array([look[s] for s in want]); sch=sorted({int(s)//SCHUNK for s in gi})
for row,(gene,cod,ps) in ROWS.items():
    vc=row//CHUNK; off=row-vc*CHUNK
    ref=dec(arr("variants/REF",vc)[off])
    alts=[dec(a) for a in np.atleast_1d(arr("variants/ALT",f"{vc}.0")[off]) if dec(a)]
    GT=np.full((len(ids),2),-1,dtype=np.int8)
    def g(sc): return sc,arr("calldata/GT",f"{vc}.{sc}.0")
    with cf.ThreadPoolExecutor(12) as ex:
        for sc,a in ex.map(g,sch):
            if a is not None: GT[sc*SCHUNK:sc*SCHUNK+a.shape[1]]=a[off,:,:]
    gg=GT[gi]
    print(f"\n=== row {row}  {gene} codon {cod}  REF={ref} (len {len(ref)})")
    for k,a in enumerate(alts,1):
        hom=int(((gg[:,0]==k)&(gg[:,1]==k)).sum())
        supported = (len(a)==len(ref))
        disp = a if len(a)<=14 else a[:11]+"..."
        print(f"   ALT{k} = {disp:<16s} len {len(a):>3d}  {'SUPPORTED' if supported else 'SKIPPED (length-changing)':<26s} homozygous carriers = {hom}")
    miss=int(((gg[:,0]<0)|(gg[:,1]<0)).sum())
    het=int((~((gg[:,0]<0)|(gg[:,1]<0))&(gg[:,0]!=gg[:,1])).sum())
    print(f"   missing={miss}  mixed={het}  homozygous-REF={int(((gg[:,0]==0)&(gg[:,1]==0)).sum())}")
print(f"\nfetched {R.bytes/1e6:.0f} MB")
