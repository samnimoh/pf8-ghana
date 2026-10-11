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

def locate(q, occurrence=None):
    """Locate q in the flattened text.

    A quote must be UNIQUE unless the edit names an `occurrence` (1-based):
    silently editing the first of several identical passages is how a
    half-corrected document gets produced.
    """
    hits = [m.start() for m in re.finditer(re.escape(q), flat)]
    if len(hits) > 1:
        if occurrence is None:
            return -2, len(hits)          # ambiguous
        if not (1 <= occurrence <= len(hits)):
            return -3, len(hits)          # out of range
        return hits[occurrence - 1], len(q)
    if hits: return hits[0], len(q)
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
applied, missing, conflict, ambiguous = [], [], [], []

for n, e in enumerate(edits):
    q, r = e["quote"], e["repl"]
    if not q.strip() or not r.strip():
        missing.append((n, e.get("concept","-"), "empty")); continue
    pos, ln = locate(q, e.get("occurrence"))
    if pos == -2:
        ambiguous.append((n, e.get("concept","-"), ln, q[:70])); continue
    if pos == -3:
        ambiguous.append((n, e.get("concept","-"), ln, "occurrence out of range: "+q[:50])); continue
    if pos < 0:
        missing.append((n, e.get("concept","-"), q[:70])); continue
    end = pos + ln
    i = bisect.bisect_right(starts, pos) - 1
    j = bisect.bisect_right(starts, end-1) - 1
    if any(k in mods for k in range(i, j+1)):
        conflict.append((n, e.get("concept","-"), q[:60])); continue
    for k in range(i, j+1):
        s_k, e_k = starts[k], starts[k]+len(dec[k])
        cov_a, cov_b = max(pos, s_k) - s_k, min(end, e_k) - s_k
        cur = mods.get(k, dec[k])
        if k == i:
            mods[k] = cur[:cov_a] + r + cur[cov_b:]
        else:
            mods[k] = cur[:cov_a] + cur[cov_b:]
    applied.append((n, e.get("concept","-"), e.get("sev","-"), j-i))

print(f"applied {len(applied)} | not located {len(missing)} | run-conflicts {len(conflict)} | ambiguous {len(ambiguous)}")
multi = sum(1 for a in applied if a[3] > 0)
print(f"  of applied, spanning >1 run: {multi}")
if missing:
    print("\nNOT LOCATED:")
    for n,c,q in missing: print(f"   [{n}] {c}: {q!r}")
if conflict:
    print("\nCONFLICTS (overlapping runs, skipped — re-run to apply):")
    for n,c,q in conflict: print(f"   [{n}] {c}: {q!r}")
if ambiguous:
    print("\nAMBIGUOUS (quote is not unique — add \"occurrence\": <1-based int>):")
    for n,c,k,q in ambiguous: print(f"   [{n}] {c}: {k} matches: {q!r}")

left = ([edits[n] for n,_,_ in missing] + [edits[n] for n,_,_ in conflict]
        + [edits[n] for n,_,_,_ in ambiguous])
leftp = os.environ.get("LEFTOVER")
if leftp:
    json.dump(left, open(leftp,"w"), indent=1)
    print(f"  leftover written: {len(left)} -> {leftp}")

if DRY:
    print("\n(dry run — nothing written)")
    sys.exit(0)

# Never write a partial result. `conflict` is benign (those edits apply on the next
# pass), but anything unlocated or ambiguous means the edit list does not match the
# document, and writing half of it produces a silently half-corrected file.
if (missing or ambiguous) and os.environ.get("ALLOW_PARTIAL") != "1":
    sys.exit(f"\nREFUSING TO WRITE: {len(missing)} not located, {len(ambiguous)} ambiguous. "
             f"Fix the edit list, or set ALLOW_PARTIAL=1 to write the {len(applied)} that matched.")

out = []
prev = 0
for k in sorted(mods):
    a, b = spans[k]
    out.append(x[prev:a]); out.append(enc(mods[k])); prev = b
out.append(x[prev:])
new = "".join(out)
open(XML, "w", encoding="utf-8").write(new)
print(f"\nwrote {XML}: {len(x)} -> {len(new)} bytes, {len(mods)} runs modified")
