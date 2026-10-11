#!/usr/bin/env python3
"""
STEP 12 — Resistance markers by reconstructed codon, not by annotation string.

Why this replaces step10. Step 10 identified markers by matching SnpEff's
ANN_HGVS_p protein-change strings against a hand-written list. That approach has
two failure modes, both of which bit:

  1. A resistance allele that IS the reference residue can never appear as an
     ALT protein change. 3D7 carries Gly at pfdhps 437 — the sulfadoxine
     resistance-associated residue — so the only annotation at that codon is
     Gly437Ala, the revertant. Searching for "Ala437Gly" matched nothing and
     A437G vanished from the panel entirely, at a true frequency near 0.90.

  2. A residue reachable only by two changes in one codon is never annotated.
     pfcrt codon 75 carries two variants, 403621 (A>G, annotated Asn75Asp) and
     403623 (T>A, annotated Asn75Lys). Asn->Glu needs both. Neither annotation
     names N75E, which is the residue the CVIET haplotype actually carries, and
     which MalariaGEN reports.

This script works at the codon instead. It maps each requested codon to its
three genomic positions through the CDS, collects every variant record at those
positions regardless of numalt or is_snp, applies each isolate's alleles to the
reference codon, and translates. The output is the full residue spectrum per
codon — reference residue included — so a resistance allele cannot hide in the
reference, and a two-SNP residue cannot be missed.

It also reconstructs within-isolate haplotypes on complete cases, because
similar marginal frequencies do not establish that variants co-occur.

Read-only with respect to everything step10 produced; writes its own outputs.

Usage:
    python step12_codon_panel.py
    python step12_codon_panel.py --threads 12 --markers markers.tsv
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import gzip
import io
import json
import re
import threading
import time
import urllib.request
from pathlib import Path

import numcodecs
import numpy as np
import pandas as pd
import requests
import zarr

import config as C

PF8_ZARR = "https://pf8-release.cog.sanger.ac.uk/zarr"
PF8_REF = "https://pf8-release.cog.sanger.ac.uk/reference/PlasmoDB-54-Pfalciparum3D7-Genome.fasta"
CHUNK, SCHUNK = 131072, 100

CODE = {}
for b1 in "TCAG":
    for b2 in "TCAG":
        for b3 in "TCAG":
            CODE[b1 + b2 + b3] = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"[
                len(CODE)]
AA3 = {"A": "Ala", "R": "Arg", "N": "Asn", "D": "Asp", "C": "Cys", "Q": "Gln", "E": "Glu",
       "G": "Gly", "H": "His", "I": "Ile", "L": "Leu", "K": "Lys", "M": "Met", "F": "Phe",
       "P": "Pro", "S": "Ser", "T": "Thr", "W": "Trp", "Y": "Tyr", "V": "Val", "*": "Ter"}
COMP = str.maketrans("ACGTNacgtn", "TGCANtgcan")

# Panel genes. Codons are requested by number; the reference residue is read
# from the genome rather than assumed, so a wrong expectation cannot bias it.
GENES = {
    "pfcrt":     ("PF3D7_0709000", [72, 73, 74, 75, 76, 220, 271, 326, 356, 371]),
    "pfmdr1":    ("PF3D7_0523000", [86, 184, 1034, 1042, 1246]),
    "pfdhfr":    ("PF3D7_0417200", [16, 51, 59, 108, 164]),
    "pfdhps":    ("PF3D7_0810800", [431, 436, 437, 540, 581, 613]),
    # WHO compendium v1.0 (Dec 2025): all 14 VALIDATED artemisinin markers
    # (F446I N458Y C469Y M476I Y493H G533S R539T I543T P553L R561H P574L C580Y
    # R622I A675V) plus all 6 CANDIDATE (E252Q P441L C469F N537I G538V V568G)
    # and the potential-tier codons that fall in the same region.
    "pfk13":     ("PF3D7_1343700", [252, 441, 446, 449, 458, 469, 476, 481, 493, 515, 527,
                                    533, 537, 538, 539, 543, 553, 561, 568, 574, 580,
                                    622, 675]),
    "pfmdr2":    ("PF3D7_1447900", [484, 492]),
    "pfcoronin": ("PF3D7_1251200", [50, 100, 107]),
    "pfap2mu":   ("PF3D7_1218300", [160]),
    "pfaat1":    ("PF3D7_0629500", [258, 313]),
}

# Haplotypes to reconstruct within isolates, on complete cases only.
HAPLOTYPES = {
    "pfdhfr_51_59_108": ("pfdhfr", [51, 59, 108], "IRN", "triple mutant (N51I+C59R+S108N)"),
    "pfdhfr_quadruple": ("pfdhfr", [51, 59, 108, 164], "IRNL", "quadruple (adds I164L)"),
    "pfcrt_72_76":      ("pfcrt", [72, 73, 74, 75, 76], "CVIET", "CVIET core motif"),
    "pfdhps_437_540":   ("pfdhps", [437, 540], "GE", "double (A437G+K540E)"),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--threads", type=int, default=10)
    p.add_argument("--samples", default=None)
    p.add_argument("--out-prefix", default="codon_panel")
    p.add_argument("--ref-cache", default=None,
                   help="Local 3D7 FASTA. Downloaded and cached if absent.")
    return p.parse_args()


# ---------------------------------------------------------------- reference
def load_reference(cache: Path, contigs: set[str]) -> dict[str, str]:
    if not cache.exists():
        print(f"Fetching the 3D7 reference once -> {cache}", flush=True)
        with urllib.request.urlopen(PF8_REF, timeout=900) as r, open(cache, "wb") as fh:
            fh.write(r.read())
    seqs, name, buf = {}, None, []
    with open(cache) as fh:
        for line in fh:
            if line.startswith(">"):
                if name and name in contigs:
                    seqs[name] = "".join(buf)
                name = line[1:].split()[0]
                buf = []
            else:
                buf.append(line.strip())
    if name and name in contigs:
        seqs[name] = "".join(buf)
    missing = contigs - set(seqs)
    if missing:
        raise SystemExit(f"Reference lacks contig(s): {sorted(missing)}")
    return seqs


# ---------------------------------------------------------------- CDS -> codons
def cds_map(gff: Path, gene_ids: set[str]) -> dict[str, dict]:
    """codon number -> the three genomic positions, in translation order."""
    mrna, cds = {}, collections.defaultdict(list)
    with open(gff) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 9:
                continue
            if f[2] == "mRNA":
                m = re.search(r"ID=([^;]+)", f[8])
                p = re.search(r"Parent=([^;]+)", f[8])
                if m and p and p.group(1) in gene_ids:
                    mrna.setdefault(p.group(1), m.group(1))
            elif f[2] == "CDS":
                p = re.search(r"Parent=([^;]+)", f[8])
                if p:
                    cds[p.group(1)].append((f[0], int(f[3]), int(f[4]), f[6]))
    out = {}
    for gid, mid in mrna.items():
        segs = sorted(cds[mid], key=lambda s: s[1])
        if not segs:
            continue
        contig, strand = segs[0][0], segs[0][3]
        pos = []
        for _, s, e, _ in segs:
            pos.extend(range(s, e + 1))
        if strand == "-":
            pos.reverse()                      # translation order
        if len(pos) % 3:
            raise SystemExit(f"{gid}: CDS length {len(pos)} is not a multiple of 3")
        out[gid] = {"contig": contig, "strand": strand,
                    "codons": {i + 1: pos[3 * i:3 * i + 3] for i in range(len(pos) // 3)}}
    return out


def translate(codon: str) -> str:
    return CODE.get(codon.upper(), "X")


# ---------------------------------------------------------------- remote Zarr
class Remote:
    def __init__(self, base, threads):
        self.base = base.rstrip("/")
        self.n = max(4, threads * 2)
        self._l = threading.local()
        self.lock = threading.Lock()
        self.bytes = 0

    def _s(self):
        s = getattr(self._l, "s", None)
        if s is None:
            s = requests.Session()
            a = requests.adapters.HTTPAdapter(pool_connections=self.n, pool_maxsize=self.n)
            s.mount("https://", a)
            self._l.s = s
        return s

    def get(self, key, attempts=6):
        for k in range(attempts):
            try:
                r = self._s().get(f"{self.base}/{key}", timeout=(30, 600))
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                with self.lock:
                    self.bytes += len(r.content)
                return r.content
            except requests.RequestException:
                if k == attempts - 1:
                    raise
                time.sleep(min(45, 3 * 2 ** k))
        return None


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def main() -> None:
    args = parse_args()
    C.banner("STEP 12 — resistance markers by reconstructed codon")

    meta = pd.read_csv(C.require(args.samples or C.ANALYSIS_SAMPLES_CSV))
    zones = sorted(meta["zone"].dropna().unique())
    print(f"Isolates: {len(meta):,}   zones: {', '.join(zones)}")

    gene_ids = {gid for gid, _ in GENES.values()}
    cmap = cds_map(Path(C.require(C.PLASMODB_GFF)), gene_ids)
    contigs = {cmap[gid]["contig"] for gid in gene_ids if gid in cmap}
    ref = load_reference(Path(args.ref_cache or (C.DATA_DIR / "Pf3D7_reference.fasta")), contigs)
    print(f"Reference contigs loaded: {len(ref)}")

    # ---- which genomic positions do we need? --------------------------
    targets = []           # (gene, gid, codon, contig, strand, [p1,p2,p3])
    need_pos = set()
    for gene, (gid, codons) in GENES.items():
        if gid not in cmap:
            print(f"  WARNING: {gene} ({gid}) absent from the GFF — skipped")
            continue
        info = cmap[gid]
        for cn in codons:
            if cn not in info["codons"]:
                print(f"  WARNING: {gene} codon {cn} beyond CDS ({len(info['codons'])} codons)")
                continue
            ps = info["codons"][cn]
            targets.append((gene, gid, cn, info["contig"], info["strand"], ps))
            need_pos.update((info["contig"], p) for p in ps)
    print(f"Codons to reconstruct: {len(targets)}  (genomic positions: {len(need_pos)})")

    # ---- variant metadata ---------------------------------------------
    remote = Remote(PF8_ZARR, args.threads)
    md = json.loads(remote.get(".zmetadata"))["metadata"]
    store = {".zmetadata": json.dumps({"metadata": md, "zarr_consolidated_format": 1}).encode()}
    for k, v in md.items():
        store[k] = json.dumps(v).encode()
    nvar = md["variants/POS/.zarray"]["shape"][0]
    nvc = -(-nvar // CHUNK)
    sz = md["samples/.zarray"]
    keys = [f"variants/{a}/{i}" for a in ("CHROM", "POS", "REF", "numalt", "is_snp", "FILTER_PASS")
            for i in range(nvc)]
    keys += [f"variants/ALT/{i}.0" for i in range(nvc)]
    keys += [f"samples/{i}" for i in range(-(-sz["shape"][0] // sz["chunks"][0]))]
    print("Fetching variant metadata ...", flush=True)
    with cf.ThreadPoolExecutor(args.threads) as ex:
        for k, blob in zip(keys, ex.map(remote.get, keys)):
            if blob is not None:
                store[k] = blob
    src = zarr.open_consolidated(store, mode="r")
    print(f"  {remote.bytes / 1e6:.0f} MB")

    chrom = np.asarray(src["variants/CHROM"][:]).astype(str)
    pos = np.asarray(src["variants/POS"][:])
    key_to_rows = collections.defaultdict(list)
    wanted_contigs = {c for c, _ in need_pos}
    for idx in np.nonzero(np.isin(chrom, list(wanted_contigs)))[0]:
        k = (chrom[idx], int(pos[idx]))
        if k in need_pos:
            key_to_rows[k].append(int(idx))
    rows = sorted({r for v in key_to_rows.values() for r in v})
    print(f"Variant records at those positions: {len(rows)} "
          f"(positions with >=1 record: {len(key_to_rows)}/{len(need_pos)})")

    refb = np.asarray(src["variants/REF"][:]).astype(str)
    altb = np.asarray(src["variants/ALT"].oindex[rows, :]).astype(str)
    numalt = np.asarray(src["variants/numalt"][:])
    fpass = np.asarray(src["variants/FILTER_PASS"][:]).astype(bool)
    row_ix = {r: i for i, r in enumerate(rows)}

    # ---- genotypes -----------------------------------------------------
    all_ids = np.asarray(src["samples"][:]).astype(str)
    lookup = {s: i for i, s in enumerate(all_ids)}
    want = meta[C.COL_SAMPLE].astype(str).tolist()
    absent = [s for s in want if s not in lookup]
    if absent:
        raise SystemExit(f"{len(absent)} isolates not in Pf8, e.g. {absent[:3]}")
    gi = np.array([lookup[s] for s in want])
    order = np.argsort(gi)
    gis = gi[order]

    za = md["calldata/GT/.zarray"]
    codec = numcodecs.get_codec(za["compressor"])
    GT = np.full((len(rows), len(gi), 2), -1, dtype=np.int8)
    vch = sorted({r // CHUNK for r in rows})
    sch = sorted({int(s) // SCHUNK for s in gis})
    print(f"Fetching GT: {len(rows)} sites x {len(gi)} isolates "
          f"({len(vch)} x {len(sch)} chunks)", flush=True)

    def fetch(vc, sc):
        blob = remote.get(f"calldata/GT/{vc}.{sc}.0")
        if blob is None:
            return vc, sc, None
        a = np.frombuffer(codec.decode(blob), dtype=np.dtype(za["dtype"]))
        return vc, sc, a.reshape(za["chunks"])

    with cf.ThreadPoolExecutor(args.threads) as ex:
        for vc, sc, arr in ex.map(lambda j: fetch(*j), [(v, s) for v in vch for s in sch]):
            if arr is None:
                continue
            rl = [r - vc * CHUNK for r in rows if r // CHUNK == vc]
            ro = [row_ix[r] for r in rows if r // CHUNK == vc]
            cl = [int(s) - sc * SCHUNK for s in gis if int(s) // SCHUNK == sc]
            co = [int(np.nonzero(gis == s)[0][0]) for s in gis if int(s) // SCHUNK == sc]
            if rl and cl:
                GT[np.ix_(ro, co)] = arr[np.ix_(rl, cl)]
    inv = np.empty_like(order)
    inv[order] = np.arange(len(order))
    GT = GT[:, inv]
    print(f"  {remote.bytes / 1e9:.2f} GB total")

    # ---- reconstruct codons -------------------------------------------
    C.banner("Codon reconstruction")
    n_iso = len(meta)
    residues = {}          # (gene, codon) -> array of 1-letter AA per isolate ('' = uncalled)
    refaa = {}
    notes = []
    for gene, gid, cn, contig, strand, ps in targets:
        seq = ref[contig]
        base = [seq[p - 1].upper() for p in ps]          # genomic order == translation order
        if strand == "-":
            base = [b.translate(COMP) for b in base]
        rcodon = "".join(base)
        refaa[(gene, cn)] = translate(rcodon)

        per = np.array([rcodon] * n_iso, dtype=object)
        called = np.ones(n_iso, dtype=bool)
        n_mixed = [0]
        for k, p in enumerate(ps):
            recs = key_to_rows.get((contig, p), [])
            if not recs:
                continue                                  # invariant site: reference base stands
            for r in recs:
                ri = row_ix[r]
                g = GT[ri]
                a0, a1 = g[:, 0], g[:, 1]
                miss = (a0 < 0) | (a1 < 0)
                mixed = (~miss) & (a0 != a1)
                # A mixed call at any constituent position makes the codon
                # ambiguous, so the isolate is uncalled at that codon rather
                # than being assigned an arbitrary residue.
                called &= ~miss & ~mixed
                n_mixed[0] += int(mixed.sum())
                alt_idx = np.where(~miss & ~mixed, a0, -1)
                for ai in range(1, int(numalt[r]) + 1):
                    carriers = alt_idx == ai
                    if not carriers.any():
                        continue
                    alt_allele = altb[ri, ai - 1]
                    if len(alt_allele) != len(refb[r]):
                        notes.append(f"{gene} codon {cn}: indel ALT at {p} skipped "
                                     f"({refb[r]}>{alt_allele})")
                        continue
                    nb = alt_allele.upper()
                    if strand == "-":
                        nb = nb.translate(COMP)
                    for i in np.nonzero(carriers)[0]:
                        c = per[i]
                        per[i] = c[:k] + nb[0] + c[k + 1:]
        aa = np.array([translate(c) if ok else "" for c, ok in zip(per, called)], dtype=object)
        residues[(gene, cn)] = aa
        if n_mixed[0]:
            notes.append(f"{gene} codon {cn}: {n_mixed[0]} mixed call(s) -> codon uncalled")

    # ---- per-zone residue spectrum ------------------------------------
    zone_arr = meta["zone"].to_numpy()
    out = []
    for gene, gid, cn, contig, strand, ps in targets:
        aa = residues[(gene, cn)]
        rr = refaa[(gene, cn)]
        ncall = int((aa != "").sum())
        spec = collections.Counter(a for a in aa if a)
        for res, k in sorted(spec.items(), key=lambda x: -x[1]):
            rec = {"gene": gene, "gene_id": gid, "codon": cn,
                   "ref_residue": rr, "ref_residue_3": AA3.get(rr, rr),
                   "residue": res, "residue_3": AA3.get(res, res),
                   "is_reference_residue": res == rr,
                   "label": f"{AA3.get(rr, rr)}{cn}{AA3.get(res, res)}",
                   "n_called": ncall, "count": k,
                   "overall_freq": k / ncall if ncall else float("nan"),
                   "contig": contig, "strand": strand,
                   "positions": ";".join(map(str, ps)),
                   "n_variant_records": sum(len(key_to_rows.get((contig, p), [])) for p in ps)}
            for z in zones:
                m = zone_arr == z
                nz = int((aa[m] != "").sum())
                kz = int((aa[m] == res).sum())
                lo, hi = wilson(kz, nz)
                zk = z.replace(" ", "_")
                rec[f"{zk}_n"], rec[f"{zk}_freq"] = nz, (kz / nz if nz else float("nan"))
                rec[f"{zk}_lo"], rec[f"{zk}_hi"] = lo, hi
            tab = np.array([[int((aa[zone_arr == z] == res).sum()),
                             int((aa[zone_arr == z] != "").sum()) -
                             int((aa[zone_arr == z] == res).sum())] for z in zones])
            tab = tab[tab.sum(axis=1) > 0]
            if tab.shape[0] >= 2 and tab.sum(axis=0).min() > 0:
                from scipy.stats import chi2_contingency
                try:
                    rec["chi2"], rec["chi2_p"] = chi2_contingency(tab)[:2]
                except ValueError:
                    rec["chi2"] = rec["chi2_p"] = float("nan")
            else:
                rec["chi2"] = rec["chi2_p"] = float("nan")
            out.append(rec)
    df = pd.DataFrame(out)
    full = C.RESULTS_DIR / f"{args.out_prefix}_residues.csv"
    df.to_csv(full, index=False)

    # ---- report --------------------------------------------------------
    C.banner("Residue spectrum at each requested codon")
    print("Every residue observed is listed, the reference residue included, so a")
    print("resistance allele that is the reference cannot be invisible.\n")
    zk = [z.replace(" ", "_") for z in zones]
    hdr = (f"{'gene':<10}{'codon':>6}  {'ref':<5}{'residue':<8}{'REF?':<6}"
           f"{'n':>6}{'overall':>9}  " + "".join(f"{z.split()[0][:7]:>9}" for z in zones) + "   chi2 p")
    print(hdr); print("-" * len(hdr))
    for (gene, cn), grp in df.groupby(["gene", "codon"], sort=False):
        for _, r in grp.iterrows():
            if r["overall_freq"] < 0.005 and not r["is_reference_residue"]:
                continue
            pv = "" if not np.isfinite(r["chi2_p"]) else (
                f"{r['chi2_p']:.1e}" + ("  **" if r["chi2_p"] < 0.001 else ""))
            print(f"{gene:<10}{cn:>6}  {r['ref_residue']:<5}{r['residue']:<8}"
                  f"{('yes' if r['is_reference_residue'] else ''):<6}{int(r['n_called']):>6}"
                  f"{r['overall_freq']:>9.3f}  " +
                  "".join(f"{r[c + '_freq']:>9.3f}" for c in zk) + f"   {pv}")

    # ---- codons with no variant record at all --------------------------
    C.banner("Codons with no variant record in Pf8")
    none_found = [(g, cn, refaa[(g, cn)]) for g, gid, cn, ct, st, ps in targets
                  if sum(len(key_to_rows.get((ct, p), [])) for p in ps) == 0]
    if none_found:
        print("These are monomorphic in the whole Pf8 callset — every isolate carries the")
        print("reference residue. This is a tested result, not an absence of testing:")
        for g, cn, rr in none_found:
            print(f"  {g:<10} codon {cn:<5} fixed at {AA3.get(rr, rr)} ({rr})")
    else:
        print("  (none)")

    # ---- haplotypes on complete cases ----------------------------------
    C.banner("Within-isolate haplotypes (complete cases only)")
    print("Marginal frequencies cannot show co-occurrence. Each haplotype below is")
    print("counted only among isolates called at EVERY constituent codon.\n")
    hap_rows = []
    for name, (gene, codons, target, desc) in HAPLOTYPES.items():
        avail = [c for c in codons if (gene, c) in residues]
        if len(avail) != len(codons):
            print(f"  {name}: codon(s) unavailable — skipped")
            continue
        mats = [residues[(gene, c)] for c in codons]
        complete = np.ones(n_iso, dtype=bool)
        for m in mats:
            complete &= (m != "")
        hap = np.array(["".join(m[i] for m in mats) if complete[i] else ""
                        for i in range(n_iso)], dtype=object)
        ncomp = int(complete.sum())
        khit = int((hap == target).sum())
        comps = {c: float((residues[(gene, c)][complete] == target[j]).mean())
                 for j, c in enumerate(codons)}
        lo, hi = wilson(khit, ncomp)
        print(f"  {desc}")
        print(f"    complete cases: {ncomp:,} of {n_iso:,} isolates "
              f"({ncomp / n_iso:.1%} callable at all {len(codons)} codons)")
        print(f"    target haplotype {target}: {khit:,}  freq {khit / ncomp if ncomp else float('nan'):.3f} "
              f"[{lo:.3f}-{hi:.3f}]")
        print(f"    component freqs on the SAME complete-case set: " +
              ", ".join(f"{c}{target[j]} {comps[c]:.3f}" for j, c in enumerate(codons)))
        print(f"    minimum component = {min(comps.values()):.3f}  "
              f"(the haplotype cannot exceed this)")
        top = collections.Counter(h for h in hap if h).most_common(5)
        print("    commonest haplotypes: " +
              ", ".join(f"{h} {n / ncomp:.3f}" for h, n in top))
        for z in zones:
            m = complete & (zone_arr == z)
            nz = int(m.sum()); kz = int((hap[m] == target).sum())
            l2, h2 = wilson(kz, nz)
            print(f"      {z:<20} n={nz:>5}  {target} {kz / nz if nz else float('nan'):.3f} [{l2:.3f}-{h2:.3f}]")
            hap_rows.append({"haplotype": name, "description": desc, "target": target,
                             "zone": z, "n_complete": nz, "count": kz,
                             "freq": kz / nz if nz else float("nan"), "lo": l2, "hi": h2})
        print()
    if hap_rows:
        hp = C.RESULTS_DIR / f"{args.out_prefix}_haplotypes.csv"
        pd.DataFrame(hap_rows).to_csv(hp, index=False)

    # ---- per-sample concordance against MalariaGEN -------------------
    C.banner("Per-sample concordance with MalariaGEN's published calls")
    print("Agreement of marginal frequencies does not show that two pipelines called")
    print("the same isolates the same way. This compares call by call, on the set of")
    print("isolates where both pipelines made a call.\n")
    drm_path = C.DATA_DIR / "Pf8_drug_resistance_marker_genotypes.tsv"
    if not drm_path.exists():
        try:
            print(f"  fetching {drm_path.name} ...", flush=True)
            urllib.request.urlretrieve(
                "https://pf8-release.cog.sanger.ac.uk/Pf8_drug_resistance_marker_genotypes.tsv",
                drm_path)
        except Exception as exc:
            print(f"  could not fetch it ({exc}); concordance skipped")
            drm_path = None
    conc_rows = []
    if drm_path and Path(drm_path).exists():
        drm = pd.read_csv(drm_path, sep="\t", low_memory=False)
        drm = drm.set_index("Sample")
        ids = meta[C.COL_SAMPLE].astype(str).to_numpy()
        COLMAP = [("pfcrt", 72, "crt_72[C]"), ("pfcrt", 74, "crt_74[M]"),
                  ("pfcrt", 75, "crt_75[N]"), ("pfcrt", 76, "crt_76[K]"),
                  ("pfcrt", 220, "crt_220[A]"), ("pfcrt", 271, "crt_271[Q]"),
                  ("pfcrt", 326, "crt_326[N]"), ("pfcrt", 356, "crt_356[I]"),
                  ("pfcrt", 371, "crt_371[R]"),
                  ("pfmdr1", 86, "mdr1_86[N]"), ("pfmdr1", 184, "mdr1_184[Y]"),
                  ("pfmdr1", 1034, "mdr1_1034[S]"), ("pfmdr1", 1042, "mdr1_1042[N]"),
                  ("pfmdr1", 1246, "mdr1_1246[D]"),
                  ("pfdhfr", 16, "dhfr_16[N]"), ("pfdhfr", 51, "dhfr_51[N]"),
                  ("pfdhfr", 59, "dhfr_59[C]"), ("pfdhfr", 108, "dhfr_108[S]"),
                  ("pfdhfr", 164, "dhfr_164[I]"),
                  ("pfdhps", 436, "dhps_436[S]"), ("pfdhps", 437, "dhps_437[G]"),
                  ("pfdhps", 540, "dhps_540[K]"), ("pfdhps", 581, "dhps_581[A]"),
                  ("pfdhps", 613, "dhps_613[A]"), ("pfmdr2", 484, "mdr2_484[T]")]
        print(f"{'marker':<16}{'both called':>12}{'agree':>8}{'disagree':>10}{'concordance':>13}  disagreements")
        print("-" * 86)
        for gene, cn, col in COLMAP:
            if col not in drm.columns or (gene, cn) not in residues:
                continue
            ours = residues[(gene, cn)]
            theirs = drm.reindex(ids)[col].astype(str).str.strip().to_numpy()
            both = np.array([(o != "") and (t not in ("-", "", "nan", "NaN") and "," not in t)
                             for o, t in zip(ours, theirs)])
            agree = np.array([o == t for o, t in zip(ours, theirs)]) & both
            n_both, n_ag = int(both.sum()), int(agree.sum())
            dis = collections.Counter(f"ours={o}/theirs={t}"
                                      for o, t, b, a in zip(ours, theirs, both, agree) if b and not a)
            conc_rows.append({"gene": gene, "codon": cn, "malariagen_column": col,
                              "n_both_called": n_both, "n_agree": n_ag,
                              "concordance": n_ag / n_both if n_both else float("nan"),
                              "disagreements": "; ".join(f"{k} x{v}" for k, v in dis.most_common(4))})
            flag = "" if (n_both and n_ag / n_both >= 0.999) else "   <--"
            print(f"{gene + ' ' + str(cn):<16}{n_both:>12}{n_ag:>8}{n_both - n_ag:>10}"
                  f"{(n_ag / n_both if n_both else float('nan')):>13.4f}  "
                  f"{'; '.join(f'{k} x{v}' for k, v in dis.most_common(2))}{flag}")
        cp = C.RESULTS_DIR / f"{args.out_prefix}_concordance.csv"
        pd.DataFrame(conc_rows).to_csv(cp, index=False)
        tot_b = sum(r["n_both_called"] for r in conc_rows)
        tot_a = sum(r["n_agree"] for r in conc_rows)
        print(f"\n  Overall: {tot_a:,}/{tot_b:,} calls agree ({tot_a / tot_b:.4%}) across "
              f"{len(conc_rows)} markers")
        print(f"  -> {cp}")

    C.banner("Output")
    print(f"  {full}")
    if hap_rows:
        print(f"  {hp}")
    if notes:
        print(f"\n{len(notes)} note(s):")
        for n in sorted(set(notes))[:10]:
            print(f"  {n}")


if __name__ == "__main__":
    main()
