"""Read-level check of the single pfk13 Asn458Asp call. Read-only; writes nothing."""
import json, sys, threading, time
import concurrent.futures as cf
import numpy as np, pandas as pd, requests, numcodecs

PF8 = "https://pf8-release.cog.sanger.ac.uk/zarr"
CHUNK, SCHUNK = 131072, 100
CONTIG = "Pf3D7_13_v3"
POSITIONS = [1725624, 1725625, 1725626]   # codon 458, minus strand
SAMPLES_CSV = "/media/biodataA/pf8/gyadu/interim/analysis_samples.csv"

class Remote:
    def __init__(self, base, n=16):
        self.base=base.rstrip("/"); self.n=n; self._l=threading.local()
        self.lock=threading.Lock(); self.bytes=0
    def _s(self):
        s=getattr(self._l,"s",None)
        if s is None:
            s=requests.Session()
            a=requests.adapters.HTTPAdapter(pool_connections=self.n,pool_maxsize=self.n)
            s.mount("https://",a); self._l.s=s
        return s
    def get(self,key,attempts=5):
        for k in range(attempts):
            try:
                r=self._s().get(f"{self.base}/{key}",timeout=(30,600))
                if r.status_code==404: return None
                r.raise_for_status()
                with self.lock: self.bytes+=len(r.content)
                return r.content
            except requests.RequestException:
                if k==attempts-1: raise
                time.sleep(min(30,2*2**k))
        return None

R = Remote(PF8)
md = json.loads(R.get(".zmetadata"))["metadata"]

def arr(name, idx):
    za = md[f"{name}/.zarray"]
    blob = R.get(f"{name}/{idx}")
    if blob is None: return None
    raw = blob if za.get("compressor") is None else numcodecs.get_codec(za["compressor"]).decode(blob)
    dt = np.dtype(za["dtype"])
    if dt.kind == "O" or za.get("filters"):
        return np.asarray(numcodecs.get_codec(za["filters"][0]).decode(raw)).reshape(za["chunks"])
    return np.frombuffer(raw, dtype=dt).reshape(za["chunks"])

nvar = md["variants/POS/.zarray"]["shape"][0]
nvc = -(-nvar // CHUNK)
# locate the variant chunk(s) holding our positions
print("scanning POS chunks for the codon-458 positions ...", flush=True)
rows = {}
for vc in range(nvc):
    pos = arr("variants/POS", vc)
    hit = np.nonzero(np.isin(pos, POSITIONS))[0]
    if hit.size == 0: continue
    ch = arr("variants/CHROM", vc).astype(str)
    for h in hit:
        if ch[h] == CONTIG:
            rows[int(vc*CHUNK + h)] = int(pos[h])
    if rows and vc*CHUNK > max(POSITIONS)+CHUNK*2: break
    if len(rows) and vc > 20: break
print("variant rows:", rows)
if not rows: sys.exit("no variant records at those positions")

rl = sorted(rows)
# REF / ALT / FILTER_PASS / numalt for those rows
info={}
for r in rl:
    vc = r // CHUNK; off = r - vc*CHUNK
    ref = arr("variants/REF", vc)[off]
    alt = arr("variants/ALT", f"{vc}.0")[off]
    fp  = arr("variants/FILTER_PASS", vc)[off]
    na  = arr("variants/numalt", vc)[off]
    dec = lambda b: b.decode() if isinstance(b,bytes) else str(b)
    info[r]=dict(pos=rows[r], ref=dec(ref), alt=[dec(a) for a in np.atleast_1d(alt) if dec(a)],
                 filter_pass=bool(fp), numalt=int(na))
    print(f"  row {r} pos {rows[r]} REF={info[r]['ref']} ALT={info[r]['alt']} PASS={info[r]['filter_pass']} numalt={info[r]['numalt']}")

# our 1,900 isolates
meta = pd.read_csv(SAMPLES_CSV)
scol = [c for c in meta.columns if c.lower() in ("sample","sample_id","id")][0]
want = meta[scol].astype(str).tolist()
nsc = -(-md["samples/.zarray"]["shape"][0] // md["samples/.zarray"]["chunks"][0])
allids=[]
for i in range(nsc):
    a = arr("samples", i)
    allids.extend([x.decode() if isinstance(x,bytes) else str(x) for x in a])
allids = np.array(allids[:md["samples/.zarray"]["shape"][0]])
lookup = {s:i for i,s in enumerate(allids)}
gi = np.array([lookup[s] for s in want if s in lookup])
print(f"\nisolates matched: {len(gi)} of {len(want)}")

# fetch GT for those rows over the sample chunks our isolates occupy
sch = sorted({int(s)//SCHUNK for s in gi})
print(f"sample chunks to fetch: {len(sch)}")
GT = np.full((len(rl), len(allids), 2), -1, dtype=np.int8)
def grab(args):
    nm, vc, sc = args
    return nm, vc, sc, arr(nm, f"{vc}.{sc}.0" if nm in ("calldata/GT",) else f"{vc}.{sc}")
jobs=[("calldata/GT", r//CHUNK, sc) for r in rl for sc in sch]
jobs=list({(a,b,c) for a,b,c in jobs})
with cf.ThreadPoolExecutor(12) as ex:
    for nm,vc,sc,a in ex.map(grab, jobs):
        if a is None: continue
        for r in rl:
            if r//CHUNK!=vc: continue
            GT[rl.index(r), sc*SCHUNK:sc*SCHUNK+a.shape[1]] = a[r-vc*CHUNK, :, :]
print(f"  fetched {R.bytes/1e6:.0f} MB")

# find carriers of a non-reference allele among our isolates
for k,r in enumerate(rl):
    g = GT[k][gi]
    nonref = np.nonzero((g[:,0] > 0) | (g[:,1] > 0))[0]
    miss   = int(((g[:,0] < 0) | (g[:,1] < 0)).sum())
    print(f"\nrow {r} pos {info[r]['pos']}: non-reference carriers among our isolates = {len(nonref)}, missing = {miss}")
    for i in nonref:
        sid = want[i]
        print(f"   carrier {sid}  GT={g[i].tolist()}")
        si = lookup[sid]; vc=r//CHUNK; sc=si//SCHUNK
        for nm, lbl in (("calldata/AD","AD"),("calldata/DP","DP"),("calldata/GQ","GQ")):
            za=md[f"{nm}/.zarray"]
            key=f"{vc}.{sc}.0" if len(za['chunks'])==3 else f"{vc}.{sc}"
            a=arr(nm,key)
            if a is None: print(f"     {lbl}: (chunk absent)"); continue
            v=a[r-vc*CHUNK, si-sc*SCHUNK]
            print(f"     {lbl}: {v.tolist() if hasattr(v,'tolist') else v}")
print(f"\ntotal fetched {R.bytes/1e6:.0f} MB")
