import json, os, re, html, sys
import xml.etree.ElementTree as ET

XML = "word/document.xml"
EDITS = os.environ["EDITS"]
DRY = os.environ.get("DRY","1") == "1"

x = open(XML, encoding="utf-8").read()
RUN = re.compile(r'<w:t\b[^>]*(?<!/)>(.*?)</w:t>', re.S)
spans = [(m.start(1), m.end(1)) for m in RUN.finditer(x) if m.group(1)]
dec   = [html.unescape(x[a:b]) for a, b in spans]
starts, o = [], 0
for d in dec:
    starts.append(o); o += len(d)
flat = "".join(dec)
def enc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# Keep the XML byte ranges for lossless editing, but use the parsed structure to
# determine where matching is allowed. Formatting runs may join within a
# paragraph; paragraph/cell boundaries and explicit controls must never invent a
# contiguous quote. Displayed symbols, hyphens and reference marks interrupt
# text just as explicit breaks do. A nested paragraph also interrupts its outer
# paragraph.
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
BOUNDARIES = {W + tag for tag in (
    "p", "tc", "tab", "ptab", "br", "cr", "drawing", "object", "pict",
    "sym", "noBreakHyphen", "softHyphen", "pgNum",
    "footnoteReference", "endnoteReference", "commentReference", "annotationRef",
    "footnoteRef", "endnoteRef", "separator", "continuationSeparator",
)}
block_ids, parsed_text = [], []
block_id = 0

def collect_blocks(node, paragraph_depth=0):
    global block_id
    if node.tag in BOUNDARIES:
        block_id += 1
    if node.tag == W + "p":
        paragraph_depth += 1
    if node.tag == W + "t" and node.text:
        if not paragraph_depth:
            block_id += 1
        block_ids.append(block_id)
        parsed_text.append(node.text)
        if not paragraph_depth:
            block_id += 1
    for child in node:
        collect_blocks(child, paragraph_depth)
    if node.tag in BOUNDARIES:
        block_id += 1

collect_blocks(ET.fromstring(x))
if parsed_text != dec:
    sys.exit("REFUSING TO WRITE: XML text ranges do not match the parsed document.")
blocks = []
for k, identity in enumerate(block_ids):
    end = starts[k] + len(dec[k])
    if blocks and identity == blocks[-1][0]:
        blocks[-1] = (identity, blocks[-1][1], end)
    else:
        blocks.append((identity, starts[k], end))

UNSPECIFIED = object()

def locate(q, occurrence=UNSPECIFIED):
    """Locate q across runs within a single logical text block.

    A quote must be UNIQUE unless the edit names an `occurrence` (1-based):
    silently editing the first of several identical passages is how a
    half-corrected document gets produced. Exact and spacing-variant matches
    belong to the same candidate list, in document order.
    """
    if occurrence is not UNSPECIFIED and (type(occurrence) is not int or occurrence < 1):
        return -3, 0
    pat = "".join(r"\s+" if part.isspace() else re.escape(part)
                  for part in re.split(r"(\s+)", q) if part)
    # Lookahead counts overlapping matches as well; a unique location must really
    # be unique, rather than the first non-overlapping result of re.finditer().
    matcher = re.compile("(?=(" + pat + "))")
    hits = [(a + m.start(1), m.end(1) - m.start(1))
            for _, a, b in blocks for m in matcher.finditer(flat[a:b])]
    if occurrence is not UNSPECIFIED:
        if occurrence > len(hits):
            return -3, len(hits)
        return hits[occurrence - 1]
    if not hits:
        return -1, 0
    if len(hits) > 1:
        return -2, len(hits)
    return hits[0]

edits = json.load(open(EDITS))
import bisect
mods = {}        # run index -> new decoded text
applied, missing, conflict, ambiguous = [], [], [], []

for n, e in enumerate(edits):
    q, r = e["quote"], e["repl"]
    if not q.strip() or not r.strip():
        missing.append((n, e.get("concept","-"), "empty")); continue
    pos, ln = locate(q, e.get("occurrence", UNSPECIFIED))
    if pos == -2:
        ambiguous.append((n, e.get("concept","-"), ln, q[:70])); continue
    if pos == -3:
        ambiguous.append((n, e.get("concept","-"), ln,
                          "occurrence must be a 1-based integer within the match count: "+q[:50])); continue
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
