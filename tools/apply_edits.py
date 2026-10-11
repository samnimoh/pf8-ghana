import json, os, re, html, sys

XML = "word/document.xml"
EDITS = os.environ["EDITS"]
DRY = os.environ.get("DRY","1") == "1"

x = open(XML, encoding="utf-8").read()
RUN = re.compile(r'<w:t(?: xml:space="preserve")?>(.*?)</w:t>', re.S)
spans = [(m.start(1), m.end(1)) for m in RUN.finditer(x)]
dec   = [html.unescape(x[a:b]) for a, b in spans]
starts, o = [], 0
for d in dec:
    starts.append(o); o += len(d)
flat = "".join(dec)
def enc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def locate(q):
    i = flat.find(q)
    if i >= 0: return i, len(q)
    # whitespace-tolerant retry
    pat = re.escape(q)
    pat = re.sub(r'(\\\s)+', r'\\s+', pat)
    pat = pat.replace(r'\ ', r'\s+')
    m = re.search(pat, flat)
    if m: return m.start(), m.end()-m.start()
    return -1, 0

edits = json.load(open(EDITS))
import bisect
mods = {}        # run index -> new decoded text
applied, missing, conflict = [], [], []

for n, e in enumerate(edits):
    q, r = e["quote"], e["repl"]
    if not q.strip() or not r.strip():
        missing.append((n, e["concept"], "empty")); continue
    pos, ln = locate(q)
    if pos < 0:
        missing.append((n, e["concept"], q[:70])); continue
    end = pos + ln
    i = bisect.bisect_right(starts, pos) - 1
    j = bisect.bisect_right(starts, end-1) - 1
    if any(k in mods for k in range(i, j+1)):
        conflict.append((n, e["concept"], q[:60])); continue
    for k in range(i, j+1):
        s_k, e_k = starts[k], starts[k]+len(dec[k])
        cov_a, cov_b = max(pos, s_k) - s_k, min(end, e_k) - s_k
        cur = mods.get(k, dec[k])
        if k == i:
            mods[k] = cur[:cov_a] + r + cur[cov_b:]
        else:
            mods[k] = cur[:cov_a] + cur[cov_b:]
    applied.append((n, e["concept"], e["sev"], j-i))

print(f"applied {len(applied)} | not located {len(missing)} | run-conflicts {len(conflict)}")
multi = sum(1 for a in applied if a[3] > 0)
print(f"  of applied, spanning >1 run: {multi}")
if missing:
    print("\nNOT LOCATED:")
    for n,c,q in missing: print(f"   [{n}] {c}: {q!r}")
if conflict:
    print("\nCONFLICTS (overlapping runs, skipped):")
    for n,c,q in conflict: print(f"   [{n}] {c}: {q!r}")

left = [edits[n] for n,_,_ in missing] + [edits[n] for n,_,_ in conflict]
leftp = os.environ.get("LEFTOVER")
if leftp:
    json.dump(left, open(leftp,"w"), indent=1)
    print(f"  leftover written: {len(left)} -> {leftp}")

if DRY:
    print("\n(dry run — nothing written)")
    sys.exit(0)

out = []
prev = 0
for k in sorted(mods):
    a, b = spans[k]
    out.append(x[prev:a]); out.append(enc(mods[k])); prev = b
out.append(x[prev:])
new = "".join(out)
open(XML, "w", encoding="utf-8").write(new)
print(f"\nwrote {XML}: {len(x)} -> {len(new)} bytes, {len(mods)} runs modified")
