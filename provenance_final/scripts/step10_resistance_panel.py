#!/usr/bin/env python3
"""
STEP 10 — Antimalarial resistance marker frequencies by agro-ecological zone.

Why this script exists. Step 3a builds the genome-wide callset under
`FILTER_PASS & is_snp & numalt == 1`. In Pf8 almost every canonical resistance
codon is multiallelic or carries a spanning-deletion ALT, so that mask silently
drops all of them: pfcrt K76T is numalt=2 with is_snp False, pfmdr1 N86Y is
numalt=3, pfdhps K540E is numalt=2. None of them ever reached the outlier scan,
which is why Step 9 reported "no validated resistance locus among the outliers".
That was an artefact of the ingest filter, not a result.

This script answers the marker question directly instead. It re-fetches the
panel genes from the Pf8 Zarr with no numalt restriction, resolves each isolate
to one allele, and reports per-zone frequencies with Wilson confidence
intervals. It does not touch the genome-wide store or any existing output.

Multiallelic handling. At a site with k ALT alleles, GT codes 0 for REF and
1..k for each ALT, and ANN_HGVS_p carries one protein consequence per ALT. The
resistance allele is therefore a specific ALT index, found by matching the
protein change rather than by assuming ALT 1.

Ploidy. Same rule as step04a: a mixed call is resolved to the allele with more
reads, ties become missing, and each isolate then contributes one allele.

Usage:
    python step10_resistance_panel.py
    python step10_resistance_panel.py --min-freq 0.01 --out-prefix panel
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import itertools
import json
import re
import threading
import time

import numcodecs
import numpy as np
import pandas as pd
import requests
import zarr

import config as C

PF8_ZARR_URL = "https://pf8-release.cog.sanger.ac.uk/zarr"

# Genes carrying validated or candidate antimalarial resistance determinants.
# pfaat1 is included because the Step 8 scan surfaced it and the thesis names it;
# it is absent from config.KNOWN_RESISTANCE_LOCI.
PANEL = {
    "PF3D7_0709000": "pfcrt",
    "PF3D7_0523000": "pfmdr1",
    "PF3D7_0417200": "pfdhfr",
    "PF3D7_0810800": "pfdhps",
    "PF3D7_1343700": "pfk13",
    "PF3D7_1447900": "pfmdr2",
    "PF3D7_1251200": "pfcoronin",
    "PF3D7_1218300": "pfap2mu",
    "PF3D7_0629500": "pfaat1",
}

# Canonical codons, flagged by name in the report when present.
CANONICAL = {
    "pfcrt": ["Cys72Ser", "Met74Ile", "Asn75Glu", "Asn75Asp", "Lys76Thr",
              "Ala220Ser", "Gln271Glu", "Asn326Ser", "Ile356Thr", "Arg371Ile"],
    "pfmdr1": ["Asn86Tyr", "Tyr184Phe", "Ser1034Cys", "Asn1042Asp", "Asp1246Tyr"],
    "pfdhfr": ["Ala16Val", "Asn51Ile", "Cys59Arg", "Ser108Asn", "Ile164Leu"],
    "pfdhps": ["Ser436Ala", "Ala437Gly", "Lys540Glu", "Ala581Gly", "Ala613Ser", "Ala613Thr"],
    "pfk13": ["Phe446Ile", "Asn458Tyr", "Cys469Tyr", "Cys469Phe", "Met476Ile",
              "Tyr493His", "Arg539Thr", "Ile543Thr", "Pro553Leu", "Arg561His",
              "Cys580Tyr", "Arg622Ile", "Ala675Val", "Pro441Leu"],
    "pfmdr2": ["Thr484Ile", "Ile492Val"],
    "pfcoronin": ["Gly50Glu", "Arg100Lys", "Glu107Val"],
    "pfap2mu": ["Ser160Asn"],
    "pfaat1": ["Ser258Leu", "Phe313Ser"],
}

CHUNK = 131072          # Pf8 variant chunk size
SAMPLE_CHUNK = 100


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--threads", type=int, default=8)
    p.add_argument("--min-freq", type=float, default=0.02,
                   help="Report non-canonical variants at or above this overall frequency.")
    p.add_argument("--samples", default=None,
                   help="Sample table. Defaults to the Step 4a analysis set.")
    p.add_argument("--out-prefix", default="resistance_panel")
    return p.parse_args()


class Remote:
    """GETs Zarr keys over HTTPS, with retries."""

    def __init__(self, base: str, threads: int):
        self.base = base.rstrip("/")
        self.n = max(4, threads * 2)
        self._local = threading.local()
        self._lock = threading.Lock()
        self.bytes = 0

    def _s(self) -> requests.Session:
        s = getattr(self._local, "s", None)
        if s is None:
            s = requests.Session()
            a = requests.adapters.HTTPAdapter(pool_connections=self.n, pool_maxsize=self.n)
            s.mount("https://", a)
            self._local.s = s
        return s

    def get(self, key: str, attempts: int = 6):
        for k in range(attempts):
            try:
                r = self._s().get(f"{self.base}/{key}", timeout=(30, 600))
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                with self._lock:
                    self.bytes += len(r.content)
                return r.content
            except requests.RequestException:
                if k == attempts - 1:
                    raise
                time.sleep(min(60, 3 * 2 ** k))
        return None


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval — behaves sensibly at 0, at 1 and at small n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def gene_spans() -> dict[str, tuple[str, int, int]]:
    """Panel gene coordinates from the PlasmoDB GFF the pipeline already uses."""
    span = {}
    with open(C.require(C.PLASMODB_GFF)) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 9 or "gene" not in f[2]:
                continue
            m = re.search(r"ID=([^;]+)", f[8])
            if m and m.group(1) in PANEL:
                span[m.group(1)] = (f[0], int(f[3]), int(f[4]))
    missing = set(PANEL) - set(span)
    if missing:
        raise SystemExit(f"Gene(s) absent from {C.PLASMODB_GFF.name}: {sorted(missing)}")
    return span


def main() -> None:
    args = parse_args()
    C.banner("STEP 10 — resistance marker frequencies by zone")
    print("Panel genes are re-fetched WITHOUT the numalt == 1 restriction that")
    print("step03a applies, because the canonical codons are multiallelic in Pf8.\n")

    meta_path = args.samples or C.ANALYSIS_SAMPLES_CSV
    meta = pd.read_csv(C.require(meta_path, "Run step04a_prepare_callset.py first."))
    print(f"Isolates: {len(meta):,} (from {str(meta_path).split('/')[-1]})")
    zones = sorted(meta["zone"].dropna().unique())
    print("Zones: " + ", ".join(f"{z} (n={int((meta['zone'] == z).sum())})" for z in zones))

    spans = gene_spans()
    remote = Remote(PF8_ZARR_URL, args.threads)
    md = json.loads(remote.get(".zmetadata"))["metadata"]
    store = {".zmetadata": json.dumps({"metadata": md, "zarr_consolidated_format": 1}).encode()}
    for k, v in md.items():
        store[k] = json.dumps(v).encode()

    n_var = md["variants/POS/.zarray"]["shape"][0]
    nvc = -(-n_var // CHUNK)

    # ---- variant metadata (1-D and 2-D annotation arrays) -----------------
    print("\nFetching variant metadata ...", flush=True)
    one_d = ["CHROM", "POS", "REF", "numalt", "is_snp", "FILTER_PASS", "RegionType"]
    two_d = ["ALT", "ANN_HGVS_p", "ANN_Annotation", "ANN_Gene_ID", "ANN_Allele"]
    keys = [f"variants/{a}/{i}" for a in one_d for i in range(nvc)]
    keys += [f"variants/{a}/{i}.0" for a in two_d for i in range(nvc)]
    sz = md["samples/.zarray"]
    keys += [f"samples/{i}" for i in range(-(-sz["shape"][0] // sz["chunks"][0]))]
    with cf.ThreadPoolExecutor(args.threads) as ex:
        for k, blob in zip(keys, ex.map(remote.get, keys)):
            if blob is not None:
                store[k] = blob
    src = zarr.open_consolidated(store, mode="r")
    print(f"  {remote.bytes / 1e6:.0f} MB")

    chrom = np.asarray(src["variants/CHROM"][:]).astype(str)
    pos = np.asarray(src["variants/POS"][:])
    in_panel = np.zeros(len(pos), dtype=bool)
    for gid, (c, s, e) in spans.items():
        in_panel |= (chrom == c) & (pos >= s) & (pos <= e)
    sel = np.nonzero(in_panel)[0]
    print(f"\nVariant records inside the {len(PANEL)} panel genes: {len(sel):,}")

    fp = np.asarray(src["variants/FILTER_PASS"][:])[sel].astype(bool)
    numalt = np.asarray(src["variants/numalt"][:])[sel]
    issnp = np.asarray(src["variants/is_snp"][:])[sel].astype(bool)
    print(f"  FILTER=PASS                      {int(fp.sum()):,}")
    print(f"  of those, numalt == 1 & is_snp   {int((fp & issnp & (numalt == 1)).sum()):,}"
          f"   <- all step03a would have kept")
    print(f"  of those, multiallelic or indel  {int((fp & ~(issnp & (numalt == 1))).sum()):,}"
          f"   <- silently dropped, incl. every canonical codon")

    keep = sel[fp]
    hgvs = np.asarray(src["variants/ANN_HGVS_p"].oindex[keep, :]).astype(str)
    annot = np.asarray(src["variants/ANN_Annotation"].oindex[keep, :]).astype(str)
    gene_ann = np.asarray(src["variants/ANN_Gene_ID"].oindex[keep, :]).astype(str)
    ann_allele = np.asarray(src["variants/ANN_Allele"].oindex[keep, :]).astype(str)
    alt = np.asarray(src["variants/ALT"].oindex[keep, :]).astype(str)
    ref = np.asarray(src["variants/REF"][:])[keep].astype(str)
    kchrom, kpos = chrom[keep], pos[keep]

    # ---- pick the (site, ALT index) pairs worth genotyping ----------------
    # SnpEff emits one annotation per (ALT, transcript) pair, so annotation column
    # a does NOT correspond to ALT allele a. Cross-checking against MalariaGEN's
    # published calls showed this mislabels proteins at multiallelic sites:
    # pfmdr1 Asn86Tyr was read as Asn86Asp and Tyr184Phe as Tyr184Ser, both at the
    # right frequency under the wrong name. ANN_Allele names the ALT base each
    # annotation describes, so the index is looked up rather than assumed.
    targets = []
    skipped_unmatched = 0
    for r in range(len(keep)):
        gid = next((g for g, (c, s, e) in spans.items()
                    if kchrom[r] == c and s <= kpos[r] <= e), None)
        for a in range(hgvs.shape[1]):
            prot, cons = hgvs[r, a], annot[r, a]
            if not prot or prot in ("", "0", "nan"):
                continue
            if gene_ann[r, a] and gene_ann[r, a] not in ("", "0") and gene_ann[r, a] != gid:
                continue
            canon = prot in CANONICAL.get(PANEL[gid], [])
            if cons != "missense_variant" and not canon:
                continue
            hit = np.nonzero(alt[r] == ann_allele[r, a])[0]
            if ann_allele[r, a] in ("", "0", "nan") or not len(hit):
                skipped_unmatched += 1
                continue
            targets.append({"row": r, "alt_index": int(hit[0]) + 1, "gene_id": gid,
                            "gene": PANEL[gid], "protein": prot, "consequence": cons,
                            "chrom": kchrom[r], "pos": int(kpos[r]),
                            "ref": ref[r], "alt": alt[r, a],
                            "numalt": int(numalt[fp][r]), "canonical": canon,
                            "ann_allele": ann_allele[r, a]})
    tg = pd.DataFrame(targets)
    if skipped_unmatched:
        print(f"  ({skipped_unmatched:,} annotations skipped: ANN_Allele matched no ALT)")
    tg = tg.drop_duplicates(subset=["row", "alt_index", "protein"]).reset_index(drop=True)
    if tg.empty:
        raise SystemExit("No annotated protein-changing alleles found in the panel genes.")
    print(f"\nProtein-changing alleles to genotype: {len(tg):,} "
          f"({int(tg['canonical'].sum())} canonical)")
    found = tg.loc[tg["canonical"], ["gene", "protein"]].drop_duplicates()
    for g in sorted(found["gene"].unique()):
        print(f"  {g:<10} " + ", ".join(sorted(found.loc[found['gene'] == g, 'protein'])))

    # ---- genotypes --------------------------------------------------------
    all_ids = np.asarray(src["samples"][:]).astype(str)
    if not all_ids[0] or all_ids[0] in ("0", "nan"):
        raise SystemExit("Sample IDs did not decode from the Zarr store.")
    lookup = {s: i for i, s in enumerate(all_ids)}
    want = meta[C.COL_SAMPLE].astype(str).tolist()
    absent = [s for s in want if s not in lookup]
    if absent:
        raise SystemExit(f"{len(absent)} isolates not in Pf8, e.g. {absent[:3]}")
    gi = np.array([lookup[s] for s in want])
    order = np.argsort(gi)
    gi_sorted = gi[order]

    rows = np.array(sorted(set(keep[tg["row"].to_numpy()])))
    row_of = {int(g): i for i, g in enumerate(rows)}
    vchunks = sorted(set(int(r) // CHUNK for r in rows))
    schunks = sorted(set(int(s) // SAMPLE_CHUNK for s in gi_sorted))
    print(f"\nFetching GT and AD: {len(rows)} sites x {len(gi)} isolates "
          f"({len(vchunks)} x {len(schunks)} source chunks)", flush=True)

    za = {f: md[f"calldata/{f}/.zarray"] for f in ("GT", "AD")}
    codec = {f: numcodecs.get_codec(za[f]["compressor"]) for f in za}
    GT = np.full((len(rows), len(gi), 2), -1, dtype=np.int8)
    AD = np.zeros((len(rows), len(gi), za["AD"]["chunks"][2]), dtype=np.int16)

    def fetch(field, vc, sc):
        blob = remote.get(f"calldata/{field}/{vc}.{sc}.0")
        ch = za[field]["chunks"]
        if blob is None:
            return field, vc, sc, None
        arr = np.frombuffer(codec[field].decode(blob), dtype=np.dtype(za[field]["dtype"]))
        return field, vc, sc, arr.reshape(ch)

    jobs = [(f, vc, sc) for f in ("GT", "AD") for vc in vchunks for sc in schunks]
    t0 = time.time()
    with cf.ThreadPoolExecutor(args.threads) as ex:
        for f, vc, sc, arr in ex.map(lambda j: fetch(*j), jobs):
            if arr is None:
                continue
            r_loc = [int(r) - vc * CHUNK for r in rows if int(r) // CHUNK == vc]
            r_out = [row_of[int(r)] for r in rows if int(r) // CHUNK == vc]
            cols = [int(s) - sc * SAMPLE_CHUNK for s in gi_sorted if int(s) // SAMPLE_CHUNK == sc]
            c_out = [int(np.nonzero(gi_sorted == s)[0][0])
                     for s in gi_sorted if int(s) // SAMPLE_CHUNK == sc]
            if not r_loc or not cols:
                continue
            block = arr[np.ix_(r_loc, cols)]
            tgt = GT if f == "GT" else AD
            tgt[np.ix_(r_out, c_out)] = block
    print(f"  {remote.bytes / 1e9:.2f} GB total in {time.time() - t0:.0f}s")

    # restore metadata order, then resolve one allele per isolate
    inv = np.empty_like(order)
    inv[order] = np.arange(len(order))
    GT, AD = GT[:, inv], AD[:, inv]

    a0, a1 = GT[:, :, 0], GT[:, :, 1]
    called = (a0 >= 0) & (a1 >= 0)
    mixed = called & (a0 != a1)
    ADc = np.where(AD < 0, 0, AD)
    best = ADc.argmax(axis=2).astype(np.int8)
    top = np.take_along_axis(ADc, best[:, :, None], axis=2)[:, :, 0]
    tie = (ADc == top[:, :, None]).sum(axis=2) > 1
    allele = np.where(called, a0, -1)
    allele = np.where(mixed, np.where(tie, -1, best), allele)
    print(f"\nMixed calls resolved by read depth: {int(mixed.sum()):,} "
          f"({int((mixed & tie).sum()):,} tied -> missing)")

    # ---- per-zone frequencies --------------------------------------------
    C.banner("Marker frequencies by zone")
    zone_arr = meta["zone"].to_numpy()
    out = []
    for _, t in tg.iterrows():
        ri = row_of[int(keep[int(t["row"])])]
        a = allele[ri]
        rec = {"gene": t["gene"], "gene_id": t["gene_id"], "protein": t["protein"],
               "consequence": t["consequence"], "canonical": bool(t["canonical"]),
               "chrom": t["chrom"], "pos": t["pos"], "ref": t["ref"], "alt": t["alt"],
               "numalt": t["numalt"],
               "in_genomewide_scan": bool(t["numalt"] == 1)}
        tot_k = int((a == t["alt_index"]).sum())
        tot_n = int((a >= 0).sum())
        rec["overall_freq"] = tot_k / tot_n if tot_n else float("nan")
        rec["n_called"] = tot_n
        for z in zones:
            m = zone_arr == z
            k = int((a[m] == t["alt_index"]).sum())
            n = int((a[m] >= 0).sum())
            lo, hi = wilson(k, n)
            key = z.replace(" ", "_")
            rec[f"{key}_n"] = n
            rec[f"{key}_freq"] = k / n if n else float("nan")
            rec[f"{key}_lo"] = lo
            rec[f"{key}_hi"] = hi
        # heterogeneity across zones
        tab = np.array([[int((a[zone_arr == z] == t["alt_index"]).sum()),
                         int((a[zone_arr == z] >= 0).sum()) -
                         int((a[zone_arr == z] == t["alt_index"]).sum())] for z in zones])
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

    df = pd.DataFrame(out).sort_values(["canonical", "overall_freq"], ascending=[False, False])
    rep = df[df["canonical"] | (df["overall_freq"] >= args.min_freq)].copy()

    zcols = [z.replace(" ", "_") for z in zones]
    hdr = f"{'gene':<10}{'variant':<12}{'scan?':<7}{'overall':>8}  " + \
          "".join(f"{z.split()[0][:8]:>10}" for z in zones) + "   chi2 p"
    print(hdr)
    print("-" * len(hdr))
    for _, r in rep.iterrows():
        mark = "*" if r["canonical"] else " "
        pv = "" if not np.isfinite(r["chi2_p"]) else (
            f"{r['chi2_p']:.1e}" + ("  **" if r["chi2_p"] < 0.001 else ""))
        print(f"{r['gene']:<10}{mark + r['protein']:<12}"
              f"{('yes' if r['in_genomewide_scan'] else 'NO'):<7}"
              f"{r['overall_freq']:>8.3f}  " +
              "".join(f"{r[c + '_freq']:>10.3f}" for c in zcols) + f"   {pv}")
    print("\n* = canonical resistance codon.  'scan?' = whether step03a's "
          "numalt==1 filter would have kept it.")
    print("chi2 p = heterogeneity of allele frequency across zones (** p < 0.001).")

    full = C.RESULTS_DIR / f"{args.out_prefix}_frequencies.csv"
    df.to_csv(full, index=False)
    print(f"\nAll {len(df):,} protein-changing alleles -> {full}")
    canon_only = C.RESULTS_DIR / f"{args.out_prefix}_canonical.csv"
    df[df["canonical"]].to_csv(canon_only, index=False)
    print(f"Canonical codons only -> {canon_only}")

    missing_genes = [g for g in sorted(set(PANEL.values()))
                     if g not in set(df.loc[df["canonical"], "gene"])]
    if missing_genes:
        print(f"\nNo canonical codon observed in: {', '.join(missing_genes)}")
        print("(the codon is monomorphic in this sample, or absent from Pf8's annotation)")


if __name__ == "__main__":
    main()
