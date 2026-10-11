"""How many panel positions carry no variant record at all? Read-only."""
import json, threading, time
import concurrent.futures as cf
import numpy as np, pandas as pd, requests, numcodecs
PF8="https://pf8-release.cog.sanger.ac.uk/zarr"; CHUNK=131072
RES="/media/biodataA/pf8/gyadu/results/codon_panel_residues.csv"
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
res=pd.read_csv(RES)
panel={}
codons={}
for _,r in res.iterrows():
    ps=[int(p) for p in str(r["positions"]).split(";")]
    codons.setdefault((r["gene"],int(r["codon"])),(r["contig"],ps))
    for p in ps: panel[(r["contig"],p)]=0
allpos={p for _,p in panel}; contigs={c for c,_ in panel}
nvar=md["variants/POS/.zarray"]["shape"][0]; nvc=-(-nvar//CHUNK)
def scan(vc):
    pos=arr("variants/POS",vc)
    if pos is None: return None
    lo,hi=min(allpos),max(allpos)
    cand=np.nonzero((pos>=lo)&(pos<=hi))[0]
    if cand.size==0: return None
    ch=arr("variants/CHROM",vc).astype(str)
    return [(ch[i],int(pos[i])) for i in cand if (ch[i],int(pos[i])) in panel]
with cf.ThreadPoolExecutor(12) as ex:
    for o in ex.map(scan,range(nvc)):
        if o:
            for k in o: panel[k]+=1
withrec=sum(1 for v in panel.values() if v>0)
print(f"panel positions              : {len(panel)}")
print(f"positions WITH >=1 record    : {withrec}")
print(f"positions with NO record     : {len(panel)-withrec}")
print(f"total records at panel pos   : {sum(panel.values())}")
# per-codon: how many of its 3 positions have a record
from collections import Counter
dist=Counter()
for (g,cn),(c,ps) in codons.items():
    dist[sum(1 for p in ps if panel[(c,p)]>0)]+=1
print(f"\ncodons by number of their 3 positions carrying a record: {dict(sorted(dist.items()))}")
print(f"codons with all 3 positions record-free: {dist[0]}")
